"""
Unit tests for evidence snapshot sealing.
"""

from datetime import datetime, timezone

import pytest
from app.services.evidence_seal import (
    SEAL_VERSION,
    _canonical_json,
    compute_evidence_hash,
    seal_evidence_snapshot,
    verify_evidence_hash,
)


class TestCanonicalJson:
    """Tests for canonical JSON serialization."""

    def test_sorted_keys(self):
        """Test that keys are sorted for deterministic output."""
        data = {"z": 1, "a": 2, "m": 3}
        result = _canonical_json(data)
        assert result == '{"a":2,"m":3,"z":1}'

    def test_no_whitespace(self):
        """Test that no whitespace is added."""
        data = {"key": "value", "nested": {"inner": "data"}}
        result = _canonical_json(data)
        assert " " not in result
        assert "\n" not in result

    def test_datetime_serialization(self):
        """Test that datetimes are ISO formatted."""
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = {"timestamp": dt}
        result = _canonical_json(data)
        assert "2026-01-15T12:00:00+00:00" in result

    def test_nested_sorting(self):
        """Test that nested dicts have sorted keys."""
        data = {"outer": {"z": 1, "a": 2}}
        result = _canonical_json(data)
        # The inner dict should also have sorted keys
        assert '"outer":{"a":2,"z":1}' in result

    def test_list_order_preserved(self):
        """Test that list order is preserved."""
        data = {"items": [3, 1, 2]}
        result = _canonical_json(data)
        assert '"items":[3,1,2]' in result


class TestComputeEvidenceHash:
    """Tests for evidence hash computation."""

    def test_deterministic_hash(self):
        """Test that same content produces same hash."""
        snapshot = {
            "snapshot_version": "1.0",
            "captured_at": "2026-01-15T12:00:00+00:00",
            "check_context": {"amount": "1000.00"},
        }

        hash1 = compute_evidence_hash(snapshot)
        hash2 = compute_evidence_hash(snapshot)

        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Test that different content produces different hash."""
        snapshot1 = {
            "snapshot_version": "1.0",
            "captured_at": "2026-01-15T12:00:00+00:00",
            "check_context": {"amount": "1000.00"},
        }
        snapshot2 = {
            "snapshot_version": "1.0",
            "captured_at": "2026-01-15T12:00:00+00:00",
            "check_context": {"amount": "2000.00"},  # Different amount
        }

        hash1 = compute_evidence_hash(snapshot1)
        hash2 = compute_evidence_hash(snapshot2)

        assert hash1 != hash2

    def test_seal_fields_excluded(self):
        """Test that seal fields are excluded from hash."""
        snapshot = {
            "snapshot_version": "1.0",
            "captured_at": "2026-01-15T12:00:00+00:00",
            "check_context": {"amount": "1000.00"},
        }

        # Add seal fields
        snapshot_with_seal = dict(snapshot)
        snapshot_with_seal["evidence_hash"] = "some_hash"
        snapshot_with_seal["seal_version"] = "sha256-v1"
        snapshot_with_seal["seal_timestamp"] = "2026-01-15T12:00:00+00:00"

        # Hash should be the same (seal fields excluded)
        hash1 = compute_evidence_hash(snapshot)
        hash2 = compute_evidence_hash(snapshot_with_seal)

        assert hash1 == hash2

    def test_hash_length(self):
        """Test that hash is SHA-256 hex (64 chars)."""
        snapshot = {"check_context": {"amount": "1000.00"}}
        hash_value = compute_evidence_hash(snapshot)
        assert len(hash_value) == 64


class TestVerifyEvidenceHash:
    """Tests for evidence hash verification."""

    def test_valid_hash(self):
        """Test verification of valid hash."""
        snapshot = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }
        snapshot["evidence_hash"] = compute_evidence_hash(snapshot)

        is_valid, error = verify_evidence_hash(snapshot)

        assert is_valid
        assert error is None

    def test_missing_hash(self):
        """Test verification fails for unsealed snapshot."""
        snapshot = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }

        is_valid, error = verify_evidence_hash(snapshot)

        assert not is_valid
        assert "not sealed" in error.lower()

    def test_tampered_content(self):
        """Test verification fails for tampered content."""
        snapshot = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }
        snapshot["evidence_hash"] = compute_evidence_hash(snapshot)

        # Tamper with content
        snapshot["check_context"]["amount"] = "9999.99"

        is_valid, error = verify_evidence_hash(snapshot)

        assert not is_valid
        assert "mismatch" in error.lower()


class TestSealEvidenceSnapshot:
    """Tests for evidence snapshot sealing."""

    def test_seal_adds_required_fields(self):
        """Test that sealing adds all required fields."""
        snapshot = {
            "snapshot_version": "1.0",
            "captured_at": "2026-01-15T12:00:00+00:00",
            "check_context": {"amount": "1000.00"},
        }

        sealed = seal_evidence_snapshot(snapshot)

        assert "seal_version" in sealed
        assert sealed["seal_version"] == SEAL_VERSION
        assert "evidence_hash" in sealed
        assert len(sealed["evidence_hash"]) == 64
        assert "seal_timestamp" in sealed
        assert "previous_evidence_hash" in sealed

    def test_seal_with_previous_hash(self):
        """Test sealing with hash chain."""
        snapshot = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }
        previous_hash = "abc123" * 10 + "abcd"  # 64 char fake hash

        sealed = seal_evidence_snapshot(snapshot, previous_evidence_hash=previous_hash)

        assert sealed["previous_evidence_hash"] == previous_hash

    def test_seal_without_previous_hash(self):
        """Test sealing first decision (no previous)."""
        snapshot = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }

        sealed = seal_evidence_snapshot(snapshot, previous_evidence_hash=None)

        assert sealed["previous_evidence_hash"] is None

    def test_sealed_snapshot_verifies(self):
        """Test that sealed snapshot passes verification."""
        snapshot = {
            "snapshot_version": "1.0",
            "captured_at": "2026-01-15T12:00:00+00:00",
            "check_context": {"amount": "1000.00"},
        }

        sealed = seal_evidence_snapshot(snapshot)
        is_valid, error = verify_evidence_hash(sealed)

        assert is_valid
        assert error is None

    def test_does_not_mutate_input(self):
        """Test that sealing doesn't mutate original dict."""
        snapshot = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }
        original_keys = set(snapshot.keys())

        seal_evidence_snapshot(snapshot)

        assert set(snapshot.keys()) == original_keys


