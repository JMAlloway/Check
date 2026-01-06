"""Policy management endpoints."""

from datetime import datetime, timezone
from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentUser, require_permission
from app.models.policy import Policy, PolicyRule, PolicyStatus, PolicyVersion
from app.schemas.policy import (
    PolicyCreate,
    PolicyListResponse,
    PolicyResponse,
    PolicyRuleCreate,
    PolicyRuleResponse,
    PolicyUpdate,
    PolicyVersionCreate,
    PolicyVersionResponse,
    RuleAction,
    RuleCondition,
)
from app.audit.service import AuditService
from app.models.audit import AuditAction

router = APIRouter()


@router.get("", response_model=list[PolicyListResponse])
async def list_policies(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("policy", "view"))],
    status_filter: PolicyStatus | None = None,
):
    """List all policies."""
    query = select(Policy).options(selectinload(Policy.versions))

    if status_filter:
        query = query.where(Policy.status == status_filter)

    query = query.order_by(Policy.is_default.desc(), Policy.name)

    result = await db.execute(query)
    policies = result.scalars().all()

    return [
        PolicyListResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            status=p.status,
            is_default=p.is_default,
            current_version_number=next(
                (v.version_number for v in p.versions if v.is_current), None
            ),
            rules_count=sum(1 for v in p.versions if v.is_current for _ in [1]),
        )
        for p in policies
    ]


