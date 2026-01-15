"""Add one-time image access tokens table.

Revision ID: 011_one_time_image_tokens
Revises: 010_policy_tenant_isolation
Create Date: 2026-01-15

SECURITY: This migration adds support for one-time-use, tenant-aware image
access tokens. These tokens replace JWT-based bearer tokens in URLs, providing:
- No JWT in URL (token is opaque UUID)
- One-time use (prevents replay attacks)
- Tenant validation (prevents cross-tenant access)
- Full audit trail
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_one_time_image_tokens'
down_revision = '010_policy_tenant_isolation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create image_access_tokens table."""
    op.create_table(
        'image_access_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('image_id', sa.String(36), sa.ForeignKey('check_images.id'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('used_by_ip', sa.String(45), nullable=True),
        sa.Column('used_by_user_agent', sa.String(500), nullable=True),
        sa.Column('is_thumbnail', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create indexes for performance
    op.create_index('ix_image_access_tokens_tenant_id', 'image_access_tokens', ['tenant_id'])
    op.create_index('ix_image_access_tokens_image_id', 'image_access_tokens', ['image_id'])
    op.create_index('ix_image_access_tokens_expires_at', 'image_access_tokens', ['expires_at'])
    op.create_index('ix_image_access_tokens_image_unused', 'image_access_tokens', ['image_id', 'used_at'])


def downgrade() -> None:
    """Drop image_access_tokens table."""
    op.drop_index('ix_image_access_tokens_image_unused', table_name='image_access_tokens')
    op.drop_index('ix_image_access_tokens_expires_at', table_name='image_access_tokens')
    op.drop_index('ix_image_access_tokens_image_id', table_name='image_access_tokens')
    op.drop_index('ix_image_access_tokens_tenant_id', table_name='image_access_tokens')
    op.drop_table('image_access_tokens')
