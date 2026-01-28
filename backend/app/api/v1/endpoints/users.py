"""User management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_permission
from app.audit.service import AuditService
from app.core.client_ip import get_client_ip
from app.core.security import get_password_hash
from app.models.audit import AuditAction
from app.models.user import Permission, Role, User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import (
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[UserListResponse])
async def list_users(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("user", "view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
    search: str | None = None,
):
    """List users with pagination and filtering."""
    # CRITICAL: Filter by tenant_id for multi-tenant isolation
    query = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.tenant_id == current_user.tenant_id)
    )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    if search:
        query = query.where(
            User.username.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | User.full_name.ilike(f"%{search}%")
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=[
            UserListResponse(
                id=u.id,
                email=u.email,
                username=u.username,
                full_name=u.full_name,
                is_active=u.is_active,
                department=u.department,
                roles=[r.name for r in u.roles],
                last_login=u.last_login,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.post("", response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: UserCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("user", "create"))],
):
    """Create a new user."""
    # Check for existing user
    result = await db.execute(
        select(User).where((User.email == user_data.email) | (User.username == user_data.username))
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )

    # Create user (inherit tenant from current user)
    user = User(
        tenant_id=current_user.tenant_id,
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        department=user_data.department,
        branch=user_data.branch,
        employee_id=user_data.employee_id,
        is_active=user_data.is_active,
    )

    # Assign roles
    if user_data.role_ids:
        roles_result = await db.execute(select(Role).where(Role.id.in_(user_data.role_ids)))
        user.roles = list(roles_result.scalars().all())

    db.add(user)
    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.USER_CREATED,
        resource_type="user",
        resource_id=user.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=get_client_ip(request),
        description=f"Created user {user.username}",
        after_value={"username": user.username, "email": user.email},
    )

    # Explicit commit for write operation
    await db.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        department=user.department,
        branch=user.branch,
        employee_id=user.employee_id,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        mfa_enabled=user.mfa_enabled,
        last_login=user.last_login,
        roles=[],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("user", "view"))],
):
    """Get a specific user."""
    # CRITICAL: Filter by tenant_id for multi-tenant isolation
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        department=user.department,
        branch=user.branch,
        employee_id=user.employee_id,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        mfa_enabled=user.mfa_enabled,
        last_login=user.last_login,
        roles=[
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                permissions=[],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in user.roles
        ],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: str,
    user_data: UserUpdate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("user", "update"))],
):
    """Update a user."""
    # CRITICAL: Filter by tenant_id for multi-tenant isolation
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Track changes for audit
    changes = {}

    if user_data.email is not None and user_data.email != user.email:
        changes["email"] = {"before": user.email, "after": user_data.email}
        user.email = user_data.email

    if user_data.full_name is not None and user_data.full_name != user.full_name:
        changes["full_name"] = {"before": user.full_name, "after": user_data.full_name}
        user.full_name = user_data.full_name

    if user_data.department is not None:
        changes["department"] = {"before": user.department, "after": user_data.department}
        user.department = user_data.department

    if user_data.branch is not None:
        changes["branch"] = {"before": user.branch, "after": user_data.branch}
        user.branch = user_data.branch

    if user_data.is_active is not None and user_data.is_active != user.is_active:
        changes["is_active"] = {"before": user.is_active, "after": user_data.is_active}
        user.is_active = user_data.is_active

    if user_data.role_ids is not None:
        old_roles = [r.name for r in user.roles]
        roles_result = await db.execute(select(Role).where(Role.id.in_(user_data.role_ids)))
        user.roles = list(roles_result.scalars().all())
        new_roles = [r.name for r in user.roles]
        if old_roles != new_roles:
            changes["roles"] = {"before": old_roles, "after": new_roles}

    # Audit log
    if changes:
        audit_service = AuditService(db)
        await audit_service.log(
            action=AuditAction.USER_UPDATED,
            resource_type="user",
            resource_id=user_id,
            user_id=current_user.id,
            username=current_user.username,
            ip_address=get_client_ip(request),
            description=f"Updated user {user.username}",
            metadata=changes,
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        department=user.department,
        branch=user.branch,
        employee_id=user.employee_id,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        mfa_enabled=user.mfa_enabled,
        last_login=user.last_login,
        roles=[
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                permissions=[],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in user.roles
        ],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# Role endpoints
@router.get("/roles/", response_model=list[RoleResponse])
async def list_roles(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("role", "view"))],
):
    """List all roles."""
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
    )
    roles = result.scalars().all()

    return [
        RoleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=[
                PermissionResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    resource=p.resource,
                    action=p.action,
                    conditions=None,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
                for p in r.permissions
            ],
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in roles
    ]


@router.post("/roles/", response_model=RoleResponse)
async def create_role(
    request: Request,
    role_data: RoleCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("role", "create"))],
):
    """Create a new role."""
    # Check for existing role
    result = await db.execute(select(Role).where(Role.name == role_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )

    role = Role(
        name=role_data.name,
        description=role_data.description,
    )

    if role_data.permission_ids:
        perms_result = await db.execute(
            select(Permission).where(Permission.id.in_(role_data.permission_ids))
        )
        role.permissions = list(perms_result.scalars().all())

    db.add(role)
    await db.flush()

    # Explicit commit for write operation
    await db.commit()

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/permissions/", response_model=list[PermissionResponse])
async def list_permissions(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("permission", "view"))],
):
    """List all permissions."""
    result = await db.execute(select(Permission).order_by(Permission.resource, Permission.action))
    perms = result.scalars().all()

    return [
        PermissionResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            resource=p.resource,
            action=p.action,
            conditions=None,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in perms
    ]
