from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

from xvector.config import get_settings


def generate_salt(nbytes: int = 16) -> str:
    return base64.b64encode(secrets.token_bytes(nbytes)).decode("ascii")


def hash_password(password: str, salt: str, iterations: int | None = None) -> str:
    settings = get_settings()
    iters = iterations or settings.password_iterations
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(salt.encode("ascii")),
        iters,
    )
    return base64.b64encode(dk).decode("ascii")


def verify_password(password: str, salt: str, password_hash: str, iterations: int | None = None) -> bool:
    expected = hash_password(password, salt, iterations=iterations)
    return hmac.compare_digest(expected, password_hash)


def bootstrap_matches(username: str, password: str) -> bool:
    """Env hot-reload override: re-read env each call."""
    env_user = os.getenv("XVECTOR_USERNAME", get_settings().username)
    env_pass = os.getenv("XVECTOR_PASSWORD", get_settings().password)
    return username == env_user and password == env_pass