class TestHashChainIntegrity:
    """Tests for hash chain integrity."""

    def test_chain_of_two(self):
        """Test hash chain with two decisions."""
        # First decision
        snapshot1 = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
        }
        sealed1 = seal_evidence_snapshot(snapshot1, previous_evidence_hash=None)

        # Second decision chains to first
        snapshot2 = {
            "snapshot_version": "1.0",
            "check_context": {"amount": "1000.00"},
            "decision_context": {"action": "approve"},
        }
        sealed2 = seal_evidence_snapshot(snapshot2, previous_evidence_hash=sealed1["evidence_hash"])

        # Verify chain
        assert sealed1["previous_evidence_hash"] is None
        assert sealed2["previous_evidence_hash"] == sealed1["evidence_hash"]

        # Both should verify independently
        assert verify_evidence_hash(sealed1)[0]
        assert verify_evidence_hash(sealed2)[0]

    def test_broken_chain_detected(self):
        """Test that a broken chain can be detected."""
        # Simulate a correct chain
        snapshot1 = {"check_context": {"amount": "1000.00"}}
        sealed1 = seal_evidence_snapshot(snapshot1, previous_evidence_hash=None)

        snapshot2 = {"check_context": {"amount": "1000.00"}}
        sealed2 = seal_evidence_snapshot(snapshot2, previous_evidence_hash=sealed1["evidence_hash"])

        # Verify the chain is intact
        assert sealed2["previous_evidence_hash"] == sealed1["evidence_hash"]

        # Simulate tampering with sealed1 after the fact (would break chain in a real audit)
        # If someone modified sealed1's content but not its hash, verify would catch it
        sealed1_tampered = dict(sealed1)
        sealed1_tampered["check_context"]["amount"] = "9999.99"

        is_valid, error = verify_evidence_hash(sealed1_tampered)
        assert not is_valid
