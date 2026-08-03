from __future__ import annotations

from typing import Any


class XvectorError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 200):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


def ok(data: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": 0, "message": "success"}
    if data is not None:
        body["data"] = data
    else:
        body["data"] = {}
    return body


# Common codes (DESIGN appendix B + Milvus-ish)
CODE_PARAM = 100
CODE_NOT_FOUND = 1001
CODE_NOT_LOADED = 1200
CODE_UNAUTHORIZED = 1800
CODE_INTERNAL = 2000
CODE_INDEX_UNSUPPORTED = 2100
CODE_IMPORT_FAILED = 2200
CODE_ALREADY_EXISTS = 65535
CODE_FORBIDDEN = 1801


def internal_error_body(error_message: str) -> dict[str, Any]:
    """Stable JSON body for unhandled failures (HTTP 500)."""
    msg = (error_message or "unknown error").strip() or "unknown error"
    return {
        "code": CODE_INTERNAL,
        "message": f"Internal Error: {msg}",
        "error_message": msg,
    }


class ParamError(XvectorError):
    def __init__(self, message: str):
        super().__init__(CODE_PARAM, message)


class NotFoundError(XvectorError):
    def __init__(self, message: str):
        super().__init__(CODE_NOT_FOUND, message)


class NotLoadedError(XvectorError):
    def __init__(self, message: str = "collection not loaded"):
        super().__init__(CODE_NOT_LOADED, message)


class UnauthorizedError(XvectorError):
    def __init__(self, message: str = "unauthorized"):
        super().__init__(CODE_UNAUTHORIZED, message, http_status=401)


class InternalError(XvectorError):
    def __init__(self, message: str = "internal error"):
        super().__init__(CODE_INTERNAL, message)


class IndexUnsupportedError(XvectorError):
    def __init__(self, message: str):
        super().__init__(CODE_INDEX_UNSUPPORTED, message)


class ImportFailedError(XvectorError):
    def __init__(self, message: str):
        super().__init__(CODE_IMPORT_FAILED, message)


class AlreadyExistsError(XvectorError):
    def __init__(self, message: str):
        super().__init__(CODE_ALREADY_EXISTS, message)
