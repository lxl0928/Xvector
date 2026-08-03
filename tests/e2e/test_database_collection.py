from __future__ import annotations

import uuid

from tests.conftest import milvus_schema


def test_database_and_collection(client, unique_name):
    db = f"db_{uuid.uuid4().hex[:8]}"
    client.create_database(db)
    assert db in client.list_databases()
    client.using_database(db)

    name = unique_name
    client.create_collection(name, schema=milvus_schema(dim=8))
    assert client.has_collection(name)["has"] is True
    assert name in client.list_collections()
    desc = client.describe_collection(name)
    assert desc["collectionName"] == name

    renamed = f"{name}_r"
    client.rename_collection(name, renamed)
    assert client.has_collection(renamed)["has"] is True
    client.drop_collection(renamed)

    client.using_database("default")
    client.drop_database(db)
