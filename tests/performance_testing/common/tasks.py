"""Shared Locust HttpUser task implementations."""

from __future__ import annotations

import logging
import os
import random
from typing import Any

from locust import HttpUser, between, task

from tests.performance_testing.common.config import (
    SEARCH_EF,
    SEARCH_TOPN,
    VECTOR_FIELD,
    WEIGHT_GET,
    WEIGHT_MIXED_READ,
    WEIGHT_MIXED_WRITE,
    WEIGHT_QUERY,
    WEIGHT_SEARCH,
    WRITE_BATCH,
    WRITE_NAME,
    load_config,
)
from tests.performance_testing.common.vectors import IdAllocator, make_entities, make_vector

logger = logging.getLogger(__name__)

# Shared across users in one locust process.
_CFG = load_config()
_ID_ALLOC = IdAllocator(start=int(os.getenv("XVECTOR_PERF_NEXT_ID", str(_CFG.target_rows))))
_MAX_EXISTING_ID = max(int(os.getenv("XVECTOR_PERF_MAX_ID", str(max(_CFG.target_rows - 1, 0)))), 0)


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": _CFG.auth_header,
        "Content-Type": "application/json",
    }


def _base_body() -> dict[str, Any]:
    return {"dbName": _CFG.db_name, "collectionName": _CFG.collection_name}


def _catch_response_ok(resp: Any, name: str) -> None:
    if resp.status_code >= 400:
        resp.failure(f"{name} http {resp.status_code}: {resp.text[:300]}")
        return
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        resp.failure(f"{name} invalid json: {resp.text[:300]}")
        return
    if isinstance(data, dict) and data.get("code", 0) != 0:
        resp.failure(f"{name} api code={data.get('code')} msg={data.get('message')}")
        return
    resp.success()


class XvectorPerfUser(HttpUser):
    abstract = True
    wait_time = between(0.0, 0.0)
    host = _CFG.host

    def on_start(self) -> None:
        self.client.headers.update(_auth_headers())

    def do_insert(self) -> None:
        start = _ID_ALLOC.allocate(WRITE_BATCH)
        payload = {
            **_base_body(),
            "data": make_entities(start, WRITE_BATCH, dim=_CFG.dim),
        }
        with self.client.post(
            "/v2/vectordb/entities/insert",
            json=payload,
            name=WRITE_NAME,
            catch_response=True,
        ) as resp:
            _catch_response_ok(resp, WRITE_NAME)

    def do_search(self) -> None:
        seed = random.randint(0, max(_MAX_EXISTING_ID, 0))
        payload = {
            **_base_body(),
            "data": [make_vector(_CFG.dim, seed=seed)],
            "annsField": VECTOR_FIELD,
            "limit": SEARCH_TOPN,
            "searchParams": {"ef": SEARCH_EF},
            "outputFields": ["id", "timestamp"],
        }
        with self.client.post(
            "/v2/vectordb/entities/search",
            json=payload,
            name="search",
            catch_response=True,
        ) as resp:
            _catch_response_ok(resp, "search")

    def do_get(self) -> None:
        pk = random.randint(0, max(_MAX_EXISTING_ID, 0))
        payload = {
            **_base_body(),
            "id": [pk],
            "outputFields": ["id", "timestamp"],
        }
        with self.client.post(
            "/v2/vectordb/entities/get",
            json=payload,
            name="get",
            catch_response=True,
        ) as resp:
            _catch_response_ok(resp, "get")

    def do_query(self) -> None:
        payload = {
            **_base_body(),
            "filter": "timestamp > 0",
            "limit": SEARCH_TOPN,
            "outputFields": ["id", "timestamp"],
        }
        with self.client.post(
            "/v2/vectordb/entities/query",
            json=payload,
            name="query",
            catch_response=True,
        ) as resp:
            _catch_response_ok(resp, "query")


class WriteOnlyUser(XvectorPerfUser):
    abstract = False

    @task
    def insert(self) -> None:
        self.do_insert()


class ReadOnlyUser(XvectorPerfUser):
    abstract = False

    @task(WEIGHT_SEARCH)
    def search(self) -> None:
        self.do_search()

    @task(WEIGHT_GET)
    def get(self) -> None:
        self.do_get()

    @task(WEIGHT_QUERY)
    def query(self) -> None:
        self.do_query()


class MixedUser(XvectorPerfUser):
    """write:read = 20:80; read internal weights remain 80:1:19."""

    abstract = False

    # Scale by read-internal total (100) so write:read stays exactly 20:80.
    @task(WEIGHT_MIXED_WRITE * (WEIGHT_SEARCH + WEIGHT_GET + WEIGHT_QUERY))
    def insert(self) -> None:
        self.do_insert()

    @task(WEIGHT_MIXED_READ * WEIGHT_SEARCH)
    def search(self) -> None:
        self.do_search()

    @task(WEIGHT_MIXED_READ * WEIGHT_GET)
    def get(self) -> None:
        self.do_get()

    @task(WEIGHT_MIXED_READ * WEIGHT_QUERY)
    def query(self) -> None:
        self.do_query()
