"""
Fraud Indicator Hashing Service.

This module provides privacy-preserving hashing for fraud indicators
using HMAC-SHA256 with a network-wide pepper (server-side secret).

Security Notes:
- The NETWORK_PEPPER must be kept secret and rotated carefully
- All hashing is deterministic to allow cross-tenant matching
- Raw indicator values are never stored in shared artifacts
- Normalization is critical for consistent matching

Pepper Rotation:
- New artifacts are always created with the current pepper version
- Matching can check against both current and prior pepper versions
- During rotation, set NETWORK_PEPPER_PRIOR and NETWORK_PEPPER_PRIOR_VERSION
- After rotation window (e.g., 30 days), clear prior pepper settings
"""

import hashlib
import hmac
import os
import re
import unicodedata
from typing import Any

from app.core.config import settings


class FraudHashingService:
    """
    Service for hashing fraud indicators for network sharing.

    Uses HMAC-SHA256 with a network pepper for deterministic,
    privacy-preserving indicator hashing.

    Supports pepper rotation:
    - New artifacts are always created with current pepper
    - Matching checks against both current and prior pepper versions
    - Prior pepper can be configured for rotation windows
    """

    def __init__(
        self,
        pepper: str | None = None,
        pepper_version: int | None = None,
        prior_pepper: str | None = None,
        prior_pepper_version: int | None = None,
    ):
        """
        Initialize the hashing service.

        Args:
            pepper: Optional override for network pepper (mainly for testing)
            pepper_version: Optional override for current pepper version
            prior_pepper: Optional override for prior pepper (for rotation)
            prior_pepper_version: Optional override for prior pepper version
        """
        self._pepper = pepper or self._get_network_pepper()
        self._pepper_version = pepper_version if pepper_version is not None else self._get_pepper_version()
        self._prior_pepper = prior_pepper if prior_pepper is not None else self._get_prior_pepper()
        self._prior_pepper_version = prior_pepper_version if prior_pepper_version is not None else self._get_prior_pepper_version()

    def _get_network_pepper(self) -> str:
        """Get the network pepper from settings or environment."""
        pepper = getattr(settings, "NETWORK_PEPPER", None)
        if not pepper:
            pepper = os.environ.get("NETWORK_PEPPER")
        if not pepper:
            # Development fallback - NEVER use in production
            pepper = "dev-pepper-not-for-production-use"
        return pepper

    def _get_pepper_version(self) -> int:
        """Get the current pepper version from settings."""
        return getattr(settings, "NETWORK_PEPPER_VERSION", 1)

    def _get_prior_pepper(self) -> str:
        """Get the prior pepper from settings (empty string if not set)."""
        return getattr(settings, "NETWORK_PEPPER_PRIOR", "")

    def _get_prior_pepper_version(self) -> int:
        """Get the prior pepper version from settings (0 if no prior)."""
        return getattr(settings, "NETWORK_PEPPER_PRIOR_VERSION", 0)

    @property
    def current_pepper_version(self) -> int:
        """Get the current pepper version."""
        return self._pepper_version

    @property
    def has_prior_pepper(self) -> bool:
        """Check if a prior pepper is configured for rotation."""
        return bool(self._prior_pepper) and self._prior_pepper_version > 0

    @property
    def active_pepper_versions(self) -> list[int]:
        """Get list of active pepper versions (current + prior if set)."""
        versions = [self._pepper_version]
        if self.has_prior_pepper:
            versions.append(self._prior_pepper_version)
        return versions

    def _hmac_hash(self, value: str, pepper: str | None = None) -> str:
        """
        Compute HMAC-SHA256 hash of a value.

        Args:
            value: The normalized value to hash
            pepper: Optional pepper override (uses current if not specified)

        Returns:
            Hex digest of the HMAC-SHA256 hash
        """
        use_pepper = pepper or self._pepper
        return hmac.new(
            use_pepper.encode("utf-8"),
            value.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _hmac_hash_with_prior(self, value: str) -> str | None:
        """
        Compute HMAC-SHA256 hash using the prior pepper.

        Args:
            value: The normalized value to hash

        Returns:
            Hex digest or None if no prior pepper configured
        """
        if not self.has_prior_pepper:
            return None
        return self._hmac_hash(value, self._prior_pepper)

    # ========================================================================
    # Normalization Methods
    # ========================================================================

    def normalize_routing_number(self, routing: str | None) -> str | None:
        """
        Normalize a routing number for hashing.

        - Removes all non-digit characters
        - Validates length (9 digits for US routing numbers)

        Args:
            routing: Raw routing number

        Returns:
            Normalized routing number or None if invalid
        """
        if not routing:
            return None

        # Extract digits only
        digits = re.sub(r"\D", "", routing)

        # US routing numbers are 9 digits
        if len(digits) != 9:
            return None

        return digits

    def normalize_payee_name(self, payee: str | None) -> str | None:
        """
        Normalize a payee name for hashing.

        - Convert to uppercase
        - Remove accents/diacritics
        - Collapse whitespace
        - Remove common punctuation
        - Remove common business suffixes (LLC, INC, etc.)

        Args:
            payee: Raw payee name

        Returns:
            Normalized payee name or None if empty
        """
        if not payee:
            return None

        # Convert to uppercase
        normalized = payee.upper()

        # Remove accents/diacritics
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))

        # Remove common punctuation
        normalized = re.sub(r"[.,;:'\"!?()[\]{}<>@#$%^&*+=|\\/_-]", " ", normalized)

        # Remove common business suffixes
        suffixes = [
            r"\bLLC\b", r"\bINC\b", r"\bCORP\b", r"\bCO\b",
            r"\bLTD\b", r"\bLP\b", r"\bLLP\b", r"\bPC\b",
            r"\bPLC\b", r"\bDBA\b", r"\bAKA\b"
        ]
        for suffix in suffixes:
            normalized = re.sub(suffix, "", normalized)

        # Collapse whitespace
        normalized = " ".join(normalized.split())

        # Remove leading/trailing whitespace
        normalized = normalized.strip()

        if not normalized:
            return None

        return normalized

    def normalize_account_number(self, account: str | None) -> str | None:
        """
        Normalize an account number for hashing.

        NOTE: Account number hashing is disabled by default due to
        privacy concerns. Only enabled if tenant config allows.

        - Removes all non-digit characters
        - Only uses last 4 digits + length prefix for privacy

        Args:
            account: Raw account number

        Returns:
            Normalized partial account identifier or None
        """
        if not account:
            return None

        # Extract digits only
        digits = re.sub(r"\D", "", account)

        if len(digits) < 4:
            return None

        # Use length prefix + last 4 for partial matching
        # This reduces uniqueness while still allowing some matching
        return f"L{len(digits)}-{digits[-4:]}"

    def normalize_check_number(self, check_num: str | None) -> str | None:
        """
        Normalize a check number.

        - Removes leading zeros
        - Removes non-digit characters

        Args:
            check_num: Raw check number

        Returns:
            Normalized check number or None
        """
        if not check_num:
            return None

        # Extract digits only
        digits = re.sub(r"\D", "", check_num)

        if not digits:
            return None

        # Remove leading zeros
        return digits.lstrip("0") or "0"

    # ========================================================================
    # Hashing Methods
    # ========================================================================

    def hash_routing_number(self, routing: str | None, pepper: str | None = None) -> str | None:
        """
        Hash a routing number.

        Args:
            routing: Raw routing number
            pepper: Optional pepper override

        Returns:
            HMAC hash of normalized routing number or None
        """
        normalized = self.normalize_routing_number(routing)
        if not normalized:
            return None
        return self._hmac_hash(f"routing:{normalized}", pepper)

    def hash_payee_name(self, payee: str | None, pepper: str | None = None) -> str | None:
        """
        Hash a payee name.

        Args:
            payee: Raw payee name
            pepper: Optional pepper override

        Returns:
            HMAC hash of normalized payee name or None
        """
        normalized = self.normalize_payee_name(payee)
        if not normalized:
            return None
        return self._hmac_hash(f"payee:{normalized}", pepper)

    def hash_account_indicator(self, account: str | None, pepper: str | None = None) -> str | None:
        """
        Hash an account indicator (partial, privacy-preserving).

        Args:
            account: Raw account number
            pepper: Optional pepper override

        Returns:
            HMAC hash of partial account indicator or None
        """
        normalized = self.normalize_account_number(account)
        if not normalized:
            return None
        return self._hmac_hash(f"account:{normalized}", pepper)

    def compute_check_fingerprint(
        self,
        routing: str | None,
        check_number: str | None,
        amount_bucket: str,
        date_bucket: str,  # YYYY-MM format
        pepper: str | None = None,
    ) -> str | None:
        """
        Compute a check fingerprint from available non-PII fields.

        This creates a composite fingerprint that can match similar
        checks without exposing individual field values.

        Args:
            routing: Routing number
            check_number: Check number
            amount_bucket: Amount bucket (e.g., "1000_to_5000")
            date_bucket: Date bucket in YYYY-MM format
            pepper: Optional pepper override

        Returns:
            HMAC hash of composite fingerprint or None
        """
        normalized_routing = self.normalize_routing_number(routing)
        normalized_check = self.normalize_check_number(check_number)

        # At minimum need routing number for fingerprint
        if not normalized_routing:
            return None

        # Build composite fingerprint
        components = [
            f"routing:{normalized_routing}",
            f"amount:{amount_bucket}",
            f"date:{date_bucket}",
        ]

        # Include check number if available
        if normalized_check:
            components.append(f"check:{normalized_check}")

        fingerprint = "|".join(sorted(components))
        return self._hmac_hash(f"fingerprint:{fingerprint}", pepper)

    def generate_indicators(
        self,
        routing_number: str | None = None,
        payee_name: str | None = None,
        check_number: str | None = None,
        amount_bucket: str | None = None,
        date_bucket: str | None = None,
        account_number: str | None = None,
        include_account: bool = False,
    ) -> dict[str, str | None]:
        """
        Generate all applicable hashed indicators for a check using current pepper.

        Args:
            routing_number: Check routing number
            payee_name: Payee name
            check_number: Check number
            amount_bucket: Amount bucket for fingerprint
            date_bucket: Date bucket (YYYY-MM) for fingerprint
            account_number: Account number (only used if include_account=True)
            include_account: Whether to include account indicator

        Returns:
            Dictionary of indicator type to hash value
        """
        indicators = {
            "routing_hash": self.hash_routing_number(routing_number),
            "payee_hash": self.hash_payee_name(payee_name),
        }

        # Compute fingerprint if we have enough data
        if routing_number and amount_bucket and date_bucket:
            indicators["check_fingerprint"] = self.compute_check_fingerprint(
                routing_number,
                check_number,
                amount_bucket,
                date_bucket,
            )
        else:
            indicators["check_fingerprint"] = None

        # Optionally include account indicator
        if include_account and account_number:
            indicators["account_hash"] = self.hash_account_indicator(account_number)

        # Also hash MICR routing if different from check routing
        indicators["micr_routing_hash"] = self.hash_routing_number(routing_number)

        # Filter out None values for cleaner storage
        return {k: v for k, v in indicators.items() if v is not None}

    def generate_indicators_for_matching(
        self,
        routing_number: str | None = None,
        payee_name: str | None = None,
        check_number: str | None = None,
        amount_bucket: str | None = None,
        date_bucket: str | None = None,
        account_number: str | None = None,
        include_account: bool = False,
    ) -> dict[int, dict[str, str]]:
        """
        Generate hashed indicators for BOTH current and prior pepper versions.

        Used when checking for matches against network artifacts that may
        have been created with different pepper versions during rotation.

        Args:
            routing_number: Check routing number
            payee_name: Payee name
            check_number: Check number
            amount_bucket: Amount bucket for fingerprint
            date_bucket: Date bucket (YYYY-MM) for fingerprint
            account_number: Account number (only used if include_account=True)
            include_account: Whether to include account indicator

        Returns:
            Dictionary mapping pepper_version -> indicators dict
        """
        result = {}

        # Generate with current pepper
        result[self._pepper_version] = self._generate_indicators_with_pepper(
            self._pepper,
            routing_number, payee_name, check_number,
            amount_bucket, date_bucket, account_number, include_account
        )

        # Generate with prior pepper if configured
        if self.has_prior_pepper:
            result[self._prior_pepper_version] = self._generate_indicators_with_pepper(
                self._prior_pepper,
                routing_number, payee_name, check_number,
                amount_bucket, date_bucket, account_number, include_account
            )

        return result

    def _generate_indicators_with_pepper(
        self,
        pepper: str,
        routing_number: str | None,
        payee_name: str | None,
        check_number: str | None,
        amount_bucket: str | None,
        date_bucket: str | None,
        account_number: str | None,
        include_account: bool,
    ) -> dict[str, str]:
        """Generate indicators with a specific pepper."""
        indicators = {
            "routing_hash": self.hash_routing_number(routing_number, pepper),
            "payee_hash": self.hash_payee_name(payee_name, pepper),
        }

        if routing_number and amount_bucket and date_bucket:
            indicators["check_fingerprint"] = self.compute_check_fingerprint(
                routing_number, check_number, amount_bucket, date_bucket, pepper
            )

        if include_account and account_number:
            indicators["account_hash"] = self.hash_account_indicator(account_number, pepper)

        return {k: v for k, v in indicators.items() if v is not None}


# Singleton instance
_hashing_service: FraudHashingService | None = None


def get_hashing_service() -> FraudHashingService:
    """Get the singleton hashing service instance."""
    global _hashing_service
    if _hashing_service is None:
        _hashing_service = FraudHashingService()
    return _hashing_service


def reset_hashing_service() -> None:
    """Reset the singleton (for testing or config reload)."""
    global _hashing_service
    _hashing_service = None
