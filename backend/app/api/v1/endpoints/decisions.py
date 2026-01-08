"""Decision endpoints."""

from datetime import datetime, timezone
from typing import Annotated, Any
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentUser, require_permission
from app.models.check import CheckItem, CheckImage, CheckStatus
from app.models.decision import Decision, DecisionAction, DecisionType, ReasonCode
from app.schemas.decision import (
    DecisionCreate,
    DecisionResponse,
    DualControlApprovalRequest,
    ReasonCodeResponse,
    EvidenceSnapshot,
    CheckContextSnapshot,
    PolicyEvaluationSnapshot,
    AIContextSnapshot,
    ImageReference,
)
from app.schemas.policy import PolicyEvaluationResult
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.policy.engine import PolicyEngine
from app.services.entitlement_service import EntitlementService

router = APIRouter()


def build_evidence_snapshot(
    check_item: CheckItem,
    policy_result: PolicyEvaluationResult,
    ai_assisted: bool,
    ai_flags_reviewed: list[str],
) -> dict[str, Any]:
    """
    Build complete evidence snapshot for audit replay.

    This captures the EXACT state at decision time:
    - Check context values (amounts, balances, tenure)
    - Image references
    - Policy evaluation results
    - AI/ML context if applicable
    """
    # Build check context snapshot
    check_context = CheckContextSnapshot(
        amount=str(check_item.amount),
        account_type=check_item.account_type.value if check_item.account_type else None,
        account_tenure_days=check_item.account_tenure_days,
        current_balance=str(check_item.current_balance) if check_item.current_balance else None,
        average_balance_30d=str(check_item.average_balance_30d) if check_item.average_balance_30d else None,
        avg_check_amount_30d=str(check_item.avg_check_amount_30d) if check_item.avg_check_amount_30d else None,
        avg_check_amount_90d=str(check_item.avg_check_amount_90d) if check_item.avg_check_amount_90d else None,
        avg_check_amount_365d=str(check_item.avg_check_amount_365d) if check_item.avg_check_amount_365d else None,
        check_frequency_30d=check_item.check_frequency_30d,
        returned_item_count_90d=check_item.returned_item_count_90d,
        exception_count_90d=check_item.exception_count_90d,
        risk_level=check_item.risk_level.value if check_item.risk_level else None,
        risk_flags=json.loads(check_item.risk_flags) if check_item.risk_flags else [],
        upstream_flags=json.loads(check_item.upstream_flags) if check_item.upstream_flags else [],
    )

    # Build image references
    images = []
    if hasattr(check_item, "images") and check_item.images:
        for img in check_item.images:
            images.append(ImageReference(
                id=img.id,
                image_type=img.image_type,
                external_id=img.external_image_id,
                content_hash=None,  # Would be populated from actual image hash
            ))

    # Build policy evaluation snapshot
    policy_snapshot = PolicyEvaluationSnapshot(
        policy_version_id=policy_result.policy_version_id,
        policy_name=None,  # Could be enriched from policy lookup
        rules_triggered=[
            {"rule_id": rule_id} for rule_id in policy_result.rules_triggered
        ],
        requires_dual_control=policy_result.requires_dual_control,
        risk_score=None,
        recommendation=None,
    )

    # Build AI context snapshot
    ai_context = AIContextSnapshot(
        ai_assisted=ai_assisted,
        model_id=None,  # Would come from AI service
        model_version=None,
        ai_risk_score=str(check_item.ai_risk_score) if check_item.ai_risk_score else None,
        features_displayed=[],  # Would come from AI service
        flags_displayed=[
            {"flag": flag} for flag in (policy_result.flags or [])
        ],
        flags_reviewed=ai_flags_reviewed,
        confidence_scores={},
    )

    # Build complete snapshot
    snapshot = EvidenceSnapshot(
        snapshot_version="1.0",
        captured_at=datetime.now(timezone.utc),
        check_context=check_context,
        images=images,
        policy_evaluation=policy_snapshot,
        ai_context=ai_context,
        decision_context={},
    )

    return snapshot.model_dump(mode="json")


