from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from xvector.config import Settings
from xvector.engine.collection_mgr import CollectionManager
from xvector.meta.catalog import Catalog
from xvector.meta.store import MetaStore
from xvector.common.paths import DataPaths

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings
    paths: DataPaths
    meta: MetaStore
    catalog: Catalog
    collections: CollectionManager
    role: str

    async def _notify_peer(
        self,
        base_url: str,
        path: str,
        body: dict[str, Any],
        *,
        peer: str,
        require_ok: bool = False,
        timeout: float = 5.0,
    ) -> dict[str, Any] | None:
        headers = {}
        if self.settings.internal_token:
            headers["X-Internal-Token"] = self.settings.internal_token
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{base_url.rstrip('/')}{path}",
                    json=body,
                    headers=headers,
                )
            data: dict[str, Any] = {}
            try:
                payload = resp.json()
                if isinstance(payload, dict):
                    data = payload
            except Exception:  # noqa: BLE001
                data = {}
            if require_ok and (resp.status_code >= 400 or data.get("ok") is False):
                raise RuntimeError(
                    f"{peer} {path} failed status={resp.status_code} body={data}"
                )
            return data
        except Exception as e:  # noqa: BLE001
            if require_ok:
                raise
            logger.warning("notify_%s %s failed: %s", peer, path, e)
            return None

    async def notify_reader(
        self,
        path: str,
        body: dict[str, Any],
        *,
        require_ok: bool = False,
        timeout: float = 5.0,
    ) -> dict[str, Any] | None:
        if self.role != "writer":
            return None
        return await self._notify_peer(
            self.settings.reader_url,
            path,
            body,
            peer="reader",
            require_ok=require_ok,
            timeout=timeout,
        )

    async def notify_writer(
        self,
        path: str,
        body: dict[str, Any],
        *,
        require_ok: bool = False,
        timeout: float = 30.0,
    ) -> dict[str, Any] | None:
        if self.role != "reader":
            return None
        return await self._notify_peer(
            self.settings.writer_url,
            path,
            body,
            peer="writer",
            require_ok=require_ok,
            timeout=timeout,
        )

    async def seal_partitions_via_writer(
        self,
        db: str,
        coll: str,
        parts: list[str],
        *,
        require_ok: bool = False,
    ) -> dict[str, Any] | None:
        """Ask Writer to RW-open + flush + close so pending WAL is cleared for RO open."""
        return await self.notify_writer(
            "/internal/flush",
            {
                "dbName": db,
                "collectionName": coll,
                "partitionNames": list(parts),
            },
            require_ok=require_ok,
            timeout=60.0,
        )

    def with_reader_released(self, db: str, coll: str, parts: list[str] | None = None):
        """Async context manager: fence+close reader handles so writer can RW-lock zvec paths.

        zvec collection LOCK is exclusive across processes. After Load, reader keeps RO
        handles; without a fence the refresh loop / concurrent search can reopen RO and
        block writer insert/upsert/delete.
        """

        @asynccontextmanager
        async def _cm() -> AsyncIterator[bool]:
            body: dict[str, Any] = {"dbName": db, "collectionName": coll, "fence": True}
            if parts is not None:
                body["partitionNames"] = list(parts)
            st = self.catalog.get_load_state(db, coll)
            was_loaded = bool(st.get("loaded"))
            # Always fence: even if not loaded yet, prevent a racing load/refresh open.
            await self.notify_reader("/internal/close", body, require_ok=False)
            try:
                yield was_loaded
            finally:
                open_parts = list(
                    parts
                    or st.get("partition_names")
                    or self.catalog.list_partitions(db, coll)
                )
                # zvec RO open cannot replay WAL into IDMap — seal before reopen notify.
                for p in open_parts:
                    if self.collections.has_wal(db, coll, p):
                        try:
                            self.collections.flush_partition(db, coll, p)
                        except Exception:  # noqa: BLE001
                            logger.exception(
                                "seal before reader reopen failed %s/%s/%s", db, coll, p
                            )
                if was_loaded:
                    open_body = {
                        "dbName": db,
                        "collectionName": coll,
                        "partitionNames": open_parts,
                    }
                    await self.notify_reader("/internal/open", open_body, require_ok=False)
                else:
                    unfence_body: dict[str, Any] = {
                        "dbName": db,
                        "collectionName": coll,
                    }
                    if parts is not None:
                        unfence_body["partitionNames"] = list(parts)
                    await self.notify_reader(
                        "/internal/unfence",
                        unfence_body,
                        require_ok=False,
                    )

        return _cm()
