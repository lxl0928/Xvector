from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from xvector.common.errors import NotFoundError, ParamError
from xvector.common.paths import DEFAULT_DB, DEFAULT_PARTITION
from xvector.meta import docs
from xvector.services.context import AppContext
from xvector.services.vector import VectorService

logger = logging.getLogger(__name__)


class ImportService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._vector = VectorService(ctx)

    def _db(self, body: dict[str, Any]) -> str:
        return body.get("dbName") or body.get("db_name") or DEFAULT_DB

    async def create(self, body: dict[str, Any]) -> dict[str, Any]:
        db = self._db(body)
        coll = body.get("collectionName") or body.get("collection_name")
        coll = self.ctx.catalog.resolve_collection_name(db, coll)
        self.ctx.catalog.require_collection(db, coll)
        files = body.get("files") or body.get("filePaths") or []
        if not files:
            raise ParamError("files required")
        fmt = (body.get("format") or "json").lower()
        if fmt not in {"json", "jsonl"}:
            raise ParamError("only json/jsonl supported")
        job_id = str(uuid.uuid4())
        part = body.get("partitionName") or DEFAULT_PARTITION
        job = {
            "job_id": job_id,
            "db_name": db,
            "collection_name": coll,
            "partition_name": part,
            "files": list(files),
            "format": fmt,
            "state": "Pending",
            "progress": 0,
            "imported_rows": 0,
            "total_rows": 0,
            "error_message": None,
            "created_at": docs.now_ms(),
            "updated_at": docs.now_ms(),
            "finished_at": None,
        }
        job_dir = self.ctx.paths.db_imports_dir(db, job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.manifest.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        self.ctx.catalog.put_import_job(job)
        threading.Thread(target=self._run_job, args=(job_id,), daemon=True).start()
        return {"jobId": job_id}

    async def get_progress(self, body: dict[str, Any]) -> dict[str, Any]:
        job_id = body.get("jobId") or body.get("job_id")
        job = self.ctx.catalog.get_import_job(job_id)
        if not job:
            raise NotFoundError(f"import job not found: {job_id}")
        return {
            "jobId": job_id,
            "state": job.get("state"),
            "progress": job.get("progress", 0),
            "importedRows": job.get("imported_rows", 0),
            "totalRows": job.get("total_rows", 0),
            "reason": job.get("error_message") or "",
        }

    async def list(self, body: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        body = body or {}
        db = body.get("dbName")
        coll = body.get("collectionName")
        jobs = self.ctx.catalog.list_import_jobs(db, coll)
        return [
            {
                "jobId": j["job_id"],
                "collectionName": j.get("collection_name"),
                "state": j.get("state"),
                "progress": j.get("progress", 0),
            }
            for j in jobs
        ]

    def _run_job(self, job_id: str) -> None:
        import asyncio

        try:
            asyncio.run(self._run_job_async(job_id))
        except Exception as e:  # noqa: BLE001
            logger.exception("import job failed %s", job_id)
            job = self.ctx.catalog.get_import_job(job_id) or {"job_id": job_id}
            job["state"] = "Failed"
            job["error_message"] = str(e)
            job["updated_at"] = docs.now_ms()
            job["finished_at"] = docs.now_ms()
            self.ctx.catalog.put_import_job(job)

    async def _run_job_async(self, job_id: str) -> None:
        job = self.ctx.catalog.get_import_job(job_id)
        if not job:
            return
        try:
            local_files: list[Path] = []
            for f in job["files"]:
                if str(f).startswith("s3://"):
                    job["state"] = "Downloading"
                    job["updated_at"] = docs.now_ms()
                    self.ctx.catalog.put_import_job(job)
                    local_files.append(self._download_s3(str(f), job_id))
                else:
                    local_files.append(Path(f))

            job["state"] = "Parsing"
            job["updated_at"] = docs.now_ms()
            self.ctx.catalog.put_import_job(job)

            rows: list[dict[str, Any]] = []
            for path in local_files:
                rows.extend(self._parse_file(path, job["format"]))
            job["total_rows"] = len(rows)
            job["state"] = "Importing"
            job["updated_at"] = docs.now_ms()
            self.ctx.catalog.put_import_job(job)

            batch = 500
            imported = 0
            for i in range(0, len(rows), batch):
                chunk = rows[i : i + batch]
                await self._vector.insert(
                    {
                        "dbName": job["db_name"],
                        "collectionName": job["collection_name"],
                        "partitionName": job.get("partition_name") or DEFAULT_PARTITION,
                        "data": chunk,
                    }
                )
                imported += len(chunk)
                job["imported_rows"] = imported
                job["progress"] = int(imported * 100 / max(job["total_rows"], 1))
                job["updated_at"] = docs.now_ms()
                self.ctx.catalog.put_import_job(job)

            job["state"] = "Completed"
            job["progress"] = 100
            job["finished_at"] = docs.now_ms()
            job["updated_at"] = docs.now_ms()
            self.ctx.catalog.put_import_job(job)
        except Exception as e:  # noqa: BLE001
            job["state"] = "Failed"
            job["error_message"] = str(e)
            job["finished_at"] = docs.now_ms()
            job["updated_at"] = docs.now_ms()
            self.ctx.catalog.put_import_job(job)
            raise

    def _parse_file(self, path: Path, fmt: str) -> list[dict[str, Any]]:
        if not path.exists():
            raise ParamError(f"import file not found: {path}")
        text = path.read_text(encoding="utf-8")
        if fmt == "jsonl":
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
            return rows
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "rows" in data:
            return list(data["rows"])
        if isinstance(data, dict) and "data" in data:
            return list(data["data"])
        raise ParamError("JSON import must be array or {rows:[...]}")

    def _download_s3(self, uri: str, job_id: str) -> Path:
        settings = self.ctx.settings
        if not settings.s3_enabled:
            raise ParamError("S3 is not configured")
        import boto3

        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        dest = self.ctx.paths.tmp_dir / job_id / Path(key).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region or None,
            use_ssl=settings.s3_secure,
        )
        client.download_file(bucket, key, str(dest))
        return dest