@router.post("", response_model=PolicyResponse)
async def create_policy(
    request: Request,
    policy_data: PolicyCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("policy", "create"))],
):
    """Create a new policy."""
    policy = Policy(
        name=policy_data.name,
        description=policy_data.description,
        status=PolicyStatus.DRAFT,
        applies_to_account_types=json.dumps(policy_data.applies_to_account_types) if policy_data.applies_to_account_types else None,
        applies_to_branches=json.dumps(policy_data.applies_to_branches) if policy_data.applies_to_branches else None,
        applies_to_markets=json.dumps(policy_data.applies_to_markets) if policy_data.applies_to_markets else None,
    )

    db.add(policy)
    await db.flush()

    # Create initial version if provided
    if policy_data.initial_version:
        version = PolicyVersion(
            policy_id=policy.id,
            version_number=1,
            effective_date=policy_data.initial_version.effective_date,
            expiry_date=policy_data.initial_version.expiry_date,
            is_current=True,
            change_notes=policy_data.initial_version.change_notes,
        )
        db.add(version)
        await db.flush()

        # Add rules
        for rule_data in policy_data.initial_version.rules:
            rule = PolicyRule(
                policy_version_id=version.id,
                name=rule_data.name,
                description=rule_data.description,
                rule_type=rule_data.rule_type,
                priority=rule_data.priority,
                is_enabled=rule_data.is_enabled,
                conditions=json.dumps([c.model_dump() for c in rule_data.conditions]),
                actions=json.dumps([a.model_dump() for a in rule_data.actions]),
                amount_threshold=rule_data.amount_threshold,
                risk_level_threshold=rule_data.risk_level_threshold,
            )
            db.add(rule)

    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.POLICY_CREATED,
        resource_type="policy",
        resource_id=policy.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Created policy {policy.name}",
    )

    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        status=policy.status,
        is_default=policy.is_default,
        applies_to_account_types=policy_data.applies_to_account_types,
        applies_to_branches=policy_data.applies_to_branches,
        applies_to_markets=policy_data.applies_to_markets,
        versions=[],
        current_version=None,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("policy", "view"))],
):
    """Get a specific policy with all versions."""
    result = await db.execute(
        select(Policy)
        .options(
            selectinload(Policy.versions).selectinload(PolicyVersion.rules)
        )
        .where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    versions = []
    current_version = None

    for v in policy.versions:
        rules = [
            PolicyRuleResponse(
                id=r.id,
                policy_version_id=r.policy_version_id,
                name=r.name,
                description=r.description,
                rule_type=r.rule_type,
                priority=r.priority,
                is_enabled=r.is_enabled,
                conditions=[RuleCondition(**c) for c in json.loads(r.conditions)],
                actions=[RuleAction(**a) for a in json.loads(r.actions)],
                amount_threshold=r.amount_threshold,
                risk_level_threshold=r.risk_level_threshold,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in v.rules
        ]

        version_response = PolicyVersionResponse(
            id=v.id,
            policy_id=v.policy_id,
            version_number=v.version_number,
            effective_date=v.effective_date,
            expiry_date=v.expiry_date,
            is_current=v.is_current,
            approved_by_id=v.approved_by_id,
            approved_at=v.approved_at,
            change_notes=v.change_notes,
            rules=rules,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )

        versions.append(version_response)
        if v.is_current:
            current_version = version_response

    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        status=policy.status,
        is_default=policy.is_default,
        applies_to_account_types=json.loads(policy.applies_to_account_types) if policy.applies_to_account_types else None,
        applies_to_branches=json.loads(policy.applies_to_branches) if policy.applies_to_branches else None,
        applies_to_markets=json.loads(policy.applies_to_markets) if policy.applies_to_markets else None,
        versions=versions,
        current_version=current_version,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.post("/{policy_id}/versions", response_model=PolicyVersionResponse)
async def create_policy_version(
    request: Request,
    policy_id: str,
    version_data: PolicyVersionCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("policy", "update"))],
):
    """Create a new version of a policy."""
    result = await db.execute(
        select(Policy).options(selectinload(Policy.versions)).where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    # Get next version number
    max_version = max((v.version_number for v in policy.versions), default=0)

    # Create new version
    version = PolicyVersion(
        policy_id=policy_id,
        version_number=max_version + 1,
        effective_date=version_data.effective_date,
        expiry_date=version_data.expiry_date,
        is_current=False,  # Must be explicitly activated
        change_notes=version_data.change_notes,
    )
    db.add(version)
    await db.flush()

    # Add rules
    rules = []
    for rule_data in version_data.rules:
        rule = PolicyRule(
            policy_version_id=version.id,
            name=rule_data.name,
            description=rule_data.description,
            rule_type=rule_data.rule_type,
            priority=rule_data.priority,
            is_enabled=rule_data.is_enabled,
            conditions=json.dumps([c.model_dump() for c in rule_data.conditions]),
            actions=json.dumps([a.model_dump() for a in rule_data.actions]),
            amount_threshold=rule_data.amount_threshold,
            risk_level_threshold=rule_data.risk_level_threshold,
        )
        db.add(rule)
        rules.append(rule)

    await db.flush()

    return PolicyVersionResponse(
        id=version.id,
        policy_id=version.policy_id,
        version_number=version.version_number,
        effective_date=version.effective_date,
        expiry_date=version.expiry_date,
        is_current=version.is_current,
        approved_by_id=version.approved_by_id,
        approved_at=version.approved_at,
        change_notes=version.change_notes,
        rules=[
            PolicyRuleResponse(
                id=r.id,
                policy_version_id=r.policy_version_id,
                name=r.name,
                description=r.description,
                rule_type=r.rule_type,
                priority=r.priority,
                is_enabled=r.is_enabled,
                conditions=[RuleCondition(**c) for c in json.loads(r.conditions)],
                actions=[RuleAction(**a) for a in json.loads(r.actions)],
                amount_threshold=r.amount_threshold,
                risk_level_threshold=r.risk_level_threshold,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rules
        ],
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


@router.post("/{policy_id}/activate")
async def activate_policy(
    request: Request,
    policy_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("policy", "activate"))],
    version_id: str | None = None,
):
    """Activate a policy (or specific version)."""
    result = await db.execute(
        select(Policy).options(selectinload(Policy.versions)).where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    # Find version to activate
    target_version = None
    if version_id:
        for v in policy.versions:
            if v.id == version_id:
                target_version = v
                break
    else:
        # Get latest version
        target_version = max(policy.versions, key=lambda v: v.version_number, default=None)

    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No version to activate",
        )

    # Deactivate other versions
    for v in policy.versions:
        v.is_current = False

    # Activate target
    target_version.is_current = True
    target_version.approved_by_id = current_user.id
    target_version.approved_at = datetime.now(timezone.utc)

    # Set policy to active
    policy.status = PolicyStatus.ACTIVE

    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.POLICY_ACTIVATED,
        resource_type="policy",
        resource_id=policy_id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Activated policy {policy.name} version {target_version.version_number}",
    )

    return {"message": f"Policy activated (version {target_version.version_number})", "version_id": target_version.id}
