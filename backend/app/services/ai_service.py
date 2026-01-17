"""
AI Service with Bank-Grade Guardrails.

CRITICAL RULES FOR AI IN FINANCIAL DECISIONS:
1. AI output is ALWAYS advisory - never authoritative
2. AI can NEVER auto-advance workflow state
3. All AI output must be recorded with model, version, timestamp
4. Human acknowledgment is REQUIRED before any AI-influenced decision
5. Confidence scores must be surfaced to reviewers
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditService


class AIRecommendation(str, Enum):
    """
    AI recommendation types.

    IMPORTANT: These are ADVISORY ONLY. They do not map directly to actions.
    A human must always make the final decision.
    """

    LIKELY_LEGITIMATE = "likely_legitimate"  # Advisory: appears normal
    NEEDS_REVIEW = "needs_review"  # Advisory: warrants closer look
    HIGH_RISK = "high_risk"  # Advisory: significant risk indicators
    ANOMALY_DETECTED = "anomaly_detected"  # Advisory: unusual pattern
    INSUFFICIENT_DATA = "insufficient_data"  # Advisory: can't assess


@dataclass
class AIAnalysisResult:
    """
    AI analysis result - ALWAYS ADVISORY.

    This structure is intentionally designed to:
    - Never suggest a specific action (approve/reject)
    - Always include confidence levels
    - Always be timestamped and versioned
    - Require explicit acknowledgment
    """

    # Identification (REQUIRED for audit)
    model_id: str
    model_version: str
    analyzed_at: datetime

    # Advisory output
    recommendation: AIRecommendation
    confidence: float  # 0.0 to 1.0
    risk_score: Decimal  # 0.0000 to 1.0000

    # Explanation (for reviewer)
    risk_factors: list[dict[str, Any]]  # {"factor": "...", "weight": ..., "description": "..."}
    flags: list[str]  # Human-readable flags
    explanation: str  # Plain text explanation for reviewer

    # Advisory label (ALWAYS set)
    is_advisory: bool = True  # Cannot be False
    requires_human_review: bool = True  # Cannot be False

    # Confidence breakdown
    confidence_by_category: dict[str, float] | None = None

    def __post_init__(self):
        """Enforce advisory-only rules."""
        # These can NEVER be False - AI cannot be authoritative
        object.__setattr__(self, "is_advisory", True)
        object.__setattr__(self, "requires_human_review", True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "analyzed_at": self.analyzed_at.isoformat(),
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "risk_score": str(self.risk_score),
            "risk_factors": self.risk_factors,
            "flags": self.flags,
            "explanation": self.explanation,
            "is_advisory": True,  # Always True
            "requires_human_review": True,  # Always True
            "confidence_by_category": self.confidence_by_category,
        }


class AIService:
    """
    AI analysis service with bank-grade guardrails.

    GUARDRAILS ENFORCED:
    1. All outputs are marked as advisory
    2. Model ID and version are always recorded
    3. Timestamps are always recorded
    4. Results can never auto-advance workflow state
    5. Audit logging is mandatory
    """

    # Current model configuration
    # In production, this would come from config/environment
    MODEL_ID = "check-risk-analyzer"
    MODEL_VERSION = "1.0.0"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)

    async def analyze_check(
        self,
        check_item_id: str,
        amount: Decimal,
        account_tenure_days: int | None,
        avg_check_amount_30d: Decimal | None,
        avg_check_amount_90d: Decimal | None,
        returned_item_count_90d: int | None,
        exception_count_90d: int | None,
        current_balance: Decimal | None,
        risk_flags: list[str] | None,
        upstream_flags: list[str] | None,
        user_id: str | None = None,
        username: str | None = None,
    ) -> AIAnalysisResult:
        """
        Analyze a check item and return ADVISORY recommendation.

        IMPORTANT: This method NEVER modifies state. It returns an advisory
        recommendation that a human must review and acknowledge.

        Returns:
            AIAnalysisResult with advisory recommendation and confidence scores
        """
        import time
        start_time = time.monotonic()

        analyzed_at = datetime.now(timezone.utc)
        risk_factors: list[dict[str, Any]] = []
        flags: list[str] = []
        risk_score = Decimal("0.0000")

        # Risk factor: Amount anomaly
        if avg_check_amount_30d and avg_check_amount_30d > 0:
            amount_ratio = amount / avg_check_amount_30d
            if amount_ratio > Decimal("3.0"):
                risk_score += Decimal("0.2500")
                risk_factors.append({
                    "factor": "amount_anomaly",
                    "weight": 0.25,
                    "description": f"Amount is {amount_ratio:.1f}x the 30-day average",
                    "value": str(amount_ratio),
                })
                flags.append("Amount significantly above average")

        # Risk factor: New account
        if account_tenure_days is not None and account_tenure_days < 90:
            tenure_risk = Decimal("0.1500") if account_tenure_days < 30 else Decimal("0.0750")
            risk_score += tenure_risk
            risk_factors.append({
                "factor": "new_account",
                "weight": float(tenure_risk),
                "description": f"Account is only {account_tenure_days} days old",
                "value": account_tenure_days,
            })
            flags.append(f"New account ({account_tenure_days} days)")

        # Risk factor: Return history
        if returned_item_count_90d and returned_item_count_90d > 0:
            return_risk = min(Decimal("0.3000"), Decimal(str(returned_item_count_90d * 0.10)))
            risk_score += return_risk
            risk_factors.append({
                "factor": "return_history",
                "weight": float(return_risk),
                "description": f"{returned_item_count_90d} returned items in last 90 days",
                "value": returned_item_count_90d,
            })
            flags.append(f"Return history ({returned_item_count_90d} in 90d)")

        # Risk factor: Balance coverage
        if current_balance is not None and amount > current_balance:
            coverage_risk = Decimal("0.2000")
            risk_score += coverage_risk
            risk_factors.append({
                "factor": "insufficient_balance",
                "weight": float(coverage_risk),
                "description": "Check amount exceeds current balance",
                "value": str(current_balance),
            })
            flags.append("Amount exceeds current balance")

        # Risk factor: Upstream flags
        if upstream_flags:
            upstream_risk = min(Decimal("0.2000"), Decimal(str(len(upstream_flags) * 0.05)))
            risk_score += upstream_risk
            risk_factors.append({
                "factor": "upstream_flags",
                "weight": float(upstream_risk),
                "description": f"{len(upstream_flags)} flags from source system",
                "value": upstream_flags,
            })
            for flag in upstream_flags[:3]:  # Limit to first 3
                flags.append(f"Upstream: {flag}")

        # Cap risk score at 1.0
        risk_score = min(risk_score, Decimal("1.0000"))

        # Determine advisory recommendation
        if risk_score < Decimal("0.2000"):
            recommendation = AIRecommendation.LIKELY_LEGITIMATE
            confidence = 0.85
        elif risk_score < Decimal("0.4000"):
            recommendation = AIRecommendation.NEEDS_REVIEW
            confidence = 0.75
        elif risk_score < Decimal("0.7000"):
            recommendation = AIRecommendation.HIGH_RISK
            confidence = 0.80
        else:
            recommendation = AIRecommendation.ANOMALY_DETECTED
            confidence = 0.70

        # If insufficient data, reduce confidence
        if not avg_check_amount_30d and not account_tenure_days:
            recommendation = AIRecommendation.INSUFFICIENT_DATA
            confidence = 0.40

        # Build explanation
        if risk_factors:
            factor_desc = ", ".join([f["description"] for f in risk_factors[:3]])
            explanation = f"ADVISORY: Risk score {risk_score:.2%}. Key factors: {factor_desc}"
        else:
            explanation = "ADVISORY: No significant risk factors detected. Standard review recommended."

        processing_time_ms = int((time.monotonic() - start_time) * 1000)

        result = AIAnalysisResult(
            model_id=self.MODEL_ID,
            model_version=self.MODEL_VERSION,
            analyzed_at=analyzed_at,
            recommendation=recommendation,
            confidence=confidence,
            risk_score=risk_score,
            risk_factors=risk_factors,
            flags=flags,
            explanation=explanation,
            confidence_by_category={
                "amount_pattern": 0.85 if avg_check_amount_30d else 0.30,
                "account_history": 0.80 if account_tenure_days else 0.30,
                "balance_coverage": 0.90 if current_balance else 0.30,
            },
        )

        # MANDATORY: Log AI inference for audit
        await self.audit_service.log_ai_inference(
            check_item_id=check_item_id,
            user_id=user_id,
            username=username,
            inference_type="check_risk_analysis",
            model_id=self.MODEL_ID,
            model_version=self.MODEL_VERSION,
            result_summary={
                "recommendation": recommendation.value,
                "risk_score": str(risk_score),
                "confidence": confidence,
                "flag_count": len(flags),
            },
            processing_time_ms=processing_time_ms,
            success=True,
        )

        return result

    async def validate_ai_acknowledgment(
        self,
        check_item_id: str,
        ai_assisted: bool,
        ai_flags_reviewed: list[str],
        ai_analysis: AIAnalysisResult | None,
    ) -> tuple[bool, str | None]:
        """
        Validate that AI output was properly acknowledged before decision.

        GUARDRAIL: If AI was used, the reviewer must have:
        1. Explicitly acknowledged AI assistance (ai_assisted=True)
        2. Reviewed the AI-generated flags

        Returns:
            (is_valid, error_message)
        """
        if not ai_analysis:
            # No AI analysis performed - nothing to validate
            if ai_assisted:
                return False, "AI assisted marked but no AI analysis found"
            return True, None

        # If AI analysis exists, reviewer must acknowledge
        if not ai_assisted:
            return False, "AI analysis was performed but not acknowledged. Set ai_assisted=True to proceed."

        # If AI generated flags, they should be reviewed
        if ai_analysis.flags and not ai_flags_reviewed:
            return False, f"AI generated {len(ai_analysis.flags)} flags that must be reviewed before decision"

        return True, None


# Singleton-ish factory for consistency
def get_ai_service(db: AsyncSession) -> AIService:
    """Get AI service instance."""
    return AIService(db)
