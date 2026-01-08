"""Audit Log Immutability Enforcement

Revision ID: 004_audit_immutability
Revises: 003_connector_b
Create Date: 2024-01-16

This migration enforces audit log immutability at the database level:

1. Creates PostgreSQL triggers to block UPDATE and DELETE operations:
   - audit_logs table: trigger blocks UPDATE/DELETE
   - item_views table: trigger blocks UPDATE/DELETE

2. Adds GIN indexes for efficient JSONB querying

NOTE: JSONB columns (before_value, after_value, extra_data, interaction_summary)
are created in 001_initial_schema.

SECURITY NOTE: These triggers provide defense-in-depth. Production deployments
should also configure the application database role with INSERT/SELECT only
permissions on these tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_audit_immutability'
down_revision = '003_connector_b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # NOTE: JSONB columns are already created in 001_initial_schema
    # This migration only adds immutability enforcement via triggers
    # ==========================================================================

    # ==========================================================================
    # CREATE IMMUTABILITY TRIGGER FUNCTION
    # ==========================================================================
    # This function raises an exception when UPDATE or DELETE is attempted,
    # enforcing write-once semantics on audit tables.

    op.execute("""
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
    """)

    # ==========================================================================
    # CREATE TRIGGERS ON AUDIT_LOGS TABLE
    # ==========================================================================

    # Trigger to block UPDATE on audit_logs
    op.execute("""
        CREATE TRIGGER audit_logs_prevent_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification();
    """)

    # Trigger to block DELETE on audit_logs
    op.execute("""
        CREATE TRIGGER audit_logs_prevent_delete
        BEFORE DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification();
    """)

    # ==========================================================================
    # CREATE TRIGGERS ON ITEM_VIEWS TABLE
    # ==========================================================================

    # Trigger to block UPDATE on item_views
    op.execute("""
        CREATE TRIGGER item_views_prevent_update
        BEFORE UPDATE ON item_views
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification();
    """)

    # Trigger to block DELETE on item_views
    op.execute("""
        CREATE TRIGGER item_views_prevent_delete
        BEFORE DELETE ON item_views
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification();
    """)

    # ==========================================================================
    # ADD GIN INDEXES FOR JSONB COLUMNS (efficient querying)
    # ==========================================================================

    op.create_index(
        'ix_audit_logs_extra_data_gin',
        'audit_logs',
        ['extra_data'],
        postgresql_using='gin',
        postgresql_ops={'extra_data': 'jsonb_path_ops'}
    )

    op.create_index(
        'ix_item_views_interaction_summary_gin',
        'item_views',
        ['interaction_summary'],
        postgresql_using='gin',
        postgresql_ops={'interaction_summary': 'jsonb_path_ops'}
    )


def downgrade() -> None:
    # ==========================================================================
    # DROP GIN INDEXES
    # ==========================================================================
    op.drop_index('ix_item_views_interaction_summary_gin', table_name='item_views')
    op.drop_index('ix_audit_logs_extra_data_gin', table_name='audit_logs')

    # ==========================================================================
    # DROP TRIGGERS
    # ==========================================================================
    op.execute("DROP TRIGGER IF EXISTS item_views_prevent_delete ON item_views")
    op.execute("DROP TRIGGER IF EXISTS item_views_prevent_update ON item_views")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_prevent_delete ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_prevent_update ON audit_logs")

    # ==========================================================================
    # DROP TRIGGER FUNCTION
    # ==========================================================================
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification()")

    # NOTE: JSONB columns stay as JSONB - they are managed by 001_initial_schema
