"""
Demo Mode Providers for Mock Services.

This module provides mock implementations of external services
(connectors, AI) for use in demo mode. These providers return
synthetic data and never connect to external systems.

IMPORTANT: These providers should ONLY be used when DEMO_MODE is enabled.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.demo.scenarios import DEMO_ACCOUNTS, DEMO_SCENARIOS, DemoScenario


class DemoCheckDataProvider:
    """
    Mock check data provider for demo mode.

    This provider returns synthetic check data without connecting
    to any external core banking systems.
    """

    def __init__(self):
        """Initialize the demo provider."""
        self._accounts = {acc.account_id: acc for acc in DEMO_ACCOUNTS}

    async def get_account_info(self, account_id: str) -> dict[str, Any] | None:
        """Get synthetic account information."""
        account = self._accounts.get(account_id)
        if not account:
            return None

        return {
            "account_id": account.account_id,
            "account_number_masked": account.account_number_masked,
            "account_type": account.account_type,
            "holder_name": account.holder_name,
            "business_name": account.business_name,
            "tenure_days": account.tenure_days,
            "current_balance": float(account.avg_balance),
            "average_balance_30d": float(account.avg_balance),
            "status": "active",
            "opened_date": (datetime.now(timezone.utc) - timedelta(days=account.tenure_days)).isoformat(),
            "is_demo": True,
        }

    async def get_check_history(
        self, account_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get synthetic check history for an account."""
        account = self._accounts.get(account_id)
        if not account:
            return []

        history = []
        for i in range(limit):
            check_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 90))
            amount = float(account.avg_check_amount) * random.uniform(0.5, 1.5)

            history.append({
                "check_number": f"{random.randint(1000, 9999)}",
                "amount": round(amount, 2),
                "check_date": check_date.isoformat(),
                "payee_name": f"DEMO-PAYEE-{i+1}",
                "status": random.choice(["cleared", "cleared", "cleared", "returned"]),
                "is_demo": True,
            })

        return sorted(history, key=lambda x: x["check_date"], reverse=True)

    async def get_check_image(
        self, check_item_id: str, image_type: str
    ) -> dict[str, Any] | None:
        """Get synthetic check image reference."""
        return {
            "check_item_id": check_item_id,
            "image_type": image_type,
            "storage_path": f"/demo/images/{check_item_id}/{image_type}.png",
            "content_type": "image/png",
            "is_demo": True,
            "watermark": "DEMO - NOT A REAL CHECK",
        }

    async def verify_routing_number(self, routing_number: str) -> dict[str, Any]:
        """Verify a routing number (demo always returns valid)."""
        return {
            "routing_number": routing_number,
            "valid": True,
            "bank_name": "DEMO COMMUNITY BANK",
            "city": "Demo City",
            "state": "DS",
            "is_demo": True,
        }


