"""Locust entry: mixed write:read = 20:80 (read internal 80:1:19)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.performance_testing.common.shape import configure_shape
from tests.performance_testing.common.tasks import MixedUser as MixedTrafficUser

StaircaseShape = configure_shape("mixed")

__all__ = ["MixedTrafficUser", "StaircaseShape"]