@router.get("/reason-codes", response_model=list[ReasonCodeResponse])
async def list_reason_codes(
    db: DBSession,
    current_user: CurrentUser,
    category: str | None = None,
    decision_type: str | None = None,
):
    """List available reason codes."""
    query = select(ReasonCode).where(ReasonCode.is_active == True)

    if category:
        query = query.where(ReasonCode.category == category)
    if decision_type:
        query = query.where(ReasonCode.decision_type == decision_type)

    query = query.order_by(ReasonCode.display_order, ReasonCode.code)

    result = await db.execute(query)
    codes = result.scalars().all()

    return [
        ReasonCodeResponse(
            id=code.id,
            code=code.code,
            description=code.description,
            category=code.category,
            decision_type=code.decision_type,
            requires_notes=code.requires_notes,
            is_active=code.is_active,
            display_order=code.display_order,
            created_at=code.created_at,
            updated_at=code.updated_at,
        )
        for code in codes
    ]


@router.post("", response_model=DecisionResponse)
async def create_decision(
    request: Request,
    decision_data: DecisionCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a decision for a check item."""
    # Get the check item with images for evidence snapshot
    result = await db.execute(
        select(CheckItem)
        .options(selectinload(CheckItem.images))
        .where(CheckItem.id == decision_data.check_item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    # Initialize entitlement service
    entitlement_service = EntitlementService(db)

    # Check entitlements based on decision type
    if decision_data.decision_type == DecisionType.REVIEW_RECOMMENDATION:
        # Check review entitlement (includes amount/queue limits)
        entitlement_result = await entitlement_service.check_review_entitlement(
            current_user, item
        )
        if not entitlement_result.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not entitled to review this item: {entitlement_result.denial_reason}",
            )

    elif decision_data.decision_type == DecisionType.APPROVAL_DECISION:
        # Check approval entitlement (stricter - includes amount thresholds)
        entitlement_result = await entitlement_service.check_approval_entitlement(
            current_user, item
        )
        if not entitlement_result.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not entitled to approve this item: {entitlement_result.denial_reason}",
            )

        # Approval decisions require the item to be in PENDING_DUAL_CONTROL state
        if item.status != CheckStatus.PENDING_DUAL_CONTROL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item must be in PENDING_DUAL_CONTROL status for approval decision (current: {item.status.value})",
            )

        # Cannot approve your own recommendation
        if item.pending_dual_control_decision_id:
            pending_decision_result = await db.execute(
                select(Decision).where(Decision.id == item.pending_dual_control_decision_id)
            )
            pending_decision = pending_decision_result.scalar_one_or_none()
            if pending_decision and pending_decision.user_id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot approve your own recommendation (dual control)",
                )

    # Get policy evaluation
    policy_engine = PolicyEngine(db)
    policy_result = await policy_engine.evaluate(item)

    # Determine if dual control is required and why
    requires_dual_control = False
    dual_control_reason = None

    if policy_result.requires_dual_control:
        requires_dual_control = True
        dual_control_reason = "policy_rule"
    elif item.requires_dual_control:
        requires_dual_control = True
        dual_control_reason = "item_flag"

    # Validate reason codes
    reason_code_ids = []
    if decision_data.reason_code_ids:
        codes_result = await db.execute(
            select(ReasonCode).where(ReasonCode.id.in_(decision_data.reason_code_ids))
        )
        codes = codes_result.scalars().all()
        reason_code_ids = [c.id for c in codes]

        # Check if any reason codes require notes
        for code in codes:
            if code.requires_notes and not decision_data.notes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Reason code '{code.code}' requires notes",
                )

    # Determine new status based on decision
    old_status = item.status
    new_status = old_status

    if decision_data.decision_type == DecisionType.REVIEW_RECOMMENDATION:
        # Review recommendation - may trigger dual control
        if decision_data.action == DecisionAction.APPROVE:
            new_status = CheckStatus.PENDING_DUAL_CONTROL if requires_dual_control else CheckStatus.APPROVED
        elif decision_data.action == DecisionAction.RETURN:
            new_status = CheckStatus.PENDING_DUAL_CONTROL if requires_dual_control else CheckStatus.RETURNED
        elif decision_data.action == DecisionAction.REJECT:
            new_status = CheckStatus.PENDING_DUAL_CONTROL if requires_dual_control else CheckStatus.REJECTED
        elif decision_data.action == DecisionAction.ESCALATE:
            new_status = CheckStatus.ESCALATED
        elif decision_data.action == DecisionAction.HOLD:
            new_status = CheckStatus.IN_REVIEW

    elif decision_data.decision_type == DecisionType.APPROVAL_DECISION:
        # Approval decision - final state
        if decision_data.action == DecisionAction.APPROVE:
            new_status = CheckStatus.APPROVED
        elif decision_data.action == DecisionAction.RETURN:
            new_status = CheckStatus.RETURNED
        elif decision_data.action == DecisionAction.REJECT:
            new_status = CheckStatus.REJECTED
        elif decision_data.action == DecisionAction.ESCALATE:
            # Approver can escalate instead of approving
            new_status = CheckStatus.ESCALATED

    # Build evidence snapshot - CRITICAL for audit replay
    evidence_snapshot = build_evidence_snapshot(
        check_item=item,
        policy_result=policy_result,
        ai_assisted=decision_data.ai_assisted,
        ai_flags_reviewed=decision_data.ai_flags_reviewed,
    )

    # Create decision record with evidence snapshot
    decision = Decision(
        check_item_id=item.id,
        user_id=current_user.id,
        decision_type=decision_data.decision_type,
        action=decision_data.action,
        reason_codes=json.dumps(reason_code_ids) if reason_code_ids else None,
        notes=decision_data.notes,
        ai_assisted=decision_data.ai_assisted,
        ai_flags_reviewed=json.dumps(decision_data.ai_flags_reviewed) if decision_data.ai_flags_reviewed else None,
        attachments=json.dumps(decision_data.attachment_ids) if decision_data.attachment_ids else None,
        policy_version_id=policy_result.policy_version_id if policy_result.policy_version_id else None,
        previous_status=old_status.value,
        new_status=new_status.value,
        is_dual_control_required=requires_dual_control,
        evidence_snapshot=evidence_snapshot,
    )

    db.add(decision)
    await db.flush()  # Flush to get decision.id

    # Update item status and dual control tracking
    item.status = new_status
    if policy_result.policy_version_id:
        item.policy_version_id = policy_result.policy_version_id

    # Track pending dual control decision for easy lookup
    if new_status == CheckStatus.PENDING_DUAL_CONTROL:
        item.pending_dual_control_decision_id = decision.id
        item.dual_control_reason = dual_control_reason
    elif decision_data.decision_type == DecisionType.APPROVAL_DECISION:
        # Clear pending dual control after approval decision
        item.pending_dual_control_decision_id = None
        item.dual_control_reason = None

    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log_decision(
        check_item_id=item.id,
        user_id=current_user.id,
        username=current_user.username,
        decision_type=decision_data.decision_type.value,
        action=decision_data.action.value,
        reason_codes=reason_code_ids,
        notes=decision_data.notes,
        ip_address=request.client.host if request.client else None,
        before_status=old_status.value,
        after_status=new_status.value,
    )

    # Get reason codes for response
    reason_codes_response = []
    if reason_code_ids:
        codes_result = await db.execute(
            select(ReasonCode).where(ReasonCode.id.in_(reason_code_ids))
        )
        for code in codes_result.scalars().all():
            reason_codes_response.append(
                ReasonCodeResponse(
                    id=code.id,
                    code=code.code,
                    description=code.description,
                    category=code.category,
                    decision_type=code.decision_type,
                    requires_notes=code.requires_notes,
                    is_active=code.is_active,
                    display_order=code.display_order,
                    created_at=code.created_at,
                    updated_at=code.updated_at,
                )
            )

    # Parse evidence snapshot back to schema for response
    evidence_response = None
    if decision.evidence_snapshot:
        evidence_response = EvidenceSnapshot(**decision.evidence_snapshot)

    return DecisionResponse(
        id=decision.id,
        check_item_id=decision.check_item_id,
        user_id=decision.user_id,
        username=current_user.username,
        decision_type=decision.decision_type,
        action=decision.action,
        reason_codes=reason_codes_response,
        notes=decision.notes,
        ai_assisted=decision.ai_assisted,
        ai_flags_reviewed=decision_data.ai_flags_reviewed,
        attachments=decision_data.attachment_ids,
        policy_version_id=decision.policy_version_id,
        previous_status=decision.previous_status,
        new_status=decision.new_status,
        is_dual_control_required=decision.is_dual_control_required,
        dual_control_approver_id=decision.dual_control_approver_id,
        dual_control_approved_at=decision.dual_control_approved_at,
        evidence_snapshot=evidence_response,
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


@router.post("/dual-control", response_model=DecisionResponse)
async def approve_dual_control(
    request: Request,
    approval: DualControlApprovalRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Approve or reject a dual control decision.

    This is the second-level approval in the dual control workflow.
    The approver must:
    - Have appropriate approval entitlement for this item
    - Not be the same user who made the original recommendation
    """
    result = await db.execute(
        select(Decision)
        .options(selectinload(Decision.check_item).selectinload(CheckItem.images))
        .where(Decision.id == approval.decision_id)
    )
    decision = result.scalar_one_or_none()

    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    if not decision.is_dual_control_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision does not require dual control",
        )

    if decision.dual_control_approved_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision already has dual control approval",
        )

    if decision.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve your own decision (dual control)",
        )

    item = decision.check_item

    # Verify item is in PENDING_DUAL_CONTROL status
    if item.status != CheckStatus.PENDING_DUAL_CONTROL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item must be in PENDING_DUAL_CONTROL status (current: {item.status.value})",
        )

    # Check approval entitlement
    entitlement_service = EntitlementService(db)
    entitlement_result = await entitlement_service.check_approval_entitlement(
        current_user, item
    )
    if not entitlement_result.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not entitled to approve this item: {entitlement_result.denial_reason}",
        )

    # Update decision
    decision.dual_control_approver_id = current_user.id
    decision.dual_control_approved_at = datetime.now(timezone.utc)

    # Update item status based on original decision action
    if approval.approve:
        if decision.action == DecisionAction.APPROVE:
            item.status = CheckStatus.APPROVED
        elif decision.action == DecisionAction.RETURN:
            item.status = CheckStatus.RETURNED
        elif decision.action == DecisionAction.REJECT:
            item.status = CheckStatus.REJECTED
    else:
        # Dual control rejected - return to review
        item.status = CheckStatus.IN_REVIEW

    # Clear pending dual control tracking
    item.pending_dual_control_decision_id = None
    item.dual_control_reason = None

    # Audit
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.DECISION_APPROVED if approval.approve else AuditAction.DECISION_REJECTED,
        resource_type="decision",
        resource_id=decision.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Dual control {'approved' if approval.approve else 'rejected'}",
        metadata={
            "notes": approval.notes,
            "entitlement_id": entitlement_result.entitlement_id,
            "entitlement_details": entitlement_result.entitlement_details,
        },
    )

    return DecisionResponse(
        id=decision.id,
        check_item_id=decision.check_item_id,
        user_id=decision.user_id,
        decision_type=decision.decision_type,
        action=decision.action,
        reason_codes=[],
        notes=decision.notes,
        ai_assisted=decision.ai_assisted,
        ai_flags_reviewed=[],
        attachments=[],
        policy_version_id=decision.policy_version_id,
        previous_status=decision.previous_status,
        new_status=item.status.value,
        is_dual_control_required=decision.is_dual_control_required,
        dual_control_approver_id=decision.dual_control_approver_id,
        dual_control_approved_at=decision.dual_control_approved_at,
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


@router.get("/{item_id}/history", response_model=list[DecisionResponse])
async def get_decision_history(
    item_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "view"))],
):
    """Get decision history for a check item."""
    result = await db.execute(
        select(Decision)
        .where(Decision.check_item_id == item_id)
        .order_by(Decision.created_at.desc())
    )
    decisions = result.scalars().all()

    responses = []
    for d in decisions:
        # Get username
        from app.models.user import User
        user_result = await db.execute(select(User.username).where(User.id == d.user_id))
        username = user_result.scalar_one_or_none()

        # Parse evidence snapshot if present
        evidence_response = None
        if d.evidence_snapshot:
            evidence_response = EvidenceSnapshot(**d.evidence_snapshot)

        responses.append(
            DecisionResponse(
                id=d.id,
                check_item_id=d.check_item_id,
                user_id=d.user_id,
                username=username,
                decision_type=d.decision_type,
                action=d.action,
                reason_codes=[],
                notes=d.notes,
                ai_assisted=d.ai_assisted,
                ai_flags_reviewed=[],
                attachments=[],
                policy_version_id=d.policy_version_id,
                previous_status=d.previous_status,
                new_status=d.new_status,
                is_dual_control_required=d.is_dual_control_required,
                dual_control_approver_id=d.dual_control_approver_id,
                dual_control_approved_at=d.dual_control_approved_at,
                evidence_snapshot=evidence_response,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
        )

    return responses