class DemoAIProvider:
    """
    Mock AI provider for demo mode.

    This provider returns deterministic AI analysis results
    based on predefined scenarios. It never triggers auto-decisions
    and only provides advisory information.
    """

    def __init__(self):
        """Initialize the demo AI provider."""
        self._scenarios = DEMO_SCENARIOS

    async def analyze_check(
        self,
        check_data: dict[str, Any],
        account_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a check and return AI advisory output.

        IMPORTANT: This is ADVISORY ONLY. It never triggers automatic decisions.
        All outputs are for informational purposes and require human review.
        """
        # Determine scenario based on check data
        scenario = self._determine_scenario(check_data, account_data)
        scenario_config = self._scenarios.get(scenario, self._scenarios[DemoScenario.KNOWN_CUSTOMER_CHECK])

        return {
            "model_id": "demo-risk-analyzer",
            "model_version": "demo-1.0.0",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": True,

            # ADVISORY: These fields are informational only
            "recommendation": scenario_config.ai_recommendation,
            "confidence": scenario_config.ai_confidence,
            "risk_level": scenario_config.risk_level,

            "flags": scenario_config.flags,
            "explanation": scenario_config.explanation,

            "risk_factors": [
                {
                    "factor": flag,
                    "severity": scenario_config.risk_level,
                    "description": f"Demo risk factor: {flag}",
                }
                for flag in scenario_config.flags
            ],

            # Explicitly mark as advisory
            "advisory_notice": (
                "This AI analysis is for ADVISORY purposes only. "
                "All decisions must be made by authorized human reviewers. "
                "AI output should never be the sole basis for a decision."
            ),

            # Never auto-approve
            "auto_decision_eligible": False,
            "requires_human_review": True,
        }

    async def compare_signatures(
        self,
        current_signature: bytes | None,
        historical_signatures: list[bytes],
    ) -> dict[str, Any]:
        """Compare signatures (demo returns random similarity)."""
        similarity = random.uniform(0.3, 0.98)
        is_match = similarity > 0.7

        return {
            "similarity_score": round(similarity, 4),
            "is_likely_match": is_match,
            "confidence": round(random.uniform(0.6, 0.95), 4),
            "comparison_count": len(historical_signatures),
            "is_demo": True,
            "advisory_notice": "Signature comparison is advisory only.",
        }

    async def detect_alterations(
        self,
        check_image: bytes | None,
    ) -> dict[str, Any]:
        """Detect image alterations (demo returns based on scenario)."""
        # Random alteration detection for demo
        has_alterations = random.random() < 0.15  # 15% chance

        return {
            "has_potential_alterations": has_alterations,
            "confidence": round(random.uniform(0.5, 0.9), 4),
            "regions_of_interest": [
                {"area": "amount", "confidence": 0.72}
            ] if has_alterations else [],
            "is_demo": True,
            "advisory_notice": "Alteration detection is advisory only.",
        }

    def _determine_scenario(
        self,
        check_data: dict[str, Any],
        account_data: dict[str, Any] | None,
    ) -> DemoScenario:
        """Determine which demo scenario applies to this check."""
        amount = Decimal(str(check_data.get("amount", 0)))

        # Check for specific indicators
        memo = check_data.get("memo", "").lower()
        if "altered" in memo:
            return DemoScenario.ALTERED_AMOUNT
        if "suspicious" in memo:
            return DemoScenario.SUSPICIOUS_ENDORSEMENT
        if "counterfeit" in memo:
            return DemoScenario.COUNTERFEIT_CHECK
        if "forged" in memo:
            return DemoScenario.FORGED_SIGNATURE
        if "payroll" in memo:
            return DemoScenario.ROUTINE_PAYROLL

        # Amount-based scenarios
        if amount > 50000:
            return DemoScenario.UNUSUAL_AMOUNT
        if amount > 15000 and account_data and account_data.get("tenure_days", 365) < 90:
            return DemoScenario.NEW_ACCOUNT_HIGH_VALUE

        # Default to routine scenarios
        return random.choice([
            DemoScenario.ROUTINE_PAYROLL,
            DemoScenario.REGULAR_VENDOR_PAYMENT,
            DemoScenario.KNOWN_CUSTOMER_CHECK,
        ])


class DemoConnectorFactory:
    """Factory for creating demo mode providers."""

    @staticmethod
    def get_check_data_provider() -> DemoCheckDataProvider:
        """Get the demo check data provider."""
        return DemoCheckDataProvider()

    @staticmethod
    def get_ai_provider() -> DemoAIProvider:
        """Get the demo AI provider."""
        return DemoAIProvider()


# Singleton instances for demo mode
_demo_check_provider: DemoCheckDataProvider | None = None
_demo_ai_provider: DemoAIProvider | None = None


def get_demo_check_provider() -> DemoCheckDataProvider:
    """Get or create demo check data provider."""
    global _demo_check_provider
    if _demo_check_provider is None:
        _demo_check_provider = DemoCheckDataProvider()
    return _demo_check_provider


def get_demo_ai_provider() -> DemoAIProvider:
    """Get or create demo AI provider."""
    global _demo_ai_provider
    if _demo_ai_provider is None:
        _demo_ai_provider = DemoAIProvider()
    return _demo_ai_provider
