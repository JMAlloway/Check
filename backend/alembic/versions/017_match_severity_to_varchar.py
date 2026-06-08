"""Convert match_severity enum columns to VARCHAR to match the ORM models.

Revision ID: 017_match_severity_varchar
Revises: 016_perm_role_unique
Create Date: 2026-06-08

Migration 002 created network_match_alerts.severity and
tenant_fraud_configs.minimum_alert_severity as the native PostgreSQL enum
`match_severity`. The ORM models, however, intentionally declare both columns as
String(10) (see app/models/fraud.py) to avoid asyncpg enum type-casting: asyncpg
sends bound parameters as VARCHAR, and Postgres refuses to coerce VARCHAR into a
native enum on INSERT/UPDATE. The result was a hard failure on any write to
those tables on alembic-provisioned databases:

    column "minimum_alert_severity" is of type match_severity
    but expression is of type character varying

This broke fraud-config writes (PATCH /fraud/config), network-alert creation,
and demo seeding whenever the schema came from migrations rather than the
development-only create_all path (which already produced VARCHAR columns).

This migration reconciles the schema with the models by converting both columns
to VARCHAR(10) and dropping the now-unused enum type. It is guarded so it is a
no-op on databases that were provisioned via create_all (where the columns are
already VARCHAR and the enum type was never created).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "017_match_severity_varchar"
down_revision = "016_perm_role_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'match_severity') THEN
                ALTER TABLE network_match_alerts
                    ALTER COLUMN severity TYPE VARCHAR(10) USING severity::text;
                ALTER TABLE tenant_fraud_configs
                    ALTER COLUMN minimum_alert_severity TYPE VARCHAR(10)
                    USING minimum_alert_severity::text;
                DROP TYPE match_severity;
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'match_severity') THEN
                CREATE TYPE match_severity AS ENUM ('low', 'medium', 'high');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        ALTER TABLE network_match_alerts
            ALTER COLUMN severity TYPE match_severity USING severity::match_severity;
        ALTER TABLE tenant_fraud_configs
            ALTER COLUMN minimum_alert_severity TYPE match_severity
            USING minimum_alert_severity::match_severity;
        """
    )
