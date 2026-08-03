from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DbScopedRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"dbName": "default"}]},
    )

    dbName: str = "default"

    __example__ = {"dbName": "default"}


class CollectionNameRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"collectionName": "demo", "dbName": "default"}]},
    )

    collectionName: str
    dbName: str = "default"

    __example__ = {"collectionName": "demo", "dbName": "default"}


class PartitionNameRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"collectionName": "demo", "partitionName": "p1", "dbName": "default"}]
        },
    )

    collectionName: str
    partitionName: str
    dbName: str = "default"

    __example__ = {"collectionName": "demo", "partitionName": "p1", "dbName": "default"}


class PartitionStatsRequest(BaseModel):
    """get_stats: partitionName defaults to `_default`."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {"collectionName": "demo", "partitionName": "_default", "dbName": "default"}
            ]
        },
    )

    collectionName: str
    partitionName: str = "_default"
    dbName: str = "default"

    __example__ = {"collectionName": "demo", "partitionName": "_default", "dbName": "default"}


class HasData(BaseModel):
    model_config = ConfigDict(extra="ignore", json_schema_extra={"examples": [{"has": True}]})

    has: bool

    __example__ = {"has": True}


class RowCountData(BaseModel):
    # After insert of 2 rows (e2e vector DML); empty collection returns 0.
    model_config = ConfigDict(extra="ignore", json_schema_extra={"examples": [{"rowCount": 2}]})

    rowCount: int

    __example__ = {"rowCount": 2}


class LoadStateData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"state": "LoadStateLoaded", "loadState": "LoadStateLoaded"}]
        },
    )

    state: str
    loadState: str | None = None

    __example__ = {"state": "LoadStateLoaded", "loadState": "LoadStateLoaded"}


class CollectionLoadRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [{"collectionName": "demo", "replicaNumber": 1, "dbName": "default"}]
        },
    )

    collectionName: str
    dbName: str = "default"
    replicaNumber: int = Field(default=1, ge=1)

    __example__ = {"collectionName": "demo", "replicaNumber": 1, "dbName": "default"}
