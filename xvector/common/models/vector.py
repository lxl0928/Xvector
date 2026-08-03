from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

Entity = dict[str, Any]
SearchHit = dict[str, Any]

_INSERT_EXAMPLE = {
    "collectionName": "demo",
    "dbName": "default",
    "data": [
        {"id": 1, "vector": [1.0, 0.0, 0.0, 0.0], "color": "red"},
        {"id": 2, "vector": [0.9, 0.1, 0.0, 0.0], "color": "blue"},
    ],
}

# Entity / search hit shapes from e2e (tests/e2e/test_vector_dml_search.py, hybrid_search).
# score/distance: present in VectorService search/hybrid paths; exact floats not asserted in e2e.
ENTITY_GET_EXAMPLE = [
    {"id": 1, "vector": [1.0, 0.0, 0.0, 0.0], "color": "red"},
    {"id": 2, "vector": [0.8, 0.2, 0.0, 0.0], "color": "green"},
]
ENTITY_QUERY_EXAMPLE = [
    {"id": 1, "color": "red"},
    {"id": 2, "color": "green"},
]
ENTITY_SEARCH_EXAMPLE = [
    [
        {"id": 1, "color": "red", "score": 0.0, "distance": 0.0},
        {"id": 2, "color": "green", "score": 0.08, "distance": 0.08},
    ]
]
ENTITY_HYBRID_EXAMPLE = [
    [
        {"id": 1, "score": 0.01639, "distance": 0.01639},
        {"id": 2, "score": 0.01613, "distance": 0.01613},
    ]
]


class EntityRow(BaseModel):
    """Dynamic entity / search-hit row (collection schema + outputFields).

    Declared fields mirror common e2e shapes; extra business fields are allowed.
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {"id": 1, "vector": [1.0, 0.0, 0.0, 0.0], "color": "red"},
                {"id": 1, "color": "red", "score": 0.0, "distance": 0.0},
            ]
        },
    )

    id: Any = None
    vector: list[float] | None = None
    color: str | None = None
    score: float | None = None
    distance: float | None = None

    __example__ = {"id": 1, "vector": [1.0, 0.0, 0.0, 0.0], "color": "red"}



class VectorInsertRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [_INSERT_EXAMPLE]},
    )

    collectionName: str
    data: list[dict[str, Any]] | dict[str, Any]
    dbName: str = "default"
    partitionName: str | None = None

    __example__ = _INSERT_EXAMPLE


class VectorUpsertRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [_INSERT_EXAMPLE]},
    )

    collectionName: str
    data: list[dict[str, Any]] | dict[str, Any]
    dbName: str = "default"
    partitionName: str | None = None

    __example__ = _INSERT_EXAMPLE


class VectorDeleteRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "filter": "id in [1]",
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str
    dbName: str = "default"
    id: Any = None
    ids: Any = None
    filter: str | None = None
    expr: str | None = None
    partitionName: str | None = None
    partitionNames: list[str] | None = None

    __example__ = {
        "collectionName": "demo",
        "filter": "id in [1]",
        "dbName": "default",
    }

    @model_validator(mode="after")
    def _require_selector(self) -> VectorDeleteRequest:
        if self.id is None and self.ids is None and not self.filter and not self.expr:
            raise ValueError("id/ids or filter/expr required")
        return self


class VectorGetRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "id": [1, 2],
                    "outputFields": ["id", "vector", "color"],
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str
    id: Any = None
    ids: Any = None
    dbName: str = "default"
    outputFields: list[str] | None = None
    refresh: bool | None = None
    refreshSeconds: int | None = None

    __example__ = {
        "collectionName": "demo",
        "id": [1, 2],
        "outputFields": ["id", "vector", "color"],
        "dbName": "default",
    }

    @model_validator(mode="after")
    def _require_id(self) -> VectorGetRequest:
        if self.id is None and self.ids is None:
            raise ValueError("id or ids required")
        return self


class VectorQueryRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "filter": "id >= 0",
                    "limit": 10,
                    "outputFields": ["id", "color"],
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str
    dbName: str = "default"
    filter: str | None = ""
    expr: str | None = None
    limit: int | None = 100
    topk: int | None = None
    outputFields: list[str] | None = None
    partitionNames: list[str] | None = None
    refresh: bool | None = None
    refreshSeconds: int | None = None

    __example__ = {
        "collectionName": "demo",
        "filter": "id >= 0",
        "limit": 10,
        "outputFields": ["id", "color"],
        "dbName": "default",
    }


class VectorSearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "data": [[1.0, 0.0, 0.0, 0.0]],
                    "annsField": "vector",
                    "limit": 2,
                    "outputFields": ["color"],
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str
    annsField: str
    dbName: str = "default"
    data: list[Any] | None = None
    vectors: list[Any] | None = None
    limit: int = 10
    filter: str | None = None
    expr: str | None = None
    searchParams: dict[str, Any] | None = None
    outputFields: list[str] | None = None
    partitionNames: list[str] | None = None
    refresh: bool | None = None
    refreshSeconds: int | None = None

    __example__ = {
        "collectionName": "demo",
        "data": [[1.0, 0.0, 0.0, 0.0]],
        "annsField": "vector",
        "limit": 2,
        "outputFields": ["color"],
        "dbName": "default",
    }

    @model_validator(mode="after")
    def _require_data(self) -> VectorSearchRequest:
        if self.data is None and self.vectors is None:
            raise ValueError("data or vectors required")
        return self


class HybridSearchSubRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[Any]
    annsField: str
    limit: int | None = None
    filter: str | None = None
    searchParams: dict[str, Any] | None = None


class VectorHybridSearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "dbName": "default",
                    "search": [
                        {"data": [[0.1, 0.2, 0.3, 0.4]], "annsField": "vector", "limit": 10}
                    ],
                    "rerank": {"strategy": "rrf", "params": {"k": 60}},
                    "limit": 10,
                    "outputFields": ["id"],
                }
            ]
        },
    )

    collectionName: str
    search: list[HybridSearchSubRequest | dict[str, Any]]
    dbName: str = "default"
    rerank: dict[str, Any] | None = None
    limit: int = 10
    outputFields: list[str] | None = None
    refresh: bool | None = None
    refreshSeconds: int | None = None

    __example__ = {
        "collectionName": "demo",
        "dbName": "default",
        "search": [{"data": [[0.1, 0.2, 0.3, 0.4]], "annsField": "vector", "limit": 10}],
        "rerank": {"strategy": "rrf", "params": {"k": 60}},
        "limit": 10,
        "outputFields": ["id"],
    }


class VectorInsertData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        # Align with tests/e2e/test_vector_dml_search.py (insertCount == 2).
        json_schema_extra={"examples": [{"insertCount": 2, "insertIds": [1, 2]}]},
    )

    insertCount: int
    insertIds: list[Any] = Field(default_factory=list)

    __example__ = {"insertCount": 2, "insertIds": [1, 2]}


class VectorUpsertData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"upsertCount": 1, "upsertIds": [2]}]},
    )

    upsertCount: int
    upsertIds: list[Any] = Field(default_factory=list)

    __example__ = {"upsertCount": 1, "upsertIds": [2]}


class VectorDeleteData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"deleteCount": 1}]},
    )

    deleteCount: int

    __example__ = {"deleteCount": 1}
