"""Authentication service."""

import hashlib
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import Role, User, UserSession
from app.schemas.auth import Token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User | None, str | None]:
        """
        Authenticate a user by username and password.

        Returns:
            Tuple of (user, error_message)
        """
        # Find user by username or email
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where((User.username == username) | (User.email == username))
        )
        user = result.scalar_one_or_none()

        if not user:
            return None, "Invalid username or password"

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            return None, f"Account locked until {user.locked_until.isoformat()}"

        # Verify password
        if not verify_password(password, user.hashed_password):
            # Increment failed attempts
            user.failed_login_attempts += 1

            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)

            await self.db.commit()
            return None, "Invalid username or password"

        # Check if user is active
        if not user.is_active:
            return None, "Account is deactivated"

        # Check IP restrictions (allowed_ips is JSONB array)
        if user.allowed_ips:
            if ip_address and ip_address not in user.allowed_ips:
                return None, "Access denied from this IP address"

        # Reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)

        await self.db.commit()

        return user, None

    async def create_tokens(
        self,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None,
    ) -> Token:
        """Create access and refresh tokens for a user."""
        # Gather roles and permissions for token
        roles = [role.name for role in user.roles]
        permissions = []
        for role in user.roles:
            for perm in role.permissions:
                perm_str = f"{perm.resource}:{perm.action}"
                if perm_str not in permissions:
                    permissions.append(perm_str)

        # Create tokens
        access_token = create_access_token(
            subject=user.id,
            additional_claims={
                "roles": roles,
                "permissions": permissions,
                "username": user.username,
            },
        )
        refresh_token = create_refresh_token(subject=user.id)

        # Store session with device fingerprint for tracking
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(session)
        await self.db.commit()

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Token | None:
        """Refresh access token using refresh token."""
        # Decode and validate refresh token
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")

        # Verify session exists and is active
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.token_hash == token_hash,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            return None

        # Get user
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        # Preserve device fingerprint from old session
        device_fingerprint = session.device_fingerprint

        # Revoke old session
        session.is_active = False
        session.revoked_at = datetime.now(timezone.utc)

        # Create new tokens with preserved device fingerprint
        return await self.create_tokens(user, ip_address, user_agent, device_fingerprint)

    async def logout(self, refresh_token: str) -> bool:
        """Logout user by revoking their session."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        result = await self.db.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        session = result.scalar_one_or_none()

        if session:
            session.is_active = False
            session.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
            return True

        return False

    async def logout_all_sessions(self, user_id: str) -> int:
        """Logout all sessions for a user."""
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
            )
        )
        sessions = result.scalars().all()

        count = 0
        for session in sessions:
            session.is_active = False
            session.revoked_at = datetime.now(timezone.utc)
            count += 1

        await self.db.commit()
        return count
