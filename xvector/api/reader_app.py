from __future__ import annotations

import asyncio
import logging

from fastapi import Request

from xvector.api.app_factory import build_context, create_base_app
from xvector.api.health import mount_health
from xvector.api.v2.deps import Services
from xvector.api.v2.routes import build_reader_router
from xvector.common.models.internal import InternalCollectionRequest
from xvector.common.paths import DEFAULT_PARTITION
from xvector.config import get_settings
from xvector.engine.collection_mgr import CollectionFencedError
from xvector.meta.store import MetaNotReadyError

logger = logging.getLogger(__name__)


def create_app():
    settings = get_settings()
    ctx = build_context(settings, role="reader")
    # Default: close /docs & /redoc UI; keep /openapi.json for Gateway merge.
    docs_url = "/docs" if settings.reader_docs_ui else None
    app = create_base_app(
        "Xvector Reader",
        docs_url=docs_url,
        redoc_url=None,
        openapi_url="/openapi.json",
        inject_request_id=False,
    )
    svc = Services(ctx)
    mount_health(app, ctx, role="reader")
    app.include_router(build_reader_router(svc))
    app.state.ctx = ctx
    app.state.svc = svc

    refresh_task = {"task": None}
    # Serialize fence/open/refresh so writer close cannot race refresh reopen.
    coord_lock = asyncio.Lock()

    @app.on_event("startup")
    async def _startup():
        async def _loop():
            meta_wait_logged = False
            while True:
                try:
                    await asyncio.sleep(max(1, settings.reader_refresh_seconds))
                    async with coord_lock:
                        if not ctx.meta.is_open:
                            ctx.meta.open()
                            logger.info("reader meta opened")
                            meta_wait_logged = False
                        else:
                            ctx.meta.reopen()
                        # open loaded collections (skip fenced — writer may be mutating)
                        for db in ctx.catalog.list_databases():
                            for coll in ctx.catalog.list_collections(db):
                                st = ctx.catalog.get_load_state(db, coll)
                                if not st.get("loaded") and not settings.auto_load:
                                    ctx.collections.close_collection(db, coll)
                                    continue
                                parts = st.get("partition_names") or ctx.catalog.list_partitions(db, coll)
                                if not parts:
                                    parts = [DEFAULT_PARTITION]
                                for p in parts:
                                    if ctx.collections.is_fenced(db, coll, p):
                                        continue
                                    try:
                                        # Close first so Writer can exclusively flush WAL.
                                        ctx.collections.close_partition(db, coll, p, flush=False)
                                        if ctx.collections.has_wal(db, coll, p):
                                            await ctx.seal_partitions_via_writer(
                                                db, coll, [p], require_ok=False
                                            )
                                        # Seal may fail / race mid-write — never RO-open with WAL.
                                        if ctx.collections.has_wal(db, coll, p):
                                            logger.warning(
                                                "skip RO open with pending WAL %s/%s/%s "
                                                "(wait for writer seal)",
                                                db,
                                                coll,
                                                p,
                                            )
                                            continue
                                        ctx.collections.open_partition(db, coll, p, force_reopen=True)
                                    except CollectionFencedError:
                                        continue
                                    except Exception:  # noqa: BLE001
                                        logger.warning(
                                            "open failed %s/%s/%s", db, coll, p, exc_info=True
                                        )
                except asyncio.CancelledError:
                    raise
                except MetaNotReadyError:
                    # Expected until writer publishes /data/meta/catalog_snapshot.json.
                    if not meta_wait_logged:
                        logger.warning("reader meta snapshot not ready yet; will retry")
                        meta_wait_logged = True
                    else:
                        logger.debug("reader meta snapshot still not ready; retrying")
                except Exception:  # noqa: BLE001
                    # Catch+log+continue — never let refresh kill lifespan / process.
                    logger.exception("reader refresh loop error")

        def _on_refresh_done(task: asyncio.Task) -> None:
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                logger.error("reader refresh task exited unexpectedly: %s", exc)

        task = asyncio.create_task(_loop(), name="reader-refresh-loop")
        task.add_done_callback(_on_refresh_done)
        refresh_task["task"] = task

    @app.on_event("shutdown")
    async def _shutdown():
        t = refresh_task.get("task")
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.exception("reader refresh task shutdown error")

    @app.post("/internal/open", include_in_schema=False)
    async def internal_open(body: InternalCollectionRequest):
        db = body.dbName
        coll = body.collectionName
        parts = body.partitionNames or [DEFAULT_PARTITION]
        async with coord_lock:
            ctx.collections.unfence_partitions(db, coll, list(parts))
            # Do NOT call Writer here: Writer often awaits this endpoint after a write,
            # and a nested /internal/flush would deadlock a single-worker Writer.
            # Writer must flush WAL before notifying; refresh loop seals leftover WAL.
            for p in parts:
                if ctx.collections.has_wal(db, coll, p):
                    logger.warning(
                        "skip RO open with pending WAL %s/%s/%s (wait for seal/refresh)",
                        db,
                        coll,
                        p,
                    )
                    continue
                try:
                    ctx.collections.open_partition(db, coll, p, force_reopen=True)
                except Exception as e:  # noqa: BLE001
                    logger.warning("internal open failed: %s", e)
                    return {"ok": False, "error": str(e)}
        return {"ok": True}

    @app.post("/internal/close", include_in_schema=False)
    async def internal_close(body: InternalCollectionRequest):
        db = body.dbName
        coll = body.collectionName
        parts = body.partitionNames
        fence = True if body.fence is None else body.fence
        async with coord_lock:
            if fence:
                ctx.collections.fence_partitions(db, coll, list(parts) if parts else None)
            elif parts:
                for p in parts:
                    ctx.collections.close_partition(db, coll, p)
            else:
                ctx.collections.close_collection(db, coll)
        return {"ok": True}

    @app.post("/internal/unfence", include_in_schema=False)
    async def internal_unfence(body: InternalCollectionRequest):
        db = body.dbName
        coll = body.collectionName
        parts = body.partitionNames
        async with coord_lock:
            ctx.collections.unfence_partitions(db, coll, list(parts) if parts else None)
        return {"ok": True}

    @app.post("/internal/reload", include_in_schema=False)
    async def internal_reload(request: Request):
        _ = await request.body()
        async with coord_lock:
            try:
                if ctx.meta.is_open:
                    ctx.meta.reopen()
                else:
                    ctx.meta.open()
            except MetaNotReadyError:
                return {"ok": False, "error": "meta not ready"}
            except Exception as e:  # noqa: BLE001
                logger.warning("internal reload meta failed: %s", e)
                return {"ok": False, "error": str(e)}
            # Close first; seal any pending WAL via Writer before RO reopen.
            opened = ctx.collections.open_keys()
            dirty: list[tuple[str, str, str]] = []
            for db, coll, part in opened:
                ctx.collections.close_partition(db, coll, part, flush=False)
                if ctx.collections.has_wal(db, coll, part):
                    dirty.append((db, coll, part))
            for db, coll, part in dirty:
                await ctx.seal_partitions_via_writer(db, coll, [part], require_ok=False)
            for db, coll, part in opened:
                if ctx.collections.is_fenced(db, coll, part):
                    continue
                if ctx.collections.has_wal(db, coll, part):
                    logger.warning(
                        "skip reload RO open with pending WAL %s/%s/%s",
                        db,
                        coll,
                        part,
                    )
                    continue
                try:
                    ctx.collections.open_partition(db, coll, part, force_reopen=True)
                except CollectionFencedError:
                    continue
                except Exception:  # noqa: BLE001
                    logger.warning("reload reopen failed %s/%s/%s", db, coll, part, exc_info=True)
        return {"ok": True}

    return app
