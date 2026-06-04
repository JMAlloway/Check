"""Simulated Fiserv core-banking adapter.

Models the wire conventions of Fiserv's item-processing / image platform
(Director / Source Capture) layered over a DNA or Premier core:

* PascalCase field names (``DocumentID``, ``RoutingTransitNumber``, ...).
* The check number is the **Serial Number**.
* Monetary values arrive as **strings** ("5000.00") - a classic source of
  float/precision bugs that this adapter's parser handles explicitly.
* Item state and item type are **integer code tables** (``DocumentStatus``,
  ``DocumentTypeNumber``), not human-readable strings.

Only the field/code-table mapping is vendor-specific; everything else is
inherited from :class:`BaseSimulatedCoreAdapter`.
"""

from datetime import datetime
from decimal import Decimal

from app.integrations.adapters.simulated.base import BaseSimulatedCoreAdapter
from app.integrations.interfaces.base import (
    AccountContext,
    CheckBehaviorStats,
    HistoricalCheck,
    PresentedItem,
)

# Fiserv DNA product-type code <-> canonical account type.
_PRODUCT_TO_CANONICAL = {
    "DDA": "consumer",
    "BUS": "business",
    "CML": "commercial",
    "NFP": "non_profit",
}
_CANONICAL_TO_PRODUCT = {v: k for k, v in _PRODUCT_TO_CANONICAL.items()}

