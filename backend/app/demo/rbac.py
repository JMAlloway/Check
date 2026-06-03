"""Reusable RBAC catalog + seeder for demo mode.

The demo seeder previously created users but no roles/permissions, so every
non-superuser demo user got 403 on everything. This module defines the same
6-role catalog as scripts/seed_db.py (the authoritative source) and seeds it
idempotently so demo users can exercise role-appropriate access.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Permission, Role

# All permission names (resource:action). Mirrors scripts/seed_db.py.
PERMISSION_NAMES: list[str] = [
    "check_item:view",
    "check_item:review",
    "check_item:approve",
    "check_item:dual_control",
    "check_item:reassign",
    "queue:view",
    "queue:create",
    "queue:update",
    "queue:assign",
    "queue:manage",
    "user:view",
    "user:create",
    "user:update",
    "user:manage",
    "role:view",
    "role:create",
    "permission:view",
    "policy:view",
    "policy:create",
    "policy:update",
    "policy:activate",
    "policy:manage",
    "report:view",
    "fraud:view",
    "fraud:create",
    "fraud:submit",
    "fraud:withdraw",
    "fraud:config",
    "audit:view",
    "audit:export",
    "archive:view",
    "archive:export",
]

# role name -> permission names. Higher roles are supersets of lower ones.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "reviewer": [
        "check_item:view",
        "check_item:review",
        "queue:view",
        "user:view",
        "role:view",
        "permission:view",
        "policy:view",
        "report:view",
        "fraud:view",
        "archive:view",
    ],
    "senior_reviewer": [
        "check_item:view",
        "check_item:review",
        "check_item:approve",
        "check_item:dual_control",
        "queue:view",
        "user:view",
        "role:view",
        "permission:view",
        "policy:view",
        "report:view",
        "fraud:view",
        "archive:view",
    ],
    "supervisor": [
        "check_item:view",
        "check_item:review",
        "check_item:approve",
        "check_item:dual_control",
        "check_item:reassign",
        "queue:view",
        "queue:create",
        "queue:update",
        "queue:assign",
        "queue:manage",
        "user:view",
        "role:view",
        "permission:view",
        "policy:view",
        "report:view",
        "fraud:view",
        "audit:view",
        "archive:view",
        "archive:export",
    ],
    "administrator": [
        "check_item:view",
        "check_item:review",
        "check_item:approve",
        "check_item:dual_control",
        "check_item:reassign",
        "queue:view",
        "queue:create",
        "queue:update",
        "queue:assign",
        "queue:manage",
        "user:view",
        "user:create",
        "user:update",
        "user:manage",
        "role:view",
        "role:create",
        "permission:view",
        "policy:view",
        "policy:create",
        "policy:update",
        "policy:activate",
        "policy:manage",
        "report:view",
        "fraud:view",
        "fraud:create",
        "fraud:submit",
        "fraud:withdraw",
        "fraud:config",
        "audit:view",
        "audit:export",
        "archive:view",
        "archive:export",
    ],
    "auditor": [
        "check_item:view",
        "queue:view",
        "user:view",
        "role:view",
        "permission:view",
        "policy:view",
        "report:view",
        "fraud:view",
        "audit:view",
        "audit:export",
        "archive:view",
        "archive:export",
    ],
    "system_admin": list(PERMISSION_NAMES),
}


async def seed_rbac(db: AsyncSession) -> dict[str, Role]:
    """Idempotently create the permission catalog and 6 system roles.

    Returns a {role_name: Role} map so callers can assign roles to users.
    Safe to call repeatedly: existing permissions/roles are reused.
    """
    # Permissions
    existing_perms = {p.name: p for p in (await db.execute(select(Permission))).scalars().all()}
    perm_lookup: dict[str, Permission] = {}
    for name in PERMISSION_NAMES:
        perm = existing_perms.get(name)
        if perm is None:
            resource, action = name.split(":", 1)
            perm = Permission(
                name=name,
                resource=resource,
                action=action,
                description=f"{action} {resource}",
                is_system=True,
            )
            db.add(perm)
        perm_lookup[name] = perm

    # Roles
    existing_roles = {r.name: r for r in (await db.execute(select(Role))).scalars().all()}
    role_map: dict[str, Role] = {}
    for role_name, perm_names in ROLE_PERMISSIONS.items():
        role = existing_roles.get(role_name)
        if role is None:
            role = Role(
                tenant_id=None,
                name=role_name,
                description=f"{role_name} (demo)",
                is_system=True,
            )
            db.add(role)
        role.permissions = [perm_lookup[n] for n in perm_names]
        role_map[role_name] = role

    await db.flush()
    return role_map
