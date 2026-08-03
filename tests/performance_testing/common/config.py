"""Performance-test constants and environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DIM = 1024
VECTOR_FIELD = "vector"
PK_FIELD = "id"
TIMESTAMP_FIELD = "timestamp"

INDEX_TYPE = "HNSW"
METRIC_TYPE = "L2"
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 200
SEARCH_TOPN = 20
SEARCH_EF = 64

PREPARE_BATCH = 200
WRITE_BATCH = 50
DEFAULT_TARGET_ROWS = 1_000_000

START_USERS = 1
USER_STEP = 5
STEP_DURATION_S = 20
MAX_USERS = 100
LATENCY_THRESHOLD_MS = 200.0

DEFAULT_HOST = "http://127.0.0.1:19530"
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "Xvector"
DEFAULT_COLLECTION = "perf_hnsw_1024"
DEFAULT_DB = "default"
DEFAULT_WEB_PORT = 8089

WRITE_NAME = "insert"
READ_NAMES = ("search", "get", "query")

# Locust task weights: search:get:query = 80:1:19
WEIGHT_SEARCH = 80
WEIGHT_GET = 1
WEIGHT_QUERY = 19

# Mixed scenario: write:read = 20:80
WEIGHT_MIXED_WRITE = 20
WEIGHT_MIXED_READ = 80

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


@dataclass(frozen=True)
class PerfConfig:
    host: str
    token: str
    collection_name: str
    db_name: str
    target_rows: int
    prepare_batch: int
    write_batch: int
    web_port: int
    dim: int = DIM

    @property
    def auth_header(self) -> str:
        return f"Bearer {self.token}"


def load_config() -> PerfConfig:
    username = os.getenv("XVECTOR_USERNAME", DEFAULT_USERNAME)
    password = os.getenv("XVECTOR_PASSWORD", DEFAULT_PASSWORD)
    token = os.getenv("XVECTOR_TOKEN") or f"{username}:{password}"
    host = os.getenv("XVECTOR_URI") or os.getenv("XVECTOR_PERF_HOST") or DEFAULT_HOST
    target_rows = int(os.getenv("XVECTOR_PERF_TARGET_ROWS", str(DEFAULT_TARGET_ROWS)))
    if target_rows < 1:
        raise ValueError("XVECTOR_PERF_TARGET_ROWS must be >= 1")
    return PerfConfig(
        host=host.rstrip("/"),
        token=token,
        collection_name=os.getenv("XVECTOR_PERF_COLLECTION", DEFAULT_COLLECTION),
        db_name=os.getenv("XVECTOR_PERF_DB", DEFAULT_DB),
        target_rows=target_rows,
        prepare_batch=int(os.getenv("XVECTOR_PERF_PREPARE_BATCH", str(PREPARE_BATCH))),
        write_batch=int(os.getenv("XVECTOR_PERF_WRITE_BATCH", str(WRITE_BATCH))),
        web_port=int(os.getenv("XVECTOR_PERF_WEB_PORT", str(DEFAULT_WEB_PORT))),
    )


def staircase_user_counts(start: int = START_USERS, step: int = USER_STEP, max_users: int = MAX_USERS) -> list[int]:
    """Return 1, 6, 11, ... while users <= max_users."""
    users: list[int] = []
    current = start
    while current <= max_users:
        users.append(current)
        current += step
    return users
