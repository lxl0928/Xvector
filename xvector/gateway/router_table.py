from __future__ import annotations

# path suffix after /v2/vectordb -> "W" or "R"
ROUTE_TABLE: dict[str, str] = {
    # databases
    "/databases/create": "W",
    "/databases/drop": "W",
    "/databases/list": "R",
    "/databases/describe": "R",
    # aliases
    "/aliases/create": "W",
    "/aliases/drop": "W",
    "/aliases/alter": "W",
    "/aliases/describe": "R",
    "/aliases/list": "R",
    # collections
    "/collections/create": "W",
    "/collections/drop": "W",
    "/collections/describe": "R",
    "/collections/has": "R",
    "/collections/list": "R",
    "/collections/rename": "W",
    "/collections/load": "W",
    "/collections/release": "W",
    "/collections/get_load_state": "R",
    "/collections/get_stats": "R",
    # partitions
    "/partitions/create": "W",
    "/partitions/drop": "W",
    "/partitions/has": "R",
    "/partitions/list": "R",
    "/partitions/get_stats": "R",
    "/partitions/load": "W",
    "/partitions/release": "W",
    # indexes
    "/indexes/create": "W",
    "/indexes/describe": "R",
    "/indexes/drop": "W",
    "/indexes/list": "R",
    # import
    "/jobs/import/create": "W",
    "/jobs/import/get_progress": "W",
    "/jobs/import/list": "W",
    # also accept /import/* aliases
    "/import/create": "W",
    "/import/get_progress": "W",
    "/import/list": "W",
    # roles
    "/roles/create": "W",
    "/roles/drop": "W",
    "/roles/describe": "W",
    "/roles/list": "W",
    "/roles/lists": "W",
    "/roles/grant_privilege": "W",
    "/roles/revoke_privilege": "W",
    # users
    "/users/create": "W",
    "/users/drop": "W",
    "/users/describe": "W",
    "/users/list": "W",
    "/users/lists": "W",
    "/users/update_password": "W",
    "/users/grant_role": "W",
    "/users/revoke_role": "W",
    # vector / entities
    "/entities/insert": "W",
    "/entities/upsert": "W",
    "/entities/delete": "W",
    "/entities/get": "R",
    "/entities/query": "R",
    "/entities/search": "R",
    "/entities/hybrid_search": "R",
}


def resolve_target(path: str) -> str | None:
    prefix = "/v2/vectordb"
    if not path.startswith(prefix):
        return None
    suffix = path[len(prefix) :] or "/"
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    return ROUTE_TABLE.get(suffix)
