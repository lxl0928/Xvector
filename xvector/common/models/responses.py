"""Named `ApiResponse[...]` wrappers with full envelope OpenAPI examples.

Examples are reverse-engineered from e2e assertions + service return shapes
(`tests/e2e/**`, `xvector/services/**`). `requestId` is optional at runtime
and documented as Gateway-injected.
"""

from __future__ import annotations

from xvector.common.models.alias import AliasDescribeData
from xvector.common.models.collection import CollectionDescribeData
from xvector.common.models.common import HasData, LoadStateData, RowCountData
from xvector.common.models.database import DatabaseDescribeData
from xvector.common.models.envelope import EmptyObject, make_api_response
from xvector.common.models.import_job import (
    ImportCreateData,
    ImportListItem,
    ImportProgressData,
)
from xvector.common.models.index import IndexDescribeItem
from xvector.common.models.role import RoleDescribeData
from xvector.common.models.user import UserCreateData, UserDescribeData
from xvector.common.models.vector import (
    ENTITY_GET_EXAMPLE,
    ENTITY_HYBRID_EXAMPLE,
    ENTITY_QUERY_EXAMPLE,
    ENTITY_SEARCH_EXAMPLE,
    EntityRow,
    VectorDeleteData,
    VectorInsertData,
    VectorUpsertData,
)

# --- empty data (most write / DDL success bodies) ---
EmptyApiResponse = make_api_response("EmptyApiResponse", EmptyObject, {})

# --- list[str] ---
DatabaseListApiResponse = make_api_response(
    "DatabaseListApiResponse", list[str], ["default", "demo_db"]
)
CollectionListApiResponse = make_api_response(
    "CollectionListApiResponse", list[str], ["demo"]
)
AliasListApiResponse = make_api_response(
    "AliasListApiResponse", list[str], ["demo_alias"]
)
PartitionListApiResponse = make_api_response(
    "PartitionListApiResponse", list[str], ["_default", "p1"]
)
IndexListApiResponse = make_api_response(
    "IndexListApiResponse", list[str], ["vector_idx"]
)
RoleListApiResponse = make_api_response(
    "RoleListApiResponse", list[str], ["data_admin"]
)
UserListApiResponse = make_api_response(
    "UserListApiResponse", list[str], ["root", "alice"]
)

# --- typed data objects ---
DatabaseDescribeApiResponse = make_api_response(
    "DatabaseDescribeApiResponse",
    DatabaseDescribeData,
    DatabaseDescribeData.__example__,
)
AliasDescribeApiResponse = make_api_response(
    "AliasDescribeApiResponse",
    AliasDescribeData,
    AliasDescribeData.__example__,
)
CollectionDescribeApiResponse = make_api_response(
    "CollectionDescribeApiResponse",
    CollectionDescribeData,
    CollectionDescribeData.__example__,
)
HasApiResponse = make_api_response("HasApiResponse", HasData, HasData.__example__)
LoadStateApiResponse = make_api_response(
    "LoadStateApiResponse", LoadStateData, LoadStateData.__example__
)
RowCountApiResponse = make_api_response(
    "RowCountApiResponse", RowCountData, RowCountData.__example__
)
IndexDescribeApiResponse = make_api_response(
    "IndexDescribeApiResponse",
    list[IndexDescribeItem],
    [IndexDescribeItem.__example__],
)
ImportCreateApiResponse = make_api_response(
    "ImportCreateApiResponse",
    ImportCreateData,
    ImportCreateData.__example__,
)
ImportProgressApiResponse = make_api_response(
    "ImportProgressApiResponse",
    ImportProgressData,
    ImportProgressData.__example__,
)
ImportListApiResponse = make_api_response(
    "ImportListApiResponse",
    list[ImportListItem],
    [ImportListItem.__example__],
)
RoleDescribeApiResponse = make_api_response(
    "RoleDescribeApiResponse",
    RoleDescribeData,
    RoleDescribeData.__example__,
)
UserCreateApiResponse = make_api_response(
    "UserCreateApiResponse",
    UserCreateData,
    UserCreateData.__example__,
)
UserDescribeApiResponse = make_api_response(
    "UserDescribeApiResponse",
    UserDescribeData,
    UserDescribeData.__example__,
)
VectorInsertApiResponse = make_api_response(
    "VectorInsertApiResponse",
    VectorInsertData,
    VectorInsertData.__example__,
)
VectorUpsertApiResponse = make_api_response(
    "VectorUpsertApiResponse",
    VectorUpsertData,
    VectorUpsertData.__example__,
)
VectorDeleteApiResponse = make_api_response(
    "VectorDeleteApiResponse",
    VectorDeleteData,
    VectorDeleteData.__example__,
)

# Entity rows use EntityRow so OpenAPI shows real field names (not additionalProp1).
EntityGetApiResponse = make_api_response(
    "EntityGetApiResponse", list[EntityRow], ENTITY_GET_EXAMPLE
)
EntityQueryApiResponse = make_api_response(
    "EntityQueryApiResponse", list[EntityRow], ENTITY_QUERY_EXAMPLE
)
EntitySearchApiResponse = make_api_response(
    "EntitySearchApiResponse", list[list[EntityRow]], ENTITY_SEARCH_EXAMPLE
)
EntityHybridSearchApiResponse = make_api_response(
    "EntityHybridSearchApiResponse", list[list[EntityRow]], ENTITY_HYBRID_EXAMPLE
)
