from __future__ import annotations

import json
import logging
from typing import Any

from xvector.common.errors import NotLoadedError, ParamError
from xvector.common.paths import DEFAULT_DB, DEFAULT_PARTITION
from xvector.common.pk import from_internal_id, generate_auto_id, to_internal_id
from xvector.common.schema_map import DYNAMIC_FIELD, ensure_pk_column_on_handle, ensure_pk_in_scalar_fields
from xvector.engine import index_map
from xvector.services.context import AppContext

logger = logging.getLogger(__name__)


class VectorService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def _db(self, body: dict[str, Any]) -> str:
        return body.get("dbName") or body.get("db_name") or DEFAULT_DB

    def _resolve(self, body: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        db = self._db(body)
        name = body.get("collectionName") or body.get("collection_name")
        name = self.ctx.catalog.resolve_collection_name(db, name)
        meta = ensure_pk_in_scalar_fields(self.ctx.catalog.require_collection(db, name))
        return db, name, meta

    def _partitions(self, body: dict[str, Any], db: str, coll: str) -> list[str]:
        if body.get("partitionName"):
            return [body["partitionName"]]
        parts = body.get("partitionNames") or body.get("partition_names")
        if parts:
            return list(parts)
        return [DEFAULT_PARTITION]

    def _ensure_loaded(self, db: str, coll: str, allow_lazy: bool = True) -> None:
        st = self.ctx.catalog.get_load_state(db, coll)
        if st.get("loaded"):
            return
        if allow_lazy and self.ctx.settings.auto_load:
            return
        raise NotLoadedError(f"collection not loaded: {db}.{coll}")

    async def _maybe_refresh(self, db: str, coll: str, parts: list[str], refresh: bool) -> None:
        """Reopen RO handles after Writer seals any pending WAL.

        zvec 0.6 RO open replays WAL into IDMap (a write). Leftover ``*.wal`` must be
        flushed by Writer before Reader can safely reopen.
        """
        if not refresh:
            return
        # Release shared locks so Writer can exclusively flush.
        for p in parts:
            self.ctx.collections.close_partition(db, coll, p, flush=False)
        if self.ctx.role == "reader":
            # Writer RW-open+flush clears WAL (required before RO open) and makes
            # the latest durable segment visible to the subsequent reopen.
            await self.ctx.seal_partitions_via_writer(db, coll, parts, require_ok=False)
        for p in parts:
            if self.ctx.collections.has_wal(db, coll, p):
                logger.warning(
                    "skip refresh RO open with pending WAL %s/%s/%s",
                    db,
                    coll,
                    p,
                )
                continue
            try:
                self.ctx.collections.open_partition(db, coll, p, force_reopen=True)
            except Exception:  # noqa: BLE001
                logger.exception("refresh reopen failed %s/%s/%s", db, coll, p)

    def _entity_to_doc(self, entity: dict[str, Any], meta: dict[str, Any]):
        import zvec

        pk_field = meta["primary_field"]
        pk_type = meta["primary_type"]
        auto_id = meta.get("auto_id", False)
        pk_val = entity.get(pk_field)
        if pk_val is None and "id" in entity and pk_field != "id":
            # common milvus examples use id
            if pk_field.lower() == "id" or pk_field == "id":
                pk_val = entity["id"]
        if pk_val is None:
            if auto_id:
                pk_val = generate_auto_id(pk_type)
            else:
                raise ParamError(f"primary key {pk_field} required")
        doc_id = to_internal_id(pk_val, pk_type)

        vector_names = {v["name"] for v in meta["vector_fields"]}
        scalar_names = {s["name"] for s in meta.get("scalar_fields") or []}
        vectors = {}
        fields = {}
        dynamic = {}
        for k, v in entity.items():
            if k == pk_field:
                continue
            if k in vector_names:
                vectors[k] = v
            elif k in scalar_names:
                fields[k] = v
            elif meta.get("enable_dynamic_field"):
                dynamic[k] = v
        # Always mirror PK into scalar fields when the catalog includes it, so
        # Milvus-style filters on the primary key work in zvec SQL.
        if pk_field in scalar_names:
            if pk_type == "Int64":
                fields[pk_field] = int(pk_val)
            else:
                fields[pk_field] = str(pk_val)
        if dynamic:
            fields[DYNAMIC_FIELD] = json.dumps(dynamic, ensure_ascii=False)
        return zvec.Doc(id=doc_id, vectors=vectors, fields=fields), from_internal_id(doc_id, pk_type)

    async def insert(self, body: dict[str, Any]) -> dict[str, Any]:
        db, coll, meta = self._resolve(body)
        data = body.get("data")
        if data is None:
            raise ParamError("data required")
        if isinstance(data, dict):
            data = [data]
        parts = self._partitions(body, db, coll)
        part = parts[0]
        async with self.ctx.with_reader_released(db, coll, parts):
            handle = self.ctx.collections.open_partition(
                db, coll, part, retries=8, retry_delay=0.05
            )
            ensure_pk_column_on_handle(handle, meta)
            ids = []
            docs = []
            for ent in data:
                doc, external_id = self._entity_to_doc(ent, meta)
                docs.append(doc)
                ids.append(external_id)
            try:
                handle.insert(docs if len(docs) > 1 else docs[0])
            finally:
                self.ctx.collections.close_partition(db, coll, part)
                handle = None
        return {"insertCount": len(ids), "insertIds": ids}

    async def upsert(self, body: dict[str, Any]) -> dict[str, Any]:
        db, coll, meta = self._resolve(body)
        data = body.get("data")
        if data is None:
            raise ParamError("data required")
        if isinstance(data, dict):
            data = [data]
        parts = self._partitions(body, db, coll)
        part = parts[0]
        async with self.ctx.with_reader_released(db, coll, parts):
            handle = self.ctx.collections.open_partition(
                db, coll, part, retries=8, retry_delay=0.05
            )
            ensure_pk_column_on_handle(handle, meta)
            ids = []
            try:
                for ent in data:
                    doc, external_id = self._entity_to_doc(ent, meta)
                    ids.append(external_id)
                    if hasattr(handle, "upsert"):
                        handle.upsert(doc)
                    else:
                        try:
                            handle.delete(ids=doc.id)
                        except Exception:  # noqa: BLE001
                            pass
                        handle.insert(doc)
            finally:
                self.ctx.collections.close_partition(db, coll, part)
                handle = None
        return {"upsertCount": len(ids), "upsertIds": ids}

    async def delete(self, body: dict[str, Any]) -> dict[str, Any]:
        db, coll, meta = self._resolve(body)
        parts = body.get("partitionNames") or self.ctx.catalog.list_partitions(db, coll)
        if body.get("partitionName"):
            parts = [body["partitionName"]]
        filter_expr = body.get("filter") or body.get("expr")
        ids = body.get("id") or body.get("ids")
        deleted = 0
        pk_type = meta["primary_type"]
        async with self.ctx.with_reader_released(db, coll, list(parts)):
            for part in parts:
                handle = self.ctx.collections.open_partition(
                    db, coll, part, retries=8, retry_delay=0.05
                )
                try:
                    if ids is not None:
                        id_list = ids if isinstance(ids, list) else [ids]
                        internal = [to_internal_id(i, pk_type) for i in id_list]
                        handle.delete(ids=internal if len(internal) > 1 else internal[0])
                        deleted += len(internal)
                    elif filter_expr:
                        if hasattr(handle, "delete_by_filter"):
                            handle.delete_by_filter(filter=filter_expr)
                        else:
                            raise ParamError("filter delete not supported by engine")
                        deleted += 1
                    else:
                        raise ParamError("id or filter required")
                finally:
                    self.ctx.collections.close_partition(db, coll, part)
                    handle = None
        return {"deleteCount": deleted}

    async def get(self, body: dict[str, Any], refresh: bool = False) -> list[dict[str, Any]]:
        db, coll, meta = self._resolve(body)
        self._ensure_loaded(db, coll)
        ids = body.get("id") or body.get("ids")
        if ids is None:
            raise ParamError("id required")
        if not isinstance(ids, list):
            ids = [ids]
        parts = body.get("partitionNames") or self.ctx.catalog.list_partitions(db, coll)
        if body.get("partitionName"):
            parts = [body["partitionName"]]
        await self._maybe_refresh(db, coll, parts, refresh)
        output_fields = body.get("outputFields") or body.get("output_fields")
        pk_type = meta["primary_type"]
        pk_field = meta["primary_field"]
        out: list[dict[str, Any]] = []
        internal_ids = [to_internal_id(i, pk_type) for i in ids]
        seen = set()
        for part in parts:
            handle = self.ctx.collections.open_partition(db, coll, part)
            for iid in internal_ids:
                if iid in seen:
                    continue
                try:
                    result = handle.fetch(ids=iid)
                except Exception:  # noqa: BLE001
                    continue
                ent = self._fetch_to_entity(result, iid, meta, output_fields)
                if ent is not None:
                    seen.add(iid)
                    out.append(ent)
        return out

    def _schema_field_names(self, meta: dict[str, Any]) -> list[str]:
        names: list[str] = []
        pk = meta.get("primary_field")
        if pk:
            names.append(pk)
        for s in meta.get("scalar_fields") or []:
            n = s.get("name")
            if n and n not in names:
                names.append(n)
        for v in meta.get("vector_fields") or []:
            n = v.get("name")
            if n and n not in names:
                names.append(n)
        # Preserve declare order from original milvus schema when present.
        schema_fields = (meta.get("schema") or {}).get("fields") or []
        if schema_fields:
            ordered: list[str] = []
            for f in schema_fields:
                n = f.get("name") or f.get("fieldName") or f.get("field_name")
                if n and n not in ordered:
                    ordered.append(n)
            for n in names:
                if n not in ordered:
                    ordered.append(n)
            return ordered
        return names

    def _resolve_output(
        self,
        meta: dict[str, Any],
        output_fields: list[str] | None,
        *,
        default_include_vectors: bool = False,
    ) -> tuple[list[str] | None, bool]:
        """Return (zvec output_fields for scalars, include_vector flag).

        zvec ``output_fields`` only accepts names present in the collection's
        scalar schema. Doc.id / Milvus PK and vector field names must not be
        passed through — PK is always taken from Doc.id, vectors via
        ``include_vector``.
        """
        vector_names = {v["name"] for v in meta.get("vector_fields") or []}
        scalar_names = {s["name"] for s in meta.get("scalar_fields") or []}
        pk = meta.get("primary_field")
        # Never forward Doc.id / PK: catalog may list PK as a mirrored scalar
        # even when the on-disk zvec schema does not have that column yet.
        reserved = {pk, "id"} - {None}
        if not output_fields:
            if default_include_vectors:
                return None, True
            return None, False
        include_vector = any(f in vector_names for f in output_fields)
        scalar_out = [
            f
            for f in output_fields
            if f in scalar_names and f not in vector_names and f not in reserved
        ]
        # None => omit zvec output_fields (engine returns all available scalars).
        return (scalar_out or None), include_vector

    @staticmethod
    def _normalize_vector_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if hasattr(value, "tolist"):
            try:
                return value.tolist()
            except Exception:  # noqa: BLE001
                pass
        try:
            return list(value)
        except Exception:  # noqa: BLE001
            return value

    def _run_zvec_query(
        self,
        handle: Any,
        *,
        vf: str,
        dim: int,
        limit: int,
        filter_expr: str,
        output_fields: list[str] | None,
        include_vector: bool,
    ) -> Any:
        import zvec

        common: dict[str, Any] = {"topk": limit, "include_vector": include_vector}
        if output_fields is not None:
            common["output_fields"] = output_fields
        if filter_expr:
            try:
                return handle.query(filter=filter_expr, **common)
            except TypeError:
                common.pop("include_vector", None)
                try:
                    return handle.query(filter=filter_expr, **common)
                except Exception:
                    pass
            except Exception:
                pass
            # Fallback: ANN + filter
            try:
                return handle.query(
                    queries=zvec.Query(field_name=vf, vector=[0.0] * dim),
                    filter=filter_expr,
                    **common,
                )
            except TypeError:
                common.pop("include_vector", None)
                return handle.query(
                    queries=zvec.Query(field_name=vf, vector=[0.0] * dim),
                    filter=filter_expr,
                    **common,
                )
        try:
            return handle.query(
                queries=zvec.Query(field_name=vf, vector=[0.0] * dim),
                **common,
            )
        except TypeError:
            common.pop("include_vector", None)
            return handle.query(
                queries=zvec.Query(field_name=vf, vector=[0.0] * dim),
                **common,
            )

    async def query(self, body: dict[str, Any], refresh: bool = False) -> list[dict[str, Any]]:
        db, coll, meta = self._resolve(body)
        self._ensure_loaded(db, coll)
        parts = body.get("partitionNames") or self.ctx.catalog.list_partitions(db, coll)
        if body.get("partitionName"):
            parts = [body["partitionName"]]
        await self._maybe_refresh(db, coll, parts, refresh)
        filter_expr = (body.get("filter") or body.get("expr") or "").strip()
        # Legacy web cursor used ``id != ""`` which zvec cannot parse (Doc.id is
        # not a SQL field unless mirrored). Treat as "no filter" list scan.
        if filter_expr.replace(" ", "") in {f'{meta["primary_field"]}!=""', f"{meta['primary_field']}!=''"}:
            filter_expr = ""
        limit = int(body.get("limit") or body.get("topk") or 100)
        output_fields = body.get("outputFields") or body.get("output_fields")
        if not output_fields:
            output_fields = self._schema_field_names(meta)
        zvec_out, include_vector = self._resolve_output(
            meta, output_fields, default_include_vectors=True
        )
        vf = meta["vector_fields"][0]["name"]
        dim = int(meta["vector_fields"][0]["dim"])

        rows: list[dict[str, Any]] = []
        for part in parts:
            handle = self.ctx.collections.open_partition(db, coll, part)
            try:
                result = self._run_zvec_query(
                    handle,
                    vf=vf,
                    dim=dim,
                    limit=limit,
                    filter_expr=filter_expr,
                    output_fields=zvec_out,
                    include_vector=include_vector,
                )
            except Exception as e:  # noqa: BLE001
                raise ParamError(f"query failed: {e}") from e
            rows.extend(self._query_to_entities(result, meta, output_fields, include_score=False))
        return rows[:limit]

    async def search(self, body: dict[str, Any], refresh: bool = False) -> list[list[dict[str, Any]]]:
        db, coll, meta = self._resolve(body)
        self._ensure_loaded(db, coll)
        parts = body.get("partitionNames") or self.ctx.catalog.list_partitions(db, coll)
        if body.get("partitionName"):
            parts = [body["partitionName"]]
        await self._maybe_refresh(db, coll, parts, refresh)

        data = body.get("data") or body.get("vectors")
        if not data:
            raise ParamError("data required")
        anns_field = body.get("annsField") or body.get("anns_field") or meta["vector_fields"][0]["name"]
        limit = int(body.get("limit") or body.get("topk") or 10)
        filter_expr = body.get("filter") or body.get("expr")
        output_fields = body.get("outputFields") or body.get("output_fields")
        zvec_out, include_vector = self._resolve_output(
            meta, output_fields, default_include_vectors=False
        )
        search_params = body.get("searchParams") or body.get("params") or {}
        if isinstance(search_params, list):
            search_params = {p.get("key"): p.get("value") for p in search_params}

        indexes = self.ctx.catalog.list_indexes(db, coll)
        idx_type = None
        for i in indexes:
            if i.get("field_name") == anns_field:
                idx_type = i.get("index_type")
                break
        qparam = index_map.to_zvec_query_param(idx_type, search_params)

        import zvec

        # search each query vector; merge across partitions
        results: list[list[dict[str, Any]]] = []
        for vec in data:
            merged: list[dict[str, Any]] = []
            for part in parts:
                try:
                    handle = self.ctx.collections.open_partition(db, coll, part)
                except Exception as e:  # noqa: BLE001
                    raise ParamError(
                        f"collection open failed for {db}/{coll}/{part}: {e}"
                    ) from e
                kwargs: dict[str, Any] = {
                    "queries": zvec.Query(field_name=anns_field, vector=vec),
                    "topk": limit,
                    "include_vector": include_vector,
                }
                if filter_expr:
                    kwargs["filter"] = filter_expr
                if zvec_out is not None:
                    kwargs["output_fields"] = zvec_out
                if qparam is not None:
                    kwargs["query_param"] = qparam
                try:
                    result = handle.query(**kwargs)
                except TypeError:
                    kwargs.pop("query_param", None)
                    try:
                        result = handle.query(**kwargs)
                    except TypeError:
                        kwargs.pop("include_vector", None)
                        result = handle.query(**kwargs)
                merged.extend(self._query_to_entities(result, meta, output_fields, include_score=True))
            # sort by score — for L2 lower better; for IP/COSINE higher better
            metric = "L2"
            for vf in meta["vector_fields"]:
                if vf["name"] == anns_field:
                    metric = vf.get("metric_type") or "L2"
            for i in indexes:
                if i.get("field_name") == anns_field:
                    metric = i.get("metric_type") or metric
            reverse = metric.upper() in {"IP", "COSINE"}
            merged.sort(key=lambda x: x.get("score", 0.0), reverse=reverse)
            # dedupe by id
            seen = set()
            deduped = []
            for row in merged:
                rid = row.get("id")
                if rid in seen:
                    continue
                seen.add(rid)
                deduped.append(row)
            results.append(deduped[:limit])
        return results

    async def hybrid_search(self, body: dict[str, Any], refresh: bool = False) -> list[list[dict[str, Any]]]:
        """Hybrid: run multiple search requests and fuse with RRF/Weighted."""
        db, coll, meta = self._resolve(body)
        self._ensure_loaded(db, coll)
        search_reqs = body.get("search") or body.get("requests") or []
        if not search_reqs:
            raise ParamError("search requests required")
        rerank = body.get("rerank") or {}
        strategy = (rerank.get("strategy") or rerank.get("name") or "rrf").lower()
        limit = int(body.get("limit") or 10)
        output_fields = body.get("outputFields") or body.get("output_fields")

        # Collect ranked lists
        ranked_lists: list[list[dict[str, Any]]] = []
        for req in search_reqs:
            req_body = {
                "dbName": db,
                "collectionName": coll,
                "data": req.get("data"),
                "annsField": req.get("annsField") or req.get("anns_field"),
                "limit": req.get("limit") or limit,
                "filter": req.get("filter"),
                "partitionNames": body.get("partitionNames") or req.get("partitionNames"),
                "searchParams": req.get("searchParams") or req.get("params") or {},
                "outputFields": output_fields,
            }
            one = await self.search(req_body, refresh=refresh)
            ranked_lists.append(one[0] if one else [])

        if strategy in {"weighted", "weightedranker"}:
            weights = rerank.get("params", {}).get("weights") or rerank.get("weights") or [1.0] * len(ranked_lists)
            fused = self._weighted_fuse(ranked_lists, weights)
        else:
            k = int((rerank.get("params") or {}).get("k") or rerank.get("k") or 60)
            fused = self._rrf_fuse(ranked_lists, k=k)
        return [fused[:limit]]

    def _rrf_fuse(self, lists: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
        scores: dict[Any, float] = {}
        payload: dict[Any, dict[str, Any]] = {}
        for lst in lists:
            for rank, row in enumerate(lst, start=1):
                rid = row.get("id")
                scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
                payload[rid] = row
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        out = []
        for rid, sc in ordered:
            row = dict(payload[rid])
            row["score"] = sc
            row["distance"] = sc
            out.append(row)
        return out

    def _weighted_fuse(self, lists: list[list[dict[str, Any]]], weights: list[float]) -> list[dict[str, Any]]:
        scores: dict[Any, float] = {}
        payload: dict[Any, dict[str, Any]] = {}
        for w, lst in zip(weights, lists):
            if not lst:
                continue
            max_s = max(abs(r.get("score", 0.0)) for r in lst) or 1.0
            for row in lst:
                rid = row.get("id")
                norm = row.get("score", 0.0) / max_s
                scores[rid] = scores.get(rid, 0.0) + float(w) * norm
                payload[rid] = row
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        out = []
        for rid, sc in ordered:
            row = dict(payload[rid])
            row["score"] = sc
            row["distance"] = sc
            out.append(row)
        return out

    def _fetch_to_entity(
        self,
        result: Any,
        doc_id: str,
        meta: dict[str, Any],
        output_fields: list[str] | None,
    ) -> dict[str, Any] | None:
        item = result
        if isinstance(result, dict) and doc_id in result:
            item = result[doc_id]
        if isinstance(result, list):
            item = result[0] if result else None
        if item is None:
            return None
        return self._item_to_entity(item, meta, output_fields, include_score=False)

    def _query_to_entities(
        self,
        result: Any,
        meta: dict[str, Any],
        output_fields: list[str] | None,
        include_score: bool,
    ) -> list[dict[str, Any]]:
        rows = result
        if isinstance(result, dict):
            rows = result.get("docs") or result.get("data") or result.get("results") or list(result.values())
        if not isinstance(rows, list):
            rows = [rows] if rows else []
        out = []
        for row in rows:
            ent = self._item_to_entity(row, meta, output_fields, include_score=include_score)
            if ent:
                out.append(ent)
        return out

    def _item_to_entity(
        self,
        item: Any,
        meta: dict[str, Any],
        output_fields: list[str] | None,
        include_score: bool,
    ) -> dict[str, Any] | None:
        if item is None:
            return None
        if isinstance(item, dict):
            doc_id = item.get("id")
            fields = item.get("fields") or {}
            vectors = item.get("vectors") or {}
            score = item.get("score")
            # flattened form
            if not fields and not vectors:
                fields = {k: v for k, v in item.items() if k not in {"id", "score", "distance"}}
        else:
            doc_id = getattr(item, "id", None)
            fields = getattr(item, "fields", {}) or {}
            vectors = getattr(item, "vectors", {}) or {}
            score = getattr(item, "score", None)

        pk_field = meta["primary_field"]
        pk_type = meta["primary_type"]
        entity: dict[str, Any] = {pk_field: from_internal_id(str(doc_id), pk_type), "id": from_internal_id(str(doc_id), pk_type)}
        for k, v in (fields or {}).items():
            if k == DYNAMIC_FIELD:
                try:
                    dyn = json.loads(v) if isinstance(v, str) else v
                    if isinstance(dyn, dict):
                        entity.update(dyn)
                except Exception:  # noqa: BLE001
                    entity[k] = v
            else:
                entity[k] = v
        for k, v in (vectors or {}).items():
            entity[k] = self._normalize_vector_value(v)
        if include_score and score is not None:
            entity["score"] = score
            entity["distance"] = score
        if output_fields:
            keep = set(output_fields) | {pk_field, "id"}
            if include_score:
                keep |= {"score", "distance"}
            entity = {k: v for k, v in entity.items() if k in keep}
        return entity
