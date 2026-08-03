from __future__ import annotations

import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from xvector.common.errors import CODE_PARAM, internal_error_body
from xvector.common.trace import HEADER_REQUEST_ID, STATE_TRACE_ID, generate_trace_id
from xvector.config import Settings
from xvector.gateway.router_table import resolve_target

logger = logging.getLogger(__name__)


class GatewayProxy:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _trace_id(self, request: Request) -> str:
        tid = getattr(request.state, STATE_TRACE_ID, None)
        if isinstance(tid, str) and tid:
            return tid
        return generate_trace_id()

    async def forward(self, request: Request, username: str) -> Response:
        if self._client is None:
            return JSONResponse(
                status_code=500,
                content=internal_error_body("gateway proxy client not started"),
            )
        target = resolve_target(request.url.path)
        if target is None:
            return JSONResponse(
                status_code=404,
                content={"code": CODE_PARAM, "message": "unknown route"},
            )
        base = self.settings.writer_url if target == "W" else self.settings.reader_url
        url = f"{base}{request.url.path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in {"host", "content-length", "authorization"}
        }
        headers["X-User"] = username
        # Canonical downstream trace header (overwrite any stray client variants).
        headers[HEADER_REQUEST_ID] = self._trace_id(request)
        if self.settings.internal_token:
            headers["X-Internal-Token"] = self.settings.internal_token
        try:
            body = await request.body()
            resp = await self._client.request(request.method, url, content=body, headers=headers)
        except httpx.TimeoutException as exc:
            logger.exception("gateway upstream timeout %s", url)
            return JSONResponse(status_code=500, content=internal_error_body(f"upstream timeout: {exc}"))
        except httpx.RequestError as exc:
            logger.exception("gateway upstream request failed %s", url)
            return JSONResponse(status_code=500, content=internal_error_body(f"upstream request failed: {exc}"))
        except Exception as exc:  # noqa: BLE001
            logger.exception("gateway forward failed %s", url)
            return JSONResponse(status_code=500, content=internal_error_body(str(exc)))
        # Response header X-Request-Id is set by TraceAccessMiddleware; body.requestId too.
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )

    async def probe(self, path: str = "/readyz") -> bool:
        if self._client is None:
            return False
        try:
            w = await self._client.get(f"{self.settings.writer_url}{path}")
            r = await self._client.get(f"{self.settings.reader_url}{path}")
            return w.status_code == 200 and r.status_code == 200 and w.json().get("status") == "ok" and r.json().get("status") == "ok"
        except Exception:  # noqa: BLE001
            return False
