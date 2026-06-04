"""Simulated Jack Henry core-banking adapter.

Models the wire conventions of Jack Henry's ``jXchange`` integration platform
over a SilverLake / CIF 20/20 core:

* Abbreviated, vowel-dropped element names (``AcctId``, ``SerialNum``,
  ``PayeeNme``, ``TranAmt``, ``RtNum``) - the hallmark of jXchange/SOAP.
* Item state is a **short string code** (``ItemProcStsCode`` = "RDY"/"RTN"),
  not an integer - the opposite of Fiserv, so the canonical model must absorb
  both shapes.
* Monetary values arrive as JSON **numbers** (floats) rather than strings.

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

# jXchange AcctType code <-> canonical account type.
_ACCT_TYPE_TO_CANONICAL = {
    "DDA": "consumer",
    "BUS": "business",
    "CML": "commercial",
    "NFP": "non_profit",
}
_CANONICAL_TO_ACCT_TYPE = {v: k for k, v in _ACCT_TYPE_TO_CANONICAL.items()}

# jXchange ItemProcStsCode values.
_READY_STS = "RDY"
_RETURNED_STS = "RTN"
_CLEARED_STS = "CLR"
_HISTORY_STS_TO_CANONICAL = {_CLEARED_STS: "cleared", _RETURNED_STS: "returned"}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class JackHenryAdapter(BaseSimulatedCoreAdapter):
    """Simulated Jack Henry adapter (jXchange + SilverLake core)."""

    source_system = "jackhenry"

    # ------------------------------------------------------------- items
    def _serialize_item(self, record: dict) -> dict:
        return {
            "ItemId": record["external_item_id"],
            "BatchId": record["batch_id"],
            "AcctId": record["account_id"],
            "AcctIdMask": record["account_number_masked"],
            "AcctType": _CANONICAL_TO_ACCT_TYPE.get(record["account_type"], "DDA"),
            "RtNum": record["routing_number"],
            "SerialNum": record["check_number"],
            "TranAmt": float(record["amount"]),  # jXchange sends money as a number
            "CurCode": record["currency"],
            "PayeeNme": record["payee_name"],
            "MemoTxt": record["memo"],
            "MICRLineTxt": record["micr_line"],
            "MICRAcctNum": record["micr_account"],
            "MICRRtNum": record["micr_routing"],
            "MICRSerialNum": record["micr_check_number"],
            "ItemDt": _iso(record["check_date"]),
            "PresentedDt": _iso(record["presented_date"]),
            "CaptureDt": _iso(record["captured_at"]),
            "ItemProcStsCode": _READY_STS,
            "ItemTypCode": str(record["item_type_code"]),
            "FrontImageId": record["front_image_id"],
            "BackImageId": record["back_image_id"],
            "ExceptCodeList": record["upstream_flags"] or [],
        }

    def _parse_item(self, wire: dict) -> PresentedItem:
        return PresentedItem(
            external_item_id=wire["ItemId"],
            source_system=self.source_system,
            account_id=wire["AcctId"],
            account_number_masked=wire["AcctIdMask"],
            account_type=_ACCT_TYPE_TO_CANONICAL.get(wire["AcctType"], "consumer"),
            routing_number=wire.get("RtNum"),
            check_number=wire.get("SerialNum"),
            amount=Decimal(str(wire["TranAmt"])),  # float -> str -> Decimal (no binary drift)
            currency=wire["CurCode"],
            payee_name=wire.get("PayeeNme"),
            memo=wire.get("MemoTxt"),
            micr_line=wire.get("MICRLineTxt"),
            micr_account=wire.get("MICRAcctNum"),
            micr_routing=wire.get("MICRRtNum"),
            micr_check_number=wire.get("MICRSerialNum"),
            presented_date=_dt(wire["PresentedDt"]),
            check_date=_dt(wire.get("ItemDt")),
            front_image_id=wire.get("FrontImageId"),
            back_image_id=wire.get("BackImageId"),
            upstream_flags=wire.get("ExceptCodeList") or None,
            batch_id=wire.get("BatchId"),
            captured_at=_dt(wire.get("CaptureDt")),
            source_status=0 if wire.get("ItemProcStsCode") == _READY_STS else 9,
            item_type_code=int(wire["ItemTypCode"]) if wire.get("ItemTypCode") else None,
        )

    # ---------------------------------------------------------- accounts
    def _serialize_account(self, record: dict) -> dict:
        return {
            "AcctId": record["account_id"],
            "AcctType": _CANONICAL_TO_ACCT_TYPE.get(record["account_type"], "DDA"),
            "DateAcctOpen": _iso(record["date_opened"]),
            "CurBal": float(record["current_balance"]),
            "AvailBal": float(record["available_balance"]),
            "AvgBal30Day": float(record["avg_balance_30d"]),
            "RelnId": record["relationship_id"],
            "BranchId": record["branch_code"],
            "MktCode": record["market_code"],
            "AcctTenureDays": record["tenure_days"],
        }

    def _parse_account(self, wire: dict) -> AccountContext:
        return AccountContext(
            account_id=wire["AcctId"],
            account_type=_ACCT_TYPE_TO_CANONICAL.get(wire["AcctType"], "consumer"),
            account_tenure_days=wire.get("AcctTenureDays"),
            current_balance=Decimal(str(wire["CurBal"])),
            average_balance_30d=Decimal(str(wire["AvgBal30Day"])),
            relationship_id=wire.get("RelnId"),
            branch_code=wire.get("BranchId"),
            market_code=wire.get("MktCode"),
        )

    # ------------------------------------------------------- behavior
    def _serialize_behavior(self, record: dict) -> dict:
        return {
            "AcctId": record["account_id"],
            "AvgChkAmt30Day": float(record["avg_check_30d"]),
            "AvgChkAmt90Day": float(record["avg_check_90d"]),
            "AvgChkAmt365Day": float(record["avg_check_365d"]),
            "ChkAmtStdDev30Day": float(record["std_dev_30d"]),
            "MaxChkAmt90Day": float(record["max_check_90d"]),
            "ChkCnt30Day": record["frequency_30d"],
            "RtnItemCnt90Day": record["returned_90d"],
            "ExceptCnt90Day": record["exceptions_90d"],
        }

    def _parse_behavior(self, wire: dict) -> CheckBehaviorStats:
        return CheckBehaviorStats(
            account_id=wire["AcctId"],
            avg_check_amount_30d=Decimal(str(wire["AvgChkAmt30Day"])),
            avg_check_amount_90d=Decimal(str(wire["AvgChkAmt90Day"])),
            avg_check_amount_365d=Decimal(str(wire["AvgChkAmt365Day"])),
            check_std_dev_30d=Decimal(str(wire["ChkAmtStdDev30Day"])),
            max_check_amount_90d=Decimal(str(wire["MaxChkAmt90Day"])),
            check_frequency_30d=wire.get("ChkCnt30Day"),
            returned_item_count_90d=wire.get("RtnItemCnt90Day"),
            exception_count_90d=wire.get("ExceptCnt90Day"),
        )

    # -------------------------------------------------------- history
    def _serialize_history(self, record: dict) -> dict:
        sts = _RETURNED_STS if record["status"] == "returned" else _CLEARED_STS
        return {
            "ItemId": record["external_item_id"],
            "AcctId": record["account_id"],
            "SerialNum": record["check_number"],
            "TranAmt": float(record["amount"]),
            "ItemDt": _iso(record["check_date"]),
            "PayeeNme": record["payee_name"],
            "ItemStsCode": sts,
            "RtnRsnTxt": record["return_reason"],
            "FrontImageId": record["front_image_id"],
            "BackImageId": record["back_image_id"],
        }

    def _parse_history(self, wire: dict) -> HistoricalCheck:
        status = _HISTORY_STS_TO_CANONICAL.get(wire["ItemStsCode"], "cleared")
        return HistoricalCheck(
            external_item_id=wire["ItemId"],
            account_id=wire["AcctId"],
            check_number=wire.get("SerialNum"),
            amount=Decimal(str(wire["TranAmt"])),
            check_date=_dt(wire["ItemDt"]),
            payee_name=wire.get("PayeeNme"),
            status=status,
            return_reason=wire.get("RtnRsnTxt"),
            front_image_id=wire.get("FrontImageId"),
            back_image_id=wire.get("BackImageId"),
        )
