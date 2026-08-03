from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from xvector.meta.store import MetaNotReadyError
from xvector.services.context import AppContext


def mount_health(app: FastAPI, ctx: AppContext | None = None, role: str = "gateway") -> None:
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "role": role}

    @app.get("/readyz")
    async def readyz():
        if role == "gateway":
            return {"status": "ok", "role": role}
        if ctx is None:
            return {"status": "ok", "role": role}
        data_ok = ctx.paths.root.exists()
        if not data_ok:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "role": role, "error": "data dir missing"},
            )
        try:
            if not ctx.meta.is_open:
                ctx.meta.open()
            ctx.catalog.list_databases()
        except MetaNotReadyError as e:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "role": role, "error": str(e)},
            )
        except Exception as e:  # noqa: BLE001
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "role": role, "error": str(e)},
            )
        return {"status": "ok", "role": role}
