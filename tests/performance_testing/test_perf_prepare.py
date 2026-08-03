"""Prepare perf collection and print Locust Web UI commands (scheme B)."""

from __future__ import annotations

import pytest

from tests.performance_testing.common.config import load_config
from tests.performance_testing.common.prepare import locust_command

SCENARIOS = ("write", "read", "mixed")


@pytest.mark.performance
@pytest.mark.timeout(0)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_prepare_and_print_locust_command(prepared_collection, scenario: str, capsys: pytest.CaptureFixture[str]):
    """
    Ensure base data is ready, then print a locust command for the scenario.

    Does NOT run the full Locust load test inside pytest.
    """
    cfg = load_config()
    summary = prepared_collection
    cmd = locust_command(scenario, cfg)

    # Make sure the printed env hints match the prepared collection for write traffic / get PKs.
    export_next = f"export XVECTOR_PERF_NEXT_ID={summary['next_id']}"
    export_max = f"export XVECTOR_PERF_MAX_ID={max(summary['row_count'] - 1, 0)}"

    banner = "\n".join(
        [
            "",
            "=" * 72,
            f"Xvector performance prepare OK — scenario={scenario}",
            f"host={cfg.host}",
            f"collection={summary['collection']}",
            f"row_count={summary['row_count']} (target={summary['target_rows']})",
            f"dim={summary['dim']}",
            export_next,
            export_max,
            "",
            "Start Locust Web UI (then open http://localhost:8089 and click Start):",
            cmd,
            "",
            "Reports will be written under tests/performance_testing/reports/",
            f"  - HTML: tests/performance_testing/reports/{scenario}.html",
            f"  - JSON: tests/performance_testing/reports/{scenario}_steps.json",
            "=" * 72,
            "",
        ]
    )
    # Print even under pytest capture so `-s` is optional when using capfd; force via print + capsys disable.
    with capsys.disabled():
        print(banner)

    assert summary["row_count"] >= cfg.target_rows
    assert "locust -f" in cmd
    assert scenario in cmd or f"locustfile_{scenario}.py" in cmd
