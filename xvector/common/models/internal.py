from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InternalAuthVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    username: str = ""
    password: str = ""


class InternalAuthVerifyData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool


class InternalCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dbName: str
    collectionName: str
    partitionNames: list[str] | None = None
    fence: bool | None = None


class InternalOkData(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = True
    error: str | None = None
