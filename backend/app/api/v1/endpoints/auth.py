"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import DBSession, CurrentUser
from app.schemas.auth import LoginRequest, RefreshTokenRequest, Token, PasswordChangeRequest
from app.schemas.common import MessageResponse
from app.schemas.user import CurrentUserResponse
from app.services.auth import AuthService
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.core.security import get_password_hash, verify_password

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: DBSession,
):
    """Authenticate user and return tokens."""
    auth_service = AuthService(db)
    audit_service = AuditService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user, error = await auth_service.authenticate_user(
        username=login_data.username,
        password=login_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if error:
        await audit_service.log(
            action=AuditAction.LOGIN_FAILED,
            resource_type="user",
            description=f"Login failed for {login_data.username}: {error}",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = await auth_service.create_tokens(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    await audit_service.log(
        action=AuditAction.LOGIN,
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
        username=user.username,
        ip_address=ip_address,
        user_agent=user_agent,
        description=f"User logged in successfully",
    )

    return tokens


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: DBSession,
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    tokens = await auth_service.refresh_tokens(
        refresh_token=refresh_data.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """Logout user and revoke refresh token."""
    auth_service = AuthService(db)
    audit_service = AuditService(db)

    success = await auth_service.logout(refresh_data.refresh_token)

    if success:
        await audit_service.log(
            action=AuditAction.LOGOUT,
            resource_type="user",
            resource_id=current_user.id,
            user_id=current_user.id,
            username=current_user.username,
            ip_address=request.client.host if request.client else None,
            description="User logged out",
        )

    return MessageResponse(message="Logged out successfully", success=True)


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """Get current user information."""
    # Gather permissions
    permissions = []
    for role in current_user.roles:
        for perm in role.permissions:
            perm_str = f"{perm.resource}:{perm.action}"
            if perm_str not in permissions:
                permissions.append(perm_str)

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        department=current_user.department,
        branch=current_user.branch,
        employee_id=current_user.employee_id,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        mfa_enabled=current_user.mfa_enabled,
        last_login=current_user.last_login,
        roles=[
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": [],
                "created_at": role.created_at,
                "updated_at": role.updated_at,
            }
            for role in current_user.roles
        ],
        permissions=permissions,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """Change current user's password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = get_password_hash(password_data.new_password)

    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.PASSWORD_CHANGE,
        resource_type="user",
        resource_id=current_user.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description="User changed password",
    )

    return MessageResponse(message="Password changed successfully", success=True)
