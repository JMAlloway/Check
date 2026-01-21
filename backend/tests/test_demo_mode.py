"""
Comprehensive tests for Demo Mode functionality.

Run with: pytest tests/test_demo_mode.py -v
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.demo import is_demo_mode, require_demo_mode, require_non_production
from app.demo.providers import (
    DemoAIProvider,
    DemoCheckDataProvider,
    DemoConnectorFactory,
    get_demo_ai_provider,
    get_demo_check_provider,
)
from app.demo.scenarios import (
    DEMO_ACCOUNTS,
    DEMO_CREDENTIALS,
    DEMO_PAYEES,
    DEMO_ROUTING_NUMBERS,
    DEMO_SCENARIOS,
    DemoAccount,
    DemoCheckScenario,
    DemoScenario,
)

# =============================================================================
# Demo Module Core Tests
# =============================================================================


class TestDemoModuleFunctions:
    """Tests for core demo module functions."""

    def test_is_demo_mode_enabled(self):
        """Test is_demo_mode returns True when enabled."""
        with patch("app.demo.settings") as mock_settings:
            mock_settings.DEMO_MODE = True
            assert is_demo_mode() is True

    def test_is_demo_mode_disabled(self):
        """Test is_demo_mode returns False when disabled."""
        with patch("app.demo.settings") as mock_settings:
            mock_settings.DEMO_MODE = False
            assert is_demo_mode() is False

    def test_require_demo_mode_when_enabled(self):
        """Test require_demo_mode passes when enabled."""
        with patch("app.demo.settings") as mock_settings:
            mock_settings.DEMO_MODE = True
            # Should not raise
            require_demo_mode()

    def test_require_demo_mode_when_disabled(self):
        """Test require_demo_mode raises when disabled."""
        with patch("app.demo.settings") as mock_settings:
            mock_settings.DEMO_MODE = False
            with pytest.raises(RuntimeError, match="requires demo mode"):
                require_demo_mode()

    def test_require_non_production_in_development(self):
        """Test require_non_production passes in development."""
        with patch("app.demo.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "development"
            # Should not raise
            require_non_production()

    def test_require_non_production_in_production(self):
        """Test require_non_production raises in production."""
        with patch("app.demo.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"
            with pytest.raises(RuntimeError, match="not allowed in production"):
                require_non_production()


# =============================================================================
# Demo Scenarios Tests
# =============================================================================


class TestDemoScenarios:
    """Tests for demo scenario definitions."""

    def test_all_scenarios_have_definitions(self):
        """Verify all DemoScenario enum values have configurations."""
        for scenario in DemoScenario:
            assert scenario in DEMO_SCENARIOS, f"Missing config for {scenario}"

    def test_scenario_config_structure(self):
        """Verify scenario configs have required fields."""
        for scenario, config in DEMO_SCENARIOS.items():
            assert isinstance(config, DemoCheckScenario)
            assert config.scenario == scenario
            assert isinstance(config.amount_range, tuple)
            assert len(config.amount_range) == 2
            assert config.amount_range[0] <= config.amount_range[1]
            assert config.risk_level in ["low", "medium", "high", "critical"]
            assert config.ai_recommendation in ["likely_legitimate", "needs_review", "likely_fraud"]
            assert 0 <= config.ai_confidence <= 1
            assert isinstance(config.flags, list)
            assert isinstance(config.explanation, str)
            assert len(config.explanation) > 0

    def test_low_risk_scenarios_have_no_flags(self):
        """Verify low risk scenarios have no flags."""
        low_risk = [
            DemoScenario.ROUTINE_PAYROLL,
            DemoScenario.REGULAR_VENDOR_PAYMENT,
            DemoScenario.KNOWN_CUSTOMER_CHECK,
        ]
        for scenario in low_risk:
            config = DEMO_SCENARIOS[scenario]
            assert config.risk_level == "low"
            assert len(config.flags) == 0
            assert config.requires_dual_control is False

    def test_critical_scenarios_require_dual_control(self):
        """Verify critical risk scenarios require dual control."""
        for scenario, config in DEMO_SCENARIOS.items():
            if config.risk_level == "critical":
                assert (
                    config.requires_dual_control is True
                ), f"{scenario} is critical but doesn't require dual control"

    def test_fraud_scenarios_have_likely_fraud_recommendation(self):
        """Verify fraud scenarios have appropriate recommendations."""
        fraud_scenarios = [
            DemoScenario.COUNTERFEIT_CHECK,
            DemoScenario.FORGED_SIGNATURE,
            DemoScenario.ACCOUNT_TAKEOVER,
            DemoScenario.DUPLICATE_CHECK,
        ]
        for scenario in fraud_scenarios:
            config = DEMO_SCENARIOS[scenario]
            assert config.ai_recommendation == "likely_fraud"


class TestDemoAccounts:
    """Tests for demo account definitions."""

    def test_demo_accounts_exist(self):
        """Verify demo accounts are defined."""
        assert len(DEMO_ACCOUNTS) > 0

    def test_demo_accounts_structure(self):
        """Verify demo accounts have correct structure."""
        for account in DEMO_ACCOUNTS:
            assert isinstance(account, DemoAccount)
            assert account.account_id.startswith("DEMO-")
            assert "****" in account.account_number_masked
            assert account.account_type in ["consumer", "business", "commercial", "non_profit"]
            assert account.tenure_days > 0
            assert account.avg_balance > 0
            assert account.avg_check_amount > 0
            assert account.check_frequency >= 0
            assert account.returned_items >= 0
            assert account.holder_name.startswith("DEMO-")

    def test_demo_accounts_have_unique_ids(self):
        """Verify demo account IDs are unique."""
        account_ids = [acc.account_id for acc in DEMO_ACCOUNTS]
        assert len(account_ids) == len(set(account_ids))

    def test_business_accounts_have_business_name(self):
        """Verify business accounts have business names."""
        for account in DEMO_ACCOUNTS:
            if account.account_type in ["business", "commercial", "non_profit"]:
                assert account.business_name is not None
                assert account.business_name.startswith("DEMO-")


class TestDemoCredentials:
    """Tests for demo credentials."""

    def test_demo_credentials_exist(self):
        """Verify demo credentials are defined."""
        assert len(DEMO_CREDENTIALS) >= 3

    def test_required_roles_exist(self):
        """Verify required roles have credentials."""
        required_roles = ["reviewer", "senior_reviewer", "administrator"]
        for role in required_roles:
            assert role in DEMO_CREDENTIALS

    def test_credentials_structure(self):
        """Verify credentials have required fields."""
        for role, cred in DEMO_CREDENTIALS.items():
            assert "username" in cred
            assert "password" in cred
            assert "role" in cred
            assert "description" in cred
            assert cred["username"].endswith("_demo")
            assert len(cred["password"]) >= 8  # Basic password policy

    def test_credentials_are_secure_enough_for_demo(self):
        """Verify demo passwords meet basic requirements."""
        for role, cred in DEMO_CREDENTIALS.items():
            password = cred["password"]
            # Check for mixed case, numbers, special chars
            assert any(c.isupper() for c in password)
            assert any(c.islower() for c in password)
            assert any(c.isdigit() for c in password)


class TestDemoPayees:
    """Tests for demo payee data."""

    def test_demo_payees_exist(self):
        """Verify demo payees are defined."""
        assert len(DEMO_PAYEES) > 0

    def test_demo_payees_are_synthetic(self):
        """Verify all payees are clearly marked as demo."""
        for payee in DEMO_PAYEES:
            assert payee.startswith("DEMO-PAYEE-")


class TestDemoRoutingNumbers:
    """Tests for demo routing numbers."""

    def test_demo_routing_numbers_exist(self):
        """Verify demo routing numbers are defined."""
        assert len(DEMO_ROUTING_NUMBERS) > 0

    def test_demo_routing_numbers_are_fake(self):
        """Verify routing numbers are clearly fake (all zeros)."""
        for routing in DEMO_ROUTING_NUMBERS:
            # Should be 9 digits, all zeros except last
            assert len(routing) == 9
            assert routing.startswith("00000000")


# =============================================================================
# Demo Providers Tests
# =============================================================================


class TestDemoCheckDataProvider:
    """Tests for DemoCheckDataProvider."""

    def setup_method(self):
        """Set up test provider."""
        self.provider = DemoCheckDataProvider()

    @pytest.mark.asyncio
    async def test_get_account_info_valid(self):
        """Test getting info for a valid demo account."""
        account = DEMO_ACCOUNTS[0]
        result = await self.provider.get_account_info(account.account_id)

        assert result is not None
        assert result["account_id"] == account.account_id
        assert result["account_type"] == account.account_type
        assert result["is_demo"] is True

    @pytest.mark.asyncio
    async def test_get_account_info_invalid(self):
        """Test getting info for an invalid account ID."""
        result = await self.provider.get_account_info("NONEXISTENT-ACCOUNT")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_check_history(self):
        """Test getting check history for an account."""
        account = DEMO_ACCOUNTS[0]
        result = await self.provider.get_check_history(account.account_id, limit=5)

        assert isinstance(result, list)
        assert len(result) == 5
        for item in result:
            assert "check_number" in item
            assert "amount" in item
            assert "is_demo" in item
            assert item["is_demo"] is True

    @pytest.mark.asyncio
    async def test_get_check_history_invalid_account(self):
        """Test getting history for invalid account returns empty."""
        result = await self.provider.get_check_history("NONEXISTENT", limit=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_check_image(self):
        """Test getting check image reference."""
        result = await self.provider.get_check_image("TEST-ITEM-001", "front")

        assert result is not None
        assert result["image_type"] == "front"
        assert result["is_demo"] is True
        assert "watermark" in result

    @pytest.mark.asyncio
    async def test_verify_routing_number(self):
        """Test routing number verification."""
        result = await self.provider.verify_routing_number("021000021")

        assert result["valid"] is True
        assert result["is_demo"] is True
        assert "DEMO" in result["bank_name"]


class TestDemoAIProvider:
    """Tests for DemoAIProvider."""

    def setup_method(self):
        """Set up test provider."""
        self.provider = DemoAIProvider()

    @pytest.mark.asyncio
    async def test_analyze_check_basic(self):
        """Test basic check analysis."""
        check_data = {
            "amount": 1500.00,
            "memo": "Regular payment",
        }
        result = await self.provider.analyze_check(check_data)

        assert result is not None
        assert result["is_demo"] is True
        assert "recommendation" in result
        assert "confidence" in result
        assert result["requires_human_review"] is True
        assert result["auto_decision_eligible"] is False

    @pytest.mark.asyncio
    async def test_analyze_check_altered_amount(self):
        """Test analysis detects altered amount scenario."""
        check_data = {
            "amount": 10000.00,
            "memo": "Demo payment - altered_amount",
        }
        result = await self.provider.analyze_check(check_data)

        assert result["recommendation"] == "needs_review"
        assert "AMOUNT_ALTERATION" in result["flags"]
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_analyze_check_counterfeit(self):
        """Test analysis detects counterfeit scenario."""
        check_data = {
            "amount": 25000.00,
            "memo": "counterfeit test",
        }
        result = await self.provider.analyze_check(check_data)

        assert result["recommendation"] == "likely_fraud"
        assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_analyze_check_high_amount(self):
        """Test analysis flags unusual high amounts."""
        check_data = {
            "amount": 75000.00,
            "memo": "Large payment",
        }
        result = await self.provider.analyze_check(check_data)

        assert result["recommendation"] == "needs_review"
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_analyze_check_new_account_high_value(self):
        """Test analysis flags new accounts with high value."""
        check_data = {
            "amount": 20000.00,
            "memo": "First check",
        }
        account_data = {
            "tenure_days": 30,  # New account
        }
        result = await self.provider.analyze_check(check_data, account_data)

        assert result["recommendation"] == "needs_review"

    @pytest.mark.asyncio
    async def test_compare_signatures(self):
        """Test signature comparison returns advisory result."""
        result = await self.provider.compare_signatures(
            current_signature=b"signature1",
            historical_signatures=[b"sig2", b"sig3"],
        )

        assert result["is_demo"] is True
        assert "similarity_score" in result
        assert 0 <= result["similarity_score"] <= 1
        assert "advisory_notice" in result

    @pytest.mark.asyncio
    async def test_detect_alterations(self):
        """Test alteration detection returns advisory result."""
        result = await self.provider.detect_alterations(check_image=b"image_data")

        assert result["is_demo"] is True
        assert "has_potential_alterations" in result
        assert "advisory_notice" in result

    @pytest.mark.asyncio
    async def test_ai_analysis_has_advisory_notice(self):
        """Test all AI outputs have advisory notices."""
        check_data = {"amount": 1000.00}
        result = await self.provider.analyze_check(check_data)

        assert "advisory_notice" in result
        assert "ADVISORY" in result["advisory_notice"]


class TestDemoConnectorFactory:
    """Tests for DemoConnectorFactory."""

    def test_get_check_data_provider(self):
        """Test factory returns check data provider."""
        provider = DemoConnectorFactory.get_check_data_provider()
        assert isinstance(provider, DemoCheckDataProvider)

    def test_get_ai_provider(self):
        """Test factory returns AI provider."""
        provider = DemoConnectorFactory.get_ai_provider()
        assert isinstance(provider, DemoAIProvider)


class TestProviderSingletons:
    """Tests for provider singleton functions."""

    def test_get_demo_check_provider_returns_same_instance(self):
        """Test singleton returns same instance."""
        # Reset singleton
        import app.demo.providers as providers

        providers._demo_check_provider = None

        provider1 = get_demo_check_provider()
        provider2 = get_demo_check_provider()
        assert provider1 is provider2

    def test_get_demo_ai_provider_returns_same_instance(self):
        """Test singleton returns same instance."""
        # Reset singleton
        import app.demo.providers as providers

        providers._demo_ai_provider = None

        provider1 = get_demo_ai_provider()
        provider2 = get_demo_ai_provider()
        assert provider1 is provider2


# =============================================================================
# Integration Tests
# =============================================================================


class TestDemoModeIntegration:
    """Integration tests for demo mode components working together."""

    @pytest.mark.asyncio
    async def test_full_check_analysis_workflow(self):
        """Test complete workflow: account lookup -> check analysis."""
        check_provider = DemoCheckDataProvider()
        ai_provider = DemoAIProvider()

        # Get account info
        account = DEMO_ACCOUNTS[0]
        account_info = await check_provider.get_account_info(account.account_id)
        assert account_info is not None

        # Analyze a check for this account
        check_data = {
            "amount": float(account.avg_check_amount),
            "memo": "Regular vendor payment",
            "account_id": account.account_id,
        }
        analysis = await ai_provider.analyze_check(check_data, account_info)

        assert analysis["is_demo"] is True
        assert analysis["requires_human_review"] is True

    @pytest.mark.asyncio
    async def test_scenario_to_analysis_mapping(self):
        """Test that each scenario maps to correct analysis output."""
        ai_provider = DemoAIProvider()

        # Test each scenario keyword
        test_cases = [
            ("payroll", "likely_legitimate", "low"),
            ("altered", "needs_review", "high"),
            ("forged", "likely_fraud", "critical"),
            ("counterfeit", "likely_fraud", "critical"),
        ]

        for keyword, expected_rec, expected_risk in test_cases:
            check_data = {"amount": 5000.00, "memo": keyword}
            result = await ai_provider.analyze_check(check_data)

            assert (
                result["recommendation"] == expected_rec
            ), f"Failed for {keyword}: got {result['recommendation']}"
            assert (
                result["risk_level"] == expected_risk
            ), f"Failed for {keyword}: got {result['risk_level']}"


# =============================================================================
# Safety Tests
# =============================================================================


class TestDemoSafety:
    """Tests verifying safety of demo mode."""

    def test_all_demo_data_marked(self):
        """Verify all demo data has proper markers."""
        # Accounts marked
        for account in DEMO_ACCOUNTS:
            assert "DEMO" in account.account_id
            assert "DEMO" in account.holder_name

        # Payees marked
        for payee in DEMO_PAYEES:
            assert payee.startswith("DEMO-")

    def test_no_real_pii_in_credentials(self):
        """Verify demo credentials don't contain real PII patterns."""
        for role, cred in DEMO_CREDENTIALS.items():
            username = cred["username"]
            # Should not look like real usernames
            assert "_demo" in username
            # Should not contain real-looking email format
            assert "@" not in username

    def test_routing_numbers_are_clearly_fake(self):
        """Verify routing numbers can't be mistaken for real ones."""
        for routing in DEMO_ROUTING_NUMBERS:
            # Real routing numbers don't start with 00000000
            assert routing.startswith("00000000")

    @pytest.mark.asyncio
    async def test_ai_never_auto_approves(self):
        """Verify AI provider never sets auto_decision_eligible."""
        ai_provider = DemoAIProvider()

        # Test various scenarios
        scenarios = [
            {"amount": 100.00},  # Small amount
            {"amount": 100000.00},  # Large amount
            {"memo": "payroll"},  # Routine
            {"memo": "suspicious"},  # Suspicious
        ]

        for check_data in scenarios:
            result = await ai_provider.analyze_check(check_data)
            assert result["auto_decision_eligible"] is False
            assert result["requires_human_review"] is True
