from __future__ import annotations

import uuid

from tests.conftest import milvus_schema


def test_user_role_crud(client, unique_name):
    user = f"u_{uuid.uuid4().hex[:8]}"
    role = f"r_{uuid.uuid4().hex[:8]}"
    client.create_role(role)
    assert role in client.list_roles()
    client.grant_privilege(role, "Collection", "*", "Search")
    desc = client.describe_role(role)
    privs = desc.get("privileges") or []
    assert any(p.get("privilege") == "Search" for p in privs)
    assert any(
        p.get("objectType") == "Collection" and p.get("objectName") == "*" for p in privs
    )

    client.create_user(user, "pass123")
    assert user in client.list_users()
    client.grant_role(user, role)
    ud = client.describe_user(user)
    assert role in ud.get("roles", [])

    # Privilege is stored but NOT enforced — bootstrap can still call business API
    name = unique_name
    client.create_collection(name, schema=milvus_schema())
    assert client.has_collection(name)["has"] is True
    client.drop_collection(name)

    client.revoke_role(user, role)
    client.drop_user(user)
    client.revoke_privilege(role, "Collection", "*", "Search")
    client.drop_role(role)
