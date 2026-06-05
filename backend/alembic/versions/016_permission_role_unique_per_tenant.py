"""Restore uniqueness on permission/role names, scoped per tenant.

Revision ID: 016_perm_role_unique
Revises: 015_permission_role_tenant
Create Date: 2026-06-05

Migration 015 dropped the global UNIQUE on permissions.name / roles.name when
it added tenant_id, but never added a replacement. That allowed duplicate
permission/role names (both within a tenant and among system rows), which makes
name-based RBAC resolution ambiguous. This restores uniqueness with two partial
indexes per table:
  - (tenant_id, name) WHERE tenant_id IS NOT NULL  -> unique per tenant
  - (name)            WHERE tenant_id IS NULL       -> unique among system rows
Two indexes are needed because Postgres treats NULL tenant_ids as distinct.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "016_perm_role_unique"
down_revision = "015_permission_role_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_permissions_tenant_name",
        "permissions",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_permissions_system_name",
        "permissions",
        ["name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    op.create_index(
        "uq_roles_tenant_name",
        "roles",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_roles_system_name",
        "roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_roles_system_name", table_name="roles")
    op.drop_index("uq_roles_tenant_name", table_name="roles")
    op.drop_index("uq_permissions_system_name", table_name="permissions")
    op.drop_index("uq_permissions_tenant_name", table_name="permissions")
