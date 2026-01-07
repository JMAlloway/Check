"""Authentication endpoints."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.api.deps import DBSession, CurrentUser
from app.schemas.auth import LoginRequest, RefreshTokenRequest, Token, PasswordChangeRequest, LoginResponse, LoginUserInfo
from app.schemas.common import MessageResponse
from app.schemas.user import CurrentUserResponse
from app.services.auth import AuthService
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.core.security import get_password_hash, verify_password
from app.core.config import settings

router = APIRouter()

# Cookie configuration
REFRESH_TOKEN_COOKIE = "refresh_token"
CSRF_TOKEN_COOKIE = "csrf_token"


def set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    """Set secure httpOnly cookie for refresh token and CSRF token."""
    # Refresh token: httpOnly (not accessible via JS), secure, same-site
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,  # Critical: prevents XSS from stealing token
        secure=settings.COOKIE_SECURE,  # HTTPS only in production
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",  # Only sent to auth endpoints
        domain=settings.COOKIE_DOMAIN,
    )
    # CSRF token: NOT httpOnly (JS needs to read it), but still secure
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=csrf_token,
        httponly=False,  # JS needs to read this to send in header
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies on logout."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path="/api/v1/auth",
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=CSRF_TOKEN_COOKIE,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: DBSession,
):
    """Authenticate user and return tokens with user info.

    Security: Refresh token is set as httpOnly cookie (XSS-safe).
    Access token is returned in body for memory-only storage.
    """
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
        description="User logged in successfully",
    )

    # Gather permissions from roles
    permissions = []
    for role in user.roles:
        for perm in role.permissions:
            perm_str = f"{perm.resource}:{perm.action}"
            if perm_str not in permissions:
                permissions.append(perm_str)

    # Generate CSRF token for cookie-based auth
    csrf_token = secrets.token_urlsafe(32)

    # Set refresh token in httpOnly cookie (secure from XSS)
    set_auth_cookies(response, tokens.refresh_token, csrf_token)

    # Return access token in body (stored in memory only, not localStorage)
    # Note: refresh_token is still included for backwards compatibility during migration
    # but frontend should NOT store it - it's in the httpOnly cookie
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token="",  # Don't expose in response body anymore
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user=LoginUserInfo(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_superuser=user.is_superuser,
            roles=[role.name for role in user.roles],
            permissions=permissions,
        ),
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    db: DBSession,
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
    refresh_data: RefreshTokenRequest | None = None,
):
    """Refresh access token using refresh token from httpOnly cookie.

    Security: Reads refresh token from httpOnly cookie (preferred) or body (legacy).
    CSRF protection via X-CSRF-Token header validation.
    """
    auth_service = AuthService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Prefer cookie-based refresh token (more secure)
    token_to_use = refresh_token_cookie
    if not token_to_use and refresh_data:
        # Fallback to body for backwards compatibility
        token_to_use = refresh_data.refresh_token

    if not token_to_use:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    # Validate CSRF token if using cookie-based auth
    if refresh_token_cookie:
        csrf_cookie = request.cookies.get(CSRF_TOKEN_COOKIE)
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )

    tokens = await auth_service.refresh_tokens(
        refresh_token=token_to_use,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not tokens:
        # Clear invalid cookies
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Generate new CSRF token and update cookies with new refresh token
    csrf_token = secrets.token_urlsafe(32)
    set_auth_cookies(response, tokens.refresh_token, csrf_token)

    # Return access token only (refresh token is in cookie)
    return Token(
        access_token=tokens.access_token,
        refresh_token="",  # Don't expose in body
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: DBSession,
    current_user: CurrentUser,
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
    refresh_data: RefreshTokenRequest | None = None,
):
    """Logout user and revoke refresh token.

    Security: Clears httpOnly cookies and revokes token server-side.
    """
    auth_service = AuthService(db)
    audit_service = AuditService(db)

    # Get token from cookie (preferred) or body (legacy)
    token_to_revoke = refresh_token_cookie
    if not token_to_revoke and refresh_data:
        token_to_revoke = refresh_data.refresh_token

    if token_to_revoke:
        await auth_service.logout(token_to_revoke)

    # Always clear cookies on logout
    clear_auth_cookies(response)

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
