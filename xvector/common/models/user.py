from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"userName": "alice", "password": "Passw0rd!"}]},
    )

    userName: str
    password: str

    __example__ = {"userName": "alice", "password": "Passw0rd!"}


class UserNameRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"userName": "alice"}]},
    )

    userName: str

    __example__ = {"userName": "alice"}


class UserUpdatePasswordRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "userName": "alice",
                    "password": "Passw0rd!",
                    "newPassword": "N3wPassw0rd!",
                }
            ]
        },
    )

    userName: str
    password: str = Field(validation_alias=AliasChoices("password", "oldPassword"))
    newPassword: str

    __example__ = {
        "userName": "alice",
        "password": "Passw0rd!",
        "newPassword": "N3wPassw0rd!",
    }


class UserRoleRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"userName": "alice", "roleName": "data_admin"}]},
    )

    userName: str
    roleName: str

    __example__ = {"userName": "alice", "roleName": "data_admin"}


class UserCreateData(BaseModel):
    """Keep `username` key for backward compatibility with existing service/e2e."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"username": "alice"}]},
    )

    username: str

    __example__ = {"username": "alice"}


class UserDescribeData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"userName": "alice", "roles": ["data_admin"]}]},
    )

    userName: str
    roles: list[str] = Field(default_factory=list)

    __example__ = {"userName": "alice", "roles": ["data_admin"]}
