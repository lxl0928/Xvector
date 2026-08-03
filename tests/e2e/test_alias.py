from __future__ import annotations

from tests.conftest import milvus_schema


def test_alias_flow(client, unique_name):
    name = unique_name
    alias = f"a_{unique_name}"
    client.create_collection(name, schema=milvus_schema(dim=4))
    client.create_index(name, "vector", index_type="FLAT", metric_type="L2")
    client.create_alias(name, alias)
    assert alias in client.list_aliases(name)
    desc = client.describe_alias(alias)
    assert desc["collectionName"] == name

    client.load_collection(alias)
    client.insert(alias, [{"id": 1, "vector": [1, 0, 0, 0]}])
    hits = client.search(alias, [[1, 0, 0, 0]], anns_field="vector", limit=1, refresh=True)
    assert hits[0]

    # create second collection and alter alias
    name2 = name + "_2"
    client.create_collection(name2, schema=milvus_schema(dim=4))
    client.alter_alias(name2, alias)
    assert client.describe_alias(alias)["collectionName"] == name2

    client.drop_alias(alias)
    client.drop_collection(name)
    client.drop_collection(name2)
