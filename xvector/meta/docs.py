from __future__ import annotations

import json
import time
from typing import Any


DOC_USER = "user"
DOC_ROLE = "role"
DOC_DATABASE = "database"
DOC_COLLECTION = "collection"
DOC_PARTITION = "partition"
DOC_ALIAS = "alias"
DOC_INDEX = "index"
DOC_LOAD = "load_state"
DOC_IMPORT = "import_job"


def now_ms() -> int:
    return int(time.time() * 1000)


def make_id(doc_type: str, natural_key: str) -> str:
    # zvec Doc.id rejects ':' and '/'; keep type/key readable and stable.
    safe_key = natural_key.replace("/", "__")
    return f"{doc_type}__{safe_key}"


def encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw)
