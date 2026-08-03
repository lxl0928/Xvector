from __future__ import annotations

from fastapi import APIRouter, Body, Request

from xvector.api.app_factory import parse_refresh_flags
from xvector.api.v2.deps import Services
from xvector.common.errors import ok
from xvector.common.models import (
    AliasAlterRequest,
    AliasCreateRequest,
    AliasDescribeRequest,
    AliasDropRequest,
    AliasListRequest,
    CollectionCreateRequest,
    CollectionLoadRequest,
    CollectionNameRequest,
    CollectionRenameRequest,
    DatabaseCreateRequest,
    DatabaseDescribeRequest,
    DatabaseDropRequest,
    DbScopedRequest,
    EmptyRequest,
    ImportCreateRequest,
    ImportListRequest,
    ImportProgressRequest,
    IndexCreateRequest,
    IndexDescribeRequest,
    IndexDropRequest,
    PartitionLoadReleaseRequest,
    PartitionNameRequest,
    PartitionStatsRequest,
    RoleNameRequest,
    RolePrivilegeRequest,
    UserCreateRequest,
    UserNameRequest,
    UserRoleRequest,
    UserUpdatePasswordRequest,
    VectorDeleteRequest,
    VectorGetRequest,
    VectorHybridSearchRequest,
    VectorInsertRequest,
    VectorQueryRequest,
    VectorSearchRequest,
    VectorUpsertRequest,
    dump_body,
)
from xvector.common.models.responses import (
    AliasDescribeApiResponse,
    AliasListApiResponse,
    CollectionDescribeApiResponse,
    CollectionListApiResponse,
    DatabaseDescribeApiResponse,
    DatabaseListApiResponse,
    EmptyApiResponse,
    EntityGetApiResponse,
    EntityHybridSearchApiResponse,
    EntityQueryApiResponse,
    EntitySearchApiResponse,
    HasApiResponse,
    ImportCreateApiResponse,
    ImportListApiResponse,
    ImportProgressApiResponse,
    IndexDescribeApiResponse,
    IndexListApiResponse,
    LoadStateApiResponse,
    PartitionListApiResponse,
    RoleDescribeApiResponse,
    RoleListApiResponse,
    RowCountApiResponse,
    UserCreateApiResponse,
    UserDescribeApiResponse,
    UserListApiResponse,
    VectorDeleteApiResponse,
    VectorInsertApiResponse,
    VectorUpsertApiResponse,
)

_RESP = {"response_model_exclude_none": True}


