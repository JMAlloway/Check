"""Make item_views mutable (drop its immutability triggers).

item_views is per-session interaction telemetry that the application updates as
a review session progresses (AuditService.update_item_view sets zoom_used,
magnifier_used, etc.). It was incorrectly covered by the audit-immutability
triggers, so every interaction-tracking UPDATE (e.g. the image-zoom endpoint)
raised restrict_violation and 500'd. The tamper-evident record of a view is the
separate immutable ITEM_VIEWED row in audit_logs; item_views is supplementary
tracking and must be updatable.

This migration drops the UPDATE/DELETE triggers on item_views. audit_logs keeps
its triggers. Idempotent via IF EXISTS.
"""

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_item_views_mutable"
down_revision = "0002_db_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("DROP TRIGGER IF EXISTS item_views_prevent_update ON item_views"))
    bind.execute(text("DROP TRIGGER IF EXISTS item_views_prevent_delete ON item_views"))


def downgrade() -> None:
    bind = op.get_bind()
    # Re-installing would re-break interaction tracking; recreate only for a
    # clean rollback of the schema object. Uses the shared trigger function,
    # which the audit_logs triggers keep present.
    bind.execute(
        text(
            "CREATE OR REPLACE TRIGGER item_views_prevent_update "
            "BEFORE UPDATE ON item_views "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification()"
        )
    )
    bind.execute(
        text(
            "CREATE OR REPLACE TRIGGER item_views_prevent_delete "
            "BEFORE DELETE ON item_views "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification()"
        )
    )
