"""Pytest fixtures for performance environment preparation."""

from __future__ import annotations

import logging
import os

import pytest

from tests.performance_testing.common.config import PerfConfig, load_config
from tests.performance_testing.common.prepare import gateway_ready, prepare_perf_collection

logger = logging.getLogger(__name__)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "performance: Locust performance preparation (excluded from default CI)")


@pytest.fixture(scope="session")
def perf_config() -> PerfConfig:
    return load_config()


@pytest.fixture(scope="session")
def perf_gateway_ready(perf_config: PerfConfig):
    if not gateway_ready(perf_config.host):
        pytest.skip(
            f"Gateway not ready at {perf_config.host}. Start with: docker compose up -d --build"
        )
    return True


@pytest.fixture(scope="session")
def prepared_collection(perf_gateway_ready, perf_config: PerfConfig) -> dict:
    """
    Create/reuse collection, ensure HNSW index, ingest to target rows, load.
    Set XVECTOR_PERF_TARGET_ROWS for local smoke (default 1_000_000).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    summary = prepare_perf_collection(perf_config)
    # Expose ids to subsequent locust processes via env hints printed in tests.
    os.environ.setdefault("XVECTOR_PERF_NEXT_ID", str(summary["next_id"]))
    os.environ.setdefault("XVECTOR_PERF_MAX_ID", str(max(summary["row_count"] - 1, 0)))
    return summary
