"""PostgreSQL ENUM type definitions and idempotent creation helper.

The fraud models declare their PgEnum columns with ``create_type=False`` (the
types are expected to already exist), so these named enum types must be created
explicitly before ``Base.metadata.create_all``. This helper is the single source
of truth, used by both application startup (app.main) and the test fixtures.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# name -> ordered list of allowed values. Keep in sync with the PgEnum columns
# declared in app/models/fraud.py (create_type=False).
FRAUD_ENUM_TYPES: dict[str, list[str]] = {
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


async def create_enum_types(conn: AsyncConnection) -> None:
    """Create the application's PostgreSQL enum types if they do not yet exist.

    Idempotent: each type is created only when absent, so this is safe to run on
    every startup and before each test-schema build. Enum names and values are
    module-level constants (never user input), so the f-string is not injectable.
    """
    for enum_name, enum_values in FRAUD_ENUM_TYPES.items():
        exists = await conn.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": enum_name}
        )
        if exists.fetchone():
            continue
        values_str = ", ".join(f"'{value}'" for value in enum_values)
        await conn.execute(text(f"CREATE TYPE {enum_name} AS ENUM ({values_str})"))
