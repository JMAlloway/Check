"""Add previous_hash column to audit_logs for chain integrity.

Revision ID: 013_audit_chain_integrity
Revises: 012_tenant_unique_user_constraints
Create Date: 2026-01-16

SECURITY: This migration adds blockchain-like chain integrity to audit logs.
Each new audit entry stores the integrity_hash of the previous entry,
creating an immutable chain where tampering with any record breaks the chain.

This enables:
- Detection of any modification to audit log entries
- Verification that no entries were deleted from the middle of the chain
- Compliance with SOC 2 and regulatory audit requirements
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "013_audit_chain_integrity"
down_revision = "012_tenant_unique_user_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add previous_hash column to audit_logs table."""
    # Add the previous_hash column
    # Nullable because existing records won't have this value
    op.add_column("audit_logs", sa.Column("previous_hash", sa.String(64), nullable=True))

    # Create index for efficient chain traversal
    op.create_index("ix_audit_logs_previous_hash", "audit_logs", ["previous_hash"])

    # For existing records, we can't compute the chain retroactively
    # because the integrity_hash was computed without previous_hash.
    # New records will have proper chain linking.
    # A separate backfill script can be run if needed to rebuild the chain.


def downgrade() -> None:
    """Remove previous_hash column from audit_logs table."""
    op.drop_index("ix_audit_logs_previous_hash", table_name="audit_logs")
    op.drop_column("audit_logs", "previous_hash")
