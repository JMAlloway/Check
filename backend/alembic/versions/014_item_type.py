"""Add item_type column to check_items for On Us vs Transit classification.

Revision ID: 014_item_type
Revises: 013_audit_chain_integrity
Create Date: 2026-01-18

Adds item_type enum column to distinguish between:
- ON_US: Check drawn on our bank's customer account (we are paying bank)
- TRANSIT: Check from another bank being deposited (we are collecting bank)

This is critical for processing workflow as On Us and Transit checks
have different risk profiles, processing rules, and regulatory requirements.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "014_item_type"
down_revision = "013_audit_chain_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add item_type column to check_items table."""
    # Create the enum type
    item_type_enum = sa.Enum("on_us", "transit", name="itemtype")
    item_type_enum.create(op.get_bind(), checkfirst=True)

    # Add the item_type column with default value of 'transit'
    # Default to transit since that's typically higher volume
    op.add_column(
        "check_items",
        sa.Column(
            "item_type",
            item_type_enum,
            nullable=False,
            server_default="transit",
            comment="on_us=check drawn on our customer, transit=check deposited by our customer",
        ),
    )

    # Create index for filtering by item type
    op.create_index("ix_check_items_item_type", "check_items", ["item_type"])

    # Create composite index for common queries (tenant + item_type)
    op.create_index("ix_check_items_tenant_item_type", "check_items", ["tenant_id", "item_type"])


def downgrade() -> None:
    """Remove item_type column from check_items table."""
    # Drop indexes
    op.drop_index("ix_check_items_tenant_item_type", table_name="check_items")
    op.drop_index("ix_check_items_item_type", table_name="check_items")

    # Drop column
    op.drop_column("check_items", "item_type")

    # Drop enum type
    item_type_enum = sa.Enum("on_us", "transit", name="itemtype")
    item_type_enum.drop(op.get_bind(), checkfirst=True)
