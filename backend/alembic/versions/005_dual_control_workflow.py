"""Dual Control Workflow Enhancements

Revision ID: 005_dual_control_workflow
Revises: 004_audit_immutability
Create Date: 2024-01-17

NOTE: This migration is now a NO-OP.

All dual control workflow columns and tables are now created in 001_initial_schema:
- check_items.pending_dual_control_decision_id
- check_items.dual_control_reason
- approval_entitlements table

This migration file is kept for revision chain integrity.
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
    # NO-OP: All dual control columns and tables are now in 001_initial_schema
    # ==========================================================================
    # The following were moved to 001_initial_schema:
    # - check_items.pending_dual_control_decision_id (with FK and index)
    # - check_items.dual_control_reason
    # - approval_entitlements table (with indexes)
    # - approvalentitlementtype enum
    pass


def downgrade() -> None:
    # ==========================================================================
    # NO-OP: Downgrade handled by 001_initial_schema
    # ==========================================================================
    pass
