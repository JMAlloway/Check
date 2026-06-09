"""DB hardening: tenant isolation for check_history, JSONB flags, indexes, constraints.

Revision ID: 0002_db_hardening
Revises: 0001_baseline
Create Date: 2026-06-09

Changes:
1. check_history gains tenant_id (backfilled from check_items by account_id;
   unmatched demo rows are deleted) - account IDs are bank-internal and can
   collide across tenants, so history must be tenant-scoped.
2. check_items.risk_flags / upstream_flags / ai_risk_factors converted from
   JSON-in-Text to JSONB.
3. Missing FK indexes: decisions.check_item_id, check_images.check_item_id.
4. Query-pattern indexes: (tenant_id, status, priority, presented_date) on
   check_items (replacing the (status, priority) index), a partial index on
   sla_due_at for in-flight items, and (tenant_id, timestamp, id) on
   audit_logs for the per-insert chain predecessor lookup.
5. CHECK constraints: positive amounts, 0..1 AI scores, 0..100 match scores.

Every statement is guarded (IF [NOT] EXISTS / pg_constraint lookup) because
the 0001 baseline runs ``Base.metadata.create_all`` against the *current*
models - on a fresh database all of this already exists and this revision
must be a clean no-op.

Note: the legacy ``pending_approval`` CheckStatus value was removed from the
model. PostgreSQL cannot drop enum values in place; databases created before
this change keep the value in the ``checkstatus`` type, which is harmless -
no row ever stored it and no code references it.
"""

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_db_hardening"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


_CHECK_CONSTRAINTS = {
    "check_items": {
        "ck_check_items_amount_positive": "amount > 0",
        "ck_check_items_ai_confidence_range": (
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)"
        ),
        "ck_check_items_ai_risk_score_range": (
            "ai_risk_score IS NULL OR (ai_risk_score >= 0 AND ai_risk_score <= 1)"
        ),
        "ck_check_items_micr_confidence_range": (
            "micr_confidence_score IS NULL OR micr_confidence_score BETWEEN 0 AND 100"
        ),
        "ck_check_items_signature_score_range": (
            "signature_match_score IS NULL OR signature_match_score BETWEEN 0 AND 100"
        ),
        "ck_check_items_deposit_regularity_range": (
            "deposit_regularity_score IS NULL OR deposit_regularity_score BETWEEN 0 AND 100"
        ),
    },
    "check_history": {
        "ck_check_history_amount_positive": "amount > 0",
    },
}


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. check_history tenant isolation -------------------------------
    bind.execute(text("ALTER TABLE check_history ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(36)"))
    # Backfill from check_items sharing the account (pre-existing data is
    # demo/dev only); rows with no owning tenant are unrecoverable - drop them.
    bind.execute(
        text(
            "UPDATE check_history ch SET tenant_id = ci.tenant_id "
            "FROM check_items ci "
            "WHERE ch.tenant_id IS NULL AND ci.account_id = ch.account_id"
        )
    )
    bind.execute(text("DELETE FROM check_history WHERE tenant_id IS NULL"))
    bind.execute(text("ALTER TABLE check_history ALTER COLUMN tenant_id SET NOT NULL"))
    bind.execute(
        text("CREATE INDEX IF NOT EXISTS ix_check_history_tenant_id ON check_history (tenant_id)")
    )
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_check_history_tenant_account_date "
            "ON check_history (tenant_id, account_id, check_date)"
        )
    )
    bind.execute(text("DROP INDEX IF EXISTS ix_check_history_account_date"))

    # --- 2. JSON-in-Text -> JSONB ----------------------------------------
    # USING ::jsonb parses the legacy json.dumps() text and is a no-op-safe
    # rewrite when the column is already jsonb.
    for col in ("risk_flags", "upstream_flags", "ai_risk_factors"):
        bind.execute(
            text(f"ALTER TABLE check_items ALTER COLUMN {col} TYPE JSONB USING {col}::jsonb")
        )

    # --- 3. Missing FK indexes --------------------------------------------
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_decisions_check_item_id " "ON decisions (check_item_id)"
        )
    )
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_check_images_check_item_id "
            "ON check_images (check_item_id)"
        )
    )

    # --- 4. Query-pattern indexes -----------------------------------------
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_check_items_tenant_status_priority "
            "ON check_items (tenant_id, status, priority, presented_date)"
        )
    )
    bind.execute(text("DROP INDEX IF EXISTS ix_check_items_status_priority"))
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_check_items_sla_due_active "
            "ON check_items (sla_due_at) "
            "WHERE status IN ('new', 'in_review', 'escalated')"
        )
    )
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_chain "
            "ON audit_logs (tenant_id, timestamp, id)"
        )
    )

    # --- 5. CHECK constraints ----------------------------------------------
    for table, constraints in _CHECK_CONSTRAINTS.items():
        for name, expr in constraints.items():
            exists = bind.execute(
                text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
                {"name": name},
            ).fetchone()
            if not exists:
                bind.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr})"))


def downgrade() -> None:
    bind = op.get_bind()

    for table, constraints in _CHECK_CONSTRAINTS.items():
        for name in constraints:
            bind.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))

    bind.execute(text("DROP INDEX IF EXISTS ix_audit_logs_tenant_chain"))
    bind.execute(text("DROP INDEX IF EXISTS ix_check_items_sla_due_active"))
    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_check_items_status_priority "
            "ON check_items (status, priority)"
        )
    )
    bind.execute(text("DROP INDEX IF EXISTS ix_check_items_tenant_status_priority"))
    bind.execute(text("DROP INDEX IF EXISTS ix_check_images_check_item_id"))
    bind.execute(text("DROP INDEX IF EXISTS ix_decisions_check_item_id"))

    for col in ("risk_flags", "upstream_flags", "ai_risk_factors"):
        bind.execute(
            text(f"ALTER TABLE check_items ALTER COLUMN {col} TYPE TEXT USING {col}::text")
        )

    bind.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_check_history_account_date "
            "ON check_history (account_id, check_date)"
        )
    )
    bind.execute(text("DROP INDEX IF EXISTS ix_check_history_tenant_account_date"))
    bind.execute(text("DROP INDEX IF EXISTS ix_check_history_tenant_id"))
    bind.execute(text("ALTER TABLE check_history DROP COLUMN IF EXISTS tenant_id"))
