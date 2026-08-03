from __future__ import annotations

from typing import Callable

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from xvector.auth.password import bootstrap_matches, verify_password
from xvector.common.errors import CODE_UNAUTHORIZED
from xvector.config import get_settings


def parse_bearer(authorization: str | None) -> tuple[str, str] | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    if ":" not in token:
        return None
    username, password = token.split(":", 1)
    return username, password


async def authenticate_via_writer(username: str, password: str) -> bool:
    if bootstrap_matches(username, password):
        return True
    settings = get_settings()
    headers = {}
    if settings.internal_token:
        headers["X-Internal-Token"] = settings.internal_token
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.writer_url}/internal/auth/verify",
            json={"username": username, "password": password},
            headers=headers,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("ok"))


def verify_local_user(user_doc: dict | None, username: str, password: str) -> bool:
    if bootstrap_matches(username, password):
        return True
    if not user_doc:
        return False
    return verify_password(password, user_doc["password_salt"], user_doc["password_hash"])


def auth_middleware(verify_fn: Callable):
    async def _middleware(request: Request, call_next):
        path = request.url.path
        if path in {"/healthz", "/readyz"} or path.startswith("/internal/"):
            return await call_next(request)
        creds = parse_bearer(request.headers.get("Authorization"))
        if not creds:
            return JSONResponse(
                status_code=401,
                content={"code": CODE_UNAUTHORIZED, "message": "missing or invalid Authorization Bearer"},
            )
        username, password = creds
        ok = await verify_fn(username, password)
        if not ok:
            return JSONResponse(
                status_code=401,
                content={"code": CODE_UNAUTHORIZED, "message": "authentication failed"},
            )
        request.state.username = username
        return await call_next(request)

    return _middleware
