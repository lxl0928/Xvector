from __future__ import annotations

import gc
import logging
import threading
import time
from typing import Any

from xvector.common.paths import DEFAULT_PARTITION, DataPaths
from xvector.common.schema_map import build_zvec_schema
from xvector.engine import zvec_runtime
from xvector.engine.partition_layout import resolve_partition_path

logger = logging.getLogger(__name__)


class CollectionFencedError(RuntimeError):
    """Reader must not open a collection while writer holds the write fence."""


class CollectionManager:
    """Process-local handle cache keyed by db/collection/partition.

    zvec uses a shared LOCK for read-only opens and an exclusive LOCK for RW.
    Writer coordinates via reader ``fence`` so refresh/search cannot reacquire
    the lock mid-write.

    Important (zvec 0.6): RO open still runs WAL recovery into IDMap. A leftover
    ``*.wal`` therefore cannot be opened read-only — Writer must flush/seal first.
    """

    def __init__(self, paths: DataPaths, read_only: bool = False):
        self.paths = paths
        self.read_only = read_only
        self._lock = threading.RLock()
        self._handles: dict[str, Any] = {}
        # Keys that must stay closed until unfenced (reader-side write coordination).
        self._fenced: set[str] = set()

    @staticmethod
    def key(db: str, coll: str, part: str) -> str:
        return f"{db}/{coll}/{part}"

    @staticmethod
    def _is_lock_error(exc: BaseException) -> bool:
        msg = str(exc).lower()
        return ("can't lock" in msg) or ("cannot lock" in msg) or (
            "lock" in msg and "collection" in msg
        )

    @staticmethod
    def partition_has_wal(
        paths: DataPaths,
        db_name: str,
        collection_name: str,
        partition_name: str = DEFAULT_PARTITION,
    ) -> bool:
        """True if zvec left unflushed WAL under the partition directory."""
        root = resolve_partition_path(paths, db_name, collection_name, partition_name)
        if not root.exists():
            return False
        # WAL lives at ``<partition>/<segment_id>/<block_id>.wal``.
        for p in root.rglob("*.wal"):
            if p.is_file():
                return True
        return False

    def has_wal(
        self,
        db_name: str,
        collection_name: str,
        partition_name: str = DEFAULT_PARTITION,
    ) -> bool:
        return self.partition_has_wal(self.paths, db_name, collection_name, partition_name)

    @staticmethod
    def _release_handle(coll: Any, *, flush: bool = True) -> bool:
        """Release a zvec handle. Returns False if flush was requested and failed."""
        if coll is None:
            return True
        flush_ok = True
        try:
            if flush and hasattr(coll, "flush"):
                try:
                    coll.flush()
                except Exception:  # noqa: BLE001
                    flush_ok = False
                    logger.exception("flush before release failed")
        finally:
            # Drop the last Python ref so zvec releases the native LOCK.
            # Important: clear *this* frame's reference; nested del is not enough.
            try:
                del coll
            except Exception:  # noqa: BLE001
                pass
            gc.collect()
        return flush_ok

    def fence_partitions(
        self,
        db_name: str,
        collection_name: str,
        partition_names: list[str] | None = None,
    ) -> None:
        """Close handles and prevent reopen until unfence."""
        with self._lock:
            released: list[Any] = []
            if partition_names:
                for p in partition_names:
                    k = self.key(db_name, collection_name, p)
                    self._fenced.add(k)
                    if k in self._handles:
                        released.append(self._handles.pop(k))
            else:
                self._fenced.add(f"{db_name}/{collection_name}/*")
                prefix = f"{db_name}/{collection_name}/"
                for k in list(self._handles):
                    if k.startswith(prefix):
                        released.append(self._handles.pop(k))
        for coll in released:
            self._release_handle(coll, flush=not self.read_only)

    def unfence_partitions(
        self,
        db_name: str,
        collection_name: str,
        partition_names: list[str] | None = None,
    ) -> None:
        with self._lock:
            self._fenced.discard(f"{db_name}/{collection_name}/*")
            if partition_names:
                for p in partition_names:
                    self._fenced.discard(self.key(db_name, collection_name, p))
            else:
                prefix = f"{db_name}/{collection_name}/"
                for k in list(self._fenced):
                    if k.startswith(prefix):
                        self._fenced.discard(k)

    def is_fenced(self, db_name: str, collection_name: str, partition_name: str) -> bool:
        k = self.key(db_name, collection_name, partition_name)
        return k in self._fenced or f"{db_name}/{collection_name}/*" in self._fenced

    def create_partition_collection(
        self,
        db_name: str,
        collection_name: str,
        partition_name: str,
        catalog_meta: dict[str, Any],
        index_defs: list[dict[str, Any]] | None = None,
    ):
        path = resolve_partition_path(self.paths, db_name, collection_name, partition_name)
        # zvec create_and_open fails if the target path already exists.
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(str(path))
        safe_part = "default" if partition_name == DEFAULT_PARTITION else partition_name
        schema = build_zvec_schema(f"{collection_name}_{safe_part}", catalog_meta, index_defs)
        k = self.key(db_name, collection_name, partition_name)
        with self._lock:
            old = self._handles.pop(k, None)
        if old is not None:
            self._release_handle(old)
        with self._lock:
            if self.read_only and self.is_fenced(db_name, collection_name, partition_name):
                raise CollectionFencedError(f"fenced: {db_name}/{collection_name}/{partition_name}")
            coll = zvec_runtime.create_and_open(str(path), schema, read_only=False)
            if self.read_only:
                self._release_handle(coll)
                coll = zvec_runtime.open_collection(str(path), read_only=True)
            self._handles[k] = coll
            return coll

    def open_partition(
        self,
        db_name: str,
        collection_name: str,
        partition_name: str = DEFAULT_PARTITION,
        force_reopen: bool = False,
        *,
        allow_fenced: bool = False,
        retries: int = 0,
        retry_delay: float = 0.05,
    ):
        path = resolve_partition_path(self.paths, db_name, collection_name, partition_name)
        if not path.exists():
            raise FileNotFoundError(str(path))
        k = self.key(db_name, collection_name, partition_name)
        attempt = 0
        while True:
            with self._lock:
                if self.read_only and not allow_fenced and self.is_fenced(db_name, collection_name, partition_name):
                    raise CollectionFencedError(f"fenced: {db_name}/{collection_name}/{partition_name}")
                if force_reopen and k in self._handles:
                    old = self._handles.pop(k)
                else:
                    old = None
                if k in self._handles:
                    return self._handles[k]
            if old is not None:
                # Reader refresh must not flush (RO); writer close should flush WAL away.
                self._release_handle(old, flush=not self.read_only)
            try:
                with self._lock:
                    if self.read_only and not allow_fenced and self.is_fenced(db_name, collection_name, partition_name):
                        raise CollectionFencedError(f"fenced: {db_name}/{collection_name}/{partition_name}")
                    if k in self._handles:
                        return self._handles[k]
                    if self.read_only and self.has_wal(db_name, collection_name, partition_name):
                        raise RuntimeError(
                            f"pending WAL blocks read-only open: {db_name}/{collection_name}/{partition_name}; "
                            "writer must flush/seal first"
                        )
                    coll = zvec_runtime.open_collection(str(path), read_only=self.read_only)
                    self._handles[k] = coll
                    return coll
            except CollectionFencedError:
                raise
            except Exception as e:  # noqa: BLE001
                if attempt >= retries or not self._is_lock_error(e):
                    raise
                attempt += 1
                logger.warning(
                    "lock conflict opening %s (attempt %s/%s): %s",
                    k,
                    attempt,
                    retries,
                    e,
                )
                time.sleep(retry_delay * attempt)

    def close_partition(
        self,
        db_name: str,
        collection_name: str,
        partition_name: str,
        *,
        flush: bool | None = None,
    ) -> bool:
        """Close cached handle. Returns False when flush was attempted and failed."""
        k = self.key(db_name, collection_name, partition_name)
        with self._lock:
            coll = self._handles.pop(k, None)
        do_flush = (not self.read_only) if flush is None else flush
        return self._release_handle(coll, flush=do_flush)

    def flush_partition(
        self,
        db_name: str,
        collection_name: str,
        partition_name: str = DEFAULT_PARTITION,
        *,
        retries: int = 8,
        retry_delay: float = 0.05,
    ) -> None:
        """Flush WAL for a partition. Writer-only.

        If the partition is already open (e.g. mid-insert), flush **in place** and
        keep the handle. Reader-triggered ``/internal/flush`` must not
        ``force_reopen``/steal an in-use handle — that races writes and can leave
        missing ``scalar.*.ipc`` / crash native zvec.
        """
        if self.read_only:
            raise RuntimeError("flush_partition requires a read-write CollectionManager")
        k = self.key(db_name, collection_name, partition_name)
        with self._lock:
            existing = self._handles.get(k)
        if existing is not None:
            # In-use handle: flush only; write path owns open/close lifecycle.
            if hasattr(existing, "flush"):
                existing.flush()
            return

        handle = self.open_partition(
            db_name,
            collection_name,
            partition_name,
            force_reopen=False,
            retries=retries,
            retry_delay=retry_delay,
        )
        try:
            if hasattr(handle, "flush"):
                handle.flush()
        finally:
            ok = self.close_partition(db_name, collection_name, partition_name, flush=True)
            handle = None
            if not ok:
                raise RuntimeError(
                    f"flush failed for {db_name}/{collection_name}/{partition_name}"
                )
            if self.has_wal(db_name, collection_name, partition_name):
                raise RuntimeError(
                    f"WAL still present after flush: {db_name}/{collection_name}/{partition_name}"
                )

    def close_collection(self, db_name: str, collection_name: str) -> None:
        prefix = f"{db_name}/{collection_name}/"
        released: list[Any] = []
        with self._lock:
            for k in list(self._handles):
                if k.startswith(prefix):
                    released.append(self._handles.pop(k))
        for coll in released:
            self._release_handle(coll, flush=not self.read_only)

    def reopen_all(self) -> None:
        with self._lock:
            keys = [k for k in self._handles.keys() if k not in self._fenced]
            # Skip collection-wide fenced prefixes.
            filtered = []
            for k in keys:
                db, coll, part = k.split("/", 2)
                if self.is_fenced(db, coll, part):
                    continue
                filtered.append(k)
            released = [self._handles.pop(k) for k in filtered]
        for coll in released:
            self._release_handle(coll, flush=not self.read_only)
        for k in filtered:
            db, coll, part = k.split("/", 2)
            try:
                self.open_partition(db, coll, part, force_reopen=True)
            except CollectionFencedError:
                logger.debug("skip reopen fenced %s", k)
            except Exception:  # noqa: BLE001
                logger.exception("reopen failed for %s", k)

    def get_if_open(self, db_name: str, collection_name: str, partition_name: str):
        return self._handles.get(self.key(db_name, collection_name, partition_name))

    def open_keys(self) -> list[tuple[str, str, str]]:
        """Return (db, collection, partition) for currently cached handles."""
        with self._lock:
            out: list[tuple[str, str, str]] = []
            for k in self._handles:
                db, coll, part = k.split("/", 2)
                out.append((db, coll, part))
            return out

    def optimize(self, db_name: str, collection_name: str, partition_name: str) -> None:
        coll = self.open_partition(db_name, collection_name, partition_name)
        if hasattr(coll, "optimize"):
            coll.optimize()
