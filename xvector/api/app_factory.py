from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from xvector.api.middleware.trace_access import TraceAccessMiddleware
from xvector.common.errors import (
    CODE_INTERNAL,
    CODE_PARAM,
    CODE_UNAUTHORIZED,
    XvectorError,
    internal_error_body,
    ok,
)
from xvector.common.paths import DataPaths
from xvector.config import Settings, get_settings
from xvector.engine.collection_mgr import CollectionManager
from xvector.meta.catalog import Catalog
from xvector.meta.store import MetaNotReadyError, MetaStore
from xvector.services.context import AppContext

logger = logging.getLogger(__name__)

try:
    from fastapi.responses import ORJSONResponse as DefaultResponse
except Exception:  # noqa: BLE001
    DefaultResponse = JSONResponse


def build_context(settings: Settings | None = None, role: str | None = None) -> AppContext:
    settings = settings or get_settings()
    role = role or settings.role
    paths = DataPaths(settings.data_dir)
    paths.ensure_layout()
    read_only_meta = role == "reader"
    meta = MetaStore(paths, read_only=read_only_meta)
    # Writer always creates/opens meta for write; reader opens read-only when ready.
    if role == "writer":
        meta.open()
        catalog = Catalog(meta)
        catalog.ensure_defaults(settings.username, settings.password)
        # Publish after bootstrap so reader can become ready without touching zvec LOCK.
        meta.publish_snapshot()
        logger.info("writer published meta snapshot at %s", paths.meta_snapshot)
    elif role == "reader":
        try:
            meta.open()
        except MetaNotReadyError:
            # Writer may not have published snapshot yet; refresh loop / readyz will retry.
            logger.warning("reader meta snapshot not ready yet; waiting for writer")
        catalog = Catalog(meta)
    else:
        # gateway does not open zvec meta
        catalog = Catalog(meta)
    collections = CollectionManager(paths, read_only=(role == "reader"))
    return AppContext(
        settings=settings,
        paths=paths,
        meta=meta,
        catalog=catalog,
        collections=collections,
        role=role,
    )


def _http_exception_code(status_code: int) -> int:
    if status_code == 401:
        return CODE_UNAUTHORIZED
    if status_code >= 500:
        return CODE_INTERNAL
    return CODE_PARAM


def register_exception_handlers(app: FastAPI) -> None:
    """Register process-safe handlers so unhandled errors become JSON 500, not ASGI crashes."""

    @app.exception_handler(XvectorError)
    async def _xvector_error_handler(_: Request, exc: XvectorError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "message" in detail:
            content = detail
        else:
            message = detail if isinstance(detail, str) else str(detail)
            content = {"code": _http_exception_code(exc.status_code), "message": message}
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": CODE_PARAM, "message": f"request validation error: {exc.errors()}"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        # Full traceback for ops; client only gets a stable JSON body.
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(status_code=500, content=internal_error_body(str(exc)))


def create_base_app(
    title: str,
    *,
    docs_url: str | None = "/docs",
    redoc_url: str | None = None,
    openapi_url: str | None = "/openapi.json",
    inject_request_id: bool = False,
    access_log_enabled: bool | None = None,
) -> FastAPI:
    settings = get_settings()
    if access_log_enabled is None:
        access_log_enabled = settings.access_log_enabled

    app = FastAPI(
        title=title,
        default_response_class=DefaultResponse,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    register_exception_handlers(app)

    # Inner: catch escaped errors (added first).
    @app.middleware("http")
    async def _catch_escaped_errors(request: Request, call_next):
        # Belt-and-suspenders: if anything escapes ExceptionMiddleware mid-stack, still respond.
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001
            logger.exception("middleware caught unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content=internal_error_body(str(exc)))

    # Outer: trace + access log (+ Gateway requestId injection). Last added = outermost.
    app.add_middleware(
        TraceAccessMiddleware,
        inject_request_id=inject_request_id,
        access_log_enabled=access_log_enabled,
    )

    return app


def parse_refresh_flags(request: Request, body: dict[str, Any] | None = None) -> bool:
    header = request.headers.get("X-XVector-Refresh")
    if header is not None:
        return header.strip().lower() in {"1", "true", "yes"}
    secs = request.headers.get("X-XVector-Refresh-Seconds")
    if secs is not None:
        try:
            return int(secs) == 0
        except ValueError:
            pass
    if request.query_params.get("refresh", "").lower() in {"1", "true", "yes"}:
        return True
    if request.query_params.get("refresh_seconds") == "0":
        return True
    body = body or {}
    if body.get("refresh") in (True, 1, "true", "True"):
        return True
    if body.get("refreshSeconds") == 0 or body.get("refresh_seconds") == 0:
        return True
    return False


def milvus_route(handler: Callable):
    async def _wrapped(request: Request):
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if not isinstance(body, dict):
            body = {}
        result = await handler(request, body)
        return ok(result)

    return _wrapped
