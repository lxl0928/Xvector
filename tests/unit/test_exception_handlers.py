from __future__ import annotations

from fastapi.testclient import TestClient

from xvector.api.app_factory import create_base_app
from xvector.common.errors import CODE_INTERNAL


def test_unhandled_exception_returns_json_500_and_process_continues():
    app = create_base_app("Xvector Exception Test")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom-test-marker")

    @app.get("/still-alive")
    async def still_alive():
        return {"status": "ok"}

    # raise_server_exceptions=False: assert ASGI path returns a response instead of crashing.
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == CODE_INTERNAL
    assert "Internal Error:" in body["message"]
    assert "boom-test-marker" in body["message"]
    assert body["error_message"] == "boom-test-marker"

    # Process / app must keep serving after the fault.
    r2 = client.get("/still-alive")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"
