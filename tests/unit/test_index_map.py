import sys

import pytest

from xvector.common.errors import IndexUnsupportedError
from xvector.engine.index_map import normalize_index_type, normalize_metric


def test_normalize_index_aliases():
    assert normalize_index_type("HNSW-RaBitQ") == "HNSW_RABITQ"
    assert normalize_index_type("IVF") == "IVF_FLAT"
    assert normalize_index_type("FLAT") == "FLAT"


def test_normalize_metric():
    assert normalize_metric("cosine") == "COSINE"
    with pytest.raises(Exception):
        normalize_metric("HAMMING")


def test_diskann_platform_gate():
    # construction of zvec param is tested only when zvec installed
    zvec = pytest.importorskip("zvec")
    from xvector.engine import index_map

    if sys.platform != "linux":
        with pytest.raises(IndexUnsupportedError):
            index_map.to_zvec_index_param("DISKANN", "L2", {})
    else:
        p = index_map.to_zvec_index_param("DISKANN", "L2", {"list_size": 20})
        assert p is not None
