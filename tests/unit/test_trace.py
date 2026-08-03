from __future__ import annotations

import re

from starlette.datastructures import Headers

from xvector.common.trace import generate_trace_id, resolve_trace_id


def test_generate_trace_id_format():
    tid = generate_trace_id()
    assert re.fullmatch(r"xv-[0-9a-f]{32}", tid)


def test_priority_x_request_id():
    h = Headers(
        {
            "X-Request-Id": "client-req-1",
            "X-Trace-Id": "trace-2",
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        }
    )
    assert resolve_trace_id(h) == "client-req-1"


def test_priority_x_trace_id():
    h = Headers(
        {
            "X-Trace-Id": "trace-2",
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        }
    )
    assert resolve_trace_id(h) == "trace-2"


def test_priority_traceparent():
    h = Headers({"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"})
    assert resolve_trace_id(h) == "0af7651916cd43dd8448eb211c80319c"


def test_invalid_traceparent_falls_back_to_generate():
    h = Headers({"traceparent": "not-a-valid-traceparent"})
    tid = resolve_trace_id(h)
    assert re.fullmatch(r"xv-[0-9a-f]{32}", tid)


def test_empty_headers_generate():
    tid = resolve_trace_id(Headers({}))
    assert re.fullmatch(r"xv-[0-9a-f]{32}", tid)


def test_trim_whitespace():
    h = Headers({"X-Request-Id": "  keep-me  "})
    assert resolve_trace_id(h) == "keep-me"
