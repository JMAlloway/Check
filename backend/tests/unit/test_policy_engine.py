"""Tests for the policy engine."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.check import AccountType, CheckItem, CheckStatus, RiskLevel
from app.policy.engine import PolicyEngine


class MockCheckItem:
    """Mock check item for testing."""

    def __init__(
        self,
        amount: Decimal = Decimal("5000"),
        account_type: AccountType = AccountType.CONSUMER,
        account_tenure_days: int = 365,
        avg_check_amount_30d: Decimal = Decimal("1000"),
        returned_item_count_90d: int = 0,
        risk_level: RiskLevel = RiskLevel.LOW,
    ):
        self.id = "test-item-id"
        self.amount = amount
        self.account_type = account_type
        self.account_tenure_days = account_tenure_days
        self.avg_check_amount_30d = avg_check_amount_30d
        self.avg_check_amount_90d = avg_check_amount_30d
        self.avg_check_amount_365d = avg_check_amount_30d
        self.max_check_amount_90d = avg_check_amount_30d * 2
        self.check_std_dev_30d = Decimal("200")
        self.current_balance = Decimal("10000")
        self.returned_item_count_90d = returned_item_count_90d
        self.exception_count_90d = 0
        self.check_frequency_30d = 5
        self.risk_level = risk_level
        self.payee_name = "Test Payee"
        self.memo = None


class TestPolicyConditionEvaluation:
    """Tests for policy condition evaluation."""

    def test_greater_than_condition(self):
        """Test greater_than operator."""
        from app.models.policy import RuleConditionOperator
        from app.policy.engine import PolicyEngine
        from app.schemas.policy import RuleCondition

        engine = PolicyEngine(None)  # No DB needed for condition evaluation
        item = MockCheckItem(amount=Decimal("10000"))

        condition = RuleCondition(
            field="amount",
            operator=RuleConditionOperator.GREATER_THAN,
            value=5000,
            value_type="number",
        )

        result = engine._evaluate_condition(condition, item)
        assert result is True

        condition.value = 15000
        result = engine._evaluate_condition(condition, item)
        assert result is False

    def test_less_than_condition(self):
        """Test less_than operator."""
        from app.models.policy import RuleConditionOperator
        from app.policy.engine import PolicyEngine
        from app.schemas.policy import RuleCondition

        engine = PolicyEngine(None)
        item = MockCheckItem(account_tenure_days=15)

        condition = RuleCondition(
            field="account_tenure_days",
            operator=RuleConditionOperator.LESS_THAN,
            value=30,
            value_type="number",
        )

        result = engine._evaluate_condition(condition, item)
        assert result is True

    def test_equals_condition(self):
        """Test equals operator."""
        from app.models.policy import RuleConditionOperator
        from app.policy.engine import PolicyEngine
        from app.schemas.policy import RuleCondition

        engine = PolicyEngine(None)
        item = MockCheckItem(account_type=AccountType.BUSINESS)

        condition = RuleCondition(
            field="account_type",
            operator=RuleConditionOperator.EQUALS,
            value="business",
            value_type="string",
        )

        result = engine._evaluate_condition(condition, item)
        assert result is True

    def test_in_condition(self):
        """Test in operator."""
        from app.models.policy import RuleConditionOperator
        from app.policy.engine import PolicyEngine
        from app.schemas.policy import RuleCondition

        engine = PolicyEngine(None)
        item = MockCheckItem(risk_level=RiskLevel.HIGH)

        condition = RuleCondition(
            field="risk_level",
            operator=RuleConditionOperator.IN,
            value=["high", "critical"],
            value_type="array",
        )

        result = engine._evaluate_condition(condition, item)
        assert result is True

    def test_computed_field_amount_vs_avg_ratio(self):
        """Test computed field for amount vs average ratio."""
        from app.models.policy import RuleConditionOperator
        from app.policy.engine import PolicyEngine
        from app.schemas.policy import RuleCondition

        engine = PolicyEngine(None)
        item = MockCheckItem(
            amount=Decimal("5000"),
            avg_check_amount_30d=Decimal("1000"),
        )

        condition = RuleCondition(
            field="amount_vs_avg_ratio",
            operator=RuleConditionOperator.GREATER_OR_EQUAL,
            value=5,
            value_type="number",
        )

        result = engine._evaluate_condition(condition, item)
        assert result is True  # 5000 / 1000 = 5


class TestRiskLevelCalculation:
    """Tests for risk level calculation in CheckService."""

    def test_high_amount_increases_risk(self):
        """Test that high amounts increase risk score."""
        from app.services.check import CheckService

        service = CheckService(None)

        # Create mock item data
        class MockItem:
            amount = Decimal("75000")
            upstream_flags = None

        class MockContext:
            account_tenure_days = 365

        class MockStats:
            avg_check_amount_30d = Decimal("5000")
            returned_item_count_90d = 0
            exception_count_90d = 0

        risk = service._calculate_risk_level(MockItem(), MockContext(), MockStats())
        assert risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    def test_new_account_increases_risk(self):
        """Test that new accounts increase risk score."""
        from app.services.check import CheckService

        service = CheckService(None)

        class MockItem:
            amount = Decimal("5000")
            upstream_flags = None

        class MockContext:
            account_tenure_days = 15  # Very new account

        class MockStats:
            avg_check_amount_30d = Decimal("5000")
            returned_item_count_90d = 0
            exception_count_90d = 0

        risk = service._calculate_risk_level(MockItem(), MockContext(), MockStats())
        assert risk != RiskLevel.LOW


class TestAIFlagGeneration:
    """Tests for AI flag generation."""

    def test_amount_exceeds_average_flag(self):
        """Test flag when amount exceeds average."""
        from app.services.check import CheckService

        service = CheckService(None)

        class MockItem:
            amount = Decimal("5000")
            avg_check_amount_30d = Decimal("1000")
            max_check_amount_90d = Decimal("2000")
            account_tenure_days = 365
            returned_item_count_90d = 0
            upstream_flags = None

        flags = service._generate_ai_flags(MockItem())

        assert len(flags) > 0
        flag_codes = [f.code for f in flags]
        assert "AMOUNT_5X_AVG" in flag_codes

    def test_prior_returns_flag(self):
        """Test flag for prior returns."""
        from app.services.check import CheckService

        service = CheckService(None)

        class MockCheckItem:
            amount = Decimal("1000")
            avg_check_amount_30d = Decimal("1000")
            max_check_amount_90d = Decimal("2000")
            account_tenure_days = 365
            returned_item_count_90d = 3
            upstream_flags = None

        flags = service._generate_ai_flags(MockCheckItem())

        flag_codes = [f.code for f in flags]
        assert "PRIOR_RETURNS" in flag_codes
