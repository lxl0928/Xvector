from __future__ import annotations

import pytest

from pyxvector.exceptions import XvectorApiError
from tests.conftest import milvus_schema


def test_partition_hybrid(client, unique_name):
    name = unique_name
    client.create_collection(name, schema=milvus_schema())
    parts = client.list_partitions(name)
    assert "_default" in parts

    client.create_partition(name, "p1")
    assert client.has_partition(name, "p1")["has"] is True

    with pytest.raises(XvectorApiError):
        client.drop_partition(name, "_default")

    client.drop_partition(name, "p1")
    client.drop_collection(name)
