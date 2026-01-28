"""Performance and Correctness Fixes

Revision ID: 006_performance_fixes
Revises: 005_dual_control_workflow
Create Date: 2024-01-18

NOTE: This migration is now a NO-OP.

The allowed_ips column is now created as JSONB in 001_initial_schema,
so no conversion from Text to JSONB is needed.

This migration file is kept for revision chain integrity.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "006_performance_fixes"
down_revision = "005_dual_control_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # NO-OP: allowed_ips is now JSONB from the start in 001_initial_schema
    # ==========================================================================
    # The users.allowed_ips column is now created as JSONB in 001_initial_schema,
    # so no Text -> JSONB conversion is needed.
    pass


def downgrade() -> None:
    # ==========================================================================
    # NO-OP: Downgrade handled by 001_initial_schema
    # ==========================================================================
    pass
