"""
PII (Personally Identifiable Information) Detection Service.

This module provides pattern-based detection of potential PII in text
to prevent accidental sharing of sensitive information in narratives.

Note: This is a best-effort detection system and should not be relied
upon as the sole safeguard. Users should always be trained to avoid
including PII in shareable fields.
"""

import re
from dataclasses import dataclass


@dataclass
class PIIMatch:
    """A potential PII match found in text."""

    pattern_type: str
    matched_text: str
    start_position: int
    end_position: int
    confidence: str  # "high", "medium", "low"


class PIIDetectionService:
    """
    Service for detecting potential PII in text.

    Checks for common patterns like:
    - Account numbers
    - Routing numbers
    - Social Security Numbers (SSN)
    - Phone numbers
    - Email addresses
    - Credit card numbers
    - Date of birth patterns
    - Street addresses
    """

    # Pattern definitions with confidence levels
    PATTERNS = [
        # High confidence patterns
        {
            "name": "ssn",
            "pattern": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
            "description": "Social Security Number",
            "confidence": "high",
        },
        {
            "name": "email",
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "description": "Email address",
            "confidence": "high",
        },
        {
            "name": "credit_card",
            "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "description": "Credit card number",
            "confidence": "high",
        },
        {
            "name": "routing_number",
            "pattern": r"\b\d{9}\b",
            "description": "Possible routing/account number (9 digits)",
            "confidence": "medium",
        },
        # Medium confidence patterns
        {
            "name": "phone_us",
            "pattern": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "description": "US phone number",
            "confidence": "medium",
        },
        {
            "name": "account_number",
            "pattern": r"\b\d{10,17}\b",
            "description": "Possible account number (10-17 digits)",
            "confidence": "medium",
        },
        {
            "name": "dob_pattern",
            "pattern": r"\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b",
            "description": "Date of birth pattern (MM/DD/YYYY)",
            "confidence": "medium",
        },
        # Low confidence patterns (common but may have false positives)
        {
            "name": "zip_code",
            "pattern": r"\b\d{5}(?:-\d{4})?\b",
            "description": "ZIP code",
            "confidence": "low",
        },
        {
            "name": "street_address",
            "pattern": r"\b\d+\s+(?:[A-Za-z]+\s+){1,4}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)\.?\b",
            "description": "Street address",
            "confidence": "low",
        },
        {
            "name": "name_with_title",
            "pattern": r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b",
            "description": "Name with title",
            "confidence": "low",
        },
    ]

    # Keywords that might indicate PII
    PII_KEYWORDS = [
        "account number",
        "acct num",
        "routing number",
        "social security",
        "ssn",
        "date of birth",
        "dob",
        "driver license",
        "dl#",
        "passport",
        "phone number",
        "cell phone",
        "home address",
        "mailing address",
        "email address",
        "credit card",
        "debit card",
        "pin number",
        "mother's maiden",
        "maiden name",
    ]

    def __init__(self, strict: bool = False):
        """
        Initialize the PII detection service.

        Args:
            strict: If True, also flag low-confidence matches
        """
        self.strict = strict
        self._compiled_patterns = [
            {
                **p,
                "regex": re.compile(p["pattern"], re.IGNORECASE)
            }
            for p in self.PATTERNS
        ]
        self._keyword_pattern = re.compile(
            r"\b(" + "|".join(re.escape(kw) for kw in self.PII_KEYWORDS) + r")\b",
            re.IGNORECASE
        )

    def detect(self, text: str) -> list[PIIMatch]:
        """
        Detect potential PII in text.

        Args:
            text: The text to analyze

        Returns:
            List of PIIMatch objects for each potential match
        """
        if not text:
            return []

        matches = []

        # Check patterns
        for pattern_def in self._compiled_patterns:
            # Skip low confidence patterns unless strict mode
            if pattern_def["confidence"] == "low" and not self.strict:
                continue

            for match in pattern_def["regex"].finditer(text):
                matches.append(PIIMatch(
                    pattern_type=pattern_def["name"],
                    matched_text=match.group(),
                    start_position=match.start(),
                    end_position=match.end(),
                    confidence=pattern_def["confidence"],
                ))

        # Check for PII keywords
        for match in self._keyword_pattern.finditer(text):
            matches.append(PIIMatch(
                pattern_type="pii_keyword",
                matched_text=match.group(),
                start_position=match.start(),
                end_position=match.end(),
                confidence="medium",
            ))

        return matches

    def has_pii(self, text: str) -> bool:
        """
        Quick check if text contains potential PII.

        Args:
            text: The text to analyze

        Returns:
            True if any potential PII detected
        """
        return len(self.detect(text)) > 0

    def get_warnings(self, text: str) -> list[str]:
        """
        Get human-readable warnings for detected PII.

        Args:
            text: The text to analyze

        Returns:
            List of warning messages
        """
        matches = self.detect(text)
        if not matches:
            return []

        warnings = []
        detected_types = set()

        for match in matches:
            if match.pattern_type not in detected_types:
                detected_types.add(match.pattern_type)

                # Get description from pattern definition
                description = None
                for p in self.PATTERNS:
                    if p["name"] == match.pattern_type:
                        description = p["description"]
                        break

                if description:
                    warnings.append(
                        f"Potential {description} detected "
                        f"({match.confidence} confidence)"
                    )
                elif match.pattern_type == "pii_keyword":
                    warnings.append(
                        f"PII keyword '{match.matched_text}' detected"
                    )

        return warnings

    def redact(self, text: str, replacement: str = "[REDACTED]") -> str:
        """
        Redact potential PII from text.

        Args:
            text: The text to redact
            replacement: The replacement string for PII

        Returns:
            Text with PII replaced
        """
        if not text:
            return text

        matches = self.detect(text)
        if not matches:
            return text

        # Sort matches by position (descending) to replace from end to start
        matches.sort(key=lambda m: m.start_position, reverse=True)

        result = text
        for match in matches:
            result = (
                result[:match.start_position] +
                replacement +
                result[match.end_position:]
            )

        return result

    def analyze(self, text: str) -> dict:
        """
        Full analysis of text for PII.

        Args:
            text: The text to analyze

        Returns:
            Dictionary with analysis results
        """
        matches = self.detect(text)

        return {
            "has_potential_pii": len(matches) > 0,
            "match_count": len(matches),
            "high_confidence_count": sum(1 for m in matches if m.confidence == "high"),
            "medium_confidence_count": sum(1 for m in matches if m.confidence == "medium"),
            "low_confidence_count": sum(1 for m in matches if m.confidence == "low"),
            "warnings": self.get_warnings(text),
            "detected_patterns": list(set(m.pattern_type for m in matches)),
            "matches": [
                {
                    "type": m.pattern_type,
                    "text": m.matched_text[:20] + "..." if len(m.matched_text) > 20 else m.matched_text,
                    "confidence": m.confidence,
                }
                for m in matches
            ]
        }


# Singleton instances
_default_service: PIIDetectionService | None = None
_strict_service: PIIDetectionService | None = None


def get_pii_detection_service(strict: bool = False) -> PIIDetectionService:
    """Get a PII detection service instance."""
    global _default_service, _strict_service

    if strict:
        if _strict_service is None:
            _strict_service = PIIDetectionService(strict=True)
        return _strict_service
    else:
        if _default_service is None:
            _default_service = PIIDetectionService(strict=False)
        return _default_service
