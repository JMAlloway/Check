"""Add tenant_id and is_system to permissions and roles for multi-tenant support.

Revision ID: 015_permission_role_tenant
Revises: 014_item_type
Create Date: 2026-01-19

SECURITY: This migration adds tenant isolation to permissions and roles.
System-wide permissions/roles have tenant_id=NULL and is_system=TRUE.
Tenant-specific permissions/roles have tenant_id set and are isolated.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "015_permission_role_tenant"
down_revision = "014_item_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tenant_id and is_system columns to permissions and roles tables."""

    # === PERMISSIONS TABLE ===

    # Add tenant_id column (nullable - NULL means system-wide permission)
    op.add_column("permissions", sa.Column("tenant_id", sa.String(36), nullable=True))

    # Add is_system column (system permissions cannot be modified by tenants)
    op.add_column(
        "permissions", sa.Column("is_system", sa.Boolean(), nullable=False, server_default="true")
    )

    # Mark existing permissions as system-wide (tenant_id=NULL, is_system=TRUE)
    op.execute(
        """
        UPDATE permissions
        SET is_system = true, tenant_id = NULL
        WHERE tenant_id IS NULL
    """
    )

    # Add index for tenant-scoped queries
    op.create_index("ix_permissions_tenant_id", "permissions", ["tenant_id"], unique=False)

    # Drop the old unique constraint on name (was globally unique)
    op.drop_constraint("permissions_name_key", "permissions", type_="unique")

    # === ROLES TABLE ===

    # Add tenant_id column (nullable - NULL means system-wide role)
    op.add_column("roles", sa.Column("tenant_id", sa.String(36), nullable=True))

    # Mark existing roles as system-wide
    op.execute(
        """
        UPDATE roles
        SET tenant_id = NULL
        WHERE tenant_id IS NULL
    """
    )

    # Add index for tenant-scoped queries
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"], unique=False)

    # Drop the old unique constraint on name (was globally unique)
    op.drop_constraint("roles_name_key", "roles", type_="unique")


def downgrade() -> None:
    """Remove tenant_id and is_system columns from permissions and roles tables."""

    # === ROLES TABLE ===
    op.create_constraint("roles_name_key", "roles", "unique", ["name"])
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_column("roles", "tenant_id")

    # === PERMISSIONS TABLE ===
    op.create_constraint("permissions_name_key", "permissions", "unique", ["name"])
    op.drop_index("ix_permissions_tenant_id", table_name="permissions")
    op.drop_column("permissions", "is_system")
    op.drop_column("permissions", "tenant_id")
