from __future__ import annotations

from tests.conftest import milvus_schema


def test_hybrid_rrf(client, unique_name):
    name = unique_name
    schema = {
        "fields": [
            {"name": "id", "dataType": "Int64", "isPrimaryKey": True},
            {"name": "v1", "dataType": "FloatVector", "dim": 4},
            {"name": "v2", "dataType": "FloatVector", "dim": 4},
        ]
    }
    client.create_collection(name, schema=schema)
    client.create_index(name, "v1", index_type="FLAT", metric_type="L2")
    client.create_index(name, "v2", index_type="FLAT", metric_type="L2")
    client.load_collection(name)
    client.insert(
        name,
        [
            {"id": 1, "v1": [1, 0, 0, 0], "v2": [0, 1, 0, 0]},
            {"id": 2, "v1": [0.9, 0.1, 0, 0], "v2": [0, 0.9, 0.1, 0]},
        ],
    )
    res = client.hybrid_search(
        name,
        search=[
            {"data": [[1, 0, 0, 0]], "annsField": "v1", "limit": 2},
            {"data": [[0, 1, 0, 0]], "annsField": "v2", "limit": 2},
        ],
        rerank={"strategy": "rrf", "params": {"k": 60}},
        limit=2,
        refresh=True,
    )
    assert res and len(res[0]) >= 1
    client.drop_collection(name)
