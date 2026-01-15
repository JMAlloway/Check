"""Structured security event logging for SOC2 compliance.

This module provides a centralized way to log security-relevant events
in a structured format suitable for SIEM ingestion and audit trails.

All security events follow a consistent schema:
- timestamp: ISO8601 UTC timestamp
- event_type: Hierarchical event type (e.g., security.auth.login_success)
- severity: info, warning, error, critical
- user_id: User who triggered the event (if known)
- tenant_id: Tenant context (if applicable)
- ip_address: Client IP address
- user_agent: Client user agent
- details: Event-specific additional data

Usage:
    from app.core.security_events import SecurityEventLogger

    logger = SecurityEventLogger()
    logger.log_login_success(user_id="...", tenant_id="...", ip="...", user_agent="...")
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# Dedicated security logger - configure to send to SIEM
security_logger = logging.getLogger("security.events")


class EventSeverity(str, Enum):
    """Security event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SecurityEventType(str, Enum):
    """Enumeration of all security event types.

    Hierarchical naming: category.subcategory.event
    """
    # Authentication events
    AUTH_LOGIN_SUCCESS = "security.auth.login_success"
    AUTH_LOGIN_FAILURE = "security.auth.login_failure"
    AUTH_LOGOUT = "security.auth.logout"
    AUTH_TOKEN_REFRESH = "security.auth.token_refresh"
    AUTH_TOKEN_INVALID = "security.auth.token_invalid"
    AUTH_MFA_REQUIRED = "security.auth.mfa_required"
    AUTH_MFA_SUCCESS = "security.auth.mfa_success"
    AUTH_MFA_FAILURE = "security.auth.mfa_failure"
    AUTH_PASSWORD_CHANGE = "security.auth.password_change"
    AUTH_PASSWORD_RESET = "security.auth.password_reset"

    # Access control events
    ACCESS_DENIED = "security.access.denied"
    ACCESS_CROSS_TENANT = "security.access.cross_tenant"
    ACCESS_PRIVILEGE_ESCALATION = "security.access.privilege_escalation"

    # Image token events
    IMAGE_TOKEN_CREATED = "security.image.token_created"
    IMAGE_TOKEN_USED = "security.image.token_used"
    IMAGE_TOKEN_EXPIRED = "security.image.token_expired"
    IMAGE_TOKEN_INVALID = "security.image.token_invalid"

    # Rate limiting events
    RATE_LIMIT_EXCEEDED = "security.rate.limit_exceeded"
    RATE_LIMIT_WARNING = "security.rate.limit_warning"

    # Data access events
    DATA_EXPORT = "security.data.export"
    DATA_BULK_ACCESS = "security.data.bulk_access"
    DATA_SENSITIVE_VIEW = "security.data.sensitive_view"

    # Admin events
    ADMIN_USER_CREATED = "security.admin.user_created"
    ADMIN_USER_MODIFIED = "security.admin.user_modified"
    ADMIN_USER_DISABLED = "security.admin.user_disabled"
    ADMIN_ROLE_CHANGED = "security.admin.role_changed"
    ADMIN_CONFIG_CHANGED = "security.admin.config_changed"

    # System events
    SYSTEM_STARTUP = "security.system.startup"
    SYSTEM_SHUTDOWN = "security.system.shutdown"
    SYSTEM_CONFIG_RELOAD = "security.system.config_reload"


