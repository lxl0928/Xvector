from __future__ import annotations

from typing import Any

from xvector.common.errors import AlreadyExistsError, NotFoundError, ParamError
from xvector.common.paths import DEFAULT_DB, validate_name
from xvector.services.context import AppContext


class AliasService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def _db(self, body: dict[str, Any]) -> str:
        return body.get("dbName") or body.get("db_name") or DEFAULT_DB

    async def create(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        alias = body.get("aliasName") or body.get("alias")
        coll = body.get("collectionName") or body.get("collection_name")
        validate_name(alias, "alias")
        self.ctx.catalog.require_collection(db, coll)
        if self.ctx.catalog.get_alias(db, alias) or self.ctx.catalog.get_collection(db, alias):
            raise AlreadyExistsError(f"alias or collection already exists: {alias}")
        self.ctx.catalog.put_alias(db, alias, coll)
        return {}

    async def drop(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        alias = body.get("aliasName") or body.get("alias")
        if not self.ctx.catalog.get_alias(db, alias):
            raise NotFoundError(f"alias not found: {alias}")
        self.ctx.catalog.delete_alias(db, alias)
        return {}

    async def alter(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        alias = body.get("aliasName") or body.get("alias")
        coll = body.get("collectionName") or body.get("collection_name")
        if not self.ctx.catalog.get_alias(db, alias):
            raise NotFoundError(f"alias not found: {alias}")
        self.ctx.catalog.require_collection(db, coll)
        self.ctx.catalog.put_alias(db, alias, coll)
        return {}

    async def describe(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        alias = body.get("aliasName") or body.get("alias")
        a = self.ctx.catalog.get_alias(db, alias)
        if not a:
            raise NotFoundError(f"alias not found: {alias}")
        return {"aliasName": alias, "collectionName": a["collection_name"], "dbName": db}

    async def list(self, body: dict[str, Any] | None = None) -> list[str]:
        body = body or {}
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        aliases = self.ctx.catalog.list_aliases(db)
        if coll:
            aliases = [a for a in aliases if a.get("collection_name") == coll]
        return [a["alias"] for a in aliases]
