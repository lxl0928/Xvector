from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

from pyxvector import XvectorClient


GATEWAY = os.getenv("XVECTOR_URI", "http://127.0.0.1:19530")
TOKEN = os.getenv("XVECTOR_TOKEN", f"{os.getenv('XVECTOR_USERNAME', 'root')}:{os.getenv('XVECTOR_PASSWORD', 'Xvector')}")


def _gateway_ready(timeout: float = 180.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{GATEWAY}/readyz", timeout=2.0)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return False


@pytest.fixture(scope="session")
def gateway_ready():
    if not _gateway_ready():
        pytest.skip(f"Gateway not ready at {GATEWAY}. Start with: docker compose up -d --build")
    return True


@pytest.fixture
def client(gateway_ready):
    c = XvectorClient(uri=GATEWAY, token=TOKEN, timeout=60.0)
    yield c
    c.close()


@pytest.fixture
def unique_name():
    return f"c_{uuid.uuid4().hex[:10]}"


def simple_schema(dim: int = 8, pk: str = "id", pk_type: str = "Int64", auto_id: bool = False, vector_name: str = "vector"):
    return {
        "autoID": auto_id,
        "enableDynamicField": False,
        "fields": [
            {
                "fieldName": "unused",
            }
        ],
        # Prefer nested milvus-like schema
    }


def milvus_schema(dim: int = 8, pk: str = "id", pk_type: str = "Int64", auto_id: bool = False, vector_name: str = "vector", extra_fields=None):
    fields = [
        {
            "name": pk,
            "dataType": pk_type,
            "isPrimaryKey": True,
            "autoID": auto_id,
        },
        {
            "name": vector_name,
            "dataType": "FloatVector",
            "dim": dim,
        },
    ]
    if extra_fields:
        fields.extend(extra_fields)
    return {"fields": fields, "autoID": auto_id}
