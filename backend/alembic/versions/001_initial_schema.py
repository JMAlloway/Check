"""Initial schema with all base tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema tables."""

    # Users and Roles
    op.create_table(
        'permissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('resource', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'roles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text),
        sa.Column('is_system', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', sa.String(36), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('department', sa.String(100)),
        sa.Column('branch', sa.String(100)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_superuser', sa.Boolean, default=False),
        sa.Column('tenant_id', sa.String(36)),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])

    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role_id', sa.String(36), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    )

    # Queues
    op.create_table(
        'queues',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('queue_type', sa.String(50), nullable=False),
        sa.Column('sla_hours', sa.Integer, default=4),
        sa.Column('warning_threshold_minutes', sa.Integer, default=30),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('display_order', sa.Integer, default=0),
        sa.Column('tenant_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Check Items
    op.create_table(
        'check_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('external_item_id', sa.String(100)),
        sa.Column('source_system', sa.String(50)),
        sa.Column('account_id', sa.String(36)),
        sa.Column('account_number_masked', sa.String(20)),
        sa.Column('account_type', sa.String(20)),
        sa.Column('routing_number', sa.String(9)),
        sa.Column('check_number', sa.String(20)),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('payee_name', sa.String(255)),
        sa.Column('memo', sa.Text),
        sa.Column('micr_line', sa.String(100)),
        sa.Column('micr_routing', sa.String(9)),
        sa.Column('micr_account', sa.String(20)),
        sa.Column('micr_check_number', sa.String(20)),
        sa.Column('presented_date', sa.DateTime(timezone=True)),
        sa.Column('check_date', sa.DateTime(timezone=True)),
        sa.Column('process_date', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False, default='new'),
        sa.Column('risk_level', sa.String(20), default='low'),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('requires_dual_control', sa.Boolean, default=False),
        sa.Column('sla_due_at', sa.DateTime(timezone=True)),
        sa.Column('sla_breached', sa.Boolean, default=False),
        sa.Column('assigned_reviewer_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('assigned_approver_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('queue_id', sa.String(36), sa.ForeignKey('queues.id', ondelete='SET NULL')),
        sa.Column('policy_version_id', sa.String(36)),
        sa.Column('ai_flags_json', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_check_items_tenant_id', 'check_items', ['tenant_id'])
    op.create_index('ix_check_items_status', 'check_items', ['status'])
    op.create_index('ix_check_items_account_id', 'check_items', ['account_id'])

    # Check Images
    op.create_table(
        'check_images',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('check_item_id', sa.String(36), sa.ForeignKey('check_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_type', sa.String(20), nullable=False),
        sa.Column('content_type', sa.String(50)),
        sa.Column('file_size', sa.Integer),
        sa.Column('width', sa.Integer),
        sa.Column('height', sa.Integer),
        sa.Column('storage_path', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Check History
    op.create_table(
        'check_history',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), nullable=False),
        sa.Column('check_number', sa.String(20)),
        sa.Column('amount', sa.Numeric(12, 2)),
        sa.Column('check_date', sa.DateTime(timezone=True)),
        sa.Column('payee_name', sa.String(255)),
        sa.Column('status', sa.String(20)),
        sa.Column('return_reason', sa.String(100)),
        sa.Column('front_image_url', sa.String(500)),
        sa.Column('back_image_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_check_history_account_id', 'check_history', ['account_id'])

    # Decisions
    op.create_table(
        'reason_codes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('category', sa.String(50)),
        sa.Column('decision_type', sa.String(50)),
        sa.Column('requires_notes', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('check_item_id', sa.String(36), sa.ForeignKey('check_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('decision_type', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text),
        sa.Column('ai_assisted', sa.Boolean, default=False),
        sa.Column('is_dual_control_required', sa.Boolean, default=False),
        sa.Column('dual_control_approver_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('dual_control_approved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'decision_reason_codes',
        sa.Column('decision_id', sa.String(36), sa.ForeignKey('decisions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('reason_code_id', sa.String(36), sa.ForeignKey('reason_codes.id', ondelete='CASCADE'), primary_key=True),
    )

    # Policies
    op.create_table(
        'policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'policy_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('policy_id', sa.String(36), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('is_active', sa.Boolean, default=False),
        sa.Column('effective_from', sa.DateTime(timezone=True)),
        sa.Column('effective_to', sa.DateTime(timezone=True)),
        sa.Column('created_by_user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'policy_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('policy_version_id', sa.String(36), sa.ForeignKey('policy_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('rule_type', sa.String(50), nullable=False),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('conditions_json', postgresql.JSONB),
        sa.Column('actions_json', postgresql.JSONB),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Audit
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36)),
        sa.Column('user_id', sa.String(36)),
        sa.Column('username', sa.String(100)),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50)),
        sa.Column('resource_id', sa.String(36)),
        sa.Column('description', sa.Text),
        sa.Column('metadata_json', postgresql.JSONB),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    op.create_table(
        'item_views',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('check_item_id', sa.String(36), sa.ForeignKey('check_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('view_duration_seconds', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Queue Assignments
    op.create_table(
        'queue_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('queue_id', sa.String(36), sa.ForeignKey('queues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('queue_assignments')
    op.drop_table('item_views')
    op.drop_table('audit_logs')
    op.drop_table('policy_rules')
    op.drop_table('policy_versions')
    op.drop_table('policies')
    op.drop_table('decision_reason_codes')
    op.drop_table('decisions')
    op.drop_table('reason_codes')
    op.drop_table('check_history')
    op.drop_table('check_images')
    op.drop_table('check_items')
    op.drop_table('queues')
    op.drop_table('user_roles')
    op.drop_table('users')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('permissions')
