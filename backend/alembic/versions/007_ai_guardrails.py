"""AI guardrails - tracking fields for bank-grade AI compliance.

Revision ID: 007_ai_guardrails
Revises: 006_performance_fixes
Create Date: 2025-01-08

This migration adds AI tracking fields to check_items for:
1. Model identification (id, version)
2. Analysis timestamp
3. Advisory recommendation (NEVER authoritative)
4. Confidence scoring
5. Explanation and risk factors

CRITICAL: AI output is ALWAYS advisory. These fields are for:
- Audit trail: prove what AI said at decision time
- Explainability: show reviewers why AI flagged something
- Compliance: demonstrate AI was not auto-decisioning
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007_ai_guardrails"
down_revision = "006_performance_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add AI tracking columns to check_items
    op.add_column(
        "check_items",
        sa.Column("ai_model_id", sa.String(100), nullable=True, comment="AI model identifier"),
    )
    op.add_column(
        "check_items",
        sa.Column("ai_model_version", sa.String(50), nullable=True, comment="AI model version"),
    )
    op.add_column(
        "check_items",
        sa.Column(
            "ai_analyzed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When AI analysis was performed",
        ),
    )
    op.add_column(
        "check_items",
        sa.Column(
            "ai_recommendation",
            sa.String(50),
            nullable=True,
            comment="ADVISORY recommendation from AI (never authoritative)",
        ),
    )
    op.add_column(
        "check_items",
        sa.Column(
            "ai_confidence",
            sa.Numeric(5, 4),
            nullable=True,
            comment="AI confidence score 0.0000-1.0000",
        ),
    )
    op.add_column(
        "check_items",
        sa.Column(
            "ai_explanation",
            sa.Text,
            nullable=True,
            comment="Human-readable AI explanation",
        ),
    )
    op.add_column(
        "check_items",
        sa.Column(
            "ai_risk_factors",
            sa.Text,
            nullable=True,
            comment="JSON array of AI-identified risk factors",
        ),
    )

    # Add index for finding items with AI analysis
    op.create_index(
        "ix_check_items_ai_analyzed",
        "check_items",
        ["ai_analyzed_at"],
        postgresql_where=sa.text("ai_analyzed_at IS NOT NULL"),
    )

    # Add comment to table explaining AI policy
    op.execute(
        """
        COMMENT ON TABLE check_items IS
        'Check items for review. AI fields (ai_*) are ADVISORY ONLY - AI never auto-decisions. Human review is always required.';
        """
    )


def downgrade() -> None:
    op.drop_index("ix_check_items_ai_analyzed", table_name="check_items")
    op.drop_column("check_items", "ai_risk_factors")
    op.drop_column("check_items", "ai_explanation")
    op.drop_column("check_items", "ai_confidence")
    op.drop_column("check_items", "ai_recommendation")
    op.drop_column("check_items", "ai_analyzed_at")
    op.drop_column("check_items", "ai_model_version")
    op.drop_column("check_items", "ai_model_id")
