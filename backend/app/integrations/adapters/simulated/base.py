"""Base class for simulated core-banking adapters.

A real integration has two concerns:

1. **Transport** - talking to the vendor (REST/SOAP, auth, retries).
2. **Translation** - mapping the vendor's wire format to the application's
   canonical model, including code-table lookups (status codes, product types).

Translation is where almost all integration bugs live. These simulated adapters
make the translation layer *real and testable today*: every read pulls a record
from a synthetic core, serializes it into the vendor's wire shape, and parses it
straight back into our canonical dataclasses. Swapping the synthetic source for
a real HTTP/SOAP client later only touches the transport layer - the proven
``_parse_*`` mappings stay exactly the same.

Subclasses implement only the vendor-specific ``_serialize_*`` / ``_parse_*``
hooks. All filtering, pagination, similarity scoring and image handling is shared
application logic and lives here.
"""

from abc import abstractmethod
from datetime import datetime
from decimal import Decimal

from app.integrations.adapters.factory import IntegrationAdapter
from app.integrations.adapters.simulated.images import is_front_image, render_check_image
from app.integrations.adapters.simulated.source_data import SyntheticCoreData
from app.integrations.interfaces.base import (
    AccountContext,
    CheckBehaviorStats,
    CheckImageData,
    HistoricalCheck,
    PresentedItem,
)


class BaseSimulatedCoreAdapter(IntegrationAdapter):
    """Shared engine for vendor adapters backed by synthetic data."""

    #: Value placed in ``PresentedItem.source_system`` (e.g. "fiserv").
    source_system: str = "simulated"

    def __init__(self, seed: int = 42) -> None:
        self._data = SyntheticCoreData(seed=seed)

    # ----------------------------------------------------- vendor translation
    # Subclasses implement these to map between the synthetic "core" record and
    # the vendor's wire format, then back to the canonical dataclass.
    @abstractmethod
    def _serialize_item(self, record: dict) -> dict:
        """Render a presented-item record as the vendor would return it."""

    @abstractmethod
    def _parse_item(self, wire: dict) -> PresentedItem:
        """Parse a vendor presented-item payload into the canonical model."""

    @abstractmethod
    def _serialize_account(self, record: dict) -> dict:
        """Render an account record as the vendor would return it."""

    @abstractmethod
    def _parse_account(self, wire: dict) -> AccountContext:
        """Parse a vendor account payload into the canonical model."""

    @abstractmethod
    def _serialize_behavior(self, record: dict) -> dict:
        """Render account check-behavior stats as the vendor would return them."""

    @abstractmethod
    def _parse_behavior(self, wire: dict) -> CheckBehaviorStats:
        """Parse vendor behavior stats into the canonical model."""

    @abstractmethod
    def _serialize_history(self, record: dict) -> dict:
        """Render a historical-check record as the vendor would return it."""

    @abstractmethod
    def _parse_history(self, wire: dict) -> HistoricalCheck:
        """Parse a vendor historical-check payload into the canonical model."""

    # Convenience wrappers: synthetic record -> vendor wire -> canonical model.
    def _item(self, record: dict) -> PresentedItem:
        return self._parse_item(self._serialize_item(record))

    def _history_item(self, record: dict) -> HistoricalCheck:
        return self._parse_history(self._serialize_history(record))

    # -------------------------------------------------------- CheckItemProvider
    async def get_presented_items(
        self,
        date_from: datetime,
        date_to: datetime,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        account_types: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PresentedItem], int]:
        filtered = []
        for record in self._data.items:
            if not (date_from <= record["presented_date"] <= date_to):
                continue
            if amount_min is not None and record["amount"] < amount_min:
                continue
            if amount_max is not None and record["amount"] > amount_max:
                continue
            if account_types and record["account_type"] not in account_types:
                continue
            filtered.append(record)

        total = len(filtered)
        page = filtered[offset : offset + limit]
        return [self._item(record) for record in page], total

    async def get_item_by_id(self, external_item_id: str) -> PresentedItem | None:
        for record in self._data.items:
            if record["external_item_id"] == external_item_id:
                return self._item(record)
        return None

    # ------------------------------------------------------- CheckImageProvider
    async def get_image(self, image_id: str) -> CheckImageData | None:
        is_front = is_front_image(image_id)
        content = render_check_image(image_id, is_front=is_front)
        return CheckImageData(
            image_id=image_id,
            image_type="front" if is_front else "back",
            content=content,
            content_type="image/png",
            width=1200,
            height=600,
            dpi=200,
        )

    async def get_image_url(self, image_id: str, expires_in: int = 60) -> str | None:
        # Simulated adapters serve images through the application's image proxy
        # (no vendor-direct signed URL), mirroring the safest real-world path.
        return None

    async def get_thumbnail(
        self, image_id: str, width: int = 200, height: int = 100
    ) -> bytes | None:
        return render_check_image(
            image_id, is_front=is_front_image(image_id), width=width, height=height
        )

    # -------------------------------------------------- AccountContextProvider
    async def get_account_context(self, account_id: str) -> AccountContext | None:
        record = self._data.accounts.get(account_id)
        if record is None:
            return None
        return self._parse_account(self._serialize_account(record))

    async def get_check_behavior_stats(self, account_id: str) -> CheckBehaviorStats | None:
        record = self._data.accounts.get(account_id)
        if record is None:
            return None
        return self._parse_behavior(self._serialize_behavior(record))

    # ---------------------------------------------------- CheckHistoryProvider
    async def get_check_history(
        self,
        account_id: str,
        limit: int = 10,
        amount_range: tuple[Decimal, Decimal] | None = None,
        payee_name: str | None = None,
    ) -> list[HistoricalCheck]:
        records = self._data.history.get(account_id, [])
        filtered = []
        for record in records:
            if amount_range and not (amount_range[0] <= record["amount"] <= amount_range[1]):
                continue
            if payee_name and record["payee_name"]:
                if payee_name.lower() not in record["payee_name"].lower():
                    continue
            filtered.append(record)
        return [self._history_item(record) for record in filtered[:limit]]

    async def get_similar_checks(
        self,
        account_id: str,
        amount: Decimal,
        payee_name: str | None = None,
        limit: int = 5,
    ) -> list[HistoricalCheck]:
        records = self._data.history.get(account_id, [])
        scored = []
        for record in records:
            amount_diff = abs(float(record["amount"]) - float(amount))
            score = max(0.0, 100 - (amount_diff / float(amount) * 100)) * 2
            if payee_name and record["payee_name"]:
                if payee_name.lower() == record["payee_name"].lower():
                    score += 50
                elif payee_name.lower() in record["payee_name"].lower():
                    score += 25
            scored.append((score, record))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [self._history_item(record) for _, record in scored[:limit]]
