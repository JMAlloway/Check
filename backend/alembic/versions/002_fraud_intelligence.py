"""Add fraud intelligence sharing tables.

Revision ID: 002_fraud
Revises: 001_initial
Create Date: 2026-01-06

This migration adds:
- fraud_events: Tenant-private fraud event records
- fraud_shared_artifacts: Network-shareable hashed indicators
- network_match_alerts: Cross-institution match alerts
- tenant_fraud_configs: Per-tenant sharing configuration
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_fraud'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create fraud intelligence tables."""

    # Enum types - use create_type=False since we create them explicitly with checkfirst
    fraud_type_enum = postgresql.ENUM(
        'check_kiting', 'counterfeit_check', 'forged_signature', 'altered_check',
        'account_takeover', 'identity_theft', 'first_party_fraud', 'synthetic_identity',
        'duplicate_deposit', 'unauthorized_endorsement', 'payee_alteration',
        'amount_alteration', 'fictitious_payee', 'other',
        name='fraud_type',
        create_type=False
    )
    fraud_type_enum.create(op.get_bind(), checkfirst=True)

    fraud_channel_enum = postgresql.ENUM(
        'branch', 'atm', 'mobile', 'rdc', 'mail', 'online', 'other',
        name='fraud_channel',
        create_type=False
    )
    fraud_channel_enum.create(op.get_bind(), checkfirst=True)

    amount_bucket_enum = postgresql.ENUM(
        'under_100', '100_to_500', '500_to_1000', '1000_to_5000',
        '5000_to_10000', '10000_to_50000', 'over_50000',
        name='amount_bucket',
        create_type=False
    )
    amount_bucket_enum.create(op.get_bind(), checkfirst=True)

    sharing_level_enum = postgresql.ENUM(
        '0', '1', '2',  # PRIVATE, AGGREGATE, NETWORK_MATCH
        name='sharing_level',
        create_type=False
    )
    sharing_level_enum.create(op.get_bind(), checkfirst=True)

    fraud_event_status_enum = postgresql.ENUM(
        'draft', 'submitted', 'withdrawn',
        name='fraud_event_status',
        create_type=False
    )
    fraud_event_status_enum.create(op.get_bind(), checkfirst=True)

    match_severity_enum = postgresql.ENUM(
        'low', 'medium', 'high',
        name='match_severity',
        create_type=False
    )
    match_severity_enum.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # fraud_events - Tenant-private fraud event records
    # =========================================================================
    op.create_table(
        'fraud_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, index=True),
        sa.Column('check_item_id', sa.String(36), sa.ForeignKey('check_items.id', ondelete='SET NULL'), index=True),
        sa.Column('case_id', sa.String(36), index=True),  # For future case management

        # Event details
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount_bucket', amount_bucket_enum, nullable=False),

        # Classification
        sa.Column('fraud_type', fraud_type_enum, nullable=False),
        sa.Column('channel', fraud_channel_enum, nullable=False),
        sa.Column('confidence', sa.Integer, nullable=False, default=3),  # 1-5 scale

        # Narratives (private narrative is NEVER shared)
        sa.Column('narrative_private', sa.Text),
        sa.Column('narrative_shareable', sa.Text),

        # Sharing configuration
        sa.Column('sharing_level', sa.Integer, nullable=False, default=0),  # 0=Private, 1=Aggregate, 2=Network
        sa.Column('status', fraud_event_status_enum, nullable=False, default='draft'),

        # Metadata
        sa.Column('created_by_user_id', sa.String(36), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True)),
        sa.Column('submitted_by_user_id', sa.String(36)),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True)),
        sa.Column('withdrawn_by_user_id', sa.String(36)),
        sa.Column('withdrawn_reason', sa.Text),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_fraud_events_tenant_status', 'fraud_events', ['tenant_id', 'status'])
    op.create_index('ix_fraud_events_tenant_type', 'fraud_events', ['tenant_id', 'fraud_type'])
    op.create_index('ix_fraud_events_event_date', 'fraud_events', ['event_date'])

    # =========================================================================
    # fraud_shared_artifacts - Network-shareable hashed indicators
    # =========================================================================
    op.create_table(
        'fraud_shared_artifacts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, index=True),
        sa.Column('fraud_event_id', sa.String(36), sa.ForeignKey('fraud_events.id', ondelete='CASCADE'), unique=True),

        # Sharing level
        sa.Column('sharing_level', sa.Integer, nullable=False),

        # Time-based (coarsened for privacy)
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('occurred_month', sa.String(7), nullable=False),  # YYYY-MM format

        # Categorization (safe to share)
        sa.Column('fraud_type', fraud_type_enum, nullable=False),
        sa.Column('channel', fraud_channel_enum, nullable=False),
        sa.Column('amount_bucket', amount_bucket_enum, nullable=False),

        # Hashed indicators for matching (only if sharing_level = 2)
        # JSON: {"routing_hash": "...", "payee_hash": "...", "check_fingerprint": "...", "pepper_version": 1}
        sa.Column('indicators_json', postgresql.JSONB),

        # Pepper version for rotation support
        sa.Column('pepper_version', sa.Integer, nullable=False, default=1),

        # Whether this artifact is active for matching
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_fraud_shared_artifacts_active', 'fraud_shared_artifacts', ['is_active', 'sharing_level'])
    op.create_index('ix_fraud_shared_artifacts_occurred_month', 'fraud_shared_artifacts', ['occurred_month'])
    op.create_index('ix_fraud_shared_artifacts_fraud_type', 'fraud_shared_artifacts', ['fraud_type'])
    op.create_index('ix_fraud_shared_artifacts_pepper_version', 'fraud_shared_artifacts', ['pepper_version'])

    # =========================================================================
    # network_match_alerts - Alerts when checks match network indicators
    # =========================================================================
    op.create_table(
        'network_match_alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False, index=True),

        # What this alert is for
        sa.Column('check_item_id', sa.String(36), sa.ForeignKey('check_items.id', ondelete='CASCADE'), index=True),
        sa.Column('case_id', sa.String(36), index=True),

        # Match details (artifact IDs stored but NEVER exposed to user)
        sa.Column('matched_artifact_ids', postgresql.ARRAY(sa.String(36)), nullable=False),

        # Match reasons (aggregated, safe to show)
        sa.Column('match_reasons', postgresql.JSONB, nullable=False),

        # Severity based on match strength
        sa.Column('severity', match_severity_enum, nullable=False),

        # Match statistics (aggregated, no PII)
        sa.Column('total_matches', sa.Integer, nullable=False, default=1),
        sa.Column('distinct_institutions', sa.Integer, nullable=False, default=1),
        sa.Column('earliest_match_date', sa.DateTime(timezone=True)),
        sa.Column('latest_match_date', sa.DateTime(timezone=True)),

        # Dismissal tracking (per-tenant case-level with audit trail)
        sa.Column('dismissed_at', sa.DateTime(timezone=True)),
        sa.Column('dismissed_by_user_id', sa.String(36)),
        sa.Column('dismissed_reason', sa.Text),

        # Status
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_network_match_alerts_tenant_check', 'network_match_alerts', ['tenant_id', 'check_item_id'])
    op.create_index('ix_network_match_alerts_severity', 'network_match_alerts', ['severity', 'dismissed_at'])

    # =========================================================================
    # tenant_fraud_configs - Per-tenant sharing configuration
    # =========================================================================
    op.create_table(
        'tenant_fraud_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), unique=True, nullable=False, index=True),

        # Default sharing level for new fraud event submissions
        sa.Column('default_sharing_level', sa.Integer, nullable=False, default=0),

        # Whether shareable narratives are allowed at all
        sa.Column('allow_narrative_sharing', sa.Boolean, default=False, nullable=False),

        # Whether to hash and share account-related indicators (higher risk)
        sa.Column('allow_account_indicator_sharing', sa.Boolean, default=False, nullable=False),

        # Data retention in months for shared artifacts
        sa.Column('shared_artifact_retention_months', sa.Integer, default=24, nullable=False),

        # Whether this tenant wants to receive network match alerts
        sa.Column('receive_network_alerts', sa.Boolean, default=True, nullable=False),

        # Minimum match severity to alert on
        sa.Column('minimum_alert_severity', match_severity_enum, default='low', nullable=False),

        # Admin who last modified
        sa.Column('last_modified_by_user_id', sa.String(36)),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop fraud intelligence tables."""
    op.drop_table('tenant_fraud_configs')
    op.drop_table('network_match_alerts')
    op.drop_table('fraud_shared_artifacts')
    op.drop_table('fraud_events')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS match_severity')
    op.execute('DROP TYPE IF EXISTS fraud_event_status')
    op.execute('DROP TYPE IF EXISTS sharing_level')
    op.execute('DROP TYPE IF EXISTS amount_bucket')
    op.execute('DROP TYPE IF EXISTS fraud_channel')
    op.execute('DROP TYPE IF EXISTS fraud_type')
