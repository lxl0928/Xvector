from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import milvus_schema


def test_import_jsonl(client, unique_name, tmp_path: Path):
    name = unique_name
    client.create_collection(name, schema=milvus_schema(dim=4))
    client.create_index(name, "vector", index_type="FLAT", metric_type="L2")
    client.load_collection(name)

    # Write into shared compose volume path if available; otherwise skip with guidance.
    # Default compose mounts named volume — host path unknown. Use /data/imports via docker exec in CI.
    # For local pytest against compose, mount an extra bind in override or write via writer.
    import_dir = Path("/data/imports")
    if not import_dir.exists():
        # fallback: skip when not inside container shared FS
        import pytest

        pytest.skip("Need shared /data/imports visible to writer container for import E2E")

    f = import_dir / f"{name}.jsonl"
    rows = [
        {"id": 1, "vector": [1, 0, 0, 0]},
        {"id": 2, "vector": [0, 1, 0, 0]},
    ]
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    job = client.create_import_job(name, files=[str(f)], format="jsonl")
    prog = client.wait_import_complete(job["jobId"], timeout=60)
    assert prog["state"] == "Completed"
    client.drop_collection(name)
