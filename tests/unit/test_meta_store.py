from __future__ import annotations

import json
from pathlib import Path

import pytest

from xvector.common.paths import DataPaths
from xvector.meta.store import MetaNotReadyError, MetaStore


def test_read_only_open_raises_when_snapshot_missing(tmp_path: Path):
    paths = DataPaths(str(tmp_path))
    store = MetaStore(paths, read_only=True)
    with pytest.raises(MetaNotReadyError, match="meta snapshot missing"):
        store.open()
    assert not store.is_open


def test_reader_loads_published_snapshot(tmp_path: Path):
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    snapshot = {
        "docs": {
            "database__default": {
                "_id": "database__default",
                "doc_type": "database",
                "db_name": "default",
            }
        },
        "updated_at": 1,
    }
    paths.meta_snapshot.write_text(json.dumps(snapshot), encoding="utf-8")

    reader = MetaStore(paths, read_only=True)
    reader.open()
    assert reader.is_open
    assert reader.get("database__default")["db_name"] == "default"
    assert reader.list_by_type("database")[0]["db_name"] == "default"
