"""Performance and Correctness Fixes

Revision ID: 006_performance_fixes
Revises: 005_dual_control_workflow
Create Date: 2024-01-18

This migration addresses performance and correctness issues:

1. Converts allowed_ips from Text to JSONB:
   - Schema defined it as list[str]
   - Code was incorrectly using .split(",")
   - Now properly stores as JSONB array

Note: Existing comma-separated values are migrated to JSONB arrays.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_performance_fixes'
down_revision = '005_dual_control_workflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # CONVERT ALLOWED_IPS FROM TEXT TO JSONB
    # ==========================================================================
    # First, convert existing comma-separated values to JSON arrays
    # Then alter the column type

    # Add temporary column
    op.add_column('users', sa.Column('allowed_ips_new', postgresql.JSONB(), nullable=True))

    # Migrate data: convert comma-separated string to JSONB array
    op.execute("""
        UPDATE users
        SET allowed_ips_new = CASE
            WHEN allowed_ips IS NULL THEN NULL
            WHEN allowed_ips = '' THEN NULL
            ELSE (
                SELECT jsonb_agg(trim(ip))
                FROM unnest(string_to_array(allowed_ips, ',')) AS ip
                WHERE trim(ip) != ''
            )
        END
    """)

    # Drop old column and rename new one
    op.drop_column('users', 'allowed_ips')
    op.alter_column('users', 'allowed_ips_new', new_column_name='allowed_ips')


def downgrade() -> None:
    # Add temporary column for Text
    op.add_column('users', sa.Column('allowed_ips_old', sa.Text(), nullable=True))

    # Convert JSONB array back to comma-separated string
    op.execute("""
        UPDATE users
        SET allowed_ips_old = CASE
            WHEN allowed_ips IS NULL THEN NULL
            ELSE (
                SELECT string_agg(ip::text, ',')
                FROM jsonb_array_elements_text(allowed_ips) AS ip
            )
        END
    """)

    # Drop JSONB column and rename Text column back
    op.drop_column('users', 'allowed_ips')
    op.alter_column('users', 'allowed_ips_old', new_column_name='allowed_ips')
