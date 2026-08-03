from __future__ import annotations

import sys
from typing import Any

from xvector.common.errors import IndexUnsupportedError, ParamError


def normalize_index_type(index_type: str) -> str:
    if not index_type:
        raise ParamError("index_type required")
    t = index_type.strip().upper().replace("-", "_")
    aliases = {
        "FLAT": "FLAT",
        "IDMAP": "FLAT",
        "HNSW": "HNSW",
        "HNSW_RABITQ": "HNSW_RABITQ",
        "DISKANN": "DISKANN",
        "IVF_FLAT": "IVF_FLAT",
        "IVF_SQ8": "IVF_SQ8",
        "IVF_PQ": "IVF_PQ",
        "IVF": "IVF_FLAT",
    }
    if index_type.strip().upper() in {"HNSW-RABITQ", "HNSW_RABITQ"}:
        return "HNSW_RABITQ"
    if t not in aliases:
        raise IndexUnsupportedError(f"unsupported index_type: {index_type}")
    return aliases[t]


def normalize_metric(metric_type: str | None) -> str:
    m = (metric_type or "L2").strip().upper()
    if m not in {"L2", "IP", "COSINE"}:
        raise ParamError(f"unsupported metric_type: {metric_type}")
    return m


def to_zvec_metric(metric_type: str):
    import zvec

    m = normalize_metric(metric_type)
    return getattr(zvec.MetricType, m)


def to_zvec_index_param(index_type: str, metric_type: str, params: dict[str, Any] | None = None):
    import zvec

    params = params or {}
    itype = normalize_index_type(index_type)
    metric = to_zvec_metric(metric_type)

    if itype == "FLAT":
        return zvec.FlatIndexParam(metric_type=metric)

    if itype == "HNSW":
        m = int(params.get("M") or params.get("m") or 16)
        ef_c = int(params.get("efConstruction") or params.get("ef_construction") or 200)
        return zvec.HnswIndexParam(metric_type=metric, m=m, ef_construction=ef_c)

    if itype == "HNSW_RABITQ":
        m = int(params.get("M") or params.get("m") or 16)
        ef_c = int(params.get("efConstruction") or params.get("ef_construction") or 200)
        kwargs: dict[str, Any] = {"metric_type": metric, "m": m, "ef_construction": ef_c}
        if "total_bits" in params or "bits" in params:
            kwargs["total_bits"] = int(params.get("total_bits") or params.get("bits") or 8)
        return zvec.HnswRabitqIndexParam(**kwargs)

    if itype == "DISKANN":
        if sys.platform != "linux":
            raise IndexUnsupportedError("DiskANN is only guaranteed on Linux/Docker")
        max_degree = int(params.get("max_degree") or params.get("R") or 100)
        list_size = int(params.get("list_size") or params.get("search_list") or params.get("L") or 50)
        return zvec.DiskAnnIndexParam(metric_type=metric, max_degree=max_degree, list_size=list_size)

    if itype in {"IVF_FLAT", "IVF_SQ8", "IVF_PQ"}:
        nlist = int(params.get("nlist") or params.get("n_list") or 128)
        kwargs = {"metric_type": metric, "n_list": nlist}
        if itype == "IVF_SQ8":
            # Map SQ8 to INT8 quantize when available
            qt = getattr(zvec, "QuantizeType", None)
            if qt is not None and hasattr(qt, "INT8"):
                kwargs["quantize_type"] = qt.INT8
        return zvec.IVFIndexParam(**kwargs)

    raise IndexUnsupportedError(f"unsupported index_type: {index_type}")


def to_zvec_query_param(index_type: str | None, search_params: dict[str, Any] | None = None):
    """Optional query-time params for search."""
    import zvec

    search_params = search_params or {}
    if not index_type:
        return None
    itype = normalize_index_type(index_type)
    if itype in {"HNSW", "HNSW_RABITQ"}:
        ef = search_params.get("ef") or search_params.get("efSearch")
        if ef is None:
            return None
        cls = zvec.HnswQueryParam if itype == "HNSW" else getattr(zvec, "HnswRabitqQueryParam", zvec.HnswQueryParam)
        return cls(ef=int(ef))
    if itype.startswith("IVF"):
        nprobe = search_params.get("nprobe") or search_params.get("n_probe")
        if nprobe is None:
            return None
        return zvec.IVFQueryParam(n_probe=int(nprobe))
    if itype == "DISKANN":
        list_size = search_params.get("search_list") or search_params.get("list_size")
        if list_size is None:
            return None
        return zvec.DiskAnnQueryParam(list_size=int(list_size))
    return None
