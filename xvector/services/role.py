from __future__ import annotations

from typing import Any

from xvector.common.errors import AlreadyExistsError, NotFoundError, ParamError
from xvector.meta import docs
from xvector.services.context import AppContext


class RoleService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def create(self, role_name: str) -> dict[str, Any]:
        if not role_name:
            raise ParamError("roleName required")
        self.ctx.catalog.create_role(role_name)
        return {}

    def drop(self, role_name: str) -> dict[str, Any]:
        if role_name == "admin":
            raise ParamError("cannot drop admin role")
        if not self.ctx.catalog.get_role(role_name):
            raise NotFoundError(f"role not found: {role_name}")
        self.ctx.catalog.delete_role(role_name)
        return {}

    def describe(self, role_name: str) -> dict[str, Any]:
        role = self.ctx.catalog.get_role(role_name)
        if not role:
            raise NotFoundError(f"role not found: {role_name}")
        privileges = []
        for p in role.get("privileges") or []:
            privileges.append(
                {
                    "objectType": p.get("objectType") or p.get("object_type"),
                    "objectName": p.get("objectName") or p.get("object_name"),
                    "privilege": p.get("privilege"),
                }
            )
        return {"roleName": role["role_name"], "privileges": privileges}

    def list(self) -> list[str]:
        return self.ctx.catalog.list_roles()

    def grant_privilege(self, role_name: str, object_type: str, object_name: str, privilege: str) -> dict[str, Any]:
        role = self.ctx.catalog.get_role(role_name)
        if not role:
            raise NotFoundError(f"role not found: {role_name}")
        privs = list(role.get("privileges") or [])
        entry = {"object_type": object_type, "object_name": object_name, "privilege": privilege}
        if entry not in privs:
            privs.append(entry)
        role["privileges"] = privs
        role["updated_at"] = docs.now_ms()
        self.ctx.catalog.put_role(role)
        return {}

    def revoke_privilege(self, role_name: str, object_type: str, object_name: str, privilege: str) -> dict[str, Any]:
        role = self.ctx.catalog.get_role(role_name)
        if not role:
            raise NotFoundError(f"role not found: {role_name}")
        privs = [
            p
            for p in (role.get("privileges") or [])
            if not (
                p.get("object_type") == object_type
                and p.get("object_name") == object_name
                and p.get("privilege") == privilege
            )
        ]
        role["privileges"] = privs
        role["updated_at"] = docs.now_ms()
        self.ctx.catalog.put_role(role)
        return {}
