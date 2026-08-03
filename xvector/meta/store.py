from __future__ import annotations

import json
import logging
import threading
from typing import Any

from xvector.common.paths import DataPaths
from xvector.engine import zvec_runtime
from xvector.meta.docs import decode_payload, encode_payload, now_ms

logger = logging.getLogger(__name__)

META_VECTOR_FIELD = "_meta_vec"


class MetaNotReadyError(RuntimeError):
    """Reader meta snapshot is not available yet."""


class MetaStore:
    """Internal metadata store.

    Writer keeps an exclusive zvec handle on ``xvector_meta`` and mirrors all
    docs to ``catalog_snapshot.json``. Reader never opens the zvec meta path:
    zvec allows multiple readers *or* a single writer, so a live writer lock
    blocks read-only open. Reader loads the shared JSON snapshot instead.
    """

    def __init__(self, paths: DataPaths, read_only: bool = False):
        self.paths = paths
        self.read_only = read_only
        self._lock = threading.RLock()
        self._coll = None
        self._docs: dict[str, dict[str, Any]] = {}
        self._opened = False

    @property
    def is_open(self) -> bool:
        return self._opened

    def publish_snapshot(self) -> None:
        """Atomically publish the in-memory catalog for readers."""
        with self._lock:
            if self.read_only:
                raise RuntimeError("meta store is read-only")
            if not self._opened:
                raise RuntimeError("MetaStore not opened")
            self._flush_snapshot()

    def open(self) -> None:
        with self._lock:
            self.paths.ensure_layout()
            if self.read_only:
                self._load_snapshot()
                self._opened = True
                return

            meta_path = str(self.paths.meta_dir)
            zvec_runtime.ensure_init()
            import zvec

            schema = zvec.CollectionSchema(
                name="xvector_meta",
                fields=[
                    zvec.FieldSchema(
                        name="doc_type",
                        data_type=zvec.DataType.STRING,
                        index_param=zvec.InvertIndexParam(),
                    ),
                    zvec.FieldSchema(
                        name="payload",
                        data_type=zvec.DataType.STRING,
                        nullable=True,
                    ),
                    zvec.FieldSchema(
                        name="updated_at",
                        data_type=zvec.DataType.INT64,
                        index_param=zvec.InvertIndexParam(enable_range_optimization=True),
                    ),
                ],
                vectors=[
                    zvec.VectorSchema(
                        name=META_VECTOR_FIELD,
                        data_type=zvec.DataType.VECTOR_FP32,
                        dimension=1,
                        index_param=zvec.FlatIndexParam(metric_type=zvec.MetricType.L2),
                    )
                ],
            )
            meta_dir = self.paths.meta_dir
            if meta_dir.exists() and any(meta_dir.iterdir()):
                self._coll = zvec_runtime.open_collection(meta_path, read_only=False)
            else:
                # Remove empty placeholder dirs created by failed boots.
                if meta_dir.exists():
                    meta_dir.rmdir()
                self._coll = zvec_runtime.create_and_open(meta_path, schema, read_only=False)
            self._rebuild_cache_from_zvec()
            # Avoid clobbering a good snapshot if zvec scan failed on an existing store.
            if self._docs or not self.paths.meta_snapshot.exists():
                self._flush_snapshot()
            elif not self._docs and self.paths.meta_snapshot.exists():
                logger.warning("zvec meta cache empty; keeping existing snapshot")
                self._load_snapshot_into_cache()
            self._opened = True

    def close(self) -> None:
        with self._lock:
            if not self.read_only and self._opened:
                try:
                    self._flush_snapshot()
                except Exception:  # noqa: BLE001
                    logger.exception("flush snapshot on close failed")
            zvec_runtime.close_collection(self._coll)
            self._coll = None
            self._docs.clear()
            self._opened = False

    def reopen(self) -> None:
        with self._lock:
            if self.read_only:
                self._load_snapshot()
                self._opened = True
                return
            zvec_runtime.close_collection(self._coll)
            self._coll = None
            self._opened = False
            self.open()

    @property
    def coll(self):
        if self._coll is None:
            raise RuntimeError("MetaStore not opened")
        return self._coll

    def upsert(self, doc_id: str, doc_type: str, payload: dict[str, Any]) -> None:
        with self._lock:
            if self.read_only:
                raise RuntimeError("meta store is read-only")
            import zvec

            body = dict(payload)
            body["doc_type"] = doc_type
            ts = now_ms()
            body.setdefault("updated_at", ts)
            body["_id"] = doc_id
            doc = zvec.Doc(
                id=doc_id,
                vectors={META_VECTOR_FIELD: [0.0]},
                fields={
                    "doc_type": doc_type,
                    "payload": encode_payload(body),
                    "updated_at": int(body["updated_at"]),
                },
            )
            if hasattr(self.coll, "upsert"):
                self.coll.upsert(doc)
            else:
                try:
                    self.coll.delete(ids=doc_id)
                except Exception:  # noqa: BLE001
                    pass
                self.coll.insert(doc)
            self._docs[doc_id] = body
            self._flush_snapshot()

    def get(self, doc_id: str) -> dict[str, Any] | None:
        with self._lock:
            if self.read_only:
                self._load_snapshot()
                self._opened = True
            if not self._opened:
                return None
            doc = self._docs.get(doc_id)
            return dict(doc) if doc else None

    def delete(self, doc_id: str) -> None:
        with self._lock:
            if self.read_only:
                raise RuntimeError("meta store is read-only")
            try:
                self.coll.delete(ids=doc_id)
            except Exception:  # noqa: BLE001
                logger.debug("meta delete miss %s", doc_id)
            self._docs.pop(doc_id, None)
            self._flush_snapshot()

    def list_by_type(self, doc_type: str) -> list[dict[str, Any]]:
        with self._lock:
            if self.read_only:
                self._load_snapshot()
                self._opened = True
            return [dict(d) for d in self._docs.values() if d.get("doc_type") == doc_type]

    def _flush_snapshot(self) -> None:
        path = self.paths.meta_snapshot
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        payload = {"docs": self._docs, "updated_at": now_ms()}
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _load_snapshot(self) -> None:
        if not self.paths.meta_snapshot.exists():
            raise MetaNotReadyError("meta snapshot missing in read-only mode")
        self._load_snapshot_into_cache()

    def _load_snapshot_into_cache(self) -> None:
        path = self.paths.meta_snapshot
        data = json.loads(path.read_text(encoding="utf-8"))
        docs = data.get("docs") or {}
        if not isinstance(docs, dict):
            raise RuntimeError("invalid meta snapshot")
        self._docs = {str(k): dict(v) for k, v in docs.items()}

    def _rebuild_cache_from_zvec(self) -> None:
        self._docs.clear()
        try:
            import zvec

            result = self.coll.query(
                queries=zvec.Query(field_name=META_VECTOR_FIELD, vector=[0.0]),
                topk=100000,
            )
            for payload in self._normalize_query(result):
                doc_id = payload.get("_id")
                if doc_id:
                    self._docs[str(doc_id)] = payload
        except Exception:  # noqa: BLE001
            logger.exception("rebuild meta cache from zvec failed")

    def _normalize_query(self, result: Any) -> list[dict[str, Any]]:
        rows = result
        if isinstance(result, dict) and "docs" in result:
            rows = result["docs"]
        elif isinstance(result, dict):
            rows = list(result.values())
        if not isinstance(rows, list):
            rows = [rows] if rows else []
        # zvec often returns [[hit, ...]] for a single query vector.
        flat: list[Any] = []
        for row in rows:
            if isinstance(row, list):
                flat.extend(row)
            else:
                flat.append(row)
        out = []
        for row in flat:
            payload = self._doc_to_payload(row)
            if payload:
                out.append(payload)
        return out

    def _doc_to_payload(self, item: Any) -> dict[str, Any] | None:
        if item is None:
            return None
        if isinstance(item, dict):
            fields = item.get("fields") or {}
            payload_raw = fields.get("payload")
            if payload_raw is None and "payload" in item:
                payload_raw = item["payload"]
            doc_id = item.get("id")
        else:
            fields = getattr(item, "fields", {}) or {}
            payload_raw = fields.get("payload")
            doc_id = getattr(item, "id", None)
            # Some zvec hit wrappers expose doc via .doc
            if payload_raw is None and hasattr(item, "doc"):
                return self._doc_to_payload(getattr(item, "doc"))
        payload = decode_payload(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        if doc_id and "_id" not in payload:
            payload["_id"] = doc_id
        return payload
