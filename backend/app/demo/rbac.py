"""Reusable RBAC catalog + seeder for demo mode.

The demo seeder previously created users but no roles/permissions, so every
non-superuser demo user got 403 on everything. This module defines the same
6-role catalog as scripts/seed_db.py (the authoritative source) and seeds it
idempotently so demo users can exercise role-appropriate access.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Permission, Role

# All permission names (resource:action) the API actually enforces.
# Keep this in sync with require_permission(...) calls across app/api.
PERMISSION_NAMES: list[str] = [
    # Check items
    "check_item:view",
    "check_item:review",
    "check_item:approve",
    "check_item:assign",
    "check_item:update",
    "check_item:sync",
    "check_image:view",
    # Queues
    "queue:view",
    "queue:create",
    "queue:update",
    "queue:assign",
    # Users / roles
    "user:view",
    "user:create",
    "user:update",
    "role:view",
    "role:create",
    "permission:view",
    # Policies
    "policy:view",
    "policy:create",
    "policy:update",
    "policy:delete",
    "policy:activate",
    # Reports / audit / archive
    "report:view",
    "report:export",
    "audit:view",
    "audit:export",
    "archive:view",
    "archive:export",
    # Fraud
    "fraud:view",
    "fraud:create",
    "fraud:submit",
    "fraud:withdraw",
    # Decision commit service (Connector B)
    "connector:view",
    "connector:approve",
    "connector:create",
    "connector:admin",
    # Image intake connector (Connector A)
    "image_connector:view",
    "image_connector:create",
    "image_connector:update",
    "image_connector:delete",
]

# Common read-only access shared by every working role.
_BASE_READ = [
    "check_item:view",
    "check_image:view",
    "queue:view",
    "user:view",
    "role:view",
    "permission:view",
    "policy:view",
    "report:view",
    "fraud:view",
    "archive:view",
]

# role name -> permission names. Higher roles are supersets of lower ones.
_REVIEWER = _BASE_READ + [
    "check_item:review",
    "fraud:create",  # front-line reviewers can report suspected fraud
]
_SENIOR_REVIEWER = _REVIEWER + [
    "check_item:approve",  # second-approver for dual control
    "check_item:assign",
    "fraud:submit",
]
_SUPERVISOR = _SENIOR_REVIEWER + [
    "check_item:update",
    "check_item:sync",
    "queue:create",
    "queue:update",
    "queue:assign",
    "audit:view",
    "audit:export",
    "report:export",
    "archive:export",
    "fraud:withdraw",
    "connector:view",
    "connector:approve",
    "image_connector:view",
]
_ADMINISTRATOR = _SUPERVISOR + [
    "user:create",
    "user:update",
    "role:create",
    "policy:create",
    "policy:update",
    "policy:delete",
    "policy:activate",
    "connector:create",
    "connector:admin",
    "image_connector:create",
    "image_connector:update",
    "image_connector:delete",
]
_AUDITOR = _BASE_READ + [
    "report:export",
    "audit:view",
    "audit:export",
    "archive:export",
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    # de-dup while preserving order
    "reviewer": list(dict.fromkeys(_REVIEWER)),
    "senior_reviewer": list(dict.fromkeys(_SENIOR_REVIEWER)),
    "supervisor": list(dict.fromkeys(_SUPERVISOR)),
    "administrator": list(dict.fromkeys(_ADMINISTRATOR)),
    "auditor": list(dict.fromkeys(_AUDITOR)),
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
