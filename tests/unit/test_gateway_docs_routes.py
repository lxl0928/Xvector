from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def gateway_client(tmp_path, monkeypatch):
    monkeypatch.setenv("XVECTOR_ROLE", "gateway")
    monkeypatch.setenv("XVECTOR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("XVECTOR_OPENAPI_REFRESH_SECONDS", "0")
    monkeypatch.setenv("XVECTOR_OPENAPI_REFRESH_RETRIES", "1")
    monkeypatch.setenv("XVECTOR_OPENAPI_FETCH_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("XVECTOR_ACCESS_LOG_ENABLED", "false")
    from xvector.config import get_settings

    get_settings.cache_clear()
    from xvector.api.gateway_app import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    get_settings.cache_clear()


def test_gateway_health_has_request_id(gateway_client):
    r = gateway_client.get("/healthz", headers={"X-Request-Id": "gw-health-1"})
    assert r.status_code == 200
    assert r.headers["X-Request-Id"] == "gw-health-1"
    assert r.json()["requestId"] == "gw-health-1"
    assert r.json()["status"] == "ok"


def test_gateway_docs_and_openapi_local(gateway_client):
    docs = gateway_client.get("/docs")
    assert docs.status_code == 200
    schema = gateway_client.get("/openapi.json")
    assert schema.status_code == 200
    body = schema.json()
    assert body["info"]["title"] == "Xvector API"
    assert "/v2/vectordb/auth" in body["paths"]
    assert "/openapi/refresh" in body["paths"]
    assert not any("full_path" in p for p in body["paths"])
    assert "BearerAuth" in body["components"]["securitySchemes"]


def test_openapi_refresh_endpoint_no_auth(gateway_client):
    # Without writer/reader, refresh fails but endpoint is callable without Bearer.
    r = gateway_client.post("/openapi/refresh")
    assert r.status_code == 503
    body = r.json()
    assert body["data"]["ok"] is False
    assert "requestId" in body
    assert "X-Request-Id" in r.headers


def test_auth_missing_bearer(gateway_client):
    r = gateway_client.post("/v2/vectordb/auth")
    assert r.status_code == 401
    assert r.json()["code"] == 1800
    assert "requestId" in r.json()