# Fiserv item DocumentStatus codes (subset) for historical items.
# 0/1/2 are in-flight; 3 = Posted (cleared), 5 = Returned.
_FISERV_RETURNED_STATUS = 5
_CANONICAL_HISTORY_STATUS = {3: "cleared", 5: "returned"}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class FiservAdapter(BaseSimulatedCoreAdapter):
    """Simulated Fiserv adapter (Director item processing + DNA core)."""

    source_system = "fiserv"

    # ------------------------------------------------------------- items
    def _serialize_item(self, record: dict) -> dict:
        return {
            "DocumentID": record["external_item_id"],
            "BatchNumber": record["batch_id"],
            "AccountNumber": record["account_id"],
            "AccountNumberMasked": record["account_number_masked"],
            "ProductType": _CANONICAL_TO_PRODUCT.get(record["account_type"], "DDA"),
            "RoutingTransitNumber": record["routing_number"],
            "SerialNumber": record["check_number"],
            "TransactionAmount": f"{record['amount']:.2f}",  # Fiserv sends money as a string
            "CurrencyCode": record["currency"],
            "PayeeName": record["payee_name"],
            "MemoText": record["memo"],
            "MICRLine": record["micr_line"],
            "MICRAccount": record["micr_account"],
            "MICRRoutingTransit": record["micr_routing"],
            "MICRSerialNumber": record["micr_check_number"],
            "ItemDate": _iso(record["check_date"]),
            "CaptureDate": _iso(record["presented_date"]),
            "DateTimeStored": _iso(record["captured_at"]),
            "DocumentStatus": record["source_status"],
            "DocumentTypeNumber": record["item_type_code"],
            "FrontImageID": record["front_image_id"],
            "BackImageID": record["back_image_id"],
            "ExceptionCodes": record["upstream_flags"] or [],
        }

    def _parse_item(self, wire: dict) -> PresentedItem:
        return PresentedItem(
            external_item_id=wire["DocumentID"],
            source_system=self.source_system,
            account_id=wire["AccountNumber"],
            account_number_masked=wire["AccountNumberMasked"],
            account_type=_PRODUCT_TO_CANONICAL.get(wire["ProductType"], "consumer"),
            routing_number=wire.get("RoutingTransitNumber"),
            check_number=wire.get("SerialNumber"),
            amount=Decimal(wire["TransactionAmount"]),  # string -> Decimal
            currency=wire["CurrencyCode"],
            payee_name=wire.get("PayeeName"),
            memo=wire.get("MemoText"),
            micr_line=wire.get("MICRLine"),
            micr_account=wire.get("MICRAccount"),
            micr_routing=wire.get("MICRRoutingTransit"),
            micr_check_number=wire.get("MICRSerialNumber"),
            presented_date=_dt(wire["CaptureDate"]),
            check_date=_dt(wire.get("ItemDate")),
            front_image_id=wire.get("FrontImageID"),
            back_image_id=wire.get("BackImageID"),
            upstream_flags=wire.get("ExceptionCodes") or None,
            batch_id=wire.get("BatchNumber"),
            captured_at=_dt(wire.get("DateTimeStored")),
            source_status=wire.get("DocumentStatus"),
            item_type_code=wire.get("DocumentTypeNumber"),
        )

    # ---------------------------------------------------------- accounts
    def _serialize_account(self, record: dict) -> dict:
        return {
            "AccountNumber": record["account_id"],
            "ProductType": _CANONICAL_TO_PRODUCT.get(record["account_type"], "DDA"),
            "DateOpened": _iso(record["date_opened"]),
            "CurrentBalance": f"{record['current_balance']:.2f}",
            "AvailableBalance": f"{record['available_balance']:.2f}",
            "AverageBalance30Day": f"{record['avg_balance_30d']:.2f}",
            "RelationshipNumber": record["relationship_id"],
            "BranchNumber": record["branch_code"],
            "MarketCode": record["market_code"],
            "TenureDays": record["tenure_days"],
        }

    def _parse_account(self, wire: dict) -> AccountContext:
        return AccountContext(
            account_id=wire["AccountNumber"],
            account_type=_PRODUCT_TO_CANONICAL.get(wire["ProductType"], "consumer"),
            account_tenure_days=wire.get("TenureDays"),
            current_balance=Decimal(wire["CurrentBalance"]),
            average_balance_30d=Decimal(wire["AverageBalance30Day"]),
            relationship_id=wire.get("RelationshipNumber"),
            branch_code=wire.get("BranchNumber"),
            market_code=wire.get("MarketCode"),
        )

    # ------------------------------------------------------- behavior
    def _serialize_behavior(self, record: dict) -> dict:
        return {
            "AccountNumber": record["account_id"],
            "AverageCheckAmount30Day": f"{record['avg_check_30d']:.2f}",
            "AverageCheckAmount90Day": f"{record['avg_check_90d']:.2f}",
            "AverageCheckAmount365Day": f"{record['avg_check_365d']:.2f}",
            "CheckAmountStdDev30Day": f"{record['std_dev_30d']:.2f}",
            "MaxCheckAmount90Day": f"{record['max_check_90d']:.2f}",
            "CheckCount30Day": record["frequency_30d"],
            "ReturnedItemCount90Day": record["returned_90d"],
            "ExceptionCount90Day": record["exceptions_90d"],
        }

    def _parse_behavior(self, wire: dict) -> CheckBehaviorStats:
        return CheckBehaviorStats(
            account_id=wire["AccountNumber"],
            avg_check_amount_30d=Decimal(wire["AverageCheckAmount30Day"]),
            avg_check_amount_90d=Decimal(wire["AverageCheckAmount90Day"]),
            avg_check_amount_365d=Decimal(wire["AverageCheckAmount365Day"]),
            check_std_dev_30d=Decimal(wire["CheckAmountStdDev30Day"]),
            max_check_amount_90d=Decimal(wire["MaxCheckAmount90Day"]),
            check_frequency_30d=wire.get("CheckCount30Day"),
            returned_item_count_90d=wire.get("ReturnedItemCount90Day"),
            exception_count_90d=wire.get("ExceptionCount90Day"),
        )

    # -------------------------------------------------------- history
    def _serialize_history(self, record: dict) -> dict:
        status_code = _FISERV_RETURNED_STATUS if record["status"] == "returned" else 3
        return {
            "DocumentID": record["external_item_id"],
            "AccountNumber": record["account_id"],
            "SerialNumber": record["check_number"],
            "TransactionAmount": f"{record['amount']:.2f}",
            "ItemDate": _iso(record["check_date"]),
            "PayeeName": record["payee_name"],
            "DocumentStatus": status_code,
            "ReturnReason": record["return_reason"],
            "FrontImageID": record["front_image_id"],
            "BackImageID": record["back_image_id"],
        }

    def _parse_history(self, wire: dict) -> HistoricalCheck:
        status = _CANONICAL_HISTORY_STATUS.get(wire["DocumentStatus"], "cleared")
        return HistoricalCheck(
            external_item_id=wire["DocumentID"],
            account_id=wire["AccountNumber"],
            check_number=wire.get("SerialNumber"),
            amount=Decimal(wire["TransactionAmount"]),
            check_date=_dt(wire["ItemDate"]),
            payee_name=wire.get("PayeeName"),
            status=status,
            return_reason=wire.get("ReturnReason"),
            front_image_id=wire.get("FrontImageID"),
            back_image_id=wire.get("BackImageID"),
        )
