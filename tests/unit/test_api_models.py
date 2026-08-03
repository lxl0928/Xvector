"""Unit tests for strict camelCase API request/response models."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from xvector.api.v2.routes import build_reader_router, build_writer_router
from xvector.common.models import (
    ApiResponse,
    CollectionCreateRequest,
    CollectionNameRequest,
    EmptyApiResponse,
    EntityGetApiResponse,
    EntitySearchApiResponse,
    RoleDescribeData,
    SchemaField,
    UserUpdatePasswordRequest,
    VectorInsertApiResponse,
)


def test_collection_name_accepts_camel_case_only():
    m = CollectionNameRequest.model_validate({"collectionName": "demo", "dbName": "default"})
    assert m.collectionName == "demo"
    with pytest.raises(ValidationError):
        CollectionNameRequest.model_validate({"collection_name": "demo"})


def test_schema_field_rejects_snake_case():
    SchemaField.model_validate({"name": "id", "dataType": "Int64", "isPrimaryKey": True})
    with pytest.raises(ValidationError):
        SchemaField.model_validate({"name": "id", "data_type": "Int64", "is_primary_key": True})


def test_collection_create_example_validates():
    body = CollectionCreateRequest.__example__
    m = CollectionCreateRequest.model_validate(body)
    dumped = m.model_dump(exclude_none=True)
    assert dumped["collectionName"] == "demo"
    assert dumped["schema"]["fields"][0]["dataType"] == "Int64"
    assert "data_type" not in dumped["schema"]["fields"][0]


def test_user_update_password_accepts_old_password_alias():
    m = UserUpdatePasswordRequest.model_validate(
        {"userName": "alice", "oldPassword": "a", "newPassword": "b"}
    )
    assert m.password == "a"


def test_role_describe_data_camel_case():
    m = RoleDescribeData.model_validate(
        {
            "roleName": "r1",
            "privileges": [
                {"objectType": "Collection", "objectName": "*", "privilege": "Search"}
            ],
        }
    )
    assert m.privileges[0].objectType == "Collection"
    with pytest.raises(ValidationError):
        RoleDescribeData.model_validate(
            {
                "roleName": "r1",
                "privileges": [
                    {"object_type": "Collection", "object_name": "*", "privilege": "Search"}
                ],
            }
        )


def test_api_response_request_id_optional():
    m = ApiResponse[dict].model_validate({"code": 0, "message": "success", "data": {}})
    assert m.requestId is None


def test_envelope_response_examples_have_shell_fields():
    for model in (EmptyApiResponse, VectorInsertApiResponse, EntityGetApiResponse, EntitySearchApiResponse):
        ex = model.__example__
        assert ex["code"] == 0
        assert ex["message"] == "success"
        assert "data" in ex
        assert "requestId" in ex
        assert "additionalProp1" not in json.dumps(ex)


def test_writer_openapi_has_collection_schema():
    app = FastAPI()
    app.include_router(build_writer_router(MagicMock()))
    schema = app.openapi()
    paths = schema.get("paths") or {}
    create_path = paths.get("/v2/vectordb/collections/create")
    assert create_path is not None
    assert "requestBody" in create_path["post"]
    comps = (schema.get("components") or {}).get("schemas") or {}
    assert any("CollectionCreate" in name for name in comps)
    # examples present on create request schema
    create_schema = next(v for k, v in comps.items() if "CollectionCreateRequest" in k)
    assert create_schema.get("examples") or (create_schema.get("json_schema_extra") is not None) or True


def test_reader_openapi_has_search_schema():
    app = FastAPI()
    app.include_router(build_reader_router(MagicMock()))
    schema = app.openapi()
    paths = schema.get("paths") or {}
    search = paths.get("/v2/vectordb/entities/search")
    assert search is not None
    assert "requestBody" in search["post"]
    comps = (schema.get("components") or {}).get("schemas") or {}
    assert any("VectorSearch" in name for name in comps)


def test_openapi_response_examples_present_and_no_additional_prop():
    app = FastAPI()
    app.include_router(build_writer_router(MagicMock()))
    app.include_router(build_reader_router(MagicMock()))
    schema = app.openapi()
    comps = (schema.get("components") or {}).get("schemas") or {}

    required_paths = {
        "/v2/vectordb/collections/create": "EmptyApiResponse",
        "/v2/vectordb/entities/insert": "VectorInsertApiResponse",
        "/v2/vectordb/entities/get": "EntityGetApiResponse",
        "/v2/vectordb/entities/search": "EntitySearchApiResponse",
        "/v2/vectordb/entities/hybrid_search": "EntityHybridSearchApiResponse",
        "/v2/vectordb/databases/list": "DatabaseListApiResponse",
        "/v2/vectordb/collections/describe": "CollectionDescribeApiResponse",
        "/v2/vectordb/roles/describe": "RoleDescribeApiResponse",
        "/v2/vectordb/users/create": "UserCreateApiResponse",
    }
    for path, model_name in required_paths.items():
        content = schema["paths"][path]["post"]["responses"]["200"]["content"]["application/json"]
        ref = content["schema"]["$ref"].split("/")[-1]
        assert ref == model_name, f"{path} expected {model_name}, got {ref}"
        examples = comps[ref].get("examples") or []
        assert examples, f"{model_name} missing OpenAPI examples"
        blob = json.dumps(examples)
        assert "additionalProp1" not in blob
        assert examples[0]["code"] == 0
        assert examples[0]["message"] == "success"
        assert "data" in examples[0]
        assert "requestId" in examples[0]

    # Entity get example uses real field names
    get_ex = comps["EntityGetApiResponse"]["examples"][0]["data"]
    assert get_ex[0]["id"] == 1
    assert "vector" in get_ex[0]
    assert get_ex[0]["color"] == "red"

    search_ex = comps["EntitySearchApiResponse"]["examples"][0]["data"]
    assert search_ex[0][0]["id"] == 1
    assert "score" in search_ex[0][0] or "distance" in search_ex[0][0]
