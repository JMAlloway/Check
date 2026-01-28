"""Add tenant_id to policies table for multi-tenant isolation.

Revision ID: 010_policy_tenant_isolation
Revises: 009_tenant_unique_external_id
Create Date: 2026-01-15

SECURITY: This migration adds tenant isolation to the policies table.
All policies will be assigned to a default tenant during migration.
After migration, policies are tenant-scoped and cannot be accessed
across tenant boundaries.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "010_policy_tenant_isolation"
down_revision = "009_tenant_unique_external_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tenant_id column to policies table."""
    # Add tenant_id column (nullable initially for existing data)
    op.add_column("policies", sa.Column("tenant_id", sa.String(36), nullable=True))

    # Update existing policies with a default tenant
    # In production, you would assign policies to appropriate tenants
    # based on business logic or manual assignment
    op.execute("""
        UPDATE policies
        SET tenant_id = (
            SELECT COALESCE(
                (SELECT tenant_id FROM users WHERE is_superuser = true LIMIT 1),
                'default-tenant'
            )
        )
        WHERE tenant_id IS NULL
    """)

    # Make tenant_id non-nullable after data migration
    op.alter_column("policies", "tenant_id", existing_type=sa.String(36), nullable=False)

    # Add index for query performance on tenant-scoped queries
    op.create_index("ix_policies_tenant_id", "policies", ["tenant_id"], unique=False)

    # Add composite index for common query pattern: tenant + status
    op.create_index("ix_policies_tenant_status", "policies", ["tenant_id", "status"], unique=False)


def downgrade() -> None:
    """Remove tenant_id column from policies table."""
    op.drop_index("ix_policies_tenant_status", table_name="policies")
    op.drop_index("ix_policies_tenant_id", table_name="policies")
    op.drop_column("policies", "tenant_id")
