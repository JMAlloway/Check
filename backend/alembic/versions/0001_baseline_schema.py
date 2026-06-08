"""Squashed baseline schema generated from the ORM models.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-08

This collapses the previous 17 incremental migrations (001..017) into a single
baseline that is generated directly from the SQLAlchemy models, which are the
source of truth. It was created because the incremental chain had drifted badly
from the models: entire tables (image_connectors, item_context_connectors and
their logs/imports, security_incidents/breach_notifications/incident_updates)
and many columns (the check_items behavioural fields, decisions.tenant_id,
audit_logs.tenant_id/integrity_hash, item_views.tenant_id) existed only in the
development ``create_all`` path and were never added by a migration, so a
production ``alembic upgrade head`` produced an incomplete, non-functional
schema.

Because the project has no production data yet, squashing to a clean baseline is
preferable to chasing the drift with a large, noisy reconciliation migration.

The baseline builds the schema the same way development does:
  1. create the PostgreSQL enum types the fraud models reference
     (declared with create_type=False, so they must pre-exist);
  2. ``Base.metadata.create_all`` to create every table and model-declared index
     exactly as the models define them (including the partial unique indexes on
     permissions/roles and the GIN indexes on the audit JSONB columns);
  3. install the audit-immutability trigger function + triggers that enforce
     write-once semantics on audit_logs and item_views.

Steps 1 and 3 mirror what app startup and the test fixtures already do for
development databases, so the alembic-provisioned schema now matches create_all.
"""

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


# Enum types referenced by app/models/fraud.py columns (create_type=False).
# Kept in sync with app/db/enums.py FRAUD_ENUM_TYPES.
_ENUM_TYPES: dict[str, list[str]] = {
    "fraud_type": [
        "check_kiting",
        "counterfeit_check",
        "forged_signature",
        "altered_check",
        "account_takeover",
        "identity_theft",
        "first_party_fraud",
        "synthetic_identity",
        "duplicate_deposit",
        "unauthorized_endorsement",
        "payee_alteration",
        "amount_alteration",
        "fictitious_payee",
        "other",
    ],
    "fraud_channel": ["branch", "atm", "mobile", "rdc", "mail", "online", "other"],
    "amount_bucket": [
        "under_100",
        "100_to_500",
        "500_to_1000",
        "1000_to_5000",
        "5000_to_10000",
        "10000_to_50000",
        "over_50000",
    ],
    "fraud_event_status": ["draft", "submitted", "withdrawn"],
}

_AUDIT_TRIGGER_TABLES = ("audit_logs", "item_views")


def _import_metadata():
    """Import every model module so Base.metadata is fully populated.

    Mirrors alembic/env.py: app.models re-exports most models, while
    image_token and the security models are imported explicitly because they
    are not re-exported from app.models.__init__.
    """
    import app.models  # noqa: F401  (all re-exported models)
    from app.db.session import Base
    from app.models import image_token  # noqa: F401  (image_access_tokens)
    from app.security import models as _security_models  # noqa: F401  (security_*)

    return Base.metadata


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Enum types (must exist before create_all builds the fraud tables).
    for name, values in _ENUM_TYPES.items():
        exists = bind.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": name}
        ).fetchone()
        if not exists:
            values_str = ", ".join(f"'{v}'" for v in values)
            bind.execute(text(f"CREATE TYPE {name} AS ENUM ({values_str})"))

    # 2. All tables + model-declared indexes. This includes the partial unique
    #    indexes on permissions/roles and the GIN indexes on the audit JSONB
    #    columns, all of which live in the models' __table_args__.
    metadata = _import_metadata()
    metadata.create_all(bind=bind)

    # 3. Audit immutability: write-once enforcement on audit_logs and item_views.
    bind.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION prevent_audit_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'UPDATE operations are not permitted on % table. Audit records are immutable.', TG_TABLE_NAME
                        USING ERRCODE = 'restrict_violation';
                ELSIF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'DELETE operations are not permitted on % table. Audit records are immutable.', TG_TABLE_NAME
                        USING ERRCODE = 'restrict_violation';
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    for tbl in _AUDIT_TRIGGER_TABLES:
        bind.execute(
            text(
                f"CREATE TRIGGER {tbl}_prevent_update BEFORE UPDATE ON {tbl} "
                "FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification()"
            )
        )
        bind.execute(
            text(
                f"CREATE TRIGGER {tbl}_prevent_delete BEFORE DELETE ON {tbl} "
                "FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification()"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Triggers depend on the function and tables; drop them first.
    for tbl in _AUDIT_TRIGGER_TABLES:
        bind.execute(text(f"DROP TRIGGER IF EXISTS {tbl}_prevent_update ON {tbl}"))
        bind.execute(text(f"DROP TRIGGER IF EXISTS {tbl}_prevent_delete ON {tbl}"))
    bind.execute(text("DROP FUNCTION IF EXISTS prevent_audit_modification()"))

    metadata = _import_metadata()
    metadata.drop_all(bind=bind)

    for name in _ENUM_TYPES:
        bind.execute(text(f"DROP TYPE IF EXISTS {name}"))
