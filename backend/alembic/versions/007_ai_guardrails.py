"""AI guardrails - tracking fields for bank-grade AI compliance.

Revision ID: 007_ai_guardrails
Revises: 006_performance_fixes
Create Date: 2025-01-08

NOTE: This migration is now a NO-OP.

All AI tracking columns are now created in 001_initial_schema:
- ai_model_id
- ai_model_version
- ai_analyzed_at
- ai_recommendation
- ai_confidence
- ai_explanation
- ai_risk_factors
- ix_check_items_ai_analyzed index

This migration file is kept for revision chain integrity.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007_ai_guardrails"
down_revision = "006_performance_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # NO-OP: All AI columns are now in 001_initial_schema
    # ==========================================================================
    # The following AI tracking columns are now created in 001_initial_schema:
    # - check_items.ai_model_id
    # - check_items.ai_model_version
    # - check_items.ai_analyzed_at
    # - check_items.ai_recommendation
    # - check_items.ai_confidence
    # - check_items.ai_explanation
    # - check_items.ai_risk_factors
    # - ix_check_items_ai_analyzed partial index
    pass


def downgrade() -> None:
    # ==========================================================================
    # NO-OP: Downgrade handled by 001_initial_schema
    # ==========================================================================
    pass
