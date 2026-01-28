"""Mock adapter for development and testing.

This adapter generates realistic mock data for all integration interfaces.
Use this for local development and testing without external dependencies.
"""

import hashlib
import io
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.integrations.interfaces.base import (
    AccountContext,
    AccountContextProvider,
    CheckBehaviorStats,
    CheckHistoryProvider,
    CheckImageData,
    CheckImageProvider,
    CheckItemProvider,
    HistoricalCheck,
    PresentedItem,
)
from PIL import Image, ImageDraw, ImageFont


class MockAdapter(
    CheckItemProvider,
    CheckImageProvider,
    AccountContextProvider,
    CheckHistoryProvider,
):
    """
    Mock adapter that generates realistic test data.

    This adapter is designed to provide realistic scenarios for testing
    the check review workflow, including various risk profiles and edge cases.
    """

    def __init__(self, seed: int | None = None):
        """Initialize mock adapter with optional random seed for reproducibility."""
        if seed is not None:
            random.seed(seed)

        self._accounts = self._generate_mock_accounts()
        self._items = self._generate_mock_items()
        self._history = self._generate_mock_history()

    def _generate_mock_accounts(self) -> dict:
        """Generate mock account data."""
        account_types = ["consumer", "business", "commercial", "non_profit"]
        accounts = {}

        for i in range(50):
            account_id = f"ACC{100000 + i:06d}"
            account_type = random.choice(account_types)

            # Business accounts tend to have higher balances and check amounts
            if account_type in ["business", "commercial"]:
                avg_balance = Decimal(random.uniform(50000, 500000)).quantize(Decimal("0.01"))
                avg_check = Decimal(random.uniform(2000, 20000)).quantize(Decimal("0.01"))
            else:
                avg_balance = Decimal(random.uniform(1000, 50000)).quantize(Decimal("0.01"))
                avg_check = Decimal(random.uniform(100, 3000)).quantize(Decimal("0.01"))

            accounts[account_id] = {
                "account_id": account_id,
                "account_type": account_type,
                "account_number_masked": f"****{1000 + i:04d}",
                "tenure_days": random.randint(30, 3650),
                "current_balance": avg_balance * Decimal(random.uniform(0.5, 1.5)),
                "avg_balance_30d": avg_balance,
                "avg_check_30d": avg_check,
                "avg_check_90d": avg_check * Decimal(random.uniform(0.9, 1.1)),
                "avg_check_365d": avg_check * Decimal(random.uniform(0.8, 1.2)),
                "std_dev_30d": avg_check * Decimal(random.uniform(0.2, 0.5)),
                "max_check_90d": avg_check * Decimal(random.uniform(2, 5)),
                "frequency_30d": random.randint(2, 30),
                "returned_90d": random.randint(0, 3),
                "exceptions_90d": random.randint(0, 5),
                "relationship_id": f"REL{10000 + (i // 3):05d}",
                "branch_code": f"BR{random.randint(1, 20):03d}",
            }

        return accounts

    def _generate_mock_items(self) -> list:
        """Generate mock presented check items."""
        items = []
        payees = [
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
            None,  # Some checks may not have extracted payee
        ]

        for i in range(100):
            account = random.choice(list(self._accounts.values()))
            account_id = account["account_id"]

            # Generate check amount - most within normal range, some outliers
            if random.random() < 0.15:  # 15% are high-value
                amount = Decimal(random.uniform(5000, 50000)).quantize(Decimal("0.01"))
            elif random.random() < 0.1:  # 10% are very high
                amount = Decimal(random.uniform(50000, 200000)).quantize(Decimal("0.01"))
            else:
                avg = float(account["avg_check_30d"])
                std = float(account["std_dev_30d"])
                amount = Decimal(max(50, random.gauss(avg, std))).quantize(Decimal("0.01"))

            presented_date = datetime.now(timezone.utc) - timedelta(
                hours=random.randint(0, 48),
                minutes=random.randint(0, 59),
            )

            # Generate some flags for high-risk items
            flags = []
            if amount > account["max_check_90d"]:
                flags.append("AMOUNT_EXCEEDS_MAX")
            if amount > account["avg_check_30d"] * 3:
                flags.append("AMOUNT_3X_AVERAGE")
            if account["returned_90d"] > 2:
                flags.append("PRIOR_RETURNS")
            if random.random() < 0.05:
                flags.append("MICR_ANOMALY")

            item_id = f"CHK{1000000 + i:07d}"
            # Fiserv Director compatibility - captured 1-4 hours after presented
            captured_at = presented_date + timedelta(
                hours=random.randint(1, 4),
                minutes=random.randint(0, 59),
            )
            items.append(
                {
                    "external_item_id": item_id,
                    "source_system": "mock",
                    "account_id": account_id,
                    "account_number_masked": account["account_number_masked"],
                    "account_type": account["account_type"],
                    "routing_number": "123456789",
                    "check_number": str(1000 + i),
                    "amount": amount,
                    "currency": "USD",
                    "payee_name": random.choice(payees),
                    "memo": random.choice(
                        ["Invoice #" + str(random.randint(1000, 9999)), None, None]
                    ),
                    "micr_line": f"T123456789T {account_id} {1000 + i}",
                    "micr_account": account_id,
                    "micr_routing": "123456789",
                    "micr_check_number": str(1000 + i),
                    "presented_date": presented_date,
                    "check_date": presented_date - timedelta(days=random.randint(0, 5)),
                    "front_image_id": f"IMG_{item_id}_FRONT",
                    "back_image_id": f"IMG_{item_id}_BACK",
                    "upstream_flags": flags if flags else None,
                    # Fiserv Director compatibility fields
                    "batch_id": f"BATCH{random.randint(100000, 999999)}",
                    "captured_at": captured_at,
                    "source_status": 0,  # 0 = ready for processing
                    "item_type_code": (
                        29 if account["account_type"] == "consumer" else 31
                    ),  # DDA Debits / Commercial
                }
            )

        return sorted(items, key=lambda x: x["presented_date"], reverse=True)

    def _generate_mock_history(self) -> dict:
        """Generate mock check history for each account."""
        history = {}

        for account_id, account in self._accounts.items():
            account_history = []
            avg = float(account["avg_check_30d"])
            std = float(account["std_dev_30d"])

            for i in range(random.randint(5, 30)):
                amount = Decimal(max(50, random.gauss(avg, std))).quantize(Decimal("0.01"))
                check_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))

                # Most checks clear successfully
                if random.random() < 0.95:
                    status = "cleared"
                    return_reason = None
                else:
                    status = "returned"
                    return_reason = random.choice(
                        [
                            "NSF",
                            "Stop Payment",
                            "Signature Mismatch",
                            "Stale Dated",
                        ]
                    )

                item_id = f"HIST{random.randint(1000000, 9999999)}"
                account_history.append(
                    {
                        "external_item_id": item_id,
                        "account_id": account_id,
                        "check_number": str(random.randint(100, 9999)),
                        "amount": amount,
                        "check_date": check_date,
                        "payee_name": random.choice(
                            [
                                "ABC Supplies Inc",
                                "Johnson & Associates",
                                "City Utilities",
                                None,
                            ]
                        ),
                        "status": status,
                        "return_reason": return_reason,
                        "front_image_id": f"IMG_{item_id}_FRONT",
                        "back_image_id": f"IMG_{item_id}_BACK",
                    }
                )

            history[account_id] = sorted(
                account_history,
                key=lambda x: x["check_date"],
                reverse=True,
            )

        return history

    def _generate_check_image(
        self,
        image_id: str,
        is_front: bool = True,
        width: int = 1200,
        height: int = 600,
    ) -> bytes:
        """Generate a mock check image."""
        # Create a realistic-looking check image
        img = Image.new("RGB", (width, height), color=(255, 255, 250))
        draw = ImageDraw.Draw(img)

        # Parse image ID to get check info
        parts = image_id.split("_")

        if is_front:
            # Draw check border
            draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(200, 200, 200), width=2)

            # Bank name area
            draw.rectangle([(20, 20), (300, 80)], outline=(100, 100, 100))
            draw.text((30, 35), "COMMUNITY BANK", fill=(0, 0, 100))
            draw.text((30, 55), "Member FDIC", fill=(100, 100, 100))

            # Check number area (top right)
            draw.text((width - 150, 30), "1234", fill=(0, 0, 0))

            # Date line
            draw.text((width - 250, 80), "DATE: __________", fill=(0, 0, 0))

            # Pay to the order of
            draw.text((30, 150), "PAY TO THE", fill=(0, 0, 0))
            draw.text((30, 170), "ORDER OF", fill=(0, 0, 0))
            draw.line([(150, 180), (width - 300, 180)], fill=(0, 0, 0))

            # Dollar amount box
            draw.rectangle([(width - 200, 140), (width - 30, 190)], outline=(0, 0, 0))
            draw.text((width - 190, 155), "$ ________", fill=(0, 0, 0))

            # Legal amount line
            draw.line([(30, 250), (width - 200, 250)], fill=(0, 0, 0))
            draw.text((width - 180, 240), "DOLLARS", fill=(0, 0, 0))

            # Memo line
            draw.text((30, 350), "MEMO", fill=(100, 100, 100))
            draw.line([(100, 360), (400, 360)], fill=(0, 0, 0))

            # Signature line
            draw.line([(width - 400, 360), (width - 50, 360)], fill=(0, 0, 0))
            draw.text((width - 350, 370), "AUTHORIZED SIGNATURE", fill=(100, 100, 100))

            # MICR line at bottom
            draw.rectangle([(30, height - 80), (width - 30, height - 30)], fill=(240, 240, 240))
            draw.text(
                (50, height - 65),
                "⑆123456789⑆ ⑈0123456789⑈ 1234",
                fill=(0, 0, 0),
            )

            # Add some "handwriting" simulation
            draw.text((160, 145), "Sample Payee Name", fill=(0, 0, 100))
            draw.text((width - 180, 155), "5,000.00", fill=(0, 0, 100))
            draw.text((30, 220), "Five Thousand and 00/100", fill=(0, 0, 100))

            # Signature simulation
            points = [(width - 350, 340)]
            for _ in range(20):
                last = points[-1]
                points.append(
                    (
                        last[0] + random.randint(10, 20),
                        last[1] + random.randint(-10, 10),
                    )
                )
            draw.line(points, fill=(0, 0, 150), width=2)

        else:
            # Back of check - endorsement area
            draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(200, 200, 200), width=2)

            # Endorsement box
            draw.rectangle([(30, 30), (400, 200)], outline=(0, 0, 0))
            draw.text((40, 40), "ENDORSE HERE", fill=(100, 100, 100))
            draw.text((40, 60), "X _______________", fill=(0, 0, 0))
            draw.text((40, 100), "DO NOT WRITE, STAMP, OR", fill=(100, 100, 100))
            draw.text((40, 120), "SIGN BELOW THIS LINE", fill=(100, 100, 100))

            # Processing stamps simulation
            draw.text((500, 100), "DEPOSITED", fill=(255, 0, 0))
            draw.text((500, 130), "01/05/2026", fill=(255, 0, 0))
            draw.text((500, 160), "COMMUNITY BANK", fill=(255, 0, 0))

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    # CheckItemProvider implementation
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
        """Get mock presented items."""
        filtered = []

        for item in self._items:
            if not (date_from <= item["presented_date"] <= date_to):
                continue
            if amount_min and item["amount"] < amount_min:
                continue
            if amount_max and item["amount"] > amount_max:
                continue
            if account_types and item["account_type"] not in account_types:
                continue
            filtered.append(item)

        total = len(filtered)
        page_items = filtered[offset : offset + limit]

        return (
            [
                PresentedItem(
                    external_item_id=item["external_item_id"],
                    source_system=item["source_system"],
                    account_id=item["account_id"],
                    account_number_masked=item["account_number_masked"],
                    account_type=item["account_type"],
                    routing_number=item["routing_number"],
                    check_number=item["check_number"],
                    amount=item["amount"],
                    currency=item["currency"],
                    payee_name=item["payee_name"],
                    memo=item["memo"],
                    micr_line=item["micr_line"],
                    micr_account=item["micr_account"],
                    micr_routing=item["micr_routing"],
                    micr_check_number=item["micr_check_number"],
                    presented_date=item["presented_date"],
                    check_date=item["check_date"],
                    front_image_id=item["front_image_id"],
                    back_image_id=item["back_image_id"],
                    upstream_flags=item["upstream_flags"],
                    # Fiserv Director compatibility fields
                    batch_id=item.get("batch_id"),
                    captured_at=item.get("captured_at"),
                    source_status=item.get("source_status"),
                    item_type_code=item.get("item_type_code"),
                )
                for item in page_items
            ],
            total,
        )

    async def get_item_by_id(self, external_item_id: str) -> PresentedItem | None:
        """Get a specific mock item."""
        for item in self._items:
            if item["external_item_id"] == external_item_id:
                return PresentedItem(
                    external_item_id=item["external_item_id"],
                    source_system=item["source_system"],
                    account_id=item["account_id"],
                    account_number_masked=item["account_number_masked"],
                    account_type=item["account_type"],
                    routing_number=item["routing_number"],
                    check_number=item["check_number"],
                    amount=item["amount"],
                    currency=item["currency"],
                    payee_name=item["payee_name"],
                    memo=item["memo"],
                    micr_line=item["micr_line"],
                    micr_account=item["micr_account"],
                    micr_routing=item["micr_routing"],
                    micr_check_number=item["micr_check_number"],
                    presented_date=item["presented_date"],
                    check_date=item["check_date"],
                    front_image_id=item["front_image_id"],
                    back_image_id=item["back_image_id"],
                    upstream_flags=item["upstream_flags"],
                    # Fiserv Director compatibility fields
                    batch_id=item.get("batch_id"),
                    captured_at=item.get("captured_at"),
                    source_status=item.get("source_status"),
                    item_type_code=item.get("item_type_code"),
                )
        return None

    # CheckImageProvider implementation
    async def get_image(self, image_id: str) -> CheckImageData | None:
        """Get a mock check image."""
        # Handle demo image IDs (format: DEMO-IMG-{uuid}-front/back)
        if image_id.startswith("DEMO-IMG-"):
            is_front = image_id.endswith("-front")
        else:
            is_front = "FRONT" in image_id

        image_bytes = self._generate_check_image(image_id, is_front=is_front)

        return CheckImageData(
            image_id=image_id,
            image_type="front" if is_front else "back",
            content=image_bytes,
            content_type="image/png",
            width=1200,
            height=600,
            dpi=200,
        )

    async def get_image_url(self, image_id: str, expires_in: int = 60) -> str | None:
        """Mock doesn't support direct URLs."""
        return None

    async def get_thumbnail(
        self, image_id: str, width: int = 200, height: int = 100
    ) -> bytes | None:
        """Get a thumbnail version."""
        # Handle demo image IDs (format: DEMO-IMG-{uuid}-front/back)
        if image_id.startswith("DEMO-IMG-"):
            is_front = image_id.endswith("-front")
        else:
            is_front = "FRONT" in image_id
        return self._generate_check_image(image_id, is_front=is_front, width=width, height=height)

    # AccountContextProvider implementation
    async def get_account_context(self, account_id: str) -> AccountContext | None:
        """Get mock account context."""
        if account_id not in self._accounts:
            return None

        account = self._accounts[account_id]
        return AccountContext(
            account_id=account_id,
            account_type=account["account_type"],
            account_tenure_days=account["tenure_days"],
            current_balance=account["current_balance"],
            average_balance_30d=account["avg_balance_30d"],
            relationship_id=account["relationship_id"],
            branch_code=account["branch_code"],
            market_code="METRO",
        )

    async def get_check_behavior_stats(self, account_id: str) -> CheckBehaviorStats | None:
        """Get mock check behavior statistics."""
        if account_id not in self._accounts:
            return None

        account = self._accounts[account_id]
        return CheckBehaviorStats(
            account_id=account_id,
            avg_check_amount_30d=account["avg_check_30d"],
            avg_check_amount_90d=account["avg_check_90d"],
            avg_check_amount_365d=account["avg_check_365d"],
            check_std_dev_30d=account["std_dev_30d"],
            max_check_amount_90d=account["max_check_90d"],
            check_frequency_30d=account["frequency_30d"],
            returned_item_count_90d=account["returned_90d"],
            exception_count_90d=account["exceptions_90d"],
        )

    # CheckHistoryProvider implementation
    async def get_check_history(
        self,
        account_id: str,
        limit: int = 10,
        amount_range: tuple[Decimal, Decimal] | None = None,
        payee_name: str | None = None,
    ) -> list[HistoricalCheck]:
        """Get mock check history."""
        if account_id not in self._history:
            return []

        history = self._history[account_id]
        filtered = []

        for item in history:
            if amount_range:
                if not (amount_range[0] <= item["amount"] <= amount_range[1]):
                    continue
            if payee_name and item["payee_name"]:
                if payee_name.lower() not in item["payee_name"].lower():
                    continue
            filtered.append(item)

        return [
            HistoricalCheck(
                external_item_id=item["external_item_id"],
                account_id=item["account_id"],
                check_number=item["check_number"],
                amount=item["amount"],
                check_date=item["check_date"],
                payee_name=item["payee_name"],
                status=item["status"],
                return_reason=item["return_reason"],
                front_image_id=item["front_image_id"],
                back_image_id=item["back_image_id"],
            )
            for item in filtered[:limit]
        ]

    async def get_similar_checks(
        self,
        account_id: str,
        amount: Decimal,
        payee_name: str | None = None,
        limit: int = 5,
    ) -> list[HistoricalCheck]:
        """Find similar historical checks."""
        if account_id not in self._history:
            return []

        history = self._history[account_id]

        # Score each historical check by similarity
        scored = []
        for item in history:
            score = 0

            # Amount similarity (closer = higher score)
            amount_diff = abs(float(item["amount"]) - float(amount))
            amount_score = max(0, 100 - (amount_diff / float(amount) * 100))
            score += amount_score * 2

            # Payee match bonus
            if payee_name and item["payee_name"]:
                if payee_name.lower() == item["payee_name"].lower():
                    score += 50
                elif payee_name.lower() in item["payee_name"].lower():
                    score += 25

            scored.append((score, item))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            HistoricalCheck(
                external_item_id=item["external_item_id"],
                account_id=item["account_id"],
                check_number=item["check_number"],
                amount=item["amount"],
                check_date=item["check_date"],
                payee_name=item["payee_name"],
                status=item["status"],
                return_reason=item["return_reason"],
                front_image_id=item["front_image_id"],
                back_image_id=item["back_image_id"],
            )
            for _, item in scored[:limit]
        ]
