from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from xvector.api.app_factory import create_base_app
from xvector.auth.gateway_auth import authenticate_via_writer, parse_bearer
from xvector.common.errors import CODE_INTERNAL, CODE_UNAUTHORIZED, internal_error_body, ok
from xvector.config import get_settings
from xvector.gateway.openapi_merge import OpenAPIMerger
from xvector.gateway.proxy import GatewayProxy

logger = logging.getLogger(__name__)


def create_app():
    settings = get_settings()
    docs_url = "/docs" if settings.docs_enabled else None
    redoc_url = "/redoc" if settings.redoc_enabled else None
    app = create_base_app(
        "Xvector Gateway",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url="/openapi.json",
        inject_request_id=True,
    )
    proxy = GatewayProxy(settings)
    merger = OpenAPIMerger(app, settings)
    app.state.proxy = proxy
    app.state.openapi_merger = merger
    app.state.merged_openapi = None

    def custom_openapi():
        return merger.cached_or_local()

    app.openapi = custom_openapi  # type: ignore[method-assign]

    @app.on_event("startup")
    async def _startup():
        try:
            await proxy.start()
        except Exception:  # noqa: BLE001
            logger.exception("gateway proxy start failed; process continues")
        try:
            await merger.start_background_refresh()
        except Exception:  # noqa: BLE001
            logger.exception("gateway openapi merge start failed; process continues")

    @app.on_event("shutdown")
    async def _shutdown():
        try:
            await merger.stop_background_refresh()
        except Exception:  # noqa: BLE001
            logger.exception("gateway openapi merge stop failed")
        try:
            await proxy.stop()
        except Exception:  # noqa: BLE001
            logger.exception("gateway proxy stop failed")

    @app.get("/healthz", tags=["Gateway / System"])
    async def healthz():
        return {"status": "ok", "role": "gateway"}

    @app.get("/readyz", tags=["Gateway / System"])
    async def readyz():
        ready = await proxy.probe("/readyz")
        if not ready:
            return JSONResponse(status_code=503, content={"status": "not_ready", "role": "gateway"})
        return {"status": "ok", "role": "gateway"}

    @app.get("/v2/vectordb/heartbeat", tags=["Gateway / System"])
    async def heartbeat():
        return {"code": 0, "message": "success", "data": {"role": "gateway", "version": "0.1.0"}}

    @app.post("/v2/vectordb/auth", tags=["Gateway / System"])
    async def auth(request: Request):
        """Validate Bearer USERNAME:PASSWORD (same rules as proxied business APIs)."""
        creds = parse_bearer(request.headers.get("Authorization"))
        if not creds:
            return JSONResponse(
                status_code=401,
                content={"code": CODE_UNAUTHORIZED, "message": "missing or invalid Authorization Bearer"},
            )
        username, password = creds
        try:
            authed = await authenticate_via_writer(username, password)
        except Exception as exc:  # noqa: BLE001
            logger.exception("gateway auth verify failed")
            return JSONResponse(status_code=500, content=internal_error_body(f"auth verify failed: {exc}"))
        if not authed:
            return JSONResponse(
                status_code=401,
                content={"code": CODE_UNAUTHORIZED, "message": "authentication failed"},
            )
        return ok({"username": username})

    @app.post("/openapi/refresh", tags=["Gateway / Admin"])
    async def openapi_refresh():
        """Force re-merge of Writer/Reader OpenAPI into Gateway docs (no auth)."""
        result = await merger.refresh()
        if not result.get("ok"):
            return JSONResponse(
                status_code=503,
                content={
                    "code": CODE_INTERNAL,
                    "message": "openapi refresh failed",
                    "data": result,
                },
            )
        return ok(result)

    @app.api_route(
        "/v2/vectordb/{full_path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        include_in_schema=False,
    )
    async def proxy_all(full_path: str, request: Request):
        # Dedicated /v2/vectordb/auth is registered above and takes precedence.
        creds = parse_bearer(request.headers.get("Authorization"))
        if not creds:
            return JSONResponse(
                status_code=401,
                content={"code": CODE_UNAUTHORIZED, "message": "missing or invalid Authorization Bearer"},
            )
        username, password = creds

        try:
            authed = await authenticate_via_writer(username, password)
        except Exception as exc:  # noqa: BLE001
            logger.exception("gateway auth verify failed")
            return JSONResponse(status_code=500, content=internal_error_body(f"auth verify failed: {exc}"))
        if not authed:
            return JSONResponse(
                status_code=401,
                content={"code": CODE_UNAUTHORIZED, "message": "authentication failed"},
            )

        return await proxy.forward(request, username)

    return app
