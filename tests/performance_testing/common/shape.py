"""Locust LoadTestShape implementing staircase rule C."""

from __future__ import annotations

import logging
from typing import Any

from locust import LoadTestShape, events

from tests.performance_testing.common.config import (
    LATENCY_THRESHOLD_MS,
    MAX_USERS,
    START_USERS,
    STEP_DURATION_S,
    USER_STEP,
    staircase_user_counts,
)
from tests.performance_testing.common.metrics import TRACKER
from tests.performance_testing.common.report import write_reports

logger = logging.getLogger(__name__)


class StaircaseShape(LoadTestShape):
    """
    users = 1 + k*5, each step STEP_DURATION_S seconds.
    Stop when step-window write_mean or read_mean > LATENCY_THRESHOLD_MS.
    Effective result is the previous step.
    """

    spawn_rate = 100  # reach target users quickly within the step window

    def __init__(self) -> None:
        super().__init__()
        self._steps = staircase_user_counts(START_USERS, USER_STEP, MAX_USERS)
        self._index = 0
        self._step_started_at: float | None = None
        self._active_users: int | None = None
        self._stopping = False
        self._reports_written = False

    def tick(self) -> tuple[int, float] | None:  # type: ignore[override]
        if self._stopping:
            self._maybe_write_reports()
            return None

        run_time = self.get_run_time()

        # Finalize current step when its window elapsed.
        if self._active_users is not None and self._step_started_at is not None:
            if run_time - self._step_started_at >= STEP_DURATION_S:
                step = TRACKER.end_step()
                if step is not None and step.exceeded:
                    reason = step.exceed_reason or "latency_threshold_exceeded"
                    TRACKER.mark_stopped(reason, hit_latency_limit=True, reached_max=False)
                    logger.warning("staircase stop: %s (users=%s)", reason, self._active_users)
                    self._stopping = True
                    self._maybe_write_reports()
                    return None
                logger.info(
                    "staircase step ok users=%s write_mean=%s read_mean=%s",
                    self._active_users,
                    None if step is None else step.write_mean_ms,
                    None if step is None else step.read_mean_ms,
                )
                self._index += 1
                self._active_users = None
                self._step_started_at = None

        if self._index >= len(self._steps):
            TRACKER.mark_stopped(
                "reached_max_users",
                hit_latency_limit=False,
                reached_max=True,
            )
            logger.info("staircase finished without exceeding latency threshold")
            self._stopping = True
            self._maybe_write_reports()
            return None

        target = self._steps[self._index]
        if self._active_users != target:
            self._active_users = target
            self._step_started_at = run_time
            TRACKER.begin_step(target)
            logger.info("staircase enter step users=%s (index=%s)", target, self._index)

        return (target, float(self.spawn_rate))

    def _maybe_write_reports(self) -> None:
        if self._reports_written:
            return
        self._reports_written = True
        env = getattr(self, "runner", None)
        environment = getattr(env, "environment", None) if env is not None else None
        try:
            paths = write_reports(environment, TRACKER.summary())
            logger.info("reports written: %s", paths)
        except Exception:  # noqa: BLE001
            logger.exception("failed to write performance reports")


_HOOKS_REGISTERED = False


def register_hooks() -> None:
    """Attach Locust request/quit hooks once per process."""
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    _HOOKS_REGISTERED = True

    @events.request.add_listener
    def _on_request(
        request_type: str,
        name: str,
        response_time: float,
        response_length: int,
        exception: Any,
        **kwargs: Any,
    ) -> None:
        # response_time is milliseconds in Locust
        if exception is not None:
            return
        TRACKER.record(name, float(response_time))

    @events.quitting.add_listener
    def _on_quitting(environment: Any, **kwargs: Any) -> None:
        if TRACKER.stop_reason is None:
            step = TRACKER.end_step()
            if step is not None and step.exceeded:
                TRACKER.mark_stopped(
                    step.exceed_reason or "latency_threshold_exceeded",
                    hit_latency_limit=True,
                    reached_max=False,
                )
            else:
                TRACKER.mark_stopped(
                    "user_stopped",
                    hit_latency_limit=False,
                    reached_max=False,
                )
        try:
            write_reports(environment, TRACKER.summary())
        except Exception:  # noqa: BLE001
            logger.exception("failed to write reports on quit")


def configure_shape(scenario: str) -> type[StaircaseShape]:
    """Initialize tracker metadata and event hooks; return shape class for locustfile import."""
    TRACKER.scenario = scenario
    TRACKER.threshold_ms = LATENCY_THRESHOLD_MS
    register_hooks()
    return StaircaseShape
