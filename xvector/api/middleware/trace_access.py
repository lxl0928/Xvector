from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from xvector.common.trace import HEADER_REQUEST_ID, STATE_TRACE_ID, resolve_trace_id

logger = logging.getLogger("xvector.access")

try:
    import orjson

    def _dumps(obj: object) -> bytes:
        return orjson.dumps(obj)

except Exception:  # noqa: BLE001

    def _dumps(obj: object) -> bytes:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def utc_iso8601_ms(dt: datetime | None = None) -> str:
    """UTC timestamp with millisecond precision and Z suffix."""
    now = dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    ms = int(now.microsecond / 1000)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def _client_addr(request: Request) -> str:
    client = request.client
    if client is None:
        return "-"
    host = client.host or "-"
    port = client.port
    if port is None:
        return host
    return f"{host}:{port}"


def _request_line(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    target = f"{path}?{query}" if query else path
    version = request.scope.get("http_version", "1.1")
    return f"{request.method} {target} HTTP/{version}"


def _reason_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _is_json_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    return "application/json" in content_type.lower()


async def _read_body(response: Response) -> bytes:
    body = getattr(response, "body", None)
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk)
        else:
            chunks.append(chunk.encode("utf-8"))
    return b"".join(chunks)


def _inject_request_id_into_json(body: bytes, trace_id: str) -> bytes | None:
    """Return new body if JSON object was patched; None to leave body unchanged."""
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    data["requestId"] = trace_id
    return _dumps(data)


class TraceAccessMiddleware(BaseHTTPMiddleware):
    """
    Resolve/generate trace_id, Start/End access logs, always set X-Request-Id.

    When inject_request_id=True (Gateway only), also inject body.requestId for JSON objects.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        inject_request_id: bool = False,
        access_log_enabled: bool = True,
    ):
        super().__init__(app)
        self.inject_request_id = inject_request_id
        self.access_log_enabled = access_log_enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = resolve_trace_id(request.headers)
        setattr(request.state, STATE_TRACE_ID, trace_id)

        req_line = _request_line(request)
        client = _client_addr(request)

        if self.access_log_enabled:
            logger.info('%s %s %s "%s" Start...', utc_iso8601_ms(), client, trace_id, req_line)

        try:
            response = await call_next(request)
        except Exception:
            if self.access_log_enabled:
                logger.info(
                    '%s %s %s "%s" 500 Internal Server Error',
                    utc_iso8601_ms(),
                    client,
                    trace_id,
                    req_line,
                )
            raise

        content_type = response.headers.get("content-type")
        out_body: bytes | None = None
        if self.inject_request_id and _is_json_content_type(content_type):
            raw = await _read_body(response)
            patched = _inject_request_id_into_json(raw, trace_id)
            if patched is not None:
                out_body = patched
            else:
                out_body = raw

        if out_body is not None:
            headers = dict(response.headers)
            headers[HEADER_REQUEST_ID] = trace_id
            headers["content-length"] = str(len(out_body))
            # Avoid duplicate content-length casing issues
            headers.pop("Content-Length", None)
            new_response = Response(
                content=out_body,
                status_code=response.status_code,
                headers=headers,
                media_type=content_type,
            )
            response = new_response
        else:
            response.headers[HEADER_REQUEST_ID] = trace_id

        if self.access_log_enabled:
            phrase = _reason_phrase(response.status_code)
            suffix = f"{response.status_code} {phrase}".rstrip()
            logger.info('%s %s %s "%s" %s', utc_iso8601_ms(), client, trace_id, req_line, suffix)

        return response
