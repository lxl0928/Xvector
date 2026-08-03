"""Per-step latency sampling for staircase stop decisions."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from tests.performance_testing.common.config import (
    LATENCY_THRESHOLD_MS,
    READ_NAMES,
    WRITE_NAME,
)


@dataclass
class StepSample:
    users: int
    started_at: float
    ended_at: float | None = None
    write_times_ms: list[float] = field(default_factory=list)
    read_times_ms: list[float] = field(default_factory=list)
    by_name: dict[str, list[float]] = field(default_factory=dict)
    write_mean_ms: float | None = None
    read_mean_ms: float | None = None
    exceeded: bool = False
    exceed_reason: str | None = None

    def finalize(self, threshold_ms: float = LATENCY_THRESHOLD_MS) -> None:
        self.ended_at = time.time()
        self.write_mean_ms = _mean(self.write_times_ms)
        self.read_mean_ms = _mean(self.read_times_ms)
        reasons: list[str] = []
        if self.write_mean_ms is not None and self.write_mean_ms > threshold_ms:
            reasons.append(f"write_mean={self.write_mean_ms:.2f}ms>{threshold_ms}ms")
            self.exceeded = True
        if self.read_mean_ms is not None and self.read_mean_ms > threshold_ms:
            reasons.append(f"read_mean={self.read_mean_ms:.2f}ms>{threshold_ms}ms")
            self.exceeded = True
        self.exceed_reason = "; ".join(reasons) if reasons else None

    def to_dict(self) -> dict[str, Any]:
        by_name_means = {k: _mean(v) for k, v in sorted(self.by_name.items())}
        return {
            "users": self.users,
            "duration_s": (self.ended_at or time.time()) - self.started_at,
            "write_count": len(self.write_times_ms),
            "read_count": len(self.read_times_ms),
            "write_mean_ms": self.write_mean_ms,
            "read_mean_ms": self.read_mean_ms,
            "by_name_mean_ms": by_name_means,
            "by_name_count": {k: len(v) for k, v in sorted(self.by_name.items())},
            "exceeded": self.exceeded,
            "exceed_reason": self.exceed_reason,
        }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


class StepLatencyTracker:
    """Thread-safe collector for the current staircase step window."""

    def __init__(self, threshold_ms: float = LATENCY_THRESHOLD_MS) -> None:
        self.threshold_ms = threshold_ms
        self._lock = threading.Lock()
        self.current: StepSample | None = None
        self.history: list[StepSample] = []
        self.stop_reason: str | None = None
        self.effective_users: int | None = None
        self.hit_latency_limit = False
        self.reached_max_users = False
        self.scenario: str = ""

    def begin_step(self, users: int) -> None:
        with self._lock:
            self.current = StepSample(users=users, started_at=time.time())

    def record(self, name: str, response_time_ms: float) -> None:
        with self._lock:
            if self.current is None:
                return
            self.current.by_name.setdefault(name, []).append(response_time_ms)
            if name == WRITE_NAME:
                self.current.write_times_ms.append(response_time_ms)
            elif name in READ_NAMES:
                self.current.read_times_ms.append(response_time_ms)

    def end_step(self) -> StepSample | None:
        with self._lock:
            if self.current is None:
                return None
            step = self.current
            step.finalize(self.threshold_ms)
            self.history.append(step)
            self.current = None
            return step

    def mark_stopped(self, reason: str, *, hit_latency_limit: bool, reached_max: bool) -> None:
        self.stop_reason = reason
        self.hit_latency_limit = hit_latency_limit
        self.reached_max_users = reached_max
        if hit_latency_limit:
            # effective = previous non-exceeding step
            if len(self.history) >= 2:
                self.effective_users = self.history[-2].users
            elif len(self.history) == 1 and not self.history[0].exceeded:
                self.effective_users = self.history[0].users
            else:
                self.effective_users = None
        elif self.history:
            self.effective_users = self.history[-1].users

    def summary(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "threshold_ms": self.threshold_ms,
            "stop_reason": self.stop_reason,
            "hit_latency_limit": self.hit_latency_limit,
            "reached_max_users": self.reached_max_users,
            "untouched_latency_limit": bool(self.reached_max_users and not self.hit_latency_limit),
            "effective_users": self.effective_users,
            "steps": [s.to_dict() for s in self.history],
        }


# Process-wide tracker used by LoadTestShape + request listeners.
TRACKER = StepLatencyTracker()
