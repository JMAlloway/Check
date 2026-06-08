"""Audit-immutability triggers (single source of truth).

The audit tables (audit_logs, item_views) are append-only: UPDATE is never
allowed, and DELETE is allowed only for an authorized retention purge that opts
in via the transaction-local flag ``app.allow_audit_purge``. This keeps the
audit trail tamper-evident while still permitting the documented retention
policy to age out records.

This DDL is defined once here and installed by:
  - the squashed baseline migration (production/alembic schema),
  - application startup's create_all reconcile path (development), and
  - the test schema fixture (so tests run against the same constraints).

All statements use CREATE OR REPLACE so installation is idempotent.
"""

# Tables that are append-only and carry the immutability triggers.
AUDIT_TRIGGER_TABLES = ("audit_logs", "item_views")

# Session flag a retention purge sets (SET LOCAL, so it is scoped to the purge
# transaction) to authorize DELETEs. Anything else is rejected by the trigger.
AUDIT_PURGE_FLAG = "app.allow_audit_purge"

_FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'UPDATE operations are not permitted on % table. Audit records are immutable.', TG_TABLE_NAME
            USING ERRCODE = 'restrict_violation';
    ELSIF TG_OP = 'DELETE' THEN
        -- Permit only an authorized retention purge, which sets this
        -- transaction-local flag immediately before deleting. Block all others.
        IF current_setting('app.allow_audit_purge', true) IS DISTINCT FROM 'on' THEN
            RAISE EXCEPTION 'DELETE operations are not permitted on % table except during an authorized retention purge.', TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def audit_immutability_ddl() -> list[str]:
    """Return the idempotent DDL statements that install the triggers."""
    statements = [_FUNCTION_DDL]
    for table in AUDIT_TRIGGER_TABLES:
        statements.append(
            f"CREATE OR REPLACE TRIGGER {table}_prevent_update "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification()"
        )
        statements.append(
            f"CREATE OR REPLACE TRIGGER {table}_prevent_delete "
            f"BEFORE DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification()"
        )
    return statements
