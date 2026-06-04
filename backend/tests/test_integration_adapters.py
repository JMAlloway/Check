"""Tests for core-banking integration adapters.

Covers the legacy mock adapter plus the simulated Fiserv and Jack Henry
adapters. These tests need no database - they exercise the adapter contract and,
critically, prove that each vendor adapter performs a *real* wire-format
translation rather than passing canonical data straight through.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.integrations.adapters.factory import AdapterFactory, IntegrationAdapter
from app.integrations.adapters.mock import MockAdapter
from app.integrations.adapters.simulated.fiserv import FiservAdapter
from app.integrations.adapters.simulated.jackhenry import JackHenryAdapter
from app.integrations.interfaces.base import (
    AccountContext,
    CheckBehaviorStats,
    CheckImageData,
    HistoricalCheck,
    PresentedItem,
)

ALL_ADAPTERS = [MockAdapter, FiservAdapter, JackHenryAdapter]
SIMULATED_ADAPTERS = [FiservAdapter, JackHenryAdapter]


def _wide_range() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=30), now + timedelta(days=1)


@pytest.fixture(params=ALL_ADAPTERS)
def adapter(request):
    return request.param()


# --------------------------------------------------------------- contract
class TestAdapterContract:
    """Every adapter must satisfy the full IntegrationAdapter contract."""

    @pytest.mark.asyncio
    async def test_get_presented_items_returns_canonical_items(self, adapter):
        date_from, date_to = _wide_range()
        items, total = await adapter.get_presented_items(date_from, date_to, limit=10)

        assert total > 0
        assert 0 < len(items) <= 10
        for item in items:
            assert isinstance(item, PresentedItem)
            assert item.external_item_id
            assert isinstance(item.amount, Decimal)
            assert item.amount > 0
            assert item.account_type in {
                "consumer",
                "business",
                "commercial",
                "non_profit",
            }
            assert item.presented_date is not None

    @pytest.mark.asyncio
    async def test_pagination_is_consistent(self, adapter):
        date_from, date_to = _wide_range()
        page1, total = await adapter.get_presented_items(date_from, date_to, limit=5, offset=0)
        page2, _ = await adapter.get_presented_items(date_from, date_to, limit=5, offset=5)

        ids1 = {i.external_item_id for i in page1}
        ids2 = {i.external_item_id for i in page2}
        assert ids1.isdisjoint(ids2)
        assert total >= len(ids1 | ids2)

    @pytest.mark.asyncio
    async def test_get_item_by_id_roundtrips(self, adapter):
        date_from, date_to = _wide_range()
        items, _ = await adapter.get_presented_items(date_from, date_to, limit=1)
        fetched = await adapter.get_item_by_id(items[0].external_item_id)

        assert fetched is not None
        assert fetched.external_item_id == items[0].external_item_id
        assert fetched.amount == items[0].amount

    @pytest.mark.asyncio
    async def test_unknown_item_returns_none(self, adapter):
        assert await adapter.get_item_by_id("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_amount_filter_is_applied(self, adapter):
        date_from, date_to = _wide_range()
        items, _ = await adapter.get_presented_items(
            date_from, date_to, amount_min=Decimal("10000"), limit=50
        )
        assert all(i.amount >= Decimal("10000") for i in items)

    @pytest.mark.asyncio
    async def test_account_context_and_behavior(self, adapter):
        date_from, date_to = _wide_range()
        items, _ = await adapter.get_presented_items(date_from, date_to, limit=1)
        account_id = items[0].account_id

        ctx = await adapter.get_account_context(account_id)
        assert isinstance(ctx, AccountContext)
        assert ctx.account_id == account_id
        assert ctx.current_balance is not None

        stats = await adapter.get_check_behavior_stats(account_id)
        assert isinstance(stats, CheckBehaviorStats)
        assert stats.avg_check_amount_30d is not None

    @pytest.mark.asyncio
    async def test_unknown_account_returns_none(self, adapter):
        assert await adapter.get_account_context("ACC999999") is None
        assert await adapter.get_check_behavior_stats("ACC999999") is None

    @pytest.mark.asyncio
    async def test_history_and_similarity(self, adapter):
        date_from, date_to = _wide_range()
        items, _ = await adapter.get_presented_items(date_from, date_to, limit=1)
        account_id = items[0].account_id

        history = await adapter.get_check_history(account_id, limit=5)
        assert all(isinstance(h, HistoricalCheck) for h in history)
        assert all(h.status in {"cleared", "returned"} for h in history)

        similar = await adapter.get_similar_checks(account_id, Decimal("1000"), limit=3)
        assert len(similar) <= 3
        assert all(isinstance(h, HistoricalCheck) for h in similar)

    @pytest.mark.asyncio
    async def test_get_image_returns_png_bytes(self, adapter):
        image = await adapter.get_image("IMG_CHK1000000_FRONT")
        assert isinstance(image, CheckImageData)
        assert image.content_type == "image/png"
        assert image.content.startswith(b"\x89PNG")
        assert image.image_type == "front"

        thumb = await adapter.get_thumbnail("IMG_CHK1000000_BACK")
        assert thumb.startswith(b"\x89PNG")


# ----------------------------------------------------- vendor translation
class TestVendorWireTranslation:
    """The simulated adapters must really translate vendor wire formats."""

    def test_fiserv_uses_fiserv_field_names_and_string_money(self):
        adapter = FiservAdapter()
        record = adapter._data.items[0]
        wire = adapter._serialize_item(record)

        # Fiserv PascalCase naming and Serial Number for the check number.
        assert "DocumentID" in wire
        assert "RoutingTransitNumber" in wire
        assert "SerialNumber" in wire
        assert "AcctId" not in wire  # not Jack Henry naming
        # Fiserv transmits money as a *string*.
        assert isinstance(wire["TransactionAmount"], str)
        # Integer code tables, not strings.
        assert isinstance(wire["DocumentStatus"], int)

        parsed = adapter._parse_item(wire)
        assert parsed.source_system == "fiserv"
        assert parsed.amount == record["amount"]
        assert parsed.check_number == record["check_number"]

    def test_jackhenry_uses_jxchange_field_names_and_numeric_money(self):
        adapter = JackHenryAdapter()
        record = adapter._data.items[0]
        wire = adapter._serialize_item(record)

        # jXchange abbreviated naming.
        assert "AcctId" in wire
        assert "SerialNum" in wire
        assert "PayeeNme" in wire
        assert "DocumentID" not in wire  # not Fiserv naming
        # jXchange transmits money as a number, and status as a short string.
        assert isinstance(wire["TranAmt"], float)
        assert isinstance(wire["ItemProcStsCode"], str)

        parsed = adapter._parse_item(wire)
        assert parsed.source_system == "jackhenry"
        assert parsed.amount == record["amount"]
        assert parsed.check_number == record["check_number"]

    @pytest.mark.parametrize("adapter_cls", SIMULATED_ADAPTERS)
    def test_money_survives_roundtrip_without_precision_loss(self, adapter_cls):
        adapter = adapter_cls()
        for record in adapter._data.items[:25]:
            parsed = adapter._parse_item(adapter._serialize_item(record))
            assert parsed.amount == record["amount"]
            # Two-decimal currency precision preserved.
            assert parsed.amount == parsed.amount.quantize(Decimal("0.01"))

    @pytest.mark.parametrize("adapter_cls", SIMULATED_ADAPTERS)
    def test_account_type_code_table_roundtrips(self, adapter_cls):
        adapter = adapter_cls()
        seen = set()
        for record in adapter._data.accounts.values():
            parsed = adapter._parse_account(adapter._serialize_account(record))
            assert parsed.account_type == record["account_type"]
            seen.add(record["account_type"])
        # The dataset exercises more than one product-type mapping.
        assert len(seen) > 1

    @pytest.mark.parametrize("adapter_cls", SIMULATED_ADAPTERS)
    def test_history_status_code_table_roundtrips(self, adapter_cls):
        adapter = adapter_cls()
        for entries in adapter._data.history.values():
            for record in entries:
                parsed = adapter._parse_history(adapter._serialize_history(record))
                assert parsed.status == record["status"]

    def test_adapters_are_deterministic_for_a_seed(self):
        a = FiservAdapter(seed=7)
        b = FiservAdapter(seed=7)
        assert [i["external_item_id"] for i in a._data.items] == [
            i["external_item_id"] for i in b._data.items
        ]


# ---------------------------------------------------------------- factory
class TestAdapterFactory:
    @pytest.mark.parametrize(
        "adapter_type,expected",
        [
            ("mock", MockAdapter),
            ("fiserv", FiservAdapter),
            ("jackhenry", JackHenryAdapter),
        ],
    )
    def test_factory_selects_adapter_by_setting(self, adapter_type, expected, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "INTEGRATION_ADAPTER", adapter_type, raising=False)
        AdapterFactory.reset()
        try:
            adapter = AdapterFactory.get_adapter()
            assert isinstance(adapter, expected)
            assert isinstance(adapter, IntegrationAdapter)
        finally:
            AdapterFactory.reset()

    def test_factory_rejects_unknown_adapter(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "INTEGRATION_ADAPTER", "nope", raising=False)
        AdapterFactory.reset()
        try:
            with pytest.raises(ValueError):
                AdapterFactory.get_adapter()
        finally:
            AdapterFactory.reset()

    def test_q2_still_not_implemented(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "INTEGRATION_ADAPTER", "q2", raising=False)
        AdapterFactory.reset()
        try:
            with pytest.raises(NotImplementedError):
                AdapterFactory.get_adapter()
        finally:
            AdapterFactory.reset()
