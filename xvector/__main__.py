from __future__ import annotations

import argparse
import logging
import os
import threading

import uvicorn

from xvector.config import get_settings, listen_port
from xvector.logging import setup_logging

logger = logging.getLogger(__name__)


def _install_thread_excepthook() -> None:
    """Log uncaught thread exceptions instead of silently dying (Py3.8+)."""

    def _hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit:
            return
        logger.error(
            "unhandled thread exception in %s",
            args.thread.name if args.thread else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _hook


def main() -> None:
    parser = argparse.ArgumentParser(description="Xvector service")
    parser.add_argument("--role", choices=["gateway", "writer", "reader"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.role:
        os.environ["XVECTOR_ROLE"] = args.role
        get_settings.cache_clear()

    setup_logging()
    _install_thread_excepthook()
    settings = get_settings()
    if not settings.role:
        raise SystemExit("XVECTOR_ROLE must be gateway|writer|reader")

    module = {
        "gateway": "xvector.api.gateway_app:create_app",
        "writer": "xvector.api.writer_app:create_app",
        "reader": "xvector.api.reader_app:create_app",
    }[settings.role]

    port = args.port or listen_port(settings)
    # Single-process serve: request handlers must not exit the container on errors.
    # Disable uvicorn access log; TraceAccessMiddleware emits Start/End lines instead.
    uvicorn.run(
        module,
        factory=True,
        host=args.host,
        port=port,
        log_level=settings.log_level.lower(),
        access_log=False,
        # Keep worker alive on handler faults; our app-level handlers return JSON 500.
        timeout_keep_alive=5,
    )


if __name__ == "__main__":
    main()
