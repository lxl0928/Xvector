from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

_COLLECTION_CREATE_EXAMPLE = {
    "dbName": "default",
    "collectionName": "demo",
    "schema": {
        "autoID": False,
        "enableDynamicField": False,
        "fields": [
            {"name": "id", "dataType": "Int64", "isPrimaryKey": True, "autoID": False},
            {"name": "vector", "dataType": "FloatVector", "dim": 8},
        ],
    },
}


class SchemaField(BaseModel):
    """Collection schema field — camelCase only (no data_type / is_primary_key)."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    fieldName: str | None = None
    dataType: Any = None
    type: Any = None
    isPrimaryKey: bool = False
    isPrimary: bool = False
    autoID: bool = False
    dim: int | None = None
    dimension: int | None = None
    nullable: bool | None = None
    metricType: str | None = None
    params: Any = None
    typeParams: Any = None
    elementTypeParams: Any = None

    __example__ = {
        "name": "id",
        "dataType": "Int64",
        "isPrimaryKey": True,
        "autoID": False,
    }

    @model_validator(mode="after")
    def _require_name_and_dtype(self) -> SchemaField:
        if not (self.name or self.fieldName):
            raise ValueError("name or fieldName required")
        if self.dataType is None and self.type is None:
            raise ValueError("dataType required")
        return self


class CollectionSchema(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [_COLLECTION_CREATE_EXAMPLE["schema"]]},
    )

    fields: list[SchemaField]
    autoID: bool = False
    enableDynamicField: bool = False
    description: str | None = None
    functions: list[Any] | None = None

    __example__ = _COLLECTION_CREATE_EXAMPLE["schema"]


class CollectionCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={"examples": [_COLLECTION_CREATE_EXAMPLE]},
    )

    collectionName: str
    collectionSchema: CollectionSchema = Field(alias="schema")
    dbName: str = "default"
    enableDynamicField: bool | None = None
    shardsNum: int | None = None
    consistencyLevel: str | None = None
    properties: dict[str, Any] | None = None
    description: str | None = None
    autoID: bool | None = None

    __example__ = _COLLECTION_CREATE_EXAMPLE

    def model_dump(self, **kwargs):  # type: ignore[override]
        # Always emit JSON key `schema` for services / OpenAPI clients.
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


class CollectionRenameRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "newCollectionName": "demo_v2",
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str = Field(validation_alias=AliasChoices("collectionName", "oldName"))
    newCollectionName: str = Field(validation_alias=AliasChoices("newCollectionName", "newName"))
    dbName: str = "default"

    __example__ = {
        "collectionName": "demo",
        "newCollectionName": "demo_v2",
        "dbName": "default",
    }


class CollectionIndexSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fieldName: str | None = None
    indexName: str | None = None
    indexType: str | None = None
    metricType: str | None = None


class CollectionDescribeData(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "dbName": "default",
                    "schema": _COLLECTION_CREATE_EXAMPLE["schema"],
                    "shardsNum": 1,
                    "consistencyLevel": "Eventually",
                    "indexes": [
                        {
                            "fieldName": "vector",
                            "indexName": "vector_idx",
                            "indexType": "HNSW",
                            "metricType": "L2",
                        }
                    ],
                    "autoId": False,
                }
            ]
        },
    )

    collectionName: str
    dbName: str = "default"
    collectionSchema: dict[str, Any] | None = Field(default=None, alias="schema")
    shardsNum: int = 1
    consistencyLevel: str = "Eventually"
    indexes: list[CollectionIndexSummary] = Field(default_factory=list)
    autoId: bool = False

    __example__ = {
        "collectionName": "demo",
        "dbName": "default",
        "schema": _COLLECTION_CREATE_EXAMPLE["schema"],
        "shardsNum": 1,
        "consistencyLevel": "Eventually",
        "indexes": [
            {
                "fieldName": "vector",
                "indexName": "vector_idx",
                "indexType": "HNSW",
                "metricType": "L2",
            }
        ],
        "autoId": False,
    }
