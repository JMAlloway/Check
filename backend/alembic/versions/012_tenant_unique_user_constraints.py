"""Change user email/username to tenant-scoped uniqueness.

Revision ID: 012_tenant_unique_user_constraints
Revises: 011_one_time_image_tokens
Create Date: 2026-01-15

SECURITY: This migration changes email and username uniqueness from global
to tenant-scoped. This is critical for proper multi-tenant isolation:
- Users in different tenants can have the same email/username
- Prevents cross-tenant user enumeration attacks
- Aligns with banking compliance requirements for tenant isolation
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_tenant_unique_user_constraints'
down_revision = '011_one_time_image_tokens'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change from global unique to tenant-scoped unique constraints."""
    # Drop existing global unique constraints
    # Note: Index names may vary - drop both possible names
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("DROP INDEX IF EXISTS ix_users_username")

    # Drop unique constraints (PostgreSQL creates these as unique indexes)
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key")

    # Create composite unique constraints (tenant + email, tenant + username)
    op.create_unique_constraint(
        'uq_users_tenant_email',
        'users',
        ['tenant_id', 'email']
    )
    op.create_unique_constraint(
        'uq_users_tenant_username',
        'users',
        ['tenant_id', 'username']
    )

    # Create composite indexes for query performance
    op.create_index(
        'ix_users_tenant_email',
        'users',
        ['tenant_id', 'email']
    )
    op.create_index(
        'ix_users_tenant_username',
        'users',
        ['tenant_id', 'username']
    )


def downgrade() -> None:
    """Revert to global unique constraints.

    WARNING: This will fail if there are duplicate emails/usernames across tenants.
    """
    # Drop composite indexes
    op.drop_index('ix_users_tenant_username', table_name='users')
    op.drop_index('ix_users_tenant_email', table_name='users')

    # Drop composite unique constraints
    op.drop_constraint('uq_users_tenant_username', 'users', type_='unique')
    op.drop_constraint('uq_users_tenant_email', 'users', type_='unique')

    # Recreate global unique constraints
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
