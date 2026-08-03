from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from xvector import __version__
from xvector.config import Settings

logger = logging.getLogger(__name__)

_RESOURCE_FIRST_SEGMENT: dict[str, str] = {
    "aliases": "Alias",
    "collections": "Collection",
    "indexes": "Index",
    "partitions": "Partition",
    "roles": "Role",
    "users": "User",
    "entities": "Vector",
    "databases": "Database",
    "import": "Import",
}

_GATEWAY_PATH_TAGS: dict[str, str] = {
    "/healthz": "Gateway / System",
    "/readyz": "Gateway / System",
    "/v2/vectordb/heartbeat": "Gateway / System",
    "/v2/vectordb/auth": "Gateway / System",
    "/openapi/refresh": "Gateway / Admin",
}

# Expected overlaps with Writer/Reader (Gateway locals win). Do not WARNING-spam.
_SILENT_OPENAPI_PATH_CONFLICTS: frozenset[str] = frozenset(
    path for path, tag in _GATEWAY_PATH_TAGS.items() if tag == "Gateway / System"
)

_RESOURCE_ORDER = [
    "System",
    "Admin",
    "Alias",
    "Collection",
    "Database",
    "Import",
    "Index",
    "Other",
    "Partition",
    "Role",
    "User",
    "Vector",
    "Internal",
]


def utc_iso8601_ms() -> str:
    now = datetime.now(timezone.utc)
    ms = int(now.microsecond / 1000)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def build_info_description() -> str:
    return """\
## Base URL

对外访问地址`http://{host}:19530` — only the **Gateway** is exposed externally. Writer/Reader are internal.

## Authentication

Use HTTP Bearer with `USERNAME:PASSWORD`:

```http
Authorization: Bearer ${USERNAME}:${PASSWORD}
```

Bootstrap admin credentials come from env (`XVECTOR_USERNAME` / `XVECTOR_PASSWORD`).
Validate credentials via **Try it out** on `POST /v2/vectordb/auth` (tag `Gateway / System`).
Business APIs under `/v2/vectordb/**` require the same Bearer token (use **Authorize** in Swagger UI).

## Request tracing

Clients may send any of:

- `X-Request-Id` (preferred)
- `X-Trace-Id`
- W3C `traceparent` (trace-id segment is used)

The Gateway reuses a non-empty client id as-is; otherwise it generates `xv-` + 32 hex digits.
Every response includes header `X-Request-Id`. JSON object responses also include body field `requestId`.

## curl example

```bash
curl -sS -X POST 'http://127.0.0.1:19530/v2/vectordb/collections/list' \\
  -H 'Authorization: Bearer root:Xvector' \\
  -H 'Content-Type: application/json' \\
  -H 'X-Request-Id: xv-client-demo-id-please-use-real-hex' \\
  -d '{}'
```

Custom ids are echoed as-is; omit the header to let the server generate `xv-` + uuidhex.

## Read / write routing

- **Writer** tagged operations → write / DDL / import / user / role
- **Reader** tagged operations → search / query / describe / load state reads

## OpenAPI refresh

`POST /openapi/refresh` (tag `Gateway / Admin`, no auth) forces a re-merge of Writer/Reader schemas.
"""


def infer_resource(path: str) -> str:
    """Map API path to resource display name for tags."""
    p = path.split("?", 1)[0]
    if p in _GATEWAY_PATH_TAGS:
        # Caller should use gateway override; keep Other as fallback.
        pass
    if not p.startswith("/v2/vectordb"):
        return "Other"
    rest = p[len("/v2/vectordb") :].lstrip("/")
    if not rest:
        return "Other"
    parts = rest.split("/")
    first = parts[0]
    if first == "jobs" and len(parts) > 1 and parts[1] == "import":
        return "Import"
    if first in _RESOURCE_FIRST_SEGMENT:
        return _RESOURCE_FIRST_SEGMENT[first]
    logger.debug("openapi tag resource fallback for path=%s", path)
    return "Other"


def tag_for_path(path: str, role: str) -> str:
    if role == "Gateway" and path in _GATEWAY_PATH_TAGS:
        return _GATEWAY_PATH_TAGS[path]
    if path.startswith("/internal"):
        return f"{role} / Internal"
    resource = infer_resource(path)
    return f"{role} / {resource}"