def build_writer_router(svc: Services) -> APIRouter:
    r = APIRouter(prefix="/v2/vectordb")

    # databases
    @r.post(
        "/databases/create",
        response_model=EmptyApiResponse,
        tags=["Database"],
        **_RESP,
    )
    async def db_create(body: DatabaseCreateRequest):
        return ok(await svc.collection.create_database(dump_body(body)))

    @r.post(
        "/databases/drop",
        response_model=EmptyApiResponse,
        tags=["Database"],
        **_RESP,
    )
    async def db_drop(body: DatabaseDropRequest):
        return ok(await svc.collection.drop_database(dump_body(body)))

    # aliases write
    @r.post(
        "/aliases/create",
        response_model=EmptyApiResponse,
        tags=["Alias"],
        **_RESP,
    )
    async def alias_create(body: AliasCreateRequest):
        return ok(await svc.alias.create(dump_body(body)))

    @r.post(
        "/aliases/drop",
        response_model=EmptyApiResponse,
        tags=["Alias"],
        **_RESP,
    )
    async def alias_drop(body: AliasDropRequest):
        return ok(await svc.alias.drop(dump_body(body)))

    @r.post(
        "/aliases/alter",
        response_model=EmptyApiResponse,
        tags=["Alias"],
        **_RESP,
    )
    async def alias_alter(body: AliasAlterRequest):
        return ok(await svc.alias.alter(dump_body(body)))

    # collections write
    @r.post(
        "/collections/create",
        response_model=EmptyApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_create(body: CollectionCreateRequest):
        return ok(await svc.collection.create_collection(dump_body(body)))

    @r.post(
        "/collections/drop",
        response_model=EmptyApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_drop(body: CollectionNameRequest):
        return ok(await svc.collection.drop_collection(dump_body(body)))

    @r.post(
        "/collections/rename",
        response_model=EmptyApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_rename(body: CollectionRenameRequest):
        return ok(await svc.collection.rename_collection(dump_body(body)))

    @r.post(
        "/collections/load",
        response_model=EmptyApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_load(body: CollectionLoadRequest):
        return ok(await svc.collection.load_collection(dump_body(body)))

    @r.post(
        "/collections/release",
        response_model=EmptyApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_release(body: CollectionNameRequest):
        return ok(await svc.collection.release_collection(dump_body(body)))

    # partitions write
    @r.post(
        "/partitions/create",
        response_model=EmptyApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_create(body: PartitionNameRequest):
        return ok(await svc.partition.create(dump_body(body)))

    @r.post(
        "/partitions/drop",
        response_model=EmptyApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_drop(body: PartitionNameRequest):
        return ok(await svc.partition.drop(dump_body(body)))

    @r.post(
        "/partitions/load",
        response_model=EmptyApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_load(body: PartitionLoadReleaseRequest):
        return ok(await svc.partition.load(dump_body(body)))

    @r.post(
        "/partitions/release",
        response_model=EmptyApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_release(body: PartitionLoadReleaseRequest):
        return ok(await svc.partition.release(dump_body(body)))

    # indexes
    @r.post(
        "/indexes/create",
        response_model=EmptyApiResponse,
        tags=["Index"],
        **_RESP,
    )
    async def idx_create(body: IndexCreateRequest):
        return ok(await svc.index.create(dump_body(body)))

    @r.post(
        "/indexes/drop",
        response_model=EmptyApiResponse,
        tags=["Index"],
        **_RESP,
    )
    async def idx_drop(body: IndexDropRequest):
        return ok(await svc.index.drop(dump_body(body)))

    # import
    @r.post(
        "/jobs/import/create",
        response_model=ImportCreateApiResponse,
        tags=["Import"],
        **_RESP,
    )
    @r.post(
        "/import/create",
        response_model=ImportCreateApiResponse,
        tags=["Import"],
        **_RESP,
    )
    async def import_create(body: ImportCreateRequest):
        return ok(await svc.import_job.create(dump_body(body)))

    @r.post(
        "/jobs/import/get_progress",
        response_model=ImportProgressApiResponse,
        tags=["Import"],
        **_RESP,
    )
    @r.post(
        "/import/get_progress",
        response_model=ImportProgressApiResponse,
        tags=["Import"],
        **_RESP,
    )
    async def import_progress(body: ImportProgressRequest):
        return ok(await svc.import_job.get_progress(dump_body(body)))

    @r.post(
        "/jobs/import/list",
        response_model=ImportListApiResponse,
        tags=["Import"],
        **_RESP,
    )
    @r.post(
        "/import/list",
        response_model=ImportListApiResponse,
        tags=["Import"],
        **_RESP,
    )
    async def import_list(body: ImportListRequest | None = Body(default=None)):
        return ok(await svc.import_job.list(dump_body(body)))

    # roles
    @r.post(
        "/roles/create",
        response_model=EmptyApiResponse,
        tags=["Role"],
        **_RESP,
    )
    async def role_create(body: RoleNameRequest):
        return ok(svc.role.create(body.roleName))

    @r.post(
        "/roles/drop",
        response_model=EmptyApiResponse,
        tags=["Role"],
        **_RESP,
    )
    async def role_drop(body: RoleNameRequest):
        return ok(svc.role.drop(body.roleName))

    @r.post(
        "/roles/describe",
        response_model=RoleDescribeApiResponse,
        tags=["Role"],
        **_RESP,
    )
    async def role_describe(body: RoleNameRequest):
        return ok(svc.role.describe(body.roleName))

    @r.post(
        "/roles/list",
        response_model=RoleListApiResponse,
        tags=["Role"],
        **_RESP,
    )
    @r.post(
        "/roles/lists",
        response_model=RoleListApiResponse,
        tags=["Role"],
        **_RESP,
    )
    async def role_list(body: EmptyRequest | None = Body(default=None)):
        _ = body
        return ok(svc.role.list())

    @r.post(
        "/roles/grant_privilege",
        response_model=EmptyApiResponse,
        tags=["Role"],
        **_RESP,
    )
    async def role_grant(body: RolePrivilegeRequest):
        return ok(
            svc.role.grant_privilege(
                body.roleName,
                body.objectType,
                body.objectName,
                body.privilege,
            )
        )

    @r.post(
        "/roles/revoke_privilege",
        response_model=EmptyApiResponse,
        tags=["Role"],
        **_RESP,
    )
    async def role_revoke(body: RolePrivilegeRequest):
        return ok(
            svc.role.revoke_privilege(
                body.roleName,
                body.objectType,
                body.objectName,
                body.privilege,
            )
        )

    # users
    @r.post(
        "/users/create",
        response_model=UserCreateApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_create(body: UserCreateRequest):
        return ok(svc.user.create(body.userName, body.password))

    @r.post(
        "/users/drop",
        response_model=EmptyApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_drop(body: UserNameRequest):
        return ok(svc.user.drop(body.userName))

    @r.post(
        "/users/describe",
        response_model=UserDescribeApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_describe(body: UserNameRequest):
        return ok(svc.user.describe(body.userName))

    @r.post(
        "/users/list",
        response_model=UserListApiResponse,
        tags=["User"],
        **_RESP,
    )
    @r.post(
        "/users/lists",
        response_model=UserListApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_list(body: EmptyRequest | None = Body(default=None)):
        _ = body
        return ok(svc.user.list())

    @r.post(
        "/users/update_password",
        response_model=EmptyApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_update_password(body: UserUpdatePasswordRequest):
        return ok(svc.user.update_password(body.userName, body.password, body.newPassword))

    @r.post(
        "/users/grant_role",
        response_model=EmptyApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_grant(body: UserRoleRequest):
        return ok(svc.user.grant_role(body.userName, body.roleName))

    @r.post(
        "/users/revoke_role",
        response_model=EmptyApiResponse,
        tags=["User"],
        **_RESP,
    )
    async def user_revoke(body: UserRoleRequest):
        return ok(svc.user.revoke_role(body.userName, body.roleName))

    # vector write
    @r.post(
        "/entities/insert",
        response_model=VectorInsertApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_insert(body: VectorInsertRequest):
        return ok(await svc.vector.insert(dump_body(body)))

    @r.post(
        "/entities/upsert",
        response_model=VectorUpsertApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_upsert(body: VectorUpsertRequest):
        return ok(await svc.vector.upsert(dump_body(body)))

    @r.post(
        "/entities/delete",
        response_model=VectorDeleteApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_delete(body: VectorDeleteRequest):
        return ok(await svc.vector.delete(dump_body(body)))

    return r


def build_reader_router(svc: Services) -> APIRouter:
    r = APIRouter(prefix="/v2/vectordb")

    @r.post(
        "/databases/list",
        response_model=DatabaseListApiResponse,
        tags=["Database"],
        **_RESP,
    )
    async def db_list(body: EmptyRequest | None = Body(default=None)):
        return ok(await svc.collection.list_databases(dump_body(body)))

    @r.post(
        "/databases/describe",
        response_model=DatabaseDescribeApiResponse,
        tags=["Database"],
        **_RESP,
    )
    async def db_describe(body: DatabaseDescribeRequest):
        return ok(await svc.collection.describe_database(dump_body(body)))

    @r.post(
        "/aliases/describe",
        response_model=AliasDescribeApiResponse,
        tags=["Alias"],
        **_RESP,
    )
    async def alias_describe(body: AliasDescribeRequest):
        return ok(await svc.alias.describe(dump_body(body)))

    @r.post(
        "/aliases/list",
        response_model=AliasListApiResponse,
        tags=["Alias"],
        **_RESP,
    )
    async def alias_list(body: AliasListRequest | None = Body(default=None)):
        return ok(await svc.alias.list(dump_body(body)))

    @r.post(
        "/collections/describe",
        response_model=CollectionDescribeApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_describe(body: CollectionNameRequest):
        return ok(await svc.collection.describe_collection(dump_body(body)))

    @r.post(
        "/collections/has",
        response_model=HasApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_has(body: CollectionNameRequest):
        return ok(await svc.collection.has_collection(dump_body(body)))

    @r.post(
        "/collections/list",
        response_model=CollectionListApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_list(body: DbScopedRequest | None = Body(default=None)):
        return ok(await svc.collection.list_collections(dump_body(body)))

    @r.post(
        "/collections/get_load_state",
        response_model=LoadStateApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_load_state(body: CollectionNameRequest):
        return ok(await svc.collection.get_load_state(dump_body(body)))

    @r.post(
        "/collections/get_stats",
        response_model=RowCountApiResponse,
        tags=["Collection"],
        **_RESP,
    )
    async def coll_stats(body: CollectionNameRequest):
        return ok(await svc.collection.get_stats(dump_body(body)))

    @r.post(
        "/partitions/has",
        response_model=HasApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_has(body: PartitionNameRequest):
        return ok(await svc.partition.has(dump_body(body)))

    @r.post(
        "/partitions/list",
        response_model=PartitionListApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_list(body: CollectionNameRequest):
        return ok(await svc.partition.list(dump_body(body)))

    @r.post(
        "/partitions/get_stats",
        response_model=RowCountApiResponse,
        tags=["Partition"],
        **_RESP,
    )
    async def part_stats(body: PartitionStatsRequest):
        return ok(await svc.partition.get_stats(dump_body(body)))

    @r.post(
        "/indexes/describe",
        response_model=IndexDescribeApiResponse,
        tags=["Index"],
        **_RESP,
    )
    async def idx_describe(body: IndexDescribeRequest):
        return ok(await svc.index.describe(dump_body(body)))

    @r.post(
        "/indexes/list",
        response_model=IndexListApiResponse,
        tags=["Index"],
        **_RESP,
    )
    async def idx_list(body: CollectionNameRequest):
        return ok(await svc.index.list(dump_body(body)))

    @r.post(
        "/entities/get",
        response_model=EntityGetApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_get(request: Request, body: VectorGetRequest):
        payload = dump_body(body)
        return ok(await svc.vector.get(payload, refresh=parse_refresh_flags(request, payload)))

    @r.post(
        "/entities/query",
        response_model=EntityQueryApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_query(request: Request, body: VectorQueryRequest):
        payload = dump_body(body)
        return ok(await svc.vector.query(payload, refresh=parse_refresh_flags(request, payload)))

    @r.post(
        "/entities/search",
        response_model=EntitySearchApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_search(request: Request, body: VectorSearchRequest):
        payload = dump_body(body)
        return ok(await svc.vector.search(payload, refresh=parse_refresh_flags(request, payload)))

    @r.post(
        "/entities/hybrid_search",
        response_model=EntityHybridSearchApiResponse,
        tags=["Vector"],
        **_RESP,
    )
    async def vec_hybrid(request: Request, body: VectorHybridSearchRequest):
        payload = dump_body(body)
        return ok(
            await svc.vector.hybrid_search(payload, refresh=parse_refresh_flags(request, payload))
        )

    return r
