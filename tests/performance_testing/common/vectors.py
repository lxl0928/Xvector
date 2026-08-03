"""Vector and entity generation helpers."""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Iterator

from tests.performance_testing.common.config import DIM, PK_FIELD, TIMESTAMP_FIELD, VECTOR_FIELD


def now_ms() -> int:
    return int(time.time() * 1000)


def make_vector(dim: int = DIM, seed: int | None = None) -> list[float]:
    """Deterministic-ish unit-ish vector; seed makes get/search reproducible when needed."""
    rng = random.Random(seed) if seed is not None else random
    vec = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def make_entities(start_id: int, count: int, dim: int = DIM) -> list[dict]:
    ts = now_ms()
    return [
        {
            PK_FIELD: start_id + i,
            TIMESTAMP_FIELD: ts,
            VECTOR_FIELD: make_vector(dim, seed=start_id + i),
        }
        for i in range(count)
    ]


class IdAllocator:
    """Thread-safe ascending id allocator for insert traffic."""

    def __init__(self, start: int = 0) -> None:
        self._next = int(start)
        self._lock = threading.Lock()

    @property
    def next_id(self) -> int:
        return self._next

    def allocate(self, count: int) -> int:
        """Reserve `count` ids; return the first id in the range."""
        with self._lock:
            start = self._next
            self._next += count
            return start

    def set_next(self, value: int) -> None:
        with self._lock:
            self._next = int(value)


def batch_ranges(start: int, end: int, batch: int) -> Iterator[tuple[int, int]]:
    """Yield (batch_start, batch_count) covering [start, end)."""
    cur = start
    while cur < end:
        n = min(batch, end - cur)
        yield cur, n
        cur += n
