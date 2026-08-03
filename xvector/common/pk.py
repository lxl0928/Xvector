from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class Snowflake:
    """Simple snowflake-ish Int64 generator for autoID."""

    def __init__(self, worker_id: int = 1):
        self.worker_id = worker_id & 0x3FF
        self._lock = threading.Lock()
        self._seq = 0
        self._last_ms = 0
        self._epoch = 1_700_000_000_000

    def next_id(self) -> int:
        with self._lock:
            now = int(time.time() * 1000)
            if now == self._last_ms:
                self._seq = (self._seq + 1) & 0xFFF
                if self._seq == 0:
                    while now <= self._last_ms:
                        now = int(time.time() * 1000)
            else:
                self._seq = 0
            self._last_ms = now
            ts = (now - self._epoch) & ((1 << 41) - 1)
            return (ts << 22) | (self.worker_id << 12) | self._seq


_snowflake = Snowflake()


def to_internal_id(value: Any, primary_type: str) -> str:
    if value is None:
        raise ValueError("primary key is required")
    if primary_type == "Int64":
        return str(int(value))
    return str(value)


def from_internal_id(value: str, primary_type: str) -> Any:
    if primary_type == "Int64":
        return int(value)
    return value


def generate_auto_id(primary_type: str) -> Any:
    if primary_type == "Int64":
        return _snowflake.next_id()
    return uuid.uuid4().hex
