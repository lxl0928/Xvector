from __future__ import annotations

from typing import Any

from xvector.auth.password import bootstrap_matches, generate_salt, hash_password, verify_password
from xvector.common.errors import AlreadyExistsError, NotFoundError, ParamError
from xvector.meta import docs
from xvector.services.context import AppContext


class UserService:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def create(self, username: str, password: str) -> dict[str, Any]:
        if not username or not password:
            raise ParamError("userName and password required")
        if self.ctx.catalog.get_user(username):
            raise AlreadyExistsError(f"user already exists: {username}")
        salt = generate_salt()
        user = {
            "username": username,
            "password_salt": salt,
            "password_hash": hash_password(password, salt),
            "roles": [],
            "is_bootstrap": False,
            "created_at": docs.now_ms(),
            "updated_at": docs.now_ms(),
        }
        self.ctx.catalog.put_user(user)
        return {"username": username}

    def drop(self, username: str) -> dict[str, Any]:
        bootstrap = self.ctx.settings.username
        if username == bootstrap:
            raise ParamError("cannot drop bootstrap user")
        if not self.ctx.catalog.get_user(username):
            raise NotFoundError(f"user not found: {username}")
        self.ctx.catalog.delete_user(username)
        return {}

    def describe(self, username: str) -> dict[str, Any]:
        user = self.ctx.catalog.get_user(username)
        if not user:
            raise NotFoundError(f"user not found: {username}")
        return {"userName": user["username"], "roles": user.get("roles") or []}

    def list(self) -> list[str]:
        return self.ctx.catalog.list_users()

    def update_password(self, username: str, old_password: str, new_password: str) -> dict[str, Any]:
        user = self.ctx.catalog.get_user(username)
        if not user and not bootstrap_matches(username, old_password):
            raise NotFoundError(f"user not found: {username}")
        ok = bootstrap_matches(username, old_password)
        if user and not ok:
            ok = verify_password(old_password, user["password_salt"], user["password_hash"])
        if not ok:
            raise ParamError("old password incorrect")
        if not user:
            # create bootstrap mapping if missing
            salt = generate_salt()
            user = {
                "username": username,
                "password_salt": salt,
                "password_hash": hash_password(new_password, salt),
                "roles": ["admin"],
                "is_bootstrap": True,
                "created_at": docs.now_ms(),
                "updated_at": docs.now_ms(),
            }
        else:
            salt = generate_salt()
            user["password_salt"] = salt
            user["password_hash"] = hash_password(new_password, salt)
            user["updated_at"] = docs.now_ms()
        self.ctx.catalog.put_user(user)
        return {}

    def grant_role(self, username: str, role_name: str) -> dict[str, Any]:
        user = self.ctx.catalog.get_user(username)
        if not user:
            raise NotFoundError(f"user not found: {username}")
        if not self.ctx.catalog.get_role(role_name):
            raise NotFoundError(f"role not found: {role_name}")
        roles = list(user.get("roles") or [])
        if role_name not in roles:
            roles.append(role_name)
        user["roles"] = roles
        user["updated_at"] = docs.now_ms()
        self.ctx.catalog.put_user(user)
        return {}

    def revoke_role(self, username: str, role_name: str) -> dict[str, Any]:
        user = self.ctx.catalog.get_user(username)
        if not user:
            raise NotFoundError(f"user not found: {username}")
        roles = [r for r in (user.get("roles") or []) if r != role_name]
        user["roles"] = roles
        user["updated_at"] = docs.now_ms()
        self.ctx.catalog.put_user(user)
        return {}

    def verify(self, username: str, password: str) -> bool:
        if bootstrap_matches(username, password):
            return True
        user = self.ctx.catalog.get_user(username)
        if not user:
            return False
        return verify_password(password, user["password_salt"], user["password_hash"])
