from __future__ import annotations

import logging

from fastapi import Request

from xvector.api.app_factory import build_context, create_base_app
from xvector.api.health import mount_health
from xvector.api.v2.deps import Services
from xvector.api.v2.routes import build_writer_router
from xvector.common.models.internal import InternalAuthVerifyRequest, InternalCollectionRequest
from xvector.common.paths import DEFAULT_PARTITION
from xvector.config import get_settings

logger = logging.getLogger(__name__)


def create_app():
    settings = get_settings()
    # build_context(role=writer) creates/opens meta and seeds defaults before serve.
    ctx = build_context(settings, role="writer")
    if not ctx.meta.is_open:
        raise RuntimeError("writer failed to open meta collection")
    # Default: close /docs & /redoc UI; keep /openapi.json for Gateway merge.
    docs_url = "/docs" if settings.writer_docs_ui else None
    app = create_base_app(
        "Xvector Writer",
        docs_url=docs_url,
        redoc_url=None,
        openapi_url="/openapi.json",
        inject_request_id=False,
    )
    svc = Services(ctx)
    mount_health(app, ctx, role="writer")
    app.include_router(build_writer_router(svc))
    app.state.ctx = ctx
    app.state.svc = svc

    @app.on_event("startup")
    async def _startup():
        # Belt-and-suspenders: ensure meta + snapshot are ready after uvicorn startup.
        # Never let startup exceptions kill the process; /readyz will surface unreadiness.
        try:
            if not ctx.meta.is_open:
                ctx.meta.open()
            ctx.meta.publish_snapshot()
            logger.info(
                "writer meta ready path=%s snapshot=%s",
                ctx.paths.meta_dir,
                ctx.paths.meta_snapshot,
            )
        except Exception:  # noqa: BLE001
            logger.exception("writer startup meta publish failed; process continues")

    @app.post("/internal/auth/verify", include_in_schema=False)
    async def auth_verify(request: Request, body: InternalAuthVerifyRequest):
        token = request.headers.get("X-Internal-Token", "")
        if settings.internal_token and token != settings.internal_token:
            return {"ok": False}
        ok = svc.user.verify(body.username, body.password)
        return {"ok": ok}

    @app.post("/internal/flush", include_in_schema=False)
    async def internal_flush(request: Request, body: InternalCollectionRequest):
        """RW-open + flush + close so Reader can safely RO-open without WAL replay."""
        token = request.headers.get("X-Internal-Token", "")
        if settings.internal_token and token != settings.internal_token:
            return {"ok": False, "error": "unauthorized"}
        db = body.dbName
        coll = body.collectionName
        parts = body.partitionNames or [DEFAULT_PARTITION]
        errors: list[str] = []
        for p in parts:
            try:
                ctx.collections.flush_partition(db, coll, p)
            except Exception as e:  # noqa: BLE001
                logger.exception("internal flush failed %s/%s/%s", db, coll, p)
                errors.append(f"{p}: {e}")
        if errors:
            return {"ok": False, "error": "; ".join(errors)}
        return {"ok": True}

    @app.get("/v2/vectordb/heartbeat")
    async def heartbeat():
        return {"code": 0, "data": {"role": "writer", "version": "0.1.0"}}

    return app
