"""
Tests for the Fraud Intelligence Sharing Module.

Run with: pytest tests/test_fraud_module.py -v
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.services.fraud_hashing import FraudHashingService
from app.services.pii_detection import PIIDetectionService


class TestFraudHashing:
    """Tests for the hashing service."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use fixed pepper for reproducible tests
        self.service = FraudHashingService(pepper="test-pepper-12345")

    def test_routing_number_normalization(self):
        """Test routing number normalization."""
        # Valid 9-digit routing number
        assert self.service.normalize_routing_number("021000021") == "021000021"

        # With formatting
        assert self.service.normalize_routing_number("021-000-021") == "021000021"
        assert self.service.normalize_routing_number("021 000 021") == "021000021"

        # Invalid (wrong length)
        assert self.service.normalize_routing_number("12345") is None
        assert self.service.normalize_routing_number("1234567890") is None

        # None input
        assert self.service.normalize_routing_number(None) is None

    def test_payee_name_normalization(self):
        """Test payee name normalization."""
        # Basic uppercase conversion
        assert self.service.normalize_payee_name("acme corp") == "ACME"

        # Remove business suffixes
        assert self.service.normalize_payee_name("Acme LLC") == "ACME"
        assert self.service.normalize_payee_name("Big Company Inc.") == "BIG COMPANY"
        assert self.service.normalize_payee_name("Test Corp Ltd") == "TEST"

        # Collapse whitespace
        assert self.service.normalize_payee_name("ACME   COMPANY") == "ACME COMPANY"

        # Remove punctuation (apostrophes become spaces, then collapsed)
        normalized = self.service.normalize_payee_name("O'Brien's Store")
        assert "BRIEN" in normalized and "STORE" in normalized

        # Empty/None handling
        assert self.service.normalize_payee_name("") is None
        assert self.service.normalize_payee_name(None) is None

    def test_account_number_normalization(self):
        """Test account number normalization (last 4 + length)."""
        # Standard account
        assert self.service.normalize_account_number("1234567890") == "L10-7890"

        # Longer account
        assert self.service.normalize_account_number("9876543210123456") == "L16-3456"

        # With formatting
        assert self.service.normalize_account_number("1234-5678-90") == "L10-7890"

        # Too short
        assert self.service.normalize_account_number("123") is None

        # None input
        assert self.service.normalize_account_number(None) is None

    def test_hash_determinism(self):
        """Test that hashes are deterministic (same input = same output)."""
        routing = "021000021"

        hash1 = self.service.hash_routing_number(routing)
        hash2 = self.service.hash_routing_number(routing)

        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 64  # SHA256 hex digest length

    def test_hash_different_inputs(self):
        """Test that different inputs produce different hashes."""
        hash1 = self.service.hash_routing_number("021000021")
        hash2 = self.service.hash_routing_number("021000022")

        assert hash1 != hash2

    def test_hash_with_different_peppers(self):
        """Test that different peppers produce different hashes."""
        service1 = FraudHashingService(pepper="pepper-1")
        service2 = FraudHashingService(pepper="pepper-2")

        routing = "021000021"

        hash1 = service1.hash_routing_number(routing)
        hash2 = service2.hash_routing_number(routing)

        assert hash1 != hash2

    def test_payee_hash_stability(self):
        """Test payee hash is stable after normalization."""
        # These should all hash to the same value
        variations = [
            "ACME CORP",
            "acme corp",
            "Acme Corp LLC",
            "  ACME   CORP  ",
            "ACME CORP, INC.",
        ]

        hashes = [self.service.hash_payee_name(v) for v in variations]

        # All non-None hashes should be equal
        non_none = [h for h in hashes if h is not None]
        assert len(non_none) > 0
        assert all(h == non_none[0] for h in non_none)

    def test_generate_indicators(self):
        """Test indicator generation."""
        indicators = self.service.generate_indicators(
            routing_number="021000021",
            payee_name="ACME Corp",
            check_number="1234",
            amount_bucket="1000_to_5000",
            date_bucket="2024-01",
        )

        assert "routing_hash" in indicators
        assert "payee_hash" in indicators
        assert "check_fingerprint" in indicators

        # Account should NOT be included by default
        assert "account_hash" not in indicators

    def test_generate_indicators_with_account(self):
        """Test indicator generation with account (opt-in)."""
        indicators = self.service.generate_indicators(
            routing_number="021000021",
            payee_name="ACME Corp",
            account_number="1234567890",
            amount_bucket="1000_to_5000",
            date_bucket="2024-01",
            include_account=True,
        )

        assert "account_hash" in indicators

    def test_check_fingerprint(self):
        """Test check fingerprint generation."""
        fp1 = self.service.compute_check_fingerprint(
            routing="021000021",
            check_number="1234",
            amount_bucket="1000_to_5000",
            date_bucket="2024-01",
        )

        fp2 = self.service.compute_check_fingerprint(
            routing="021000021",
            check_number="1234",
            amount_bucket="1000_to_5000",
            date_bucket="2024-01",
        )

        assert fp1 == fp2
        assert fp1 is not None

        # Different parameters should produce different fingerprint
        fp3 = self.service.compute_check_fingerprint(
            routing="021000022",  # Different routing
            check_number="1234",
            amount_bucket="1000_to_5000",
            date_bucket="2024-01",
        )

        assert fp1 != fp3


