"""Integration test for the Connector C (item context) demo import.

Regression coverage for bugs found via demo: the item-context RecordStatus enum
collided with the connector-B RecordStatus PG type (so import-record writes
failed), and the demo had no way to run an import without a real SFTP server.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.check import CheckItem, CheckStatus, ItemType, RiskLevel
from app.models.item_context_connector import (
    ContextConnectorStatus,
    FileFormat,
    ImportStatus,
    ItemContextConnector,
)
from app.services.item_context_service import ItemContextImportService


async def _make_connector(db_session, tenant_id: str) -> ItemContextConnector:
    connector = ItemContextConnector(
        tenant_id=tenant_id,
        name="Demo Tenure Feed",
        source_system="fiserv_premier",
        status=ContextConnectorStatus.ACTIVE,
        is_enabled=True,
        sftp_host="sftp.demo.example",
        sftp_username="svc",
        file_format=FileFormat.CSV,
        has_header_row=True,
        field_mapping={
            "external_item_id": {"name": "item_id"},
            "account_tenure_days": {"name": "tenure_days", "type": "int"},
            "current_balance": {"name": "current_balance", "type": "decimal"},
        },
        match_field="external_item_id",
        match_by_external_item_id=True,
        update_existing=True,
        created_by_user_id="DEMO-USER-SYSTEM_ADMIN",
    )
    db_session.add(connector)

    for i in range(3):
        db_session.add(
            CheckItem(
                id=f"ctx-item-{i}",
                source_system="demo",
                account_number_masked="****0000",
                account_type="business",
                tenant_id=tenant_id,
                external_item_id=f"EXT-CTX-{i}",
                account_id=f"acct-{i}",
                amount=Decimal("100.00"),
                status=CheckStatus.NEW,
                risk_level=RiskLevel.LOW,
                item_type=ItemType.TRANSIT,
                presented_date=datetime.now(timezone.utc),
            )
        )
    await db_session.commit()
    return connector


@pytest.mark.asyncio
async def test_demo_import_matches_and_enriches(db_session, test_tenant_id):
    connector = await _make_connector(db_session, test_tenant_id)

    service = ItemContextImportService(db_session)
    import_record = await service.run_demo_import(
        connector=connector, triggered_by="test", file_limit=50
    )

    # No SFTP, no enum-collision crash: the import completes and enriches items.
    assert import_record.status == ImportStatus.COMPLETED
    assert import_record.total_records == 3
    assert import_record.matched_records == 3
    assert import_record.applied_records == 3

    # The enrichment actually wrote context onto the matched items.
    item = (
        await db_session.execute(select(CheckItem).where(CheckItem.id == "ctx-item-0"))
    ).scalar_one()
    assert item.account_tenure_days is not None
