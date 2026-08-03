from __future__ import annotations

from pathlib import Path

import pytest

from xvector.common.paths import DEFAULT_PARTITION, DataPaths
from xvector.engine.collection_mgr import CollectionFencedError, CollectionManager


def test_fence_blocks_readonly_open(tmp_path: Path, monkeypatch):
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    mgr = CollectionManager(paths, read_only=True)

    part_path = paths.partition_dir("default", "c1", DEFAULT_PARTITION)
    part_path.mkdir(parents=True)
    (part_path / "LOCK").write_text("x", encoding="utf-8")

    opened = {"n": 0}

    def fake_open(path: str, read_only: bool = False):
        opened["n"] += 1
        return {"path": path, "read_only": read_only}

    monkeypatch.setattr("xvector.engine.zvec_runtime.open_collection", fake_open)

    mgr.fence_partitions("default", "c1", [DEFAULT_PARTITION])
    assert mgr.is_fenced("default", "c1", DEFAULT_PARTITION)
    with pytest.raises(CollectionFencedError):
        mgr.open_partition("default", "c1", DEFAULT_PARTITION)
    assert opened["n"] == 0

    mgr.unfence_partitions("default", "c1", [DEFAULT_PARTITION])
    handle = mgr.open_partition("default", "c1", DEFAULT_PARTITION)
    assert handle["path"] == str(part_path)
    assert opened["n"] == 1


def test_collection_wide_fence(tmp_path: Path, monkeypatch):
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    mgr = CollectionManager(paths, read_only=True)
    part_path = paths.partition_dir("default", "c1", DEFAULT_PARTITION)
    part_path.mkdir(parents=True)

    monkeypatch.setattr(
        "xvector.engine.zvec_runtime.open_collection",
        lambda path, read_only=False: object(),
    )

    mgr.fence_partitions("default", "c1", None)
    with pytest.raises(CollectionFencedError):
        mgr.open_partition("default", "c1", DEFAULT_PARTITION)
    mgr.unfence_partitions("default", "c1", None)
    assert mgr.open_partition("default", "c1", DEFAULT_PARTITION) is not None
