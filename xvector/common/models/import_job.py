from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ImportCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "collectionName": "demo",
                    "files": ["/data/imports/demo.json"],
                    "format": "json",
                    "dbName": "default",
                }
            ]
        },
    )

    collectionName: str
    files: list[str]
    dbName: str = "default"
    format: str = "json"
    partitionName: str | None = None

    __example__ = {
        "collectionName": "demo",
        "files": ["/data/imports/demo.json"],
        "format": "json",
        "dbName": "default",
    }


class ImportProgressRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"jobId": "00000000-0000-0000-0000-000000000001"}]},
    )

    jobId: str

    __example__ = {"jobId": "00000000-0000-0000-0000-000000000001"}


class ImportListRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"dbName": "default", "collectionName": "demo"}]},
    )

    dbName: str | None = None
    collectionName: str | None = None

    __example__ = {"dbName": "default", "collectionName": "demo"}


class ImportCreateData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"jobId": "00000000-0000-0000-0000-000000000001"}]},
    )

    jobId: str

    __example__ = {"jobId": "00000000-0000-0000-0000-000000000001"}


class ImportProgressData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "jobId": "00000000-0000-0000-0000-000000000001",
                    "state": "Completed",
                    "progress": 100,
                    "importedRows": 2,
                    "totalRows": 2,
                    "reason": "",
                }
            ]
        },
    )

    jobId: str
    state: str
    progress: int = 0
    importedRows: int = 0
    totalRows: int = 0
    reason: str = ""

    # Align with tests/e2e/test_import.py (2-row jsonl → state Completed).
    __example__ = {
        "jobId": "00000000-0000-0000-0000-000000000001",
        "state": "Completed",
        "progress": 100,
        "importedRows": 2,
        "totalRows": 2,
        "reason": "",
    }


class ImportListItem(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "jobId": "00000000-0000-0000-0000-000000000001",
                    "collectionName": "demo",
                    "state": "Completed",
                    "progress": 100,
                }
            ]
        },
    )

    jobId: str
    collectionName: str | None = None
    state: str | None = None
    progress: int = 0

    __example__ = {
        "jobId": "00000000-0000-0000-0000-000000000001",
        "collectionName": "demo",
        "state": "Completed",
        "progress": 100,
    }
