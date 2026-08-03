from __future__ import annotations

import uuid

HEADER_REQUEST_ID = "X-Request-Id"
HEADER_TRACE_ID = "X-Trace-Id"
HEADER_TRACEPARENT = "traceparent"

# Canonical attribute on request.state
STATE_TRACE_ID = "trace_id"


def generate_trace_id() -> str:
    """Server-generated id: xv- + 32 hex (no hyphens)."""
    return f"xv-{uuid.uuid4().hex}"


def _parse_traceparent(value: str) -> str | None:
    """Extract 32-hex trace-id from W3C traceparent; return None if invalid."""
    parts = value.strip().split("-")
    if len(parts) < 4:
        return None
    trace_id = parts[1].strip().lower()
    if len(trace_id) != 32:
        return None
    try:
        int(trace_id, 16)
    except ValueError:
        return None
    return trace_id


def resolve_trace_id(headers) -> str:
    """
    Resolve trace id from request headers (case-insensitive via Starlette Headers).

    Priority: X-Request-Id > X-Trace-Id > traceparent (trace-id segment) > generate.
    Non-empty client values are trusted as-is (trimmed); only generated ids use xv- prefix.
    """
    request_id = (headers.get(HEADER_REQUEST_ID) or "").strip()
    if request_id:
        return request_id

    trace_id = (headers.get(HEADER_TRACE_ID) or "").strip()
    if trace_id:
        return trace_id

    traceparent = (headers.get(HEADER_TRACEPARENT) or "").strip()
    if traceparent:
        parsed = _parse_traceparent(traceparent)
        if parsed:
            return parsed

    return generate_trace_id()
