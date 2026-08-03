from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    username: str
    password: str
    data_dir: str
    http_port: int
    writer_url: str
    reader_url: str
    writer_port: int
    reader_port: int
    role: str
    auto_load: bool
    reader_refresh_seconds: int
    meta_refresh_seconds: int
    internal_token: str
    log_level: str
    password_iterations: int
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    s3_region: str
    s3_secure: bool
    # OpenAPI merge / docs / access log (DESIGN-api-docs-and-logging §4.6)
    openapi_refresh_seconds: int
    openapi_refresh_retries: int
    openapi_refresh_retry_interval_seconds: float
    openapi_fetch_timeout_seconds: float
    docs_enabled: bool
    redoc_enabled: bool
    writer_docs_ui: bool
    reader_docs_ui: bool
    openapi_include_internal: bool
    access_log_enabled: bool

    @property
    def s3_enabled(self) -> bool:
        return bool(self.s3_endpoint and self.s3_access_key and self.s3_secret_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    role = os.getenv("XVECTOR_ROLE", "").strip().lower()
    return Settings(
        username=os.getenv("XVECTOR_USERNAME", "root"),
        password=os.getenv("XVECTOR_PASSWORD", "Xvector"),
        data_dir=os.getenv("XVECTOR_DATA_DIR", "/data"),
        http_port=_env_int("XVECTOR_HTTP_PORT", 19530),
        writer_url=os.getenv("XVECTOR_WRITER_URL", "http://writer:18081"),
        reader_url=os.getenv("XVECTOR_READER_URL", "http://reader:18082"),
        writer_port=_env_int("XVECTOR_WRITER_PORT", 18081),
        reader_port=_env_int("XVECTOR_READER_PORT", 18082),
        role=role,
        auto_load=_env_bool("XVECTOR_AUTO_LOAD", False),
        reader_refresh_seconds=_env_int("XVECTOR_READER_REFRESH_SECONDS", 10),
        meta_refresh_seconds=_env_int("XVECTOR_META_REFRESH_SECONDS", 10),
        internal_token=os.getenv("XVECTOR_INTERNAL_TOKEN", ""),
        log_level=os.getenv("XVECTOR_LOG_LEVEL", "INFO").upper(),
        password_iterations=_env_int("XVECTOR_PASSWORD_ITERATIONS", 200_000),
        s3_endpoint=os.getenv("XVECTOR_S3_ENDPOINT", ""),
        s3_access_key=os.getenv("XVECTOR_S3_ACCESS_KEY", ""),
        s3_secret_key=os.getenv("XVECTOR_S3_SECRET_KEY", ""),
        s3_bucket=os.getenv("XVECTOR_S3_BUCKET", ""),
        s3_region=os.getenv("XVECTOR_S3_REGION", ""),
        s3_secure=_env_bool("XVECTOR_S3_SECURE", False),
        openapi_refresh_seconds=_env_int("XVECTOR_OPENAPI_REFRESH_SECONDS", 60),
        openapi_refresh_retries=_env_int("XVECTOR_OPENAPI_REFRESH_RETRIES", 3),
        openapi_refresh_retry_interval_seconds=_env_float(
            "XVECTOR_OPENAPI_REFRESH_RETRY_INTERVAL_SECONDS", 1.0
        ),
        openapi_fetch_timeout_seconds=_env_float("XVECTOR_OPENAPI_FETCH_TIMEOUT_SECONDS", 5.0),
        docs_enabled=_env_bool("XVECTOR_DOCS_ENABLED", True),
        redoc_enabled=_env_bool("XVECTOR_REDOC_ENABLED", False),
        writer_docs_ui=_env_bool("XVECTOR_WRITER_DOCS_UI", False),
        reader_docs_ui=_env_bool("XVECTOR_READER_DOCS_UI", False),
        openapi_include_internal=_env_bool("XVECTOR_OPENAPI_INCLUDE_INTERNAL", False),
        access_log_enabled=_env_bool("XVECTOR_ACCESS_LOG_ENABLED", True),
    )


def listen_port(settings: Settings | None = None) -> int:
    s = settings or get_settings()
    if s.role == "gateway":
        return s.http_port
    if s.role == "writer":
        return s.writer_port
    if s.role == "reader":
        return s.reader_port
    raise ValueError(f"Unknown XVECTOR_ROLE: {s.role!r}")
