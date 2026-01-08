"""Dual Control Workflow Enhancements

Revision ID: 005_dual_control_workflow
Revises: 004_audit_immutability
Create Date: 2024-01-17

This migration implements proper dual control workflow modeling:

1. Adds pending_dual_control_decision_id to track which decision awaits approval
2. Adds dual_control_reason to document why dual control was triggered
3. Creates approval_entitlements table for fine-grained approval limits:
   - Amount thresholds (min/max)
   - Account type restrictions
   - Queue restrictions
   - Risk level restrictions
   - Business line restrictions

NOTE: status column is String(20) in 001_initial, so 'pending_dual_control'
status value can be used directly without schema changes.

This enables:
- Clear separation of "review recommendation" vs "approval decision" states
- Entitlement-based approval (approvers can only approve within their limits)
- Easy UI + audit tracking of pending dual control items
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_dual_control_workflow'
down_revision = '004_audit_immutability'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # NOTE: status column is String(20) in 001_initial, not an enum
    # No ALTER TYPE needed - strings can hold 'pending_dual_control' directly
    # ==========================================================================

    # ==========================================================================
    # ADD DUAL CONTROL TRACKING COLUMNS TO CHECK_ITEMS
    # ==========================================================================

    # pending_dual_control_decision_id - FK to the decision awaiting approval
    op.add_column(
        'check_items',
        sa.Column('pending_dual_control_decision_id', sa.String(36), nullable=True)
    )
    op.create_foreign_key(
        'fk_check_items_pending_decision',
        'check_items',
        'decisions',
        ['pending_dual_control_decision_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        'ix_check_items_pending_dual_control',
        'check_items',
        ['pending_dual_control_decision_id']
    )

    # dual_control_reason - why dual control was triggered
    op.add_column(
        'check_items',
        sa.Column('dual_control_reason', sa.String(100), nullable=True)
    )

    # ==========================================================================
    # CREATE APPROVAL ENTITLEMENT TYPE ENUM
    # ==========================================================================
    approval_entitlement_type = postgresql.ENUM(
        'review',
        'approve',
        'override',
        name='approvalentitlementtype',
        create_type=False
    )
    approval_entitlement_type.create(op.get_bind(), checkfirst=True)

    # ==========================================================================
    # CREATE APPROVAL_ENTITLEMENTS TABLE
    # ==========================================================================
    op.create_table(
        'approval_entitlements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),

        # Who has this entitlement
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=True),

        # Type of entitlement
        sa.Column('entitlement_type', postgresql.ENUM('review', 'approve', 'override', name='approvalentitlementtype', create_type=False), nullable=False),

        # Amount limits (NULL = no limit)
        sa.Column('min_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('max_amount', sa.Numeric(12, 2), nullable=True),

        # Scope restrictions (JSONB arrays, NULL = all allowed)
        sa.Column('allowed_account_types', postgresql.JSONB(), nullable=True),
        sa.Column('allowed_queue_ids', postgresql.JSONB(), nullable=True),
        sa.Column('allowed_risk_levels', postgresql.JSONB(), nullable=True),
        sa.Column('allowed_business_lines', postgresql.JSONB(), nullable=True),

        # Multi-tenant support
        sa.Column('tenant_id', sa.String(36), nullable=True),

        # Flexible additional conditions
        sa.Column('conditions', postgresql.JSONB(), nullable=True),

        # Status and validity period
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_until', sa.DateTime(timezone=True), nullable=True),

        # Audit trail
        sa.Column('granted_by_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('grant_reason', sa.Text(), nullable=True),
    )

    # Create indexes for efficient lookup
    op.create_index('ix_approval_entitlements_user_id', 'approval_entitlements', ['user_id'])
    op.create_index('ix_approval_entitlements_role_id', 'approval_entitlements', ['role_id'])
    op.create_index('ix_approval_entitlements_tenant_id', 'approval_entitlements', ['tenant_id'])
    op.create_index(
        'ix_approval_entitlements_active_type',
        'approval_entitlements',
        ['is_active', 'entitlement_type']
    )

    # ==========================================================================
    # CREATE DEFAULT ENTITLEMENTS FOR EXISTING USERS WITH APPROVE PERMISSION
    # ==========================================================================
    # This ensures existing approvers continue to work after migration
    # They get unlimited approval entitlement by default
    op.execute("""
        INSERT INTO approval_entitlements (
            id, user_id, entitlement_type, is_active, effective_from, grant_reason, created_at, updated_at
        )
        SELECT
            gen_random_uuid()::text,
            u.id,
            'approve',
            true,
            NOW(),
            'Auto-migrated from existing approve permission',
            NOW(),
            NOW()
        FROM users u
        WHERE u.id IN (
            SELECT DISTINCT rp.role_id
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.id
            WHERE p.name = 'approve' AND p.resource = 'check_item'
        )
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_approval_entitlements_active_type', table_name='approval_entitlements')
    op.drop_index('ix_approval_entitlements_tenant_id', table_name='approval_entitlements')
    op.drop_index('ix_approval_entitlements_role_id', table_name='approval_entitlements')
    op.drop_index('ix_approval_entitlements_user_id', table_name='approval_entitlements')

    # Drop table
    op.drop_table('approval_entitlements')

    # Drop enum
    op.execute("DROP TYPE IF EXISTS approvalentitlementtype")

    # Remove columns from check_items
    op.drop_index('ix_check_items_pending_dual_control', table_name='check_items')
    op.drop_constraint('fk_check_items_pending_decision', 'check_items', type_='foreignkey')
    op.drop_column('check_items', 'dual_control_reason')
    op.drop_column('check_items', 'pending_dual_control_decision_id')

    # Note: status column is String(20), so 'pending_dual_control' values are just data
