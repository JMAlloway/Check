"""Add is_demo column to key tables for demo mode support.

Revision ID: 008_demo_mode
Revises: 007_ai_guardrails
Create Date: 2025-01-08

Adds is_demo boolean column to track synthetic demo data:
- check_items
- check_images
- check_history
- users
- decisions
- queues
- audit_logs
- item_views

This supports the demo mode feature which provides synthetic data
for demonstrations without requiring real PII or external integrations.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "008_demo_mode"
down_revision = "007_ai_guardrails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_demo column to check_items
    op.add_column(
        "check_items",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_check_items_is_demo", "check_items", ["is_demo"])

    # Add is_demo column to check_images
    op.add_column(
        "check_images",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Add is_demo column to check_history
    op.add_column(
        "check_history",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Add is_demo column to users
    op.add_column(
        "users",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Add is_demo column to decisions
    op.add_column(
        "decisions",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Add is_demo column to queues
    op.add_column(
        "queues",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Add is_demo column to audit_logs
    op.add_column(
        "audit_logs",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Add is_demo column to item_views
    op.add_column(
        "item_views",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    # Remove is_demo columns in reverse order
    op.drop_column("item_views", "is_demo")
    op.drop_column("audit_logs", "is_demo")
    op.drop_column("queues", "is_demo")
    op.drop_column("decisions", "is_demo")
    op.drop_column("users", "is_demo")
    op.drop_column("check_history", "is_demo")
    op.drop_column("check_images", "is_demo")
    op.drop_index("ix_check_items_is_demo", "check_items")
    op.drop_column("check_items", "is_demo")
