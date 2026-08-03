from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class DatabaseCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"dbName": "demo_db"}]},
    )

    dbName: str

    __example__ = {"dbName": "demo_db"}


class DatabaseDropRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"dbName": "demo_db"}]},
    )

    dbName: str

    __example__ = {"dbName": "demo_db"}


class DatabaseDescribeRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"dbName": "default"}]},
    )

    dbName: str = "default"

    __example__ = {"dbName": "default"}


class DatabaseDescribeData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"dbName": "default", "properties": {}}]},
    )

    dbName: str
    properties: dict[str, Any] = {}

    __example__ = {"dbName": "default", "properties": {}}
