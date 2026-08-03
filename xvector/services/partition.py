from __future__ import annotations

from typing import Any

from xvector.common.errors import AlreadyExistsError, NotFoundError, ParamError
from xvector.common.paths import DEFAULT_DB, DEFAULT_PARTITION, validate_name
from xvector.engine.partition_layout import partition_kind
from xvector.services.context import AppContext


class PartitionService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def _db(self, body: dict[str, Any]) -> str:
        return body.get("dbName") or body.get("db_name") or DEFAULT_DB

    async def create(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        part = body.get("partitionName") or body.get("partition_name")
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        validate_name(part, "partition")
        if part == DEFAULT_PARTITION:
            raise ParamError("_default already exists")
        meta = self.ctx.catalog.require_collection(db, coll)
        if self.ctx.catalog.get_partition(db, coll, part):
            raise AlreadyExistsError(f"partition already exists: {part}")
        indexes = self.ctx.catalog.list_indexes(db, coll)
        self.ctx.catalog.put_partition(db, coll, part, partition_kind(part))
        self.ctx.collections.create_partition_collection(db, coll, part, meta, index_defs=indexes)
        if self.ctx.role == "writer":
            self.ctx.collections.close_partition(db, coll, part)
        return {}

    async def drop(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        part = body.get("partitionName") or body.get("partition_name")
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        if part == DEFAULT_PARTITION:
            raise ParamError("cannot drop _default partition")
        if not self.ctx.catalog.get_partition(db, coll, part):
            raise NotFoundError(f"partition not found: {part}")
        self.ctx.collections.close_partition(db, coll, part)
        self.ctx.paths.remove_path(self.ctx.paths.partition_dir(db, coll, part))
        self.ctx.catalog.delete_partition(db, coll, part)
        await self.ctx.notify_reader(
            "/internal/close",
            {"dbName": db, "collectionName": coll, "partitionNames": [part]},
        )
        return {}

    async def has(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        part = body.get("partitionName") or body.get("partition_name")
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        exists = part in self.ctx.catalog.list_partitions(db, coll)
        return {"has": exists}

    async def list(self, body: dict[str, Any]) -> list[str]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        self.ctx.catalog.require_collection(db, coll)
        return self.ctx.catalog.list_partitions(db, coll)

    async def get_stats(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        part = body.get("partitionName") or body.get("partition_name") or DEFAULT_PARTITION
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        handle = self.ctx.collections.open_partition(db, coll, part)
        try:
            stats = getattr(handle, "stats", None)
            if callable(stats):
                stats = stats()
            row_count = 0
            if isinstance(stats, dict):
                row_count = int(stats.get("row_count") or stats.get("doc_count") or 0)
            elif stats is not None:
                row_count = int(getattr(stats, "row_count", getattr(stats, "doc_count", 0)) or 0)
        finally:
            if self.ctx.role == "writer":
                self.ctx.collections.close_partition(db, coll, part)
        return {"rowCount": row_count}

    async def load(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        parts = body.get("partitionNames") or body.get("partition_names") or []
        if body.get("partitionName"):
            parts = [body["partitionName"]]
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        self.ctx.catalog.require_collection(db, coll)
        self.ctx.catalog.set_load_state(db, coll, loaded=True, scope="partition", partition_names=list(parts))
        for p in parts:
            self.ctx.collections.close_partition(db, coll, p)
        await self.ctx.notify_reader(
            "/internal/open",
            {"dbName": db, "collectionName": coll, "partitionNames": list(parts)},
        )
        return {}

    async def release(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        parts = body.get("partitionNames") or body.get("partition_names") or []
        if body.get("partitionName"):
            parts = [body["partitionName"]]
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        for p in parts:
            self.ctx.collections.close_partition(db, coll, p)
        # if releasing all, mark unloaded
        all_parts = set(self.ctx.catalog.list_partitions(db, coll))
        if not parts or set(parts) >= all_parts:
            self.ctx.catalog.set_load_state(db, coll, loaded=False)
        await self.ctx.notify_reader(
            "/internal/close",
            {"dbName": db, "collectionName": coll, "partitionNames": list(parts)},
        )
        return {}
