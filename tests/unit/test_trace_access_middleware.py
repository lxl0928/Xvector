from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from xvector.api.middleware.trace_access import TraceAccessMiddleware
from xvector.common.errors import CODE_INTERNAL


def _app(*, inject: bool) -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceAccessMiddleware, inject_request_id=inject, access_log_enabled=False)

    @app.get("/obj")
    async def obj():
        return {"code": 0, "message": "success", "data": {}}

    @app.get("/arr")
    async def arr():
        return [1, 2, 3]

    @app.get("/plain")
    async def plain():
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse("ok")

    @app.get("/boom")
    async def boom():
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=500, content={"code": CODE_INTERNAL, "message": "fail"})

    return app


def test_gateway_injects_request_id_and_header():
    client = TestClient(_app(inject=True))
    r = client.get("/obj", headers={"X-Request-Id": "xv-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"})
    assert r.status_code == 200
    assert r.headers["X-Request-Id"] == "xv-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    body = r.json()
    assert body["requestId"] == "xv-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert body["code"] == 0


def test_writer_style_no_body_inject_but_header():
    client = TestClient(_app(inject=False))
    r = client.get("/obj", headers={"X-Request-Id": "keep-header"})
    assert r.headers["X-Request-Id"] == "keep-header"
    assert "requestId" not in r.json()


def test_json_array_not_modified():
    client = TestClient(_app(inject=True))
    r = client.get("/arr", headers={"X-Request-Id": "arr-id"})
    assert r.headers["X-Request-Id"] == "arr-id"
    assert r.json() == [1, 2, 3]


def test_non_json_only_header():
    client = TestClient(_app(inject=True))
    r = client.get("/plain", headers={"X-Request-Id": "plain-id"})
    assert r.headers["X-Request-Id"] == "plain-id"
    assert r.text == "ok"


def test_error_json_gets_request_id():
    client = TestClient(_app(inject=True))
    r = client.get("/boom", headers={"X-Trace-Id": "err-trace"})
    assert r.status_code == 500
    assert r.headers["X-Request-Id"] == "err-trace"
    assert r.json()["requestId"] == "err-trace"


def test_generated_id_format():
    client = TestClient(_app(inject=True))
    r = client.get("/obj")
    tid = r.headers["X-Request-Id"]
    assert re.fullmatch(r"xv-[0-9a-f]{32}", tid)
    assert r.json()["requestId"] == tid


def test_traceparent_used():
    client = TestClient(_app(inject=True))
    r = client.get(
        "/obj",
        headers={"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"},
    )
    assert r.headers["X-Request-Id"] == "0af7651916cd43dd8448eb211c80319c"