def _is_internal_path(path: str) -> bool:
    return path.startswith("/internal/") or path == "/internal"


def _log_path_conflict(path: str, fmt: str) -> None:
    """Warn on unexpected path conflicts; silence expected system/probe overlaps."""
    if path in _SILENT_OPENAPI_PATH_CONFLICTS:
        return
    logger.warning(fmt, path)


def _operation_items(path_item: dict[str, Any]):
    methods = ("get", "post", "put", "delete", "patch", "head", "options", "trace")
    for method in methods:
        op = path_item.get(method)
        if isinstance(op, dict):
            yield method, op


def _apply_tags_and_security(
    paths: dict[str, Any],
    role: str,
    *,
    include_internal: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, item in paths.items():
        if not include_internal and _is_internal_path(path):
            continue
        # Never expose catch-all proxy style path (FastAPI: {full_path:path})
        if "full_path" in path:
            continue
        new_item = copy.deepcopy(item)
        tag = tag_for_path(path, role)
        for _method, op in _operation_items(new_item):
            op["tags"] = [tag]
            # security for business + auth; health/admin refresh stay open
            if path in {"/healthz", "/readyz", "/openapi/refresh"}:
                op.pop("security", None)
            elif path.startswith("/v2/vectordb"):
                op["security"] = [{"BearerAuth": []}]
            elif path.startswith("/internal"):
                op.pop("security", None)
        out[path] = new_item
    return out


def _tag_sort_key(tag: str) -> tuple:
    # Gateway System/Admin first, then Role alpha, then resource order
    if " / " not in tag:
        return (2, tag, 99, tag)
    role, resource = tag.split(" / ", 1)
    role_rank = {"Gateway": 0, "Writer": 1, "Reader": 2}.get(role, 3)
    try:
        res_rank = _RESOURCE_ORDER.index(resource)
    except ValueError:
        res_rank = 50
    if role == "Gateway" and resource in {"System", "Admin"}:
        return (0, role_rank, res_rank, tag)
    return (1, role_rank, res_rank, tag)


def _collect_tags(paths: dict[str, Any]) -> list[dict[str, str]]:
    seen: set[str] = set()
    for item in paths.values():
        for _m, op in _operation_items(item):
            for t in op.get("tags") or []:
                seen.add(t)
    ordered = sorted(seen, key=_tag_sort_key)
    return [{"name": t} for t in ordered]


def merge_schemas(
    gateway_schema: dict[str, Any],
    writer_schema: dict[str, Any] | None,
    reader_schema: dict[str, Any] | None,
    *,
    include_internal: bool = False,
) -> dict[str, Any]:
    paths: dict[str, Any] = {}

    gw_paths = _apply_tags_and_security(
        gateway_schema.get("paths") or {},
        "Gateway",
        include_internal=include_internal,
    )
    paths.update(gw_paths)

    # Gateway locals always win for overlapping paths (healthz/readyz/heartbeat/auth).
    # Writer vs Reader conflicts: Writer wins (route table is normally disjoint).
    if writer_schema:
        w_paths = _apply_tags_and_security(
            writer_schema.get("paths") or {},
            "Writer",
            include_internal=include_internal,
        )
        for p, item in w_paths.items():
            if p in paths:
                _log_path_conflict(p, "openapi path conflict, keeping Gateway/existing: %s")
                continue
            paths[p] = item

    if reader_schema:
        r_paths = _apply_tags_and_security(
            reader_schema.get("paths") or {},
            "Reader",
            include_internal=include_internal,
        )
        for p, item in r_paths.items():
            if p in paths:
                _log_path_conflict(
                    p, "openapi path conflict (Reader vs existing), keeping existing: %s"
                )
                continue
            paths[p] = item

    components: dict[str, Any] = {}
    for schema in (gateway_schema, writer_schema, reader_schema):
        if not schema:
            continue
        src = schema.get("components") or {}
        for key, value in src.items():
            if key == "securitySchemes":
                continue
            if isinstance(value, dict):
                components.setdefault(key, {}).update(value)
            else:
                components[key] = value

    components["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "USERNAME:PASSWORD",
            "description": "Authorization: Bearer ${USERNAME}:${PASSWORD}",
        }
    }

    return {
        "openapi": gateway_schema.get("openapi", "3.1.0"),
        "info": {
            "title": "Xvector API",
            "version": __version__,
            "description": build_info_description(),
        },
        "paths": paths,
        "components": components,
        "tags": _collect_tags(paths),
    }


