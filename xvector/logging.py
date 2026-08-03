from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from xvector.config import get_settings


class UTCISO8601Formatter(logging.Formatter):
    """Format asctime as UTC ISO8601 with millisecond precision and Z suffix."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        ms = int(record.msecs)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    app_handler = logging.StreamHandler(sys.stdout)
    app_handler.setFormatter(
        UTCISO8601Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(app_handler)

    # Access logger: message is already a full line (UTC + client + trace + request).
    access = logging.getLogger("xvector.access")
    access.handlers.clear()
    access.propagate = False
    access.setLevel(logging.INFO)
    access_handler = logging.StreamHandler(sys.stdout)
    access_handler.setFormatter(logging.Formatter("%(message)s"))
    access.addHandler(access_handler)

    # Never log Authorization / passwords via noisy httpx if enabled later.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
