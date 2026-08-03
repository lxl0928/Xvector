from __future__ import annotations

import pytest

from pyxvector.exceptions import XvectorApiError
from tests.conftest import milvus_schema


def test_load_release_gate(client, unique_name):
    name = unique_name
    client.create_collection(name, schema=milvus_schema(dim=4))
    client.create_index(name, "vector", index_type="FLAT", metric_type="L2")
    client.insert(name, [{"id": 1, "vector": [0.1, 0.2, 0.3, 0.4]}])

    # default AUTO_LOAD=false -> search should fail before load
    with pytest.raises(XvectorApiError) as ei:
        client.search(name, [[0.1, 0.2, 0.3, 0.4]], anns_field="vector", limit=1, refresh=True)
    assert ei.value.code in {1200, 2000, 100}

    client.load_collection(name)
    client.wait_loaded(name)
    hits = client.search(name, [[0.1, 0.2, 0.3, 0.4]], anns_field="vector", limit=1, refresh=True)
    assert hits and len(hits[0]) >= 1

    client.release_collection(name)
    with pytest.raises(XvectorApiError):
        client.search(name, [[0.1, 0.2, 0.3, 0.4]], anns_field="vector", limit=1, refresh=True)

    client.drop_collection(name)
