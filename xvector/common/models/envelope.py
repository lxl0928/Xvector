from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

# Documented Gateway-injected request id (optional on Writer/Reader responses).
REQUEST_ID_EXAMPLE = "xv-0123456789abcdef0123456789abcdef"


def envelope_example(data: Any) -> dict[str, Any]:
    """Build a success envelope example for OpenAPI / `__example__`."""
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "requestId": REQUEST_ID_EXAMPLE,
    }


class EmptyObject(BaseModel):
    """Empty success `data` object `{}`."""

    model_config = ConfigDict(extra="allow", json_schema_extra={"examples": [{}]})

    __example__ = {}


class EmptyRequest(BaseModel):
    """Optional / empty JSON body (list endpoints)."""

    model_config = ConfigDict(extra="ignore", json_schema_extra={"examples": [{}]})

    dbName: str | None = None

    __example__ = {}


class ApiResponse(BaseModel, Generic[T]):
    """Unified success envelope. `requestId` optional (Gateway injects)."""

    model_config = ConfigDict(extra="ignore")

    code: int = 0
    message: str = "success"
    data: T
    requestId: str | None = None

    __example__ = {
        "code": 0,
        "message": "success",
        "data": {},
        "requestId": REQUEST_ID_EXAMPLE,
    }


def make_api_response(name: str, data_type: Any, data_example: Any) -> type[ApiResponse]:
    """Concrete `ApiResponse[T]` subclass with schema-level examples (visible in /docs)."""
    example = envelope_example(data_example)
    return type(
        name,
        (ApiResponse[data_type],),
        {
            "model_config": ConfigDict(
                extra="ignore",
                json_schema_extra={"examples": [example]},
            ),
            "__example__": example,
            "__doc__": f"Success envelope for `{name}` (code/message/data; requestId via Gateway).",
        },
    )


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "code": 100,
                    "message": "request validation error",
                    "requestId": REQUEST_ID_EXAMPLE,
                }
            ]
        },
    )

    code: int
    message: str
    requestId: str | None = None

    __example__ = {
        "code": 100,
        "message": "request validation error",
        "requestId": REQUEST_ID_EXAMPLE,
    }


class InternalErrorResponse(ErrorResponse):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "code": 2000,
                    "message": "Internal Error: boom",
                    "error_message": "boom",
                    "requestId": REQUEST_ID_EXAMPLE,
                }
            ]
        },
    )

    # Keep snake_case to match existing `internal_error_body` contract.
    error_message: str = Field(
        ...,
        description="Raw error detail (HTTP 500). Kept as error_message for compatibility.",
    )

    __example__ = {
        "code": 2000,
        "message": "Internal Error: boom",
        "error_message": "boom",
        "requestId": REQUEST_ID_EXAMPLE,
    }


def dump_body(model: BaseModel | None) -> dict[str, Any]:
    """Serialize request model to camelCase dict for services."""
    if model is None:
        return {}
    return model.model_dump(exclude_none=True, by_alias=True)
