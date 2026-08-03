from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RoleNameRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"roleName": "data_admin"}]},
    )

    roleName: str

    __example__ = {"roleName": "data_admin"}


class RolePrivilegeRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "roleName": "data_admin",
                    "objectType": "Collection",
                    "objectName": "demo",
                    "privilege": "Insert",
                }
            ]
        },
    )

    roleName: str
    objectType: str
    objectName: str
    privilege: str

    __example__ = {
        "roleName": "data_admin",
        "objectType": "Collection",
        "objectName": "demo",
        "privilege": "Insert",
    }


class RolePrivilegeItem(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {"objectType": "Collection", "objectName": "demo", "privilege": "Insert"}
            ]
        },
    )

    objectType: str
    objectName: str
    privilege: str

    __example__ = {"objectType": "Collection", "objectName": "demo", "privilege": "Insert"}


class RoleDescribeData(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "roleName": "data_admin",
                    "privileges": [
                        {
                            "objectType": "Collection",
                            "objectName": "*",
                            "privilege": "Search",
                        }
                    ],
                }
            ]
        },
    )

    roleName: str
    privileges: list[RolePrivilegeItem] = Field(default_factory=list)

    # Align with tests/e2e/test_user_role.py grant_privilege(..., "*", "Search").
    __example__ = {
        "roleName": "data_admin",
        "privileges": [
            {"objectType": "Collection", "objectName": "*", "privilege": "Search"}
        ],
    }
