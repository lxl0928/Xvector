"""Write Locust HTML report and staircase summary JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tests.performance_testing.common.config import REPORTS_DIR

logger = logging.getLogger(__name__)

_written_scenarios: set[str] = set()


def ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _scenario_name(summary: dict[str, Any]) -> str:
    return str(summary.get("scenario") or "perf")


def write_step_summary(summary: dict[str, Any], path: Path | None = None) -> Path:
    ensure_reports_dir()
    scenario = _scenario_name(summary)
    out = path or (REPORTS_DIR / f"{scenario}_steps.json")
    payload = dict(summary)
    # human-friendly aliases matching DESIGN wording
    payload["effective_result_users"] = summary.get("effective_users")
    payload["untouched_latency_limit_label"] = (
        "未触达延迟上限" if summary.get("untouched_latency_limit") else None
    )
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("wrote step summary %s", out)
    return out


def write_html_report(environment: Any, path: Path | None = None, scenario: str = "perf") -> Path | None:
    """Best-effort Locust HTML report. May no-op if locust.html API differs."""
    ensure_reports_dir()
    out = path or (REPORTS_DIR / f"{scenario}.html")
    if environment is None:
        return None
    try:
        from locust.html import get_html_report  # type: ignore

        html = get_html_report(environment, show_download_link=False)
        out.write_text(html, encoding="utf-8")
        logger.info("wrote html report %s", out)
        return out
    except Exception as exc:  # noqa: BLE001
        # `--html` on the CLI still produces a report; this is a backup.
        logger.warning("could not write locust html via API (%s); rely on --html if set", exc)
        return None


def _overall_interface_stats(environment: Any) -> dict[str, Any]:
    """Pull Locust cumulative per-name stats for the JSON summary."""
    stats_obj = getattr(environment, "stats", None) if environment is not None else None
    if stats_obj is None:
        return {}
    out: dict[str, Any] = {}
    entries = getattr(stats_obj, "entries", {}) or {}
    for key, entry in entries.items():
        name = key[1] if isinstance(key, tuple) and len(key) >= 2 else str(key)
        if name == "Aggregated":
            continue
        out[name] = {
            "num_requests": getattr(entry, "num_requests", 0),
            "num_failures": getattr(entry, "num_failures", 0),
            "avg_response_time_ms": getattr(entry, "avg_response_time", None),
            "min_response_time_ms": getattr(entry, "min_response_time", None),
            "max_response_time_ms": getattr(entry, "max_response_time", None),
            "current_rps": getattr(entry, "current_rps", None),
        }
    total = getattr(stats_obj, "total", None)
    if total is not None:
        out["Aggregated"] = {
            "num_requests": getattr(total, "num_requests", 0),
            "num_failures": getattr(total, "num_failures", 0),
            "avg_response_time_ms": getattr(total, "avg_response_time", None),
        }
    return out


def write_reports(environment: Any, summary: dict[str, Any]) -> dict[str, str]:
    scenario = _scenario_name(summary)
    if scenario in _written_scenarios:
        return {
            "json": str(REPORTS_DIR / f"{scenario}_steps.json"),
            "html": str(REPORTS_DIR / f"{scenario}.html"),
        }
    enriched = dict(summary)
    enriched["overall_by_interface"] = _overall_interface_stats(environment)
    json_path = write_step_summary(enriched)
    html_path = write_html_report(environment, scenario=scenario)
    _written_scenarios.add(scenario)
    result = {"json": str(json_path)}
    if html_path is not None:
        result["html"] = str(html_path)
    return result