class TestPIIDetection:
    """Tests for PII detection service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PIIDetectionService(strict=False)
        self.strict_service = PIIDetectionService(strict=True)

    def test_detect_ssn(self):
        """Test SSN detection."""
        text = "Customer SSN is 123-45-6789"
        matches = self.service.detect(text)

        assert any(m.pattern_type == "ssn" for m in matches)
        assert any(m.confidence == "high" for m in matches)

    def test_detect_email(self):
        """Test email detection."""
        text = "Contact at john.doe@example.com for more info"
        matches = self.service.detect(text)

        assert any(m.pattern_type == "email" for m in matches)

    def test_detect_credit_card(self):
        """Test credit card detection."""
        text = "Card number 4111-1111-1111-1111 was used"
        matches = self.service.detect(text)

        assert any(m.pattern_type == "credit_card" for m in matches)

    def test_detect_phone_number(self):
        """Test phone number detection."""
        text = "Call us at (555) 123-4567"
        matches = self.service.detect(text)

        assert any(m.pattern_type == "phone_us" for m in matches)

    def test_detect_account_number(self):
        """Test account number detection."""
        text = "Account 12345678901234 was debited"
        matches = self.service.detect(text)

        assert any(m.pattern_type == "account_number" for m in matches)

    def test_detect_routing_number(self):
        """Test routing number detection."""
        text = "Routing number 123456789"
        matches = self.service.detect(text)

        assert any(m.pattern_type == "routing_number" for m in matches)

    def test_detect_pii_keywords(self):
        """Test PII keyword detection."""
        text = "Please do not share the account number or SSN"
        matches = self.service.detect(text)

        keyword_matches = [m for m in matches if m.pattern_type == "pii_keyword"]
        assert len(keyword_matches) >= 2

    def test_no_pii_in_safe_text(self):
        """Test clean text passes."""
        text = "The check was returned for insufficient funds on January 15th"
        matches = self.service.detect(text)

        # Should have no high-confidence matches
        high_confidence = [m for m in matches if m.confidence == "high"]
        assert len(high_confidence) == 0

    def test_has_pii_convenience_method(self):
        """Test has_pii convenience method."""
        assert self.service.has_pii("SSN: 123-45-6789") == True
        assert self.service.has_pii("The check was returned") == False

    def test_get_warnings(self):
        """Test human-readable warnings."""
        text = "SSN is 123-45-6789, email john@test.com"
        warnings = self.service.get_warnings(text)

        assert len(warnings) >= 2
        assert any("Social Security" in w for w in warnings)
        assert any("Email" in w for w in warnings)

    def test_redact(self):
        """Test PII redaction."""
        text = "Call 555-123-4567 or email test@example.com"
        redacted = self.service.redact(text)

        assert "555-123-4567" not in redacted
        assert "test@example.com" not in redacted
        assert "[REDACTED]" in redacted

    def test_strict_mode_detects_more(self):
        """Test strict mode catches low-confidence patterns."""
        text = "He lives at 123 Main Street"

        normal_matches = self.service.detect(text)
        strict_matches = self.strict_service.detect(text)

        # Strict should find street address
        assert len(strict_matches) >= len(normal_matches)

    def test_analyze_returns_full_report(self):
        """Test analyze method returns comprehensive report."""
        text = "SSN: 123-45-6789"
        result = self.service.analyze(text)

        assert "has_potential_pii" in result
        assert "match_count" in result
        assert "high_confidence_count" in result
        assert "warnings" in result
        assert "detected_patterns" in result

        assert result["has_potential_pii"] == True
        assert result["high_confidence_count"] >= 1


class TestTenantIsolation:
    """Tests for tenant isolation in fraud queries."""

    def test_tenant_id_required_in_event_queries(self):
        """
        Verify that all fraud event queries include tenant_id filter.

        This is a code review test - verifying the implementation.
        """
        import inspect
        from app.services.fraud_service import FraudService

        # Get source code of key methods
        methods_to_check = [
            'get_fraud_event',
            'list_fraud_events',
            'dismiss_alert',
        ]

        for method_name in methods_to_check:
            method = getattr(FraudService, method_name)
            source = inspect.getsource(method)

            # Verify tenant_id is used in the method
            assert 'tenant_id' in source, f"{method_name} must filter by tenant_id"

    def test_same_tenant_excluded_in_matching(self):
        """
        Verify that _find_matching_artifacts excludes same tenant.

        This is a code review test - verifying the implementation.
        """
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService._find_matching_artifacts)

        # Must exclude same tenant
        assert 'tenant_id !=' in source or 'tenant_id!=' in source, \
            "_find_matching_artifacts must exclude same tenant"


class TestMatchingLogic:
    """Tests for network matching logic."""

    def test_sharing_level_filter_in_matching(self):
        """
        Verify that matching only uses sharing_level=2 artifacts.

        This is a code review test - verifying the implementation.
        """
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService._find_matching_artifacts)

        # Must filter by NETWORK_MATCH sharing level
        assert 'NETWORK_MATCH' in source or 'sharing_level' in source, \
            "_find_matching_artifacts must filter by sharing_level"

    def test_severity_scoring_rules(self):
        """Test severity scoring implementation."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import MatchSeverity

        # Create mock service (won't use DB)
        class MockSession:
            pass

        service = FraudService(MockSession())

        # Test HIGH: 2+ indicator types matched
        assert service._compute_severity(
            artifacts=[1, 2],  # 2 artifacts
            match_reasons={"routing_hash": {}, "payee_hash": {}}  # 2 types
        ) == MatchSeverity.HIGH

        # Test HIGH: 3+ artifacts on 1 type
        assert service._compute_severity(
            artifacts=[1, 2, 3],  # 3 artifacts
            match_reasons={"routing_hash": {}}  # 1 type
        ) == MatchSeverity.HIGH

        # Test MEDIUM: 2 artifacts on 1 type
        assert service._compute_severity(
            artifacts=[1, 2],  # 2 artifacts
            match_reasons={"routing_hash": {}}  # 1 type
        ) == MatchSeverity.MEDIUM

        # Test LOW: 1 artifact
        assert service._compute_severity(
            artifacts=[1],  # 1 artifact
            match_reasons={"routing_hash": {}}  # 1 type
        ) == MatchSeverity.LOW


