from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_initialized = False


def ensure_init() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        import zvec

        try:
            zvec.init()
        except RuntimeError as e:
            # already initialized in-process
            if "already" not in str(e).lower():
                raise
        _initialized = True
        logger.info("zvec initialized")


def create_and_open(path: str, schema: Any, read_only: bool = False):
    ensure_init()
    import zvec

    option = zvec.CollectionOption(read_only=read_only, enable_mmap=True)
    return zvec.create_and_open(path=path, schema=schema, option=option)


def open_collection(path: str, read_only: bool = False):
    ensure_init()
    import zvec

    option = zvec.CollectionOption(read_only=read_only, enable_mmap=True)
    if hasattr(zvec, "open"):
        return zvec.open(path=path, option=option)
    # Fallback naming
    return zvec.open_collection(path=path, option=option)


def close_collection(coll: Any) -> None:
    """Release a zvec collection handle.

    zvec 0.6 has no close(); process-exclusive LOCK is released when the
    Collection object is destroyed (and GC'd). destroy() deletes data — do not use.
    """
    if coll is None:
        return
    try:
        if hasattr(coll, "flush"):
            try:
                coll.flush()
            except Exception:  # noqa: BLE001
                # Leftover WAL breaks Reader RO open (IDMap put in recovery).
                logger.exception("flush before close failed")
    finally:
        try:
            del coll
        except Exception:  # noqa: BLE001
            pass
        import gc

        gc.collect()
