"""Locust entry: write-only (100% insert, batch=50)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.performance_testing.common.shape import configure_shape
from tests.performance_testing.common.tasks import WriteOnlyUser as WriteUser

StaircaseShape = configure_shape("write")

__all__ = ["WriteUser", "StaircaseShape"]
