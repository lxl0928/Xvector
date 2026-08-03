from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from xvector.common.errors import ParamError

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")
DEFAULT_DB = "default"
DEFAULT_PARTITION = "_default"
META_NAME = "xvector_meta"
RESERVED_NAMES = {META_NAME}


def validate_name(name: str, kind: str = "name") -> str:
    if not name or not isinstance(name, str):
        raise ParamError(f"invalid {kind}: empty")
    if name in RESERVED_NAMES:
        raise ParamError(f"{kind} '{name}' is reserved")
    if kind == "partition" and name == DEFAULT_PARTITION:
        return name
    if not NAME_RE.match(name):
        raise ParamError(f"invalid {kind}: {name!r}")
    return name


class DataPaths:
    def __init__(self, data_dir: str):
        self.root = Path(data_dir)

    def ensure_layout(self) -> None:
        # Do not create meta_dir itself: zvec create_and_open requires a non-existent path.
        for p in (self.root, self.root / "meta", self.dbs_dir, self.imports_dir, self.tmp_dir):
            p.mkdir(parents=True, exist_ok=True)

    @property
    def meta_dir(self) -> Path:
        return self.root / "meta" / META_NAME

    @property
    def meta_snapshot(self) -> Path:
        return self.root / "meta" / "catalog_snapshot.json"

    @property
    def dbs_dir(self) -> Path:
        return self.root / "dbs"

    @property
    def imports_dir(self) -> Path:
        return self.root / "imports"

    @property
    def tmp_dir(self) -> Path:
        return self.root / "tmp"

    def db_dir(self, db_name: str) -> Path:
        return self.dbs_dir / db_name

    def collection_dir(self, db_name: str, collection_name: str) -> Path:
        return self.db_dir(db_name) / "collections" / collection_name

    def partition_dir(self, db_name: str, collection_name: str, partition_name: str) -> Path:
        return self.collection_dir(db_name, collection_name) / partition_name

    def db_imports_dir(self, db_name: str, job_id: str) -> Path:
        return self.db_dir(db_name) / "imports" / job_id

    def remove_path(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)

    def rename_path(self, src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src, dst)
