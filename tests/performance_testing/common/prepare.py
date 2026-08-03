"""Collection lifecycle and base-data preparation for performance tests."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from pyxvector import XvectorClient
from pyxvector.exceptions import XvectorApiError

from tests.performance_testing.common.config import PerfConfig, load_config
from tests.performance_testing.common.schema import index_spec, perf_schema
from tests.performance_testing.common.vectors import batch_ranges, make_entities

logger = logging.getLogger(__name__)

ALREADY_EXISTS = 65535


def gateway_ready(host: str, timeout: float = 180.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{host.rstrip('/')}/readyz", timeout=2.0)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return False


def make_client(cfg: PerfConfig | None = None, timeout: float = 120.0) -> XvectorClient:
    cfg = cfg or load_config()
    return XvectorClient(uri=cfg.host, token=cfg.token, timeout=timeout)


def row_count(client: XvectorClient, collection_name: str) -> int:
    stats = client.get_collection_stats(collection_name)
    if isinstance(stats, dict):
        return int(stats.get("rowCount") or 0)
    return 0


def has_collection(client: XvectorClient, collection_name: str) -> bool:
    try:
        result = client.has_collection(collection_name)
    except XvectorApiError:
        return False
    if isinstance(result, dict):
        return bool(result.get("has"))
    return bool(result)


def ensure_collection(client: XvectorClient, cfg: PerfConfig) -> None:
    name = cfg.collection_name
    if has_collection(client, name):
        logger.info("reuse existing collection %s", name)
        return
    logger.info("create collection %s (dim=%s)", name, cfg.dim)
    client.create_collection(name, schema=perf_schema(cfg.dim))


def ensure_index(client: XvectorClient, cfg: PerfConfig) -> None:
    name = cfg.collection_name
    spec = index_spec()
    existing = []
    try:
        existing = client.list_indexes(name) or []
    except XvectorApiError as exc:
        logger.warning("list_indexes failed: %s", exc)

    already = False
    for item in existing:
        text = str(item)
        if spec["index_name"] in text or spec["field_name"] in text:
            already = True
            break
        if isinstance(item, dict) and (
            item.get("indexName") == spec["index_name"] or item.get("fieldName") == spec["field_name"]
        ):
            already = True
            break

    if already:
        logger.info("index already present on %s", name)
        return

    logger.info(
        "create HNSW index on %s (M=%s, efConstruction=%s)",
        name,
        spec["params"]["M"],
        spec["params"]["efConstruction"],
    )
    try:
        client.create_index(
            name,
            spec["fieldName"],
            index_name=spec["indexName"],
            index_type=spec["indexType"],
            metric_type=spec["metricType"],
            params=spec["params"],
        )
    except XvectorApiError as exc:
        if exc.code == ALREADY_EXISTS or "already" in exc.message.lower():
            logger.info("index create skipped (already exists): %s", exc.message)
            return
        raise


def ensure_loaded(client: XvectorClient, cfg: PerfConfig, timeout: float = 300.0) -> None:
    name = cfg.collection_name
    logger.info("load collection %s", name)
    client.load_collection(name)
    client.wait_loaded(name, timeout=timeout)


def ingest_until(
    client: XvectorClient,
    cfg: PerfConfig,
    target_rows: int | None = None,
    log_every_batches: int = 25,
) -> dict[str, Any]:
    """Insert until row_count >= target. Supports resume from current row_count as next id."""
    target = int(target_rows if target_rows is not None else cfg.target_rows)
    name = cfg.collection_name
    current = row_count(client, name)
    if current >= target:
        logger.info("collection %s already has %s rows (>= %s); skip ingest", name, current, target)
        return {"start_rows": current, "end_rows": current, "inserted": 0, "next_id": current}

    start_rows = current
    start_id = current  # ids are 0..N-1 when prepared by this helper
    logger.info(
        "ingest %s: current=%s target=%s batch=%s start_id=%s",
        name,
        current,
        target,
        cfg.prepare_batch,
        start_id,
    )

    inserted = 0
    batches = 0
    t0 = time.time()
    for batch_start, n in batch_ranges(start_id, target, cfg.prepare_batch):
        data = make_entities(batch_start, n, dim=cfg.dim)
        # insert may be slow for large vectors; retry a few times on transient errors
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                client.insert(name, data)
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("insert batch start_id=%s attempt=%s failed: %s", batch_start, attempt + 1, exc)
                time.sleep(1.0 * (attempt + 1))
        if last_err is not None:
            raise RuntimeError(f"insert failed at id={batch_start}: {last_err}") from last_err

        inserted += n
        batches += 1
        if batches % log_every_batches == 0:
            elapsed = max(time.time() - t0, 1e-6)
            rate = inserted / elapsed
            logger.info(
                "ingest progress: +%s rows (id<%s), ~%.0f rows/s, elapsed=%.1fs",
                inserted,
                batch_start + n,
                rate,
                elapsed,
            )

    # stats may lag slightly; prefer logical end id after successful inserts
    end_rows = max(row_count(client, name), start_id + inserted)
    logger.info("ingest done: start=%s end~=%s inserted=%s", start_rows, end_rows, inserted)
    return {
        "start_rows": start_rows,
        "end_rows": end_rows,
        "inserted": inserted,
        "next_id": start_id + inserted,
    }


def prepare_perf_collection(cfg: PerfConfig | None = None) -> dict[str, Any]:
    """
    Ensure collection + HNSW index + >= target_rows + loaded.
    Returns summary including next_id for write traffic.
    """
    cfg = cfg or load_config()
    if not gateway_ready(cfg.host):
        raise RuntimeError(f"Gateway not ready at {cfg.host}. Start with: docker compose up -d --build")

    client = make_client(cfg)
    try:
        ensure_collection(client, cfg)
        ensure_index(client, cfg)
        ingest = ingest_until(client, cfg)
        ensure_loaded(client, cfg)
        final_rows = row_count(client, cfg.collection_name)
        if final_rows < cfg.target_rows:
            # after load, re-check; if still short, fail loudly
            raise RuntimeError(
                f"collection {cfg.collection_name} rowCount={final_rows} < target={cfg.target_rows}"
            )
        next_id = max(ingest["next_id"], final_rows)
        summary = {
            "host": cfg.host,
            "collection": cfg.collection_name,
            "row_count": final_rows,
            "target_rows": cfg.target_rows,
            "next_id": next_id,
            "dim": cfg.dim,
            "ingest": ingest,
        }
        logger.info("prepare complete: %s", summary)
        return summary
    finally:
        client.close()


def locust_command(scenario: str, cfg: PerfConfig | None = None) -> str:
    """Build a copy-pasteable locust Web UI command for one scenario."""
    cfg = cfg or load_config()
    mapping = {
        "write": "locustfile_write.py",
        "read": "locustfile_read.py",
        "mixed": "locustfile_mixed.py",
    }
    if scenario not in mapping:
        raise ValueError(f"unknown scenario: {scenario}")
    locustfile = f"tests/performance_testing/{mapping[scenario]}"
    html = f"tests/performance_testing/reports/{scenario}.html"
    return (
        f"locust -f {locustfile} "
        f"--host {cfg.host} "
        f"--web-host 0.0.0.0 --web-port {cfg.web_port} "
        f"--html {html}"
    )