class SecurityEventLogger:
    """Structured security event logger for SOC2 compliance.

    Logs security events in a consistent JSON format suitable for
    SIEM ingestion, audit trails, and compliance reporting.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize the security event logger.

        Args:
            logger: Optional custom logger. Defaults to security.events logger.
        """
        self.logger = logger or security_logger

    def _log_event(
        self,
        event_type: SecurityEventType,
        severity: EventSeverity,
        user_id: str | None = None,
        tenant_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log a security event with structured data.

        Args:
            event_type: The type of security event
            severity: Event severity level
            user_id: ID of user who triggered the event
            tenant_id: Tenant context
            ip_address: Client IP address
            user_agent: Client user agent string
            resource_type: Type of resource accessed (e.g., "check_item")
            resource_id: ID of resource accessed
            details: Additional event-specific data

        Returns:
            The logged event data for testing/verification
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "severity": severity.value,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "ip_address": ip_address,
            "user_agent": user_agent[:500] if user_agent else None,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
        }

        # Log at appropriate level
        log_level = {
            EventSeverity.INFO: logging.INFO,
            EventSeverity.WARNING: logging.WARNING,
            EventSeverity.ERROR: logging.ERROR,
            EventSeverity.CRITICAL: logging.CRITICAL,
        }.get(severity, logging.INFO)

        self.logger.log(log_level, json.dumps(event))
        return event

    # Authentication events

    def log_login_success(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        mfa_used: bool = False,
    ) -> dict[str, Any]:
        """Log successful login."""
        return self._log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            severity=EventSeverity.INFO,
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"mfa_used": mfa_used},
        )

    def log_login_failure(
        self,
        username: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str = "invalid_credentials",
    ) -> dict[str, Any]:
        """Log failed login attempt."""
        return self._log_event(
            event_type=SecurityEventType.AUTH_LOGIN_FAILURE,
            severity=EventSeverity.WARNING,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"username": username, "reason": reason},
        )

    def log_logout(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log user logout."""
        return self._log_event(
            event_type=SecurityEventType.AUTH_LOGOUT,
            severity=EventSeverity.INFO,
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
        )

    def log_token_refresh(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log token refresh."""
        return self._log_event(
            event_type=SecurityEventType.AUTH_TOKEN_REFRESH,
            severity=EventSeverity.INFO,
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
        )

    def log_mfa_failure(
        self,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Log MFA verification failure."""
        return self._log_event(
            event_type=SecurityEventType.AUTH_MFA_FAILURE,
            severity=EventSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # Access control events

    def log_access_denied(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        required_permission: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log authorization denial."""
        return self._log_event(
            event_type=SecurityEventType.ACCESS_DENIED,
            severity=EventSeverity.WARNING,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details={"required_permission": required_permission},
        )

    def log_cross_tenant_attempt(
        self,
        user_id: str,
        user_tenant_id: str,
        resource_tenant_id: str,
        resource_type: str,
        resource_id: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log cross-tenant access attempt (CRITICAL - potential breach)."""
        return self._log_event(
            event_type=SecurityEventType.ACCESS_CROSS_TENANT,
            severity=EventSeverity.CRITICAL,
            user_id=user_id,
            tenant_id=user_tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details={
                "user_tenant_id": user_tenant_id,
                "resource_tenant_id": resource_tenant_id,
            },
        )

    # Image token events

    def log_image_token_created(
        self,
        user_id: str,
        tenant_id: str,
        token_id: str,
        image_id: str,
        expires_at: str,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log image access token creation."""
        return self._log_event(
            event_type=SecurityEventType.IMAGE_TOKEN_CREATED,
            severity=EventSeverity.INFO,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="image_access_token",
            resource_id=token_id,
            ip_address=ip_address,
            details={"image_id": image_id, "expires_at": expires_at},
        )

    def log_image_token_used(
        self,
        token_id: str,
        image_id: str,
        tenant_id: str,
        created_by_user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Log image access token consumption."""
        return self._log_event(
            event_type=SecurityEventType.IMAGE_TOKEN_USED,
            severity=EventSeverity.INFO,
            user_id=created_by_user_id,
            tenant_id=tenant_id,
            resource_type="image_access_token",
            resource_id=token_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"image_id": image_id},
        )

    def log_image_token_invalid(
        self,
        token_id: str,
        reason: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Log invalid/expired/used token access attempt."""
        return self._log_event(
            event_type=SecurityEventType.IMAGE_TOKEN_INVALID,
            severity=EventSeverity.WARNING,
            resource_type="image_access_token",
            resource_id=token_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"reason": reason},
        )

    # Rate limiting events

    def log_rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Log rate limit exceeded."""
        return self._log_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=EventSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            details={"endpoint": endpoint, "limit": limit},
        )

    # Admin events

    def log_user_created(
        self,
        admin_user_id: str,
        tenant_id: str,
        created_user_id: str,
        created_username: str,
        roles: list[str],
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log user account creation."""
        return self._log_event(
            event_type=SecurityEventType.ADMIN_USER_CREATED,
            severity=EventSeverity.INFO,
            user_id=admin_user_id,
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=created_user_id,
            ip_address=ip_address,
            details={"username": created_username, "roles": roles},
        )

    def log_user_disabled(
        self,
        admin_user_id: str,
        tenant_id: str,
        disabled_user_id: str,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log user account disabling."""
        return self._log_event(
            event_type=SecurityEventType.ADMIN_USER_DISABLED,
            severity=EventSeverity.INFO,
            user_id=admin_user_id,
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=disabled_user_id,
            ip_address=ip_address,
            details={"reason": reason},
        )

    def log_role_changed(
        self,
        admin_user_id: str,
        tenant_id: str,
        target_user_id: str,
        old_roles: list[str],
        new_roles: list[str],
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Log role assignment change."""
        return self._log_event(
            event_type=SecurityEventType.ADMIN_ROLE_CHANGED,
            severity=EventSeverity.INFO,
            user_id=admin_user_id,
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=target_user_id,
            ip_address=ip_address,
            details={"old_roles": old_roles, "new_roles": new_roles},
        )


# Global instance for convenience
security_events = SecurityEventLogger()
