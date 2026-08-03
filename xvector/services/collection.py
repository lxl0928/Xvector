from __future__ import annotations

from typing import Any

from xvector.common.errors import AlreadyExistsError, NotFoundError, ParamError
from xvector.common.paths import DEFAULT_DB, DEFAULT_PARTITION, validate_name
from xvector.common.schema_map import parse_milvus_schema
from xvector.engine.partition_layout import partition_kind
from xvector.services.context import AppContext


class CollectionService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def _db(self, body: dict[str, Any]) -> str:
        return body.get("dbName") or body.get("db_name") or DEFAULT_DB

    async def create_database(self, body: dict[str, Any]) -> dict[str, Any]:
        db = body.get("dbName") or body.get("db_name")
        validate_name(db, "dbName")
        self.ctx.paths.db_dir(db).mkdir(parents=True, exist_ok=True)
        self.ctx.catalog.create_database(db)
        return {}

    async def drop_database(self, body: dict[str, Any]) -> dict[str, Any]:
        db = body.get("dbName") or body.get("db_name")
        self.ctx.catalog.drop_database(db)
        self.ctx.paths.remove_path(self.ctx.paths.db_dir(db))
        return {}

    async def list_databases(self, body: dict[str, Any] | None = None) -> list[str]:
        return self.ctx.catalog.list_databases()

    async def describe_database(self, body: dict[str, Any]) -> dict[str, Any]:
        db = body.get("dbName") or body.get("db_name") or DEFAULT_DB
        meta = self.ctx.catalog.get_database(db)
        if not meta:
            raise NotFoundError(f"database not found: {db}")
        return {"dbName": db, "properties": {}}

    async def create_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        validate_name(name, "collectionName")
        if not self.ctx.catalog.get_database(db):
            raise NotFoundError(f"database not found: {db}")
        if self.ctx.catalog.get_collection(db, name):
            raise AlreadyExistsError(f"collection already exists: {name}")

        parsed = parse_milvus_schema(body)
        self.ctx.catalog.put_collection(db, name, parsed)
        self.ctx.catalog.put_partition(db, name, DEFAULT_PARTITION, partition_kind(DEFAULT_PARTITION))
        self.ctx.collections.create_partition_collection(db, name, DEFAULT_PARTITION, parsed, index_defs=[])
        # close writer handle after create to keep resources light; reopen on demand
        if self.ctx.role == "writer":
            self.ctx.collections.close_partition(db, name, DEFAULT_PARTITION)
        self.ctx.catalog.set_load_state(db, name, loaded=False)
        return {}

    async def drop_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        self.ctx.catalog.require_collection(db, name)
        self.ctx.collections.close_collection(db, name)
        self.ctx.paths.remove_path(self.ctx.paths.collection_dir(db, name))
        self.ctx.catalog.delete_collection_meta(db, name)
        await self.ctx.notify_reader("/internal/close", {"dbName": db, "collectionName": name})
        return {}

    async def describe_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        meta = self.ctx.catalog.require_collection(db, name)
        indexes = self.ctx.catalog.list_indexes(db, name)
        return {
            "collectionName": name,
            "dbName": db,
            "schema": meta.get("schema") or {},
            "shardsNum": meta.get("shards_num", 1),
            "consistencyLevel": meta.get("consistency_level", "Eventually"),
            "indexes": [
                {
                    "fieldName": i.get("field_name"),
                    "indexName": i.get("index_name"),
                    "indexType": i.get("index_type"),
                    "metricType": i.get("metric_type"),
                }
                for i in indexes
            ],
            "autoId": meta.get("auto_id", False),
            "primaryField": meta.get("primary_field"),
        }

    async def has_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        resolved = self.ctx.catalog.resolve_collection_name(db, name)
        exists = self.ctx.catalog.get_collection(db, resolved) is not None
        return {"has": exists}

    async def list_collections(self, body: dict[str, Any] | None = None) -> list[str]:
        body = body or {}
        db = self._db(body)
        return self.ctx.catalog.list_collections(db)

    async def rename_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        old = body.get("collectionName") or body.get("oldName")
        new = body.get("newCollectionName") or body.get("newName")
        validate_name(new, "collectionName")
        meta = self.ctx.catalog.require_collection(db, old)
        if self.ctx.catalog.get_collection(db, new):
            raise AlreadyExistsError(f"collection already exists: {new}")
        self.ctx.collections.close_collection(db, old)
        src = self.ctx.paths.collection_dir(db, old)
        dst = self.ctx.paths.collection_dir(db, new)
        self.ctx.paths.rename_path(src, dst)
        # rewrite meta
        parts = self.ctx.catalog.list_partitions(db, old)
        indexes = self.ctx.catalog.list_indexes(db, old)
        load = self.ctx.catalog.get_load_state(db, old)
        self.ctx.catalog.delete_collection_meta(db, old)
        meta["collection_name"] = new
        self.ctx.catalog.put_collection(db, new, meta)
        for p in parts:
            self.ctx.catalog.put_partition(db, new, p, partition_kind(p))
        for idx in indexes:
            idx["collection_name"] = new
            self.ctx.catalog.put_index(db, new, idx)
        self.ctx.catalog.set_load_state(
            db,
            new,
            loaded=bool(load.get("loaded")),
            scope=load.get("scope", "collection"),
            partition_names=load.get("partition_names") or [],
            replica_number=int(load.get("replica_number") or 1),
        )
        return {}

    async def load_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        self.ctx.catalog.require_collection(db, name)
        replica = int(body.get("replicaNumber") or body.get("replica_number") or 1)
        self.ctx.catalog.set_load_state(db, name, loaded=True, scope="collection", replica_number=replica)
        parts = self.ctx.catalog.list_partitions(db, name)
        # zvec LOCK is exclusive: writer must release before reader opens.
        self.ctx.collections.close_collection(db, name)
        await self.ctx.notify_reader(
            "/internal/open",
            {"dbName": db, "collectionName": name, "partitionNames": parts},
        )
        return {}

    async def release_collection(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        self.ctx.catalog.require_collection(db, name)
        self.ctx.catalog.set_load_state(db, name, loaded=False)
        self.ctx.collections.close_collection(db, name)
        await self.ctx.notify_reader("/internal/close", {"dbName": db, "collectionName": name})
        return {}

    async def get_load_state(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        st = self.ctx.catalog.get_load_state(db, name)
        state = "LoadStateLoaded" if st.get("loaded") else "LoadStateNotLoad"
        return {"state": state, "loadState": state}

    async def get_stats(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        self.ctx.catalog.require_collection(db, name)
        row_count = 0
        for part in self.ctx.catalog.list_partitions(db, name):
            try:
                coll = self.ctx.collections.open_partition(db, name, part)
                try:
                    stats = getattr(coll, "stats", None)
                    if callable(stats):
                        stats = stats()
                    if stats is None:
                        continue
                    if isinstance(stats, dict):
                        row_count += int(
                            stats.get("row_count") or stats.get("doc_count") or stats.get("count") or 0
                        )
                    else:
                        row_count += int(
                            getattr(stats, "row_count", getattr(stats, "doc_count", 0)) or 0
                        )
                finally:
                    # Writer must not keep RW handles; they block reader RO open.
                    if self.ctx.role == "writer":
                        self.ctx.collections.close_partition(db, name, part)
            except Exception:  # noqa: BLE001
                continue
        return {"rowCount": row_count}
