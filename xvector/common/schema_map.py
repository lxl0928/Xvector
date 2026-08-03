from __future__ import annotations

from typing import Any

from xvector.common.errors import ParamError
from xvector.engine import index_map


DYNAMIC_FIELD = "$_dynamic"


def parse_milvus_schema(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize create-collection body into catalog schema."""
    schema = body.get("schema") or {}
    fields = schema.get("fields") or body.get("fields") or []
    if not fields:
        raise ParamError("schema.fields is required")

    def _fname(f: dict[str, Any]) -> str | None:
        return f.get("name") or f.get("fieldName") or f.get("field_name")

    pk_fields = [f for f in fields if f.get("is_primary_key") or f.get("isPrimaryKey") or f.get("isPrimary")]
    if len(pk_fields) != 1:
        raise ParamError("schema must contain exactly one primary key field")
    pk = pk_fields[0]
    pk_name = _fname(pk)
    pk_type = _normalize_dtype(pk.get("data_type") or pk.get("dataType") or pk.get("type"))
    if pk_type not in {"Int64", "VarChar"}:
        raise ParamError("primary key type must be Int64 or VarChar")

    auto_id = bool(
        pk.get("auto_id")
        or pk.get("autoID")
        or schema.get("autoID")
        or body.get("autoID")
        or False
    )

    vector_fields: list[dict[str, Any]] = []
    scalars: list[dict[str, Any]] = []
    # Mirror PK as a filterable scalar field. zvec Doc.id is not part of the SQL
    # schema, so Milvus-style filters like ``id >= 0`` / ``id > 1`` need this.
    scalars.append({"name": pk_name, "data_type": pk_type, "nullable": False})
    for f in fields:
        name = _fname(f)
        dtype = _normalize_dtype(f.get("data_type") or f.get("dataType") or f.get("type"))
        if not name:
            raise ParamError("field name required")
        if dtype in {"FloatVector", "BinaryVector", "SparseFloatVector", "Float16Vector", "BFloat16Vector"}:
            dim = f.get("dim") or f.get("dimension")
            params = f.get("params") or f.get("typeParams") or f.get("elementTypeParams") or {}
            if isinstance(params, list):
                params = {p.get("key"): p.get("value") for p in params}
            if dim is None:
                dim = params.get("dim") or params.get("dimension")
            if dim is None and dtype != "SparseFloatVector":
                raise ParamError(f"vector field {name} missing dim")
            vector_fields.append(
                {
                    "name": name,
                    "data_type": dtype,
                    "dim": int(dim) if dim is not None else None,
                    "metric_type": (f.get("metric_type") or f.get("metricType") or "L2"),
                }
            )
        elif name == pk_name:
            continue
        else:
            scalars.append({"name": name, "data_type": dtype, "nullable": bool(f.get("nullable", True))})

    if not vector_fields:
        raise ParamError("at least one vector field is required")

    enable_dynamic = bool(
        schema.get("enable_dynamic_field")
        or schema.get("enableDynamicField")
        or body.get("enableDynamicField")
        or False
    )

    return {
        "schema": {
            "fields": fields,
            "functions": schema.get("functions") or [],
            "enableDynamicField": enable_dynamic,
            "description": schema.get("description") or body.get("description") or "",
        },
        "properties": body.get("properties") or {},
        "shards_num": int(body.get("shardsNum") or body.get("shards_num") or 1),
        "consistency_level": body.get("consistencyLevel") or body.get("consistency_level") or "Eventually",
        "auto_id": auto_id,
        "primary_field": pk_name,
        "primary_type": pk_type,
        "vector_fields": vector_fields,
        "scalar_fields": scalars,
        "enable_dynamic_field": enable_dynamic,
    }


def _normalize_dtype(dtype: Any) -> str:
    if dtype is None:
        raise ParamError("field data type required")
    if isinstance(dtype, int):
        # Milvus numeric enum subset
        mapping = {
            5: "Int64",
            21: "VarChar",
            101: "FloatVector",
            100: "BinaryVector",
            104: "SparseFloatVector",
            4: "Int32",
            3: "Int16",
            2: "Int8",
            10: "Float",
            11: "Double",
            1: "Bool",
        }
        return mapping.get(dtype, str(dtype))
    s = str(dtype)
    aliases = {
        "INT64": "Int64",
        "VARCHAR": "VarChar",
        "FLOAT_VECTOR": "FloatVector",
        "BINARY_VECTOR": "BinaryVector",
        "SPARSE_FLOAT_VECTOR": "SparseFloatVector",
        "BOOL": "Bool",
        "INT8": "Int8",
        "INT16": "Int16",
        "INT32": "Int32",
        "FLOAT": "Float",
        "DOUBLE": "Double",
        "JSON": "JSON",
        "ARRAY": "Array",
    }
    return aliases.get(s.upper(), s if s[:1].isupper() else s)


def build_zvec_schema(name: str, catalog: dict[str, Any], index_defs: list[dict[str, Any]] | None = None):
    """Build zvec.CollectionSchema from catalog meta."""
    import zvec

    index_by_field = {}
    for idx in index_defs or []:
        index_by_field[idx["field_name"]] = idx

    fields = []
    for sf in catalog.get("scalar_fields") or []:
        dtype = _to_zvec_scalar(sf["data_type"])
        fields.append(
            zvec.FieldSchema(
                name=sf["name"],
                data_type=dtype,
                nullable=bool(sf.get("nullable", True)),
                index_param=zvec.InvertIndexParam(enable_range_optimization=True),
            )
        )
    if catalog.get("enable_dynamic_field"):
        fields.append(
            zvec.FieldSchema(
                name=DYNAMIC_FIELD,
                data_type=zvec.DataType.STRING,
                nullable=True,
            )
        )

    vectors = []
    for vf in catalog["vector_fields"]:
        idx = index_by_field.get(vf["name"])
        if idx:
            index_param = index_map.to_zvec_index_param(idx["index_type"], idx.get("metric_type") or vf.get("metric_type") or "L2", idx.get("params") or {})
        else:
            # default Flat until CreateIndex
            index_param = index_map.to_zvec_index_param("FLAT", vf.get("metric_type") or "L2", {})
        vectors.append(
            zvec.VectorSchema(
                name=vf["name"],
                data_type=zvec.DataType.VECTOR_FP32,
                dimension=int(vf["dim"]),
                index_param=index_param,
            )
        )

    return zvec.CollectionSchema(name=name, fields=fields, vectors=vectors)


def _to_zvec_scalar(dtype: str):
    import zvec

    # zvec 0.6 has no INT8/INT16; widen to INT32.
    mapping = {
        "Bool": zvec.DataType.BOOL,
        "Int8": zvec.DataType.INT32,
        "Int16": zvec.DataType.INT32,
        "Int32": zvec.DataType.INT32,
        "Int64": zvec.DataType.INT64,
        "Float": zvec.DataType.FLOAT,
        "Double": zvec.DataType.DOUBLE,
        "VarChar": zvec.DataType.STRING,
        "String": zvec.DataType.STRING,
        "JSON": zvec.DataType.STRING,
    }
    if dtype not in mapping:
        # Best-effort: store as string
        return zvec.DataType.STRING
    return mapping[dtype]


def ensure_pk_in_scalar_fields(meta: dict[str, Any]) -> dict[str, Any]:
    """Ensure catalog meta lists the PK as a filterable scalar field."""
    pk = meta.get("primary_field")
    pk_type = meta.get("primary_type") or "Int64"
    if not pk:
        return meta
    scalars = list(meta.get("scalar_fields") or [])
    if any(s.get("name") == pk for s in scalars):
        return meta
    scalars.insert(0, {"name": pk, "data_type": pk_type, "nullable": False})
    out = dict(meta)
    out["scalar_fields"] = scalars
    return out


def ensure_pk_column_on_handle(handle: Any, meta: dict[str, Any]) -> None:
    """Best-effort: add mirrored Int64 PK column on an existing zvec collection."""
    pk = meta.get("primary_field")
    pk_type = meta.get("primary_type") or "Int64"
    if not pk or pk_type != "Int64" or handle is None:
        return
    try:
        schema = getattr(handle, "schema", None)
        existing = set()
        if schema is not None:
            for f in getattr(schema, "fields", None) or []:
                existing.add(getattr(f, "name", None) or (f.get("name") if isinstance(f, dict) else None))
        if pk in existing:
            return
        if not hasattr(handle, "add_column"):
            return
        import zvec

        handle.add_column(
            zvec.FieldSchema(
                name=pk,
                data_type=zvec.DataType.INT64,
                nullable=True,
                index_param=zvec.InvertIndexParam(enable_range_optimization=True),
            ),
            expression="0",
        )
    except Exception:  # noqa: BLE001
        # Existing collections may already have the column or reject add_column.
        pass
