from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

_INDEX_CREATE_EXAMPLE = {
    "collectionName": "demo",
    "fieldName": "vector",
    "indexName": "vector_idx",
    "indexType": "HNSW",
    "metricType": "L2",
    "params": {"M": 16, "efConstruction": 200},
    "dbName": "default",
}


class IndexCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [_INDEX_CREATE_EXAMPLE]},
    )

    collectionName: str
    fieldName: str
    dbName: str = "default"
    indexName: str | None = None
    indexType: str | None = None
    metricType: str | None = None
    params: dict[str, Any] | None = None
    indexParams: dict[str, Any] | list[dict[str, Any]] | None = None

    __example__ = _INDEX_CREATE_EXAMPLE

    @model_validator(mode="after")
    def _require_index_type(self) -> IndexCreateRequest:
        has_type = bool(self.indexType)
        if isinstance(self.indexParams, dict):
            has_type = has_type or bool(
                self.indexParams.get("indexType") or self.indexParams.get("index_type")
            )
        if not has_type and not self.indexParams:
            # allow default FLAT in service; still valid request
            pass
        return self


class IndexDropRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"collectionName": "demo", "indexName": "vector_idx", "dbName": "default"}]
        },
    )

    collectionName: str
    indexName: str
    dbName: str = "default"

    __example__ = {"collectionName": "demo", "indexName": "vector_idx", "dbName": "default"}


class IndexDescribeRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"collectionName": "demo", "indexName": "vector_idx", "dbName": "default"}]
        },
    )

    collectionName: str
    dbName: str = "default"
    indexName: str | None = None

    __example__ = {"collectionName": "demo", "indexName": "vector_idx", "dbName": "default"}


class IndexDescribeItem(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "indexName": "vector_idx",
                    "fieldName": "vector",
                    "indexType": "HNSW",
                    "metricType": "L2",
                    "indexState": "Finished",
                    "params": {"M": 16, "efConstruction": 200},
                }
            ]
        },
    )

    indexName: str | None = None
    fieldName: str | None = None
    indexType: str | None = None
    metricType: str | None = None
    indexState: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    __example__ = {
        "indexName": "vector_idx",
        "fieldName": "vector",
        "indexType": "HNSW",
        "metricType": "L2",
        "indexState": "Finished",
        "params": {"M": 16, "efConstruction": 200},
    }
