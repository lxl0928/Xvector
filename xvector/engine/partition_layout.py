from __future__ import annotations

from pathlib import Path

from xvector.common.paths import DEFAULT_PARTITION, DataPaths


def partition_kind(partition_name: str) -> str:
    return "default_dir" if partition_name == DEFAULT_PARTITION else "explicit_dir"


def resolve_partition_path(
    paths: DataPaths,
    db_name: str,
    collection_name: str,
    partition_name: str | None = None,
) -> Path:
    part = partition_name or DEFAULT_PARTITION
    return paths.partition_dir(db_name, collection_name, part)
