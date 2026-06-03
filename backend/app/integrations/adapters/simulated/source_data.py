"""Synthetic core-banking dataset shared by the simulated vendor adapters.

This represents the canonical "truth" that lives inside a fake core banking
system. Each vendor adapter (Fiserv, Jack Henry) serializes this truth into its
own wire format and then parses it back into the application's canonical
dataclasses - exercising exactly the marshalling code a real integration needs.

The dataset is fully deterministic for a given seed so demos and tests are
reproducible.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

_PAYEES = [
    "ABC Supplies Inc",
    "Johnson & Associates",
    "City Utilities",
    "Metro Insurance Co",
    "Smith Contractors LLC",
    "Global Trading Corp",
    "Premier Services",
    "Acme Industries",
    "First Capital Group",
    "Valley Equipment",
    None,  # not every check has an extracted payee
]

_RETURN_REASONS = ["NSF", "Stop Payment", "Signature Mismatch", "Stale Dated"]


def _money(value: float) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


class SyntheticCoreData:
    """Deterministic in-memory dataset of accounts, presented items and history."""

    def __init__(
        self,
        seed: int = 42,
        account_count: int = 50,
        item_count: int = 100,
    ) -> None:
        self._rng = random.Random(seed)
        self.accounts: dict[str, dict] = self._build_accounts(account_count)
        self.items: list[dict] = self._build_items(item_count)
        self.history: dict[str, list[dict]] = self._build_history()

    # ------------------------------------------------------------------ build
    def _build_accounts(self, count: int) -> dict[str, dict]:
        rng = self._rng
        account_types = ["consumer", "business", "commercial", "non_profit"]
        now = datetime.now(timezone.utc)
        accounts: dict[str, dict] = {}

        for i in range(count):
            account_id = f"ACC{100000 + i:06d}"
            account_type = rng.choice(account_types)

            if account_type in ("business", "commercial"):
                avg_balance = _money(rng.uniform(50000, 500000))
                avg_check = _money(rng.uniform(2000, 20000))
            else:
                avg_balance = _money(rng.uniform(1000, 50000))
                avg_check = _money(rng.uniform(100, 3000))

            tenure_days = rng.randint(30, 3650)
            current_balance = _money(float(avg_balance) * rng.uniform(0.5, 1.5))

            accounts[account_id] = {
                "account_id": account_id,
                "account_type": account_type,
                "account_number_masked": f"****{1000 + i:04d}",
                "routing_number": "123456789",
                "tenure_days": tenure_days,
                "date_opened": now - timedelta(days=tenure_days),
                "current_balance": current_balance,
                "available_balance": _money(float(current_balance) * rng.uniform(0.9, 1.0)),
                "avg_balance_30d": avg_balance,
                "avg_check_30d": avg_check,
                "avg_check_90d": _money(float(avg_check) * rng.uniform(0.9, 1.1)),
                "avg_check_365d": _money(float(avg_check) * rng.uniform(0.8, 1.2)),
                "std_dev_30d": _money(float(avg_check) * rng.uniform(0.2, 0.5)),
                "max_check_90d": _money(float(avg_check) * rng.uniform(2, 5)),
                "frequency_30d": rng.randint(2, 30),
                "returned_90d": rng.randint(0, 3),
                "exceptions_90d": rng.randint(0, 5),
                "relationship_id": f"REL{10000 + (i // 3):05d}",
                "branch_code": f"BR{rng.randint(1, 20):03d}",
                "market_code": "METRO",
            }

        return accounts

    def _build_items(self, count: int) -> list[dict]:
        rng = self._rng
        now = datetime.now(timezone.utc)
        items: list[dict] = []

        for i in range(count):
            account = rng.choice(list(self.accounts.values()))
            account_id = account["account_id"]

            if rng.random() < 0.15:
                amount = _money(rng.uniform(5000, 50000))
            elif rng.random() < 0.1:
                amount = _money(rng.uniform(50000, 200000))
            else:
                avg = float(account["avg_check_30d"])
                std = float(account["std_dev_30d"])
                amount = _money(max(50, rng.gauss(avg, std)))

            presented_date = now - timedelta(hours=rng.randint(0, 48), minutes=rng.randint(0, 59))
            captured_at = presented_date + timedelta(
                hours=rng.randint(1, 4), minutes=rng.randint(0, 59)
            )

            flags: list[str] = []
            if amount > account["max_check_90d"]:
                flags.append("AMOUNT_EXCEEDS_MAX")
            if amount > account["avg_check_30d"] * 3:
                flags.append("AMOUNT_3X_AVERAGE")
            if account["returned_90d"] > 2:
                flags.append("PRIOR_RETURNS")
            if rng.random() < 0.05:
                flags.append("MICR_ANOMALY")

            item_id = f"CHK{1000000 + i:07d}"
            check_number = str(1000 + i)
            items.append(
                {
                    "external_item_id": item_id,
                    "account_id": account_id,
                    "account_number_masked": account["account_number_masked"],
                    "account_type": account["account_type"],
                    "routing_number": account["routing_number"],
                    "check_number": check_number,
                    "amount": amount,
                    "currency": "USD",
                    "payee_name": rng.choice(_PAYEES),
                    "memo": rng.choice([f"Invoice #{rng.randint(1000, 9999)}", None, None]),
                    "micr_line": f"T{account['routing_number']}T {account_id} {check_number}",
                    "micr_account": account_id,
                    "micr_routing": account["routing_number"],
                    "micr_check_number": check_number,
                    "presented_date": presented_date,
                    "check_date": presented_date - timedelta(days=rng.randint(0, 5)),
                    "captured_at": captured_at,
                    "batch_id": f"BATCH{rng.randint(100000, 999999)}",
                    "source_status": 0,  # 0 = ready for processing
                    "item_type_code": 29 if account["account_type"] == "consumer" else 31,
                    "front_image_id": f"IMG_{item_id}_FRONT",
                    "back_image_id": f"IMG_{item_id}_BACK",
                    "upstream_flags": flags or None,
                }
            )

        return sorted(items, key=lambda x: x["presented_date"], reverse=True)

    def _build_history(self) -> dict[str, list[dict]]:
        rng = self._rng
        now = datetime.now(timezone.utc)
        history: dict[str, list[dict]] = {}

        for account_id, account in self.accounts.items():
            avg = float(account["avg_check_30d"])
            std = float(account["std_dev_30d"])
            entries: list[dict] = []

            for _ in range(rng.randint(5, 30)):
                amount = _money(max(50, rng.gauss(avg, std)))
                check_date = now - timedelta(days=rng.randint(1, 365))

                if rng.random() < 0.95:
                    status, return_reason = "cleared", None
                else:
                    status, return_reason = "returned", rng.choice(_RETURN_REASONS)

                item_id = f"HIST{rng.randint(1000000, 9999999)}"
                entries.append(
                    {
                        "external_item_id": item_id,
                        "account_id": account_id,
                        "check_number": str(rng.randint(100, 9999)),
                        "amount": amount,
                        "check_date": check_date,
                        "payee_name": rng.choice(_PAYEES),
                        "status": status,
                        "return_reason": return_reason,
                        "front_image_id": f"IMG_{item_id}_FRONT",
                        "back_image_id": f"IMG_{item_id}_BACK",
                    }
                )

            history[account_id] = sorted(entries, key=lambda x: x["check_date"], reverse=True)

        return history