class OpenAPIMerger:
    """Fetch Writer/Reader OpenAPI, merge with Gateway locals, cache + refresh."""

    def __init__(self, app: FastAPI, settings: Settings):
        self.app = app
        self.settings = settings
        self._lock = asyncio.Lock()
        self._schema: dict[str, Any] | None = None
        self._last_ok_at: str | None = None
        self._refresh_task: asyncio.Task | None = None

    @property
    def schema(self) -> dict[str, Any] | None:
        return self._schema

    def local_gateway_schema(self) -> dict[str, Any]:
        return get_openapi(
            title="Xvector Gateway",
            version=__version__,
            routes=self.app.routes,
        )

    def cached_or_local(self) -> dict[str, Any]:
        if self._schema is not None:
            return self._schema
        # First boot / no successful merge yet: Gateway locals only.
        local = merge_schemas(
            self.local_gateway_schema(),
            None,
            None,
            include_internal=self.settings.openapi_include_internal,
        )
        return local

    async def _fetch_once(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError(f"openapi root must be object: {url}")
        return data

    async def _fetch_with_retries(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        retries = max(1, self.settings.openapi_refresh_retries)
        interval = max(0.0, self.settings.openapi_refresh_retry_interval_seconds)
        timeout = self.settings.openapi_fetch_timeout_seconds
        writer_url = f"{self.settings.writer_url.rstrip('/')}/openapi.json"
        reader_url = f"{self.settings.reader_url.rstrip('/')}/openapi.json"
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    writer_schema, reader_schema = await asyncio.gather(
                        self._fetch_once(client, writer_url),
                        self._fetch_once(client, reader_url),
                    )
                return writer_schema, reader_schema
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning(
                    "openapi fetch attempt %s/%s failed: %s",
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries and interval > 0:
                    await asyncio.sleep(interval)
        raise RuntimeError(f"openapi fetch failed after {retries} attempts: {last_err}")

    async def refresh(self) -> dict[str, Any]:
        """
        Merge once (with retries). On success update cache.
        On failure keep previous cache.

        Returns data payload for /openapi/refresh.
        """
        async with self._lock:
            try:
                writer_schema, reader_schema = await self._fetch_with_retries()
                merged = merge_schemas(
                    self.local_gateway_schema(),
                    writer_schema,
                    reader_schema,
                    include_internal=self.settings.openapi_include_internal,
                )
                self._schema = merged
                self._last_ok_at = utc_iso8601_ms()
                self.app.state.merged_openapi = merged
                return {
                    "ok": True,
                    "paths": len(merged.get("paths") or {}),
                    "refreshedAt": self._last_ok_at,
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning("openapi refresh failed; keeping previous cache: %s", exc)
                return {
                    "ok": False,
                    "error": str(exc),
                    "paths": len((self._schema or {}).get("paths") or {}),
                    "refreshedAt": self._last_ok_at,
                }

    async def start_background_refresh(self) -> None:
        # Initial merge (may fail if W/R not ready yet).
        await self.refresh()
        seconds = self.settings.openapi_refresh_seconds
        if seconds <= 0:
            return

        async def _loop():
            while True:
                try:
                    await asyncio.sleep(seconds)
                    await self.refresh()
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001
                    logger.exception("openapi background refresh loop error")

        def _done(task: asyncio.Task) -> None:
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                logger.error("openapi refresh task exited: %s", exc)

        self._refresh_task = asyncio.create_task(_loop(), name="openapi-refresh-loop")
        self._refresh_task.add_done_callback(_done)

    async def stop_background_refresh(self) -> None:
        t = self._refresh_task
        self._refresh_task = None
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.exception("openapi refresh task shutdown error")
