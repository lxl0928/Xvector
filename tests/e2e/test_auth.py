from __future__ import annotations

import httpx
import pytest

from pyxvector.exceptions import XvectorApiError
from tests.conftest import GATEWAY, TOKEN


def test_missing_token(gateway_ready):
    r = httpx.post(f"{GATEWAY}/v2/vectordb/collections/list", json={}, timeout=10)
    assert r.status_code == 401
    assert r.json().get("code") == 1800


def test_wrong_password(gateway_ready):
    r = httpx.post(
        f"{GATEWAY}/v2/vectordb/collections/list",
        json={},
        headers={"Authorization": "Bearer root:wrong-password"},
        timeout=10,
    )
    assert r.status_code == 401


def test_valid_bearer(client):
    dbs = client.list_databases()
    assert "default" in dbs


def test_health_no_auth(gateway_ready):
    r = httpx.get(f"{GATEWAY}/healthz", timeout=5)
    assert r.status_code == 200
