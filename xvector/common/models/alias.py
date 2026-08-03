from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AliasCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"aliasName": "demo_alias", "collectionName": "demo", "dbName": "default"}]
        },
    )

    aliasName: str
    collectionName: str
    dbName: str = "default"

    __example__ = {"aliasName": "demo_alias", "collectionName": "demo", "dbName": "default"}


class AliasDropRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"aliasName": "demo_alias", "dbName": "default"}]},
    )

    aliasName: str
    dbName: str = "default"

    __example__ = {"aliasName": "demo_alias", "dbName": "default"}


class AliasAlterRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"aliasName": "demo_alias", "collectionName": "demo_v2", "dbName": "default"}]
        },
    )

    aliasName: str
    collectionName: str
    dbName: str = "default"

    __example__ = {"aliasName": "demo_alias", "collectionName": "demo_v2", "dbName": "default"}


class AliasDescribeRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"aliasName": "demo_alias", "dbName": "default"}]},
    )

    aliasName: str
    dbName: str = "default"

    __example__ = {"aliasName": "demo_alias", "dbName": "default"}


class AliasListRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"collectionName": "demo", "dbName": "default"}]},
    )

    dbName: str = "default"
    collectionName: str | None = None

    __example__ = {"collectionName": "demo", "dbName": "default"}


class AliasDescribeData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {"aliasName": "demo_alias", "collectionName": "demo", "dbName": "default"}
            ]
        },
    )

    aliasName: str
    collectionName: str
    dbName: str = "default"

    __example__ = {"aliasName": "demo_alias", "collectionName": "demo", "dbName": "default"}
