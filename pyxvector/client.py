from __future__ import annotations

import time
from typing import Any

from pyxvector.http import HttpClient


class XvectorClient:
    def __init__(self, uri: str = "http://localhost:19530", token: str = "root:Xvector", timeout: float = 60.0):
        self._http = HttpClient(uri=uri, token=token, timeout=timeout)
        self._db = "default"

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "XvectorClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def using_database(self, db_name: str) -> "XvectorClient":
        self._db = db_name
        return self

    def _with_db(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = dict(body or {})
        body.setdefault("dbName", self._db)
        return body

    def _post(self, path: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None):
        return self._http.request("POST", path, json=self._with_db(body), headers=headers)

    # Database
    def create_database(self, db_name: str):
        return self._post("/v2/vectordb/databases/create", {"dbName": db_name})

    def drop_database(self, db_name: str):
        return self._post("/v2/vectordb/databases/drop", {"dbName": db_name})

    def list_databases(self):
        return self._post("/v2/vectordb/databases/list", {})

    def describe_database(self, db_name: str | None = None):
        return self._post("/v2/vectordb/databases/describe", {"dbName": db_name or self._db})

    # User
    def create_user(self, user_name: str, password: str):
        return self._post("/v2/vectordb/users/create", {"userName": user_name, "password": password})

    def drop_user(self, user_name: str):
        return self._post("/v2/vectordb/users/drop", {"userName": user_name})

    def list_users(self):
        return self._post("/v2/vectordb/users/list", {})

    def describe_user(self, user_name: str):
        return self._post("/v2/vectordb/users/describe", {"userName": user_name})

    def update_password(self, user_name: str, old_password: str, new_password: str):
        return self._post(
            "/v2/vectordb/users/update_password",
            {"userName": user_name, "password": old_password, "newPassword": new_password},
        )

    def grant_role(self, user_name: str, role_name: str):
        return self._post("/v2/vectordb/users/grant_role", {"userName": user_name, "roleName": role_name})

    def revoke_role(self, user_name: str, role_name: str):
        return self._post("/v2/vectordb/users/revoke_role", {"userName": user_name, "roleName": role_name})

    # Role
    def create_role(self, role_name: str):
        return self._post("/v2/vectordb/roles/create", {"roleName": role_name})

    def drop_role(self, role_name: str):
        return self._post("/v2/vectordb/roles/drop", {"roleName": role_name})

    def list_roles(self):
        return self._post("/v2/vectordb/roles/list", {})

    def describe_role(self, role_name: str):
        return self._post("/v2/vectordb/roles/describe", {"roleName": role_name})

    def grant_privilege(self, role_name: str, object_type: str, object_name: str, privilege: str):
        return self._post(
            "/v2/vectordb/roles/grant_privilege",
            {
                "roleName": role_name,
                "objectType": object_type,
                "objectName": object_name,
                "privilege": privilege,
            },
        )

    def revoke_privilege(self, role_name: str, object_type: str, object_name: str, privilege: str):
        return self._post(
            "/v2/vectordb/roles/revoke_privilege",
            {
                "roleName": role_name,
                "objectType": object_type,
                "objectName": object_name,
                "privilege": privilege,
            },
        )

    # Collection
    def create_collection(self, collection_name: str, schema: dict[str, Any] | None = None, **kwargs):
        body = {"collectionName": collection_name, **kwargs}
        if schema is not None:
            body["schema"] = schema
        return self._post("/v2/vectordb/collections/create", body)

    def drop_collection(self, collection_name: str):
        return self._post("/v2/vectordb/collections/drop", {"collectionName": collection_name})

    def describe_collection(self, collection_name: str):
        return self._post("/v2/vectordb/collections/describe", {"collectionName": collection_name})

    def has_collection(self, collection_name: str):
        return self._post("/v2/vectordb/collections/has", {"collectionName": collection_name})

    def list_collections(self):
        return self._post("/v2/vectordb/collections/list", {})

    def rename_collection(self, collection_name: str, new_collection_name: str):
        return self._post(
            "/v2/vectordb/collections/rename",
            {"collectionName": collection_name, "newCollectionName": new_collection_name},
        )

    def load_collection(self, collection_name: str, replica_number: int = 1):
        return self._post(
            "/v2/vectordb/collections/load",
            {"collectionName": collection_name, "replicaNumber": replica_number},
        )

    def release_collection(self, collection_name: str):
        return self._post("/v2/vectordb/collections/release", {"collectionName": collection_name})

    def get_load_state(self, collection_name: str):
        return self._post("/v2/vectordb/collections/get_load_state", {"collectionName": collection_name})

    def get_collection_stats(self, collection_name: str):
        return self._post("/v2/vectordb/collections/get_stats", {"collectionName": collection_name})

    # Partition
    def create_partition(self, collection_name: str, partition_name: str):
        return self._post(
            "/v2/vectordb/partitions/create",
            {"collectionName": collection_name, "partitionName": partition_name},
        )

    def drop_partition(self, collection_name: str, partition_name: str):
        return self._post(
            "/v2/vectordb/partitions/drop",
            {"collectionName": collection_name, "partitionName": partition_name},
        )

    def has_partition(self, collection_name: str, partition_name: str):
        return self._post(
            "/v2/vectordb/partitions/has",
            {"collectionName": collection_name, "partitionName": partition_name},
        )

    def list_partitions(self, collection_name: str):
        return self._post("/v2/vectordb/partitions/list", {"collectionName": collection_name})

    def load_partitions(self, collection_name: str, partition_names: list[str]):
        return self._post(
            "/v2/vectordb/partitions/load",
            {"collectionName": collection_name, "partitionNames": partition_names},
        )

    def release_partitions(self, collection_name: str, partition_names: list[str]):
        return self._post(
            "/v2/vectordb/partitions/release",
            {"collectionName": collection_name, "partitionNames": partition_names},
        )

    def get_partition_stats(self, collection_name: str, partition_name: str):
        return self._post(
            "/v2/vectordb/partitions/get_stats",
            {"collectionName": collection_name, "partitionName": partition_name},
        )

    # Index
    def create_index(
        self,
        collection_name: str,
        field_name: str,
        index_name: str | None = None,
        index_type: str = "FLAT",
        metric_type: str = "L2",
        params: dict[str, Any] | None = None,
    ):
        return self._post(
            "/v2/vectordb/indexes/create",
            {
                "collectionName": collection_name,
                "fieldName": field_name,
                "indexName": index_name or f"{field_name}_idx",
                "indexType": index_type,
                "metricType": metric_type,
                "params": params or {},
            },
        )

    def describe_index(self, collection_name: str, index_name: str | None = None):
        body: dict[str, Any] = {"collectionName": collection_name}
        if index_name:
            body["indexName"] = index_name
        return self._post("/v2/vectordb/indexes/describe", body)

    def drop_index(self, collection_name: str, index_name: str):
        return self._post(
            "/v2/vectordb/indexes/drop",
            {"collectionName": collection_name, "indexName": index_name},
        )

    def list_indexes(self, collection_name: str):
        return self._post("/v2/vectordb/indexes/list", {"collectionName": collection_name})

    # Alias
    def create_alias(self, collection_name: str, alias: str):
        return self._post(
            "/v2/vectordb/aliases/create",
            {"collectionName": collection_name, "aliasName": alias},
        )

    def drop_alias(self, alias: str):
        return self._post("/v2/vectordb/aliases/drop", {"aliasName": alias})

    def alter_alias(self, collection_name: str, alias: str):
        return self._post(
            "/v2/vectordb/aliases/alter",
            {"collectionName": collection_name, "aliasName": alias},
        )

    def describe_alias(self, alias: str):
        return self._post("/v2/vectordb/aliases/describe", {"aliasName": alias})

    def list_aliases(self, collection_name: str | None = None):
        body: dict[str, Any] = {}
        if collection_name:
            body["collectionName"] = collection_name
        return self._post("/v2/vectordb/aliases/list", body)

    # Vector
    def insert(self, collection_name: str, data: list[dict[str, Any]] | dict[str, Any], partition_name: str | None = None):
        body: dict[str, Any] = {"collectionName": collection_name, "data": data}
        if partition_name:
            body["partitionName"] = partition_name
        return self._post("/v2/vectordb/entities/insert", body)

    def upsert(self, collection_name: str, data: list[dict[str, Any]] | dict[str, Any], partition_name: str | None = None):
        body: dict[str, Any] = {"collectionName": collection_name, "data": data}
        if partition_name:
            body["partitionName"] = partition_name
        return self._post("/v2/vectordb/entities/upsert", body)

    def delete(self, collection_name: str, filter: str | None = None, ids: Any = None, partition_name: str | None = None):
        body: dict[str, Any] = {"collectionName": collection_name}
        if filter is not None:
            body["filter"] = filter
        if ids is not None:
            body["id"] = ids
        if partition_name:
            body["partitionName"] = partition_name
        return self._post("/v2/vectordb/entities/delete", body)

    def get(self, collection_name: str, ids: Any, output_fields: list[str] | None = None, refresh: bool = False):
        body: dict[str, Any] = {"collectionName": collection_name, "id": ids}
        if output_fields:
            body["outputFields"] = output_fields
        headers = {"X-XVector-Refresh": "true"} if refresh else None
        return self._post("/v2/vectordb/entities/get", body, headers=headers)

    def query(
        self,
        collection_name: str,
        filter: str = "",
        output_fields: list[str] | None = None,
        limit: int = 100,
        refresh: bool = False,
        partition_names: list[str] | None = None,
    ):
        body: dict[str, Any] = {"collectionName": collection_name, "filter": filter, "limit": limit}
        if output_fields:
            body["outputFields"] = output_fields
        if partition_names:
            body["partitionNames"] = partition_names
        headers = {"X-XVector-Refresh": "true"} if refresh else None
        return self._post("/v2/vectordb/entities/query", body, headers=headers)

    def search(
        self,
        collection_name: str,
        data: list[list[float]],
        anns_field: str,
        limit: int = 10,
        filter: str | None = None,
        output_fields: list[str] | None = None,
        search_params: dict[str, Any] | None = None,
        refresh: bool = False,
        partition_names: list[str] | None = None,
    ):
        body: dict[str, Any] = {
            "collectionName": collection_name,
            "data": data,
            "annsField": anns_field,
            "limit": limit,
        }
        if filter:
            body["filter"] = filter
        if output_fields:
            body["outputFields"] = output_fields
        if search_params:
            body["searchParams"] = search_params
        if partition_names:
            body["partitionNames"] = partition_names
        headers = {"X-XVector-Refresh": "true"} if refresh else None
        return self._post("/v2/vectordb/entities/search", body, headers=headers)

    def hybrid_search(
        self,
        collection_name: str,
        search: list[dict[str, Any]],
        rerank: dict[str, Any] | None = None,
        limit: int = 10,
        output_fields: list[str] | None = None,
        refresh: bool = False,
    ):
        body: dict[str, Any] = {
            "collectionName": collection_name,
            "search": search,
            "limit": limit,
            "rerank": rerank or {"strategy": "rrf", "params": {"k": 60}},
        }
        if output_fields:
            body["outputFields"] = output_fields
        headers = {"X-XVector-Refresh": "true"} if refresh else None
        return self._post("/v2/vectordb/entities/hybrid_search", body, headers=headers)

    # Import
    def create_import_job(self, collection_name: str, files: list[str], format: str = "json", partition_name: str | None = None):
        body: dict[str, Any] = {"collectionName": collection_name, "files": files, "format": format}
        if partition_name:
            body["partitionName"] = partition_name
        return self._post("/v2/vectordb/jobs/import/create", body)

    def get_import_progress(self, job_id: str):
        return self._post("/v2/vectordb/jobs/import/get_progress", {"jobId": job_id})

    def list_import_jobs(self, collection_name: str | None = None):
        body: dict[str, Any] = {}
        if collection_name:
            body["collectionName"] = collection_name
        return self._post("/v2/vectordb/jobs/import/list", body)

    # Helpers
    def wait_loaded(self, collection_name: str, timeout: float = 30.0):
        start = time.time()
        while time.time() - start < timeout:
            st = self.get_load_state(collection_name)
            state = st.get("state") or st.get("loadState") or ""
            if "Loaded" in str(state):
                return st
            time.sleep(0.5)
        raise TimeoutError(f"collection not loaded: {collection_name}")

    def wait_import_complete(self, job_id: str, timeout: float = 120.0):
        start = time.time()
        while time.time() - start < timeout:
            prog = self.get_import_progress(job_id)
            if prog.get("state") == "Completed":
                return prog
            if prog.get("state") == "Failed":
                raise RuntimeError(prog.get("reason") or "import failed")
            time.sleep(0.5)
        raise TimeoutError(f"import not complete: {job_id}")

    def search_after_write(self, *args, refresh: bool = True, **kwargs):
        return self.search(*args, refresh=refresh, **kwargs)
