"""Schema and index definitions for the performance collection."""

from __future__ import annotations

from typing import Any

from tests.performance_testing.common.config import (
    DIM,
    HNSW_EF_CONSTRUCTION,
    HNSW_M,
    INDEX_TYPE,
    METRIC_TYPE,
    PK_FIELD,
    TIMESTAMP_FIELD,
    VECTOR_FIELD,
)


def perf_schema(dim: int = DIM) -> dict[str, Any]:
    return {
        "autoID": False,
        "enableDynamicField": False,
        "fields": [
            {
                "name": PK_FIELD,
                "dataType": "Int64",
                "isPrimaryKey": True,
                "autoID": False,
            },
            {
                "name": TIMESTAMP_FIELD,
                "dataType": "Int64",
            },
            {
                "name": VECTOR_FIELD,
                "dataType": "FloatVector",
                "dim": dim,
            },
        ],
    }


def hnsw_index_params() -> dict[str, Any]:
    return {"M": HNSW_M, "efConstruction": HNSW_EF_CONSTRUCTION}


def index_spec() -> dict[str, Any]:
    return {
        "fieldName": VECTOR_FIELD,
        "indexType": INDEX_TYPE,
        "metricType": METRIC_TYPE,
        "params": hnsw_index_params(),
        "indexName": f"{VECTOR_FIELD}_hnsw_idx",
    }
