"""Unit tests for pending-WAL detection and RO open guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from xvector.common.paths import DEFAULT_PARTITION, DataPaths
from xvector.engine.collection_mgr import CollectionManager


class _FakeHandle:
    def __init__(self) -> None:
        self.flush_count = 0
        self.closed = False

    def flush(self) -> None:
        self.flush_count += 1


def test_partition_has_wal_detects_nested_wal(tmp_path: Path):
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    part = paths.partition_dir("default", "c1", DEFAULT_PARTITION)
    wal = part / "0" / "915.wal"
    wal.parent.mkdir(parents=True)
    wal.write_bytes(b"wal")

    assert CollectionManager.partition_has_wal(paths, "default", "c1", DEFAULT_PARTITION)
    assert not CollectionManager.partition_has_wal(paths, "default", "missing", DEFAULT_PARTITION)


def test_readonly_open_blocked_when_wal_present(tmp_path: Path, monkeypatch):
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    mgr = CollectionManager(paths, read_only=True)
    part = paths.partition_dir("default", "c1", DEFAULT_PARTITION)
    part.mkdir(parents=True)
    (part / "0").mkdir()
    (part / "0" / "1.wal").write_bytes(b"x")

    opened = {"n": 0}

    def fake_open(path: str, read_only: bool = False):
        opened["n"] += 1
        return {"path": path, "read_only": read_only}

    monkeypatch.setattr("xvector.engine.zvec_runtime.open_collection", fake_open)

    with pytest.raises(RuntimeError, match="pending WAL"):
        mgr.open_partition("default", "c1", DEFAULT_PARTITION)
    assert opened["n"] == 0


def test_flush_partition_reuses_open_handle(tmp_path: Path, monkeypatch):
    """Reader seal must not steal an in-use writer handle via force_reopen."""
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    mgr = CollectionManager(paths, read_only=False)
    part = paths.partition_dir("default", "c1", DEFAULT_PARTITION)
    part.mkdir(parents=True)

    handle = _FakeHandle()
    opens = {"n": 0}

    def fake_open(path: str, read_only: bool = False):
        opens["n"] += 1
        return _FakeHandle()

    monkeypatch.setattr("xvector.engine.zvec_runtime.open_collection", fake_open)
    key = mgr.key("default", "c1", DEFAULT_PARTITION)
    mgr._handles[key] = handle

    mgr.flush_partition("default", "c1", DEFAULT_PARTITION)

    assert handle.flush_count == 1
    assert mgr.get_if_open("default", "c1", DEFAULT_PARTITION) is handle
    assert opens["n"] == 0


def test_flush_partition_opens_flushes_and_closes_when_idle(tmp_path: Path, monkeypatch):
    paths = DataPaths(str(tmp_path))
    paths.ensure_layout()
    mgr = CollectionManager(paths, read_only=False)
    part = paths.partition_dir("default", "c1", DEFAULT_PARTITION)
    part.mkdir(parents=True)

    handle = _FakeHandle()

    def fake_open(path: str, read_only: bool = False):
        return handle

    monkeypatch.setattr("xvector.engine.zvec_runtime.open_collection", fake_open)

    mgr.flush_partition("default", "c1", DEFAULT_PARTITION)

    assert handle.flush_count >= 1
    assert mgr.get_if_open("default", "c1", DEFAULT_PARTITION) is None
