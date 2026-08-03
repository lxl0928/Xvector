from __future__ import annotations

from tests.conftest import milvus_schema


def test_vector_int64_pk(client, unique_name):
    name = unique_name
    client.create_collection(
        name,
        schema=milvus_schema(
            dim=4,
            extra_fields=[{"name": "color", "dataType": "VarChar"}],
        ),
    )
    client.create_index(name, "vector", index_type="FLAT", metric_type="L2")
    client.load_collection(name)

    ins = client.insert(
        name,
        [
            {"id": 1, "vector": [1, 0, 0, 0], "color": "red"},
            {"id": 2, "vector": [0.9, 0.1, 0, 0], "color": "blue"},
        ],
    )
    assert ins["insertCount"] == 2

    client.upsert(name, [{"id": 2, "vector": [0.8, 0.2, 0, 0], "color": "green"}])
    got = client.get(name, [1, 2], refresh=True)
    assert len(got) == 2

    hits = client.search(
        name,
        [[1, 0, 0, 0]],
        anns_field="vector",
        limit=2,
        output_fields=["color"],
        refresh=True,
    )
    assert hits[0][0]["id"] == 1

    client.delete(name, ids=[2])
    client.drop_collection(name)


def test_vector_varchar_autoid(client, unique_name):
    name = unique_name + "_vc"
    client.create_collection(
        name,
        schema=milvus_schema(dim=4, pk="pk", pk_type="VarChar", auto_id=True),
    )
    client.create_index(name, "vector", index_type="HNSW", metric_type="COSINE", params={"M": 8, "efConstruction": 50})
    client.load_collection(name)
    ins = client.insert(name, [{"vector": [0.1, 0.2, 0.3, 0.4]}, {"vector": [0.2, 0.1, 0.3, 0.4]}])
    assert len(ins["insertIds"]) == 2
    client.drop_collection(name)
