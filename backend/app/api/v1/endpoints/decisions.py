"""Decision endpoints."""

from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentUser, require_permission
from app.models.check import CheckItem, CheckStatus
from app.models.decision import Decision, DecisionAction, DecisionType, ReasonCode
from app.schemas.decision import (
    DecisionCreate,
    DecisionResponse,
    DualControlApprovalRequest,
    ReasonCodeResponse,
)
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.policy.engine import PolicyEngine

router = APIRouter()


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
    # Get the check item
    result = await db.execute(
        select(CheckItem).where(CheckItem.id == decision_data.check_item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check item not found",
        )

    # Check permissions based on decision type
    if decision_data.decision_type == DecisionType.REVIEW_RECOMMENDATION:
        if not current_user.has_permission("check_item", "review"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: cannot review items",
            )
    elif decision_data.decision_type == DecisionType.APPROVAL_DECISION:
        if not current_user.has_permission("check_item", "approve"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: cannot approve items",
            )

    # Get policy evaluation
    policy_engine = PolicyEngine(db)
    policy_result = await policy_engine.evaluate(item)

    # Check if dual control is required
    requires_dual_control = policy_result.requires_dual_control or item.requires_dual_control

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
        if decision_data.action == DecisionAction.APPROVE:
            new_status = CheckStatus.PENDING_APPROVAL if requires_dual_control else CheckStatus.APPROVED
        elif decision_data.action == DecisionAction.RETURN:
            new_status = CheckStatus.PENDING_APPROVAL if requires_dual_control else CheckStatus.RETURNED
        elif decision_data.action == DecisionAction.REJECT:
            new_status = CheckStatus.PENDING_APPROVAL if requires_dual_control else CheckStatus.REJECTED
        elif decision_data.action == DecisionAction.ESCALATE:
            new_status = CheckStatus.ESCALATED
        elif decision_data.action == DecisionAction.HOLD:
            new_status = CheckStatus.IN_REVIEW

    elif decision_data.decision_type == DecisionType.APPROVAL_DECISION:
        if decision_data.action == DecisionAction.APPROVE:
            new_status = CheckStatus.APPROVED
        elif decision_data.action == DecisionAction.RETURN:
            new_status = CheckStatus.RETURNED
        elif decision_data.action == DecisionAction.REJECT:
            new_status = CheckStatus.REJECTED

    # Create decision record
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
    )

    db.add(decision)

    # Update item status
    item.status = new_status
    if policy_result.policy_version_id:
        item.policy_version_id = policy_result.policy_version_id

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
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


@router.post("/dual-control", response_model=DecisionResponse)
async def approve_dual_control(
    request: Request,
    approval: DualControlApprovalRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("check_item", "approve"))],
):
    """Approve or reject a dual control decision."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(Decision)
        .options(selectinload(Decision.check_item))
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

    # Update decision
    decision.dual_control_approver_id = current_user.id
    decision.dual_control_approved_at = datetime.now(timezone.utc)

    # Update item status based on original decision action
    item = decision.check_item
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
        metadata={"notes": approval.notes},
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
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
        )

    return responses
