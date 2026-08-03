from __future__ import annotations

from typing import Any

from xvector.auth.password import generate_salt, hash_password
from xvector.common.errors import AlreadyExistsError, NotFoundError, ParamError
from xvector.common.paths import DEFAULT_DB, DEFAULT_PARTITION, validate_name
from xvector.meta import docs
from xvector.meta.store import MetaStore


class Catalog:
    def __init__(self, store: MetaStore):
        self.store = store

    # ---------- bootstrap ----------
    def ensure_defaults(self, bootstrap_username: str, bootstrap_password: str) -> None:
        if not self.get_database(DEFAULT_DB):
            self.create_database(DEFAULT_DB)
        user = self.get_user(bootstrap_username)
        salt = generate_salt()
        payload = {
            "username": bootstrap_username,
            "password_salt": salt,
            "password_hash": hash_password(bootstrap_password, salt),
            "roles": ["admin"],
            "is_bootstrap": True,
            "created_at": docs.now_ms(),
            "updated_at": docs.now_ms(),
        }
        if user:
            payload["created_at"] = user.get("created_at", payload["created_at"])
            # keep existing hash unless bootstrap flag; always refresh roles/bootstrap marker
            if not user.get("is_bootstrap"):
                payload["password_salt"] = user["password_salt"]
                payload["password_hash"] = user["password_hash"]
        self.store.upsert(docs.make_id(docs.DOC_USER, bootstrap_username), docs.DOC_USER, payload)
        if not self.get_role("admin"):
            self.create_role("admin", privileges=[])

    # ---------- database ----------
    def create_database(self, db_name: str) -> None:
        validate_name(db_name, "dbName")
        if self.get_database(db_name):
            raise AlreadyExistsError(f"database already exists: {db_name}")
        self.store.upsert(
            docs.make_id(docs.DOC_DATABASE, db_name),
            docs.DOC_DATABASE,
            {"db_name": db_name, "created_at": docs.now_ms()},
        )

    def drop_database(self, db_name: str) -> None:
        validate_name(db_name, "dbName")
        if db_name == DEFAULT_DB:
            raise ParamError("cannot drop default database")
        if not self.get_database(db_name):
            raise NotFoundError(f"database not found: {db_name}")
        cols = self.list_collections(db_name)
        if cols:
            raise ParamError("database is not empty")
        self.store.delete(docs.make_id(docs.DOC_DATABASE, db_name))

    def get_database(self, db_name: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_DATABASE, db_name))

    def list_databases(self) -> list[str]:
        return sorted({d["db_name"] for d in self.store.list_by_type(docs.DOC_DATABASE) if "db_name" in d})

    # ---------- collection ----------
    def put_collection(self, db_name: str, collection_name: str, meta: dict[str, Any]) -> None:
        validate_name(db_name, "dbName")
        validate_name(collection_name, "collectionName")
        payload = dict(meta)
        payload.update(
            {
                "db_name": db_name,
                "collection_name": collection_name,
                "updated_at": docs.now_ms(),
            }
        )
        payload.setdefault("created_at", docs.now_ms())
        self.store.upsert(
            docs.make_id(docs.DOC_COLLECTION, f"{db_name}/{collection_name}"),
            docs.DOC_COLLECTION,
            payload,
        )

    def get_collection(self, db_name: str, collection_name: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_COLLECTION, f"{db_name}/{collection_name}"))

    def require_collection(self, db_name: str, collection_name: str) -> dict[str, Any]:
        coll = self.get_collection(db_name, collection_name)
        if not coll:
            raise NotFoundError(f"collection not found: {db_name}.{collection_name}")
        return coll

    def list_collections(self, db_name: str) -> list[str]:
        out = []
        for d in self.store.list_by_type(docs.DOC_COLLECTION):
            if d.get("db_name") == db_name:
                out.append(d["collection_name"])
        return sorted(out)

    def delete_collection_meta(self, db_name: str, collection_name: str) -> None:
        self.store.delete(docs.make_id(docs.DOC_COLLECTION, f"{db_name}/{collection_name}"))
        for p in self.list_partitions(db_name, collection_name):
            self.store.delete(docs.make_id(docs.DOC_PARTITION, f"{db_name}/{collection_name}/{p}"))
        for idx in self.list_indexes(db_name, collection_name):
            self.store.delete(
                docs.make_id(docs.DOC_INDEX, f"{db_name}/{collection_name}/{idx['index_name']}")
            )
        for a in self.list_aliases(db_name):
            if a.get("collection_name") == collection_name:
                self.store.delete(docs.make_id(docs.DOC_ALIAS, f"{db_name}/{a['alias']}"))
        self.store.delete(docs.make_id(docs.DOC_LOAD, f"{db_name}/{collection_name}"))

    # ---------- partition ----------
    def put_partition(self, db_name: str, collection_name: str, partition_name: str, kind: str) -> None:
        validate_name(partition_name, "partition")
        self.store.upsert(
            docs.make_id(docs.DOC_PARTITION, f"{db_name}/{collection_name}/{partition_name}"),
            docs.DOC_PARTITION,
            {
                "db_name": db_name,
                "collection_name": collection_name,
                "partition_name": partition_name,
                "kind": kind,
                "created_at": docs.now_ms(),
            },
        )

    def get_partition(self, db_name: str, collection_name: str, partition_name: str) -> dict[str, Any] | None:
        return self.store.get(
            docs.make_id(docs.DOC_PARTITION, f"{db_name}/{collection_name}/{partition_name}")
        )

    def list_partitions(self, db_name: str, collection_name: str) -> list[str]:
        out = []
        for d in self.store.list_by_type(docs.DOC_PARTITION):
            if d.get("db_name") == db_name and d.get("collection_name") == collection_name:
                out.append(d["partition_name"])
        if DEFAULT_PARTITION not in out and self.get_collection(db_name, collection_name):
            out.append(DEFAULT_PARTITION)
        return sorted(set(out), key=lambda x: (x != DEFAULT_PARTITION, x))

    def delete_partition(self, db_name: str, collection_name: str, partition_name: str) -> None:
        self.store.delete(docs.make_id(docs.DOC_PARTITION, f"{db_name}/{collection_name}/{partition_name}"))

    # ---------- alias ----------
    def put_alias(self, db_name: str, alias: str, collection_name: str) -> None:
        self.store.upsert(
            docs.make_id(docs.DOC_ALIAS, f"{db_name}/{alias}"),
            docs.DOC_ALIAS,
            {
                "db_name": db_name,
                "alias": alias,
                "collection_name": collection_name,
                "updated_at": docs.now_ms(),
            },
        )

    def get_alias(self, db_name: str, alias: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_ALIAS, f"{db_name}/{alias}"))

    def list_aliases(self, db_name: str) -> list[dict[str, Any]]:
        return [d for d in self.store.list_by_type(docs.DOC_ALIAS) if d.get("db_name") == db_name]

    def delete_alias(self, db_name: str, alias: str) -> None:
        self.store.delete(docs.make_id(docs.DOC_ALIAS, f"{db_name}/{alias}"))

    def resolve_collection_name(self, db_name: str, name: str) -> str:
        """Resolve alias or return collection name."""
        if self.get_collection(db_name, name):
            return name
        alias = self.get_alias(db_name, name)
        if alias:
            return alias["collection_name"]
        return name

    # ---------- index ----------
    def put_index(self, db_name: str, collection_name: str, index: dict[str, Any]) -> None:
        name = index["index_name"]
        payload = dict(index)
        payload.update(
            {
                "db_name": db_name,
                "collection_name": collection_name,
                "updated_at": docs.now_ms(),
            }
        )
        payload.setdefault("created_at", docs.now_ms())
        self.store.upsert(
            docs.make_id(docs.DOC_INDEX, f"{db_name}/{collection_name}/{name}"),
            docs.DOC_INDEX,
            payload,
        )

    def get_index(self, db_name: str, collection_name: str, index_name: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_INDEX, f"{db_name}/{collection_name}/{index_name}"))

    def list_indexes(self, db_name: str, collection_name: str) -> list[dict[str, Any]]:
        return [
            d
            for d in self.store.list_by_type(docs.DOC_INDEX)
            if d.get("db_name") == db_name and d.get("collection_name") == collection_name
        ]

    def delete_index(self, db_name: str, collection_name: str, index_name: str) -> None:
        self.store.delete(docs.make_id(docs.DOC_INDEX, f"{db_name}/{collection_name}/{index_name}"))

    # ---------- load ----------
    def set_load_state(
        self,
        db_name: str,
        collection_name: str,
        loaded: bool,
        scope: str = "collection",
        partition_names: list[str] | None = None,
        replica_number: int = 1,
    ) -> None:
        key = f"{db_name}/{collection_name}"
        self.store.upsert(
            docs.make_id(docs.DOC_LOAD, key),
            docs.DOC_LOAD,
            {
                "db_name": db_name,
                "collection_name": collection_name,
                "scope": scope,
                "partition_names": partition_names or [],
                "loaded": loaded,
                "replica_number": replica_number,
                "updated_at": docs.now_ms(),
            },
        )

    def get_load_state(self, db_name: str, collection_name: str) -> dict[str, Any]:
        st = self.store.get(docs.make_id(docs.DOC_LOAD, f"{db_name}/{collection_name}"))
        if not st:
            return {
                "db_name": db_name,
                "collection_name": collection_name,
                "loaded": False,
                "scope": "collection",
                "partition_names": [],
                "replica_number": 1,
            }
        return st

    # ---------- user / role ----------
    def get_user(self, username: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_USER, username))

    def put_user(self, user: dict[str, Any]) -> None:
        self.store.upsert(docs.make_id(docs.DOC_USER, user["username"]), docs.DOC_USER, user)

    def delete_user(self, username: str) -> None:
        self.store.delete(docs.make_id(docs.DOC_USER, username))

    def list_users(self) -> list[str]:
        return sorted(d["username"] for d in self.store.list_by_type(docs.DOC_USER) if "username" in d)

    def get_role(self, role_name: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_ROLE, role_name))

    def create_role(self, role_name: str, privileges: list | None = None) -> None:
        if self.get_role(role_name):
            raise AlreadyExistsError(f"role already exists: {role_name}")
        self.store.upsert(
            docs.make_id(docs.DOC_ROLE, role_name),
            docs.DOC_ROLE,
            {
                "role_name": role_name,
                "privileges": privileges or [],
                "created_at": docs.now_ms(),
                "updated_at": docs.now_ms(),
            },
        )

    def put_role(self, role: dict[str, Any]) -> None:
        self.store.upsert(docs.make_id(docs.DOC_ROLE, role["role_name"]), docs.DOC_ROLE, role)

    def delete_role(self, role_name: str) -> None:
        self.store.delete(docs.make_id(docs.DOC_ROLE, role_name))

    def list_roles(self) -> list[str]:
        return sorted(d["role_name"] for d in self.store.list_by_type(docs.DOC_ROLE) if "role_name" in d)

    # ---------- import jobs ----------
    def put_import_job(self, job: dict[str, Any]) -> None:
        self.store.upsert(docs.make_id(docs.DOC_IMPORT, job["job_id"]), docs.DOC_IMPORT, job)

    def get_import_job(self, job_id: str) -> dict[str, Any] | None:
        return self.store.get(docs.make_id(docs.DOC_IMPORT, job_id))

    def list_import_jobs(self, db_name: str | None = None, collection_name: str | None = None) -> list[dict[str, Any]]:
        jobs = self.store.list_by_type(docs.DOC_IMPORT)
        if db_name:
            jobs = [j for j in jobs if j.get("db_name") == db_name]
        if collection_name:
            jobs = [j for j in jobs if j.get("collection_name") == collection_name]
        return jobs
