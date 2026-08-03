from __future__ import annotations

import sys

import pytest

from tests.conftest import milvus_schema

requires_diskann = pytest.mark.skipif(
    sys.platform != "linux",
    reason="DiskANN verified on Linux/Docker only",
)


@pytest.mark.parametrize(
    "index_type,params",
    [
        ("FLAT", {}),
        ("HNSW", {"M": 16, "efConstruction": 100}),
        ("HNSW_RABITQ", {"M": 16, "efConstruction": 100}),
        ("IVF_FLAT", {"nlist": 64}),
    ],
)
def test_create_index_types(client, unique_name, index_type, params):
    name = unique_name + "_" + index_type.lower()
    client.create_collection(name, schema=milvus_schema(dim=8))
    client.create_index(name, "vector", index_type=index_type, metric_type="L2", params=params)
    listed = client.list_indexes(name)
    assert any("vector" in str(x) for x in listed) or len(listed) >= 1
    client.drop_collection(name)


@requires_diskann
def test_diskann_index(client, unique_name):
    name = unique_name + "_diskann"
    client.create_collection(name, schema=milvus_schema(dim=8))
    client.create_index(name, "vector", index_type="DISKANN", metric_type="L2", params={"list_size": 50})
    client.drop_collection(name)