class TestPrivacyThresholds:
    """Tests for privacy threshold suppression."""

    def test_threshold_applied_to_all_aggregations(self):
        """
        Verify that privacy threshold is applied to all group-bys.

        This is a code review test - verifying the implementation.
        """
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService.get_network_trends)

        # Must reference privacy_threshold
        assert 'privacy_threshold' in source or 'FRAUD_PRIVACY_THRESHOLD' in source, \
            "get_network_trends must apply privacy threshold"

        # Check _aggregate_by_field also uses threshold
        agg_source = inspect.getsource(FraudService._aggregate_by_field)
        assert 'threshold' in agg_source, \
            "_aggregate_by_field must use threshold parameter"

    def test_aggregate_by_field_suppresses_low_counts(self):
        """Test that _aggregate_by_field suppresses counts below threshold."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import FraudType

        class MockSession:
            pass

        service = FraudService(MockSession())

        # Create mock data with count of 1 (below threshold of 3)
        class MockRow:
            def __init__(self, fraud_type, count):
                self.fraud_type = fraud_type
                self.count = count

        your_data = [MockRow(FraudType.CHECK_KITING, 1)]  # Below threshold
        network_data = [MockRow(FraudType.CHECK_KITING, 5)]  # Above threshold

        result = service._aggregate_by_field(
            your_data, network_data, "fraud_type", threshold=3
        )

        # Find the check_kiting entry
        entry = next(r for r in result if r["fraud_type"] == "check_kiting")

        # Your bank count should be suppressed
        assert entry["your_bank_display"] == "<3"
        # Network count should show actual value
        assert entry["network_display"] == "5"


class TestPepperVersioning:
    """Tests for pepper rotation support."""

    def test_pepper_version_property(self):
        """Test that current pepper version is accessible."""
        service = FraudHashingService(pepper="test", pepper_version=2)
        assert service.current_pepper_version == 2

    def test_has_prior_pepper_false_by_default(self):
        """Test that prior pepper is not set by default."""
        service = FraudHashingService(pepper="test", pepper_version=1)
        assert service.has_prior_pepper == False

    def test_has_prior_pepper_when_configured(self):
        """Test that prior pepper is detected when configured."""
        service = FraudHashingService(
            pepper="current-pepper",
            pepper_version=2,
            prior_pepper="old-pepper",
            prior_pepper_version=1,
        )
        assert service.has_prior_pepper == True

    def test_active_pepper_versions_single(self):
        """Test active versions list with single pepper."""
        service = FraudHashingService(pepper="test", pepper_version=3)
        assert service.active_pepper_versions == [3]

    def test_active_pepper_versions_with_prior(self):
        """Test active versions list with prior pepper."""
        service = FraudHashingService(
            pepper="current",
            pepper_version=2,
            prior_pepper="prior",
            prior_pepper_version=1,
        )
        versions = service.active_pepper_versions
        assert 2 in versions
        assert 1 in versions
        assert len(versions) == 2

    def test_generate_indicators_for_matching_single_version(self):
        """Test indicator generation for matching with single pepper."""
        service = FraudHashingService(pepper="test", pepper_version=1)

        result = service.generate_indicators_for_matching(
            routing_number="021000021",
            payee_name="ACME Corp",
        )

        assert 1 in result
        assert "routing_hash" in result[1]
        assert "payee_hash" in result[1]

    def test_generate_indicators_for_matching_multi_version(self):
        """Test indicator generation for matching with prior pepper."""
        service = FraudHashingService(
            pepper="new-pepper",
            pepper_version=2,
            prior_pepper="old-pepper",
            prior_pepper_version=1,
        )

        result = service.generate_indicators_for_matching(
            routing_number="021000021",
            payee_name="ACME Corp",
        )

        # Should have indicators for both versions
        assert 1 in result
        assert 2 in result

        # Hashes should be different for different peppers
        assert result[1]["routing_hash"] != result[2]["routing_hash"]

    def test_different_pepper_produces_different_hash(self):
        """Test that different peppers produce different hashes."""
        service1 = FraudHashingService(pepper="pepper-v1", pepper_version=1)
        service2 = FraudHashingService(pepper="pepper-v2", pepper_version=2)

        hash1 = service1.hash_routing_number("021000021")
        hash2 = service2.hash_routing_number("021000021")

        assert hash1 != hash2


class TestCrossTenantIsolation:
    """
    Comprehensive tests for cross-tenant isolation.

    These tests verify that tenant A cannot access tenant B's data.
    """

    def test_fraud_event_query_requires_tenant_filter(self):
        """Verify get_fraud_event uses tenant_id in WHERE clause."""
        import ast
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService.get_fraud_event)

        # Parse as AST and look for comparison with tenant_id
        assert "tenant_id == tenant_id" in source or "FraudEvent.tenant_id ==" in source, \
            "get_fraud_event must filter by tenant_id"

    def test_list_fraud_events_query_requires_tenant_filter(self):
        """Verify list_fraud_events uses tenant_id in WHERE clause."""
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService.list_fraud_events)

        assert "FraudEvent.tenant_id ==" in source or "tenant_id ==" in source, \
            "list_fraud_events must filter by tenant_id"

    def test_dismiss_alert_query_requires_tenant_filter(self):
        """Verify dismiss_alert uses tenant_id in WHERE clause."""
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService.dismiss_alert)

        assert "NetworkMatchAlert.tenant_id ==" in source, \
            "dismiss_alert must filter by tenant_id"

    def test_matching_excludes_same_tenant_artifacts(self):
        """Verify _find_matching_artifacts excludes own tenant."""
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService._find_matching_artifacts)

        # Must have tenant_id != tenant_id filter
        assert "tenant_id != tenant_id" in source or "tenant_id!=" in source, \
            "_find_matching_artifacts must exclude same tenant"

    def test_matching_only_uses_network_match_level(self):
        """Verify matching only uses sharing_level=2 (NETWORK_MATCH)."""
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService._find_matching_artifacts)

        assert "NETWORK_MATCH" in source or "sharing_level ==" in source, \
            "_find_matching_artifacts must filter by sharing_level"


class TestMatchingAcrossTenants:
    """
    Tests for cross-tenant matching behavior.

    Simulates matching behavior with mock data structures.
    """

    def test_severity_high_with_multiple_indicator_types(self):
        """Test HIGH severity when 2+ indicator types match."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import MatchSeverity

        class MockSession:
            pass

        service = FraudService(MockSession())

        # 2 artifacts matching 2 different indicator types = HIGH
        severity = service._compute_severity(
            artifacts=["artifact-1", "artifact-2"],
            match_reasons={
                "routing_hash": {"count": 1},
                "payee_hash": {"count": 1},
            }
        )
        assert severity == MatchSeverity.HIGH

    def test_severity_high_with_many_artifacts(self):
        """Test HIGH severity when 3+ artifacts match on 1 indicator."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import MatchSeverity

        class MockSession:
            pass

        service = FraudService(MockSession())

        # 3 artifacts on 1 indicator type = HIGH
        severity = service._compute_severity(
            artifacts=["a1", "a2", "a3"],
            match_reasons={"routing_hash": {"count": 3}}
        )
        assert severity == MatchSeverity.HIGH

    def test_severity_medium_with_two_artifacts(self):
        """Test MEDIUM severity when 2 artifacts match on 1 indicator."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import MatchSeverity

        class MockSession:
            pass

        service = FraudService(MockSession())

        # 2 artifacts on 1 indicator type = MEDIUM
        severity = service._compute_severity(
            artifacts=["a1", "a2"],
            match_reasons={"routing_hash": {"count": 2}}
        )
        assert severity == MatchSeverity.MEDIUM

    def test_severity_low_with_one_artifact(self):
        """Test LOW severity when only 1 artifact matches."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import MatchSeverity

        class MockSession:
            pass

        service = FraudService(MockSession())

        # 1 artifact = LOW
        severity = service._compute_severity(
            artifacts=["a1"],
            match_reasons={"routing_hash": {"count": 1}}
        )
        assert severity == MatchSeverity.LOW

    def test_withdrawal_deactivates_artifact_code_review(self):
        """Verify withdrawal sets is_active=False on artifact."""
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService.withdraw_fraud_event)

        # Must set is_active = False
        assert "is_active = False" in source or "is_active=False" in source, \
            "withdraw_fraud_event must deactivate shared_artifact"

    def test_matching_filters_by_is_active(self):
        """Verify matching only considers active artifacts."""
        import inspect
        from app.services.fraud_service import FraudService

        source = inspect.getsource(FraudService._find_matching_artifacts)

        # Must filter by is_active == True
        assert "is_active == True" in source or "is_active=True" in source, \
            "_find_matching_artifacts must filter by is_active"


class TestPrivacySuppressionBackend:
    """
    Tests for privacy threshold suppression in backend.

    Verifies that counts below threshold are NEVER returned as raw values.
    """

    def test_suppression_uses_less_than_format(self):
        """Test that suppressed values use '<N' format, never raw numbers."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import FraudType

        class MockSession:
            pass

        service = FraudService(MockSession())

        class MockRow:
            def __init__(self, fraud_type, count):
                self.fraud_type = fraud_type
                self.count = count

        # Test with count = 1 (below threshold of 3)
        your_data = [MockRow(FraudType.CHECK_KITING, 1)]
        network_data = []

        result = service._aggregate_by_field(
            your_data, network_data, "fraud_type", threshold=3
        )

        entry = next(r for r in result if r["fraud_type"] == "check_kiting")

        # Display should be "<3", not "1"
        assert entry["your_bank_display"] == "<3"
        assert entry["your_bank_display"] != "1"

    def test_suppression_applies_to_count_of_2(self):
        """Test suppression applies to count of 2 when threshold is 3."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import FraudType

        class MockSession:
            pass

        service = FraudService(MockSession())

        class MockRow:
            def __init__(self, fraud_type, count):
                self.fraud_type = fraud_type
                self.count = count

        # Test with count = 2 (below threshold of 3)
        your_data = [MockRow(FraudType.FORGED_SIGNATURE, 2)]
        network_data = []

        result = service._aggregate_by_field(
            your_data, network_data, "fraud_type", threshold=3
        )

        entry = next(r for r in result if r["fraud_type"] == "forged_signature")

        # Display should be "<3", not "2"
        assert entry["your_bank_display"] == "<3"
        assert entry["your_bank_display"] != "2"

    def test_suppression_not_applied_to_count_at_threshold(self):
        """Test that counts AT threshold are shown."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import FraudType

        class MockSession:
            pass

        service = FraudService(MockSession())

        class MockRow:
            def __init__(self, fraud_type, count):
                self.fraud_type = fraud_type
                self.count = count

        # Test with count = 3 (at threshold of 3)
        your_data = [MockRow(FraudType.ALTERED_CHECK, 3)]
        network_data = []

        result = service._aggregate_by_field(
            your_data, network_data, "fraud_type", threshold=3
        )

        entry = next(r for r in result if r["fraud_type"] == "altered_check")

        # Display should be "3", not suppressed
        assert entry["your_bank_display"] == "3"

    def test_suppression_applies_to_network_data_too(self):
        """Test that network data is also suppressed below threshold."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import FraudType

        class MockSession:
            pass

        service = FraudService(MockSession())

        class MockRow:
            def __init__(self, fraud_type, count):
                self.fraud_type = fraud_type
                self.count = count

        # Test network data with count = 1
        your_data = []
        network_data = [MockRow(FraudType.DUPLICATE_DEPOSIT, 1)]

        result = service._aggregate_by_field(
            your_data, network_data, "fraud_type", threshold=3
        )

        entry = next(r for r in result if r["fraud_type"] == "duplicate_deposit")

        # Network display should also be suppressed
        assert entry["network_display"] == "<3"

    def test_suppression_applies_to_all_field_types(self):
        """Test that suppression works for channel aggregation too."""
        from app.services.fraud_service import FraudService
        from app.models.fraud import FraudChannel

        class MockSession:
            pass

        service = FraudService(MockSession())

        class MockRow:
            def __init__(self, channel, count):
                self.channel = channel
                self.count = count

        your_data = [MockRow(FraudChannel.MOBILE, 1)]
        network_data = [MockRow(FraudChannel.MOBILE, 10)]

        result = service._aggregate_by_field(
            your_data, network_data, "channel", threshold=3
        )

        entry = next(r for r in result if r["channel"] == "mobile")

        # Your bank suppressed, network shown
        assert entry["your_bank_display"] == "<3"
        assert entry["network_display"] == "10"


class TestArtifactNeverReturnedDirectly:
    """Tests that FraudSharedArtifact is never returned to clients."""

    def test_alert_response_does_not_include_artifact_ids(self):
        """Verify NetworkAlertResponse schema doesn't expose artifact IDs."""
        from app.schemas.fraud import NetworkAlertResponse

        # Get the schema fields
        fields = NetworkAlertResponse.model_fields.keys()

        # matched_artifact_ids should NOT be in the response schema
        assert "matched_artifact_ids" not in fields, \
            "NetworkAlertResponse must not expose matched_artifact_ids"

    def test_alert_response_only_includes_safe_fields(self):
        """Verify NetworkAlertResponse only includes aggregated safe fields."""
        from app.schemas.fraud import NetworkAlertResponse

        allowed_fields = {
            "id", "check_item_id", "case_id", "severity",
            "total_matches", "distinct_institutions",
            "earliest_match_date", "latest_match_date",
            "match_reasons", "created_at", "last_checked_at",
            "is_dismissed", "dismissed_at", "dismissed_reason"
        }

        actual_fields = set(NetworkAlertResponse.model_fields.keys())

        # No unexpected fields
        unexpected = actual_fields - allowed_fields
        assert not unexpected, f"Unexpected fields in NetworkAlertResponse: {unexpected}"


# To run tests:
# cd /home/user/Check/backend
# source venv/bin/activate
# pytest tests/test_fraud_module.py -v
