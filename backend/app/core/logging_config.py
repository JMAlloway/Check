"""Structured logging configuration for SIEM integration.

Provides JSON-formatted logging suitable for:
- Splunk
- Elasticsearch/ELK Stack
- AWS CloudWatch
- Datadog
- Any JSON-based log aggregation system

All logs include:
- ISO8601 timestamp
- Log level
- Logger name
- Event type (for filtering)
- Correlation ID (request tracking)
- Additional structured data

Security events are tagged for easy SIEM rule creation.
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.core.config import settings


# Log directory for file-based shipping
LOG_DIR = Path("/var/log/check-review")


class SIEMJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for SIEM compatibility.

    Adds required fields for security monitoring:
    - @timestamp: ISO8601 timestamp (ELK compatible)
    - level: Log level
    - service: Service name
    - environment: Deployment environment
    - event_type: For SIEM filtering
    """

    def __init__(self, *args, **kwargs):
        # Include all standard fields
        super().__init__(
            *args,
            fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
            rename_fields={
                'asctime': '@timestamp',
                'levelname': 'level',
                'name': 'logger',
            },
            **kwargs
        )

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add SIEM-required fields to every log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO8601 format
        log_record['@timestamp'] = datetime.now(timezone.utc).isoformat()

        # Add service metadata
        log_record['service'] = {
            'name': settings.APP_NAME,
            'version': settings.APP_VERSION,
            'environment': settings.ENVIRONMENT,
        }

        # Ensure level is uppercase for consistency
        if 'level' in log_record:
            log_record['level'] = log_record['level'].upper()

        # Add event_type if not present (for filtering)
        if 'event_type' not in log_record:
            log_record['event_type'] = f"log.{record.name}"

        # Add source file information for debugging
        log_record['source'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
        }

        # Add process/thread info for concurrency debugging
        log_record['process'] = {
            'id': record.process,
            'name': record.processName,
            'thread_id': record.thread,
            'thread_name': record.threadName,
        }


class SecurityEventFilter(logging.Filter):
    """Filter to tag security-relevant events.

    Adds 'is_security_event' flag and 'soc2_control' when applicable.
    """

    SECURITY_LOGGERS = {
        'security.auth',
        'security.events',
        'security.access',
        'alertmanager.webhook',
        'frontend.monitoring',
    }

    SECURITY_KEYWORDS = {
        'login', 'logout', 'authentication', 'authorization',
        'permission', 'access', 'denied', 'blocked', 'violation',
        'tenant', 'cross-tenant', 'token', 'session', 'mfa',
        'alert', 'security', 'breach', 'attack',
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Add security tags to relevant log records."""
        # Check if from security logger
        is_security_logger = any(
            record.name.startswith(logger)
            for logger in self.SECURITY_LOGGERS
        )

        # Check message for security keywords
        msg_lower = str(record.getMessage()).lower()
        has_security_keyword = any(
            keyword in msg_lower
            for keyword in self.SECURITY_KEYWORDS
        )

        # Tag the record
        record.is_security_event = is_security_logger or has_security_keyword

        # Add SOC2 control reference if present in extra
        if hasattr(record, 'soc2_control'):
            pass  # Already set
        elif is_security_logger:
            record.soc2_control = 'CC6.1'  # Default for security events

        return True  # Always allow through


def configure_logging() -> None:
    """Configure structured logging for the application.

    Sets up:
    1. Console handler with JSON formatting
    2. File handlers for different log types (if log directory exists)
    3. Security event filtering
    4. Log rotation

    Call this at application startup.
    """
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create JSON formatter
    json_formatter = SIEMJsonFormatter()

    # Console handler - always enabled
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    console_handler.addFilter(SecurityEventFilter())
    root_logger.addHandler(console_handler)

    # File handlers - only if log directory exists (production)
    if LOG_DIR.exists():
        _setup_file_handlers(json_formatter)

    # Configure specific loggers
    _configure_uvicorn_loggers(json_formatter)

    logging.info(
        "Logging configured",
        extra={
            "event_type": "system.startup.logging_configured",
            "log_level": "INFO",
            "file_logging": LOG_DIR.exists(),
        }
    )


def _setup_file_handlers(formatter: logging.Formatter) -> None:
    """Set up rotating file handlers for different log types."""
    root_logger = logging.getLogger()

    # Application logs - rotated daily, keep 30 days
    app_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "application.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    app_handler.setFormatter(formatter)
    app_handler.addFilter(SecurityEventFilter())
    root_logger.addHandler(app_handler)

    # Security logs - separate file for SIEM, rotated daily, keep 365 days
    security_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "security.log",
        when="midnight",
        interval=1,
        backupCount=365,
        encoding="utf-8",
    )
    security_handler.setFormatter(formatter)
    security_handler.addFilter(SecurityEventFilter())
    security_handler.addFilter(_SecurityOnlyFilter())  # Only security events
    root_logger.addHandler(security_handler)

    # Audit logs - separate file, rotated daily, keep for compliance period
    audit_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "audit.log",
        when="midnight",
        interval=1,
        backupCount=2555,  # ~7 years for compliance
        encoding="utf-8",
    )
    audit_handler.setFormatter(formatter)
    audit_handler.addFilter(_AuditOnlyFilter())  # Only audit events
    root_logger.addHandler(audit_handler)

    # Access logs - high volume, keep 90 days
    access_logger = logging.getLogger("uvicorn.access")
    access_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "access.log",
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    access_handler.setFormatter(formatter)
    access_logger.addHandler(access_handler)


class _SecurityOnlyFilter(logging.Filter):
    """Filter that only allows security events."""

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, 'is_security_event', False)


class _AuditOnlyFilter(logging.Filter):
    """Filter that only allows audit events."""

    AUDIT_EVENT_TYPES = {
        'audit.', 'decision.', 'login', 'logout',
        'permission', 'role', 'user.', 'mfa',
    }

    def filter(self, record: logging.LogRecord) -> bool:
        event_type = getattr(record, 'event_type', '')
        return any(
            event_type.startswith(prefix) or prefix in event_type
            for prefix in self.AUDIT_EVENT_TYPES
        )


def _configure_uvicorn_loggers(formatter: logging.Formatter) -> None:
    """Configure uvicorn loggers to use JSON format."""
    for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        logger = logging.getLogger(logger_name)
        # Remove default handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        # Add JSON handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)


# =============================================================================
# SIEM Export Utilities
# =============================================================================

def format_security_event(
    event_type: str,
    severity: str,
    description: str,
    user_id: str | None = None,
    username: str | None = None,
    ip_address: str | None = None,
    tenant_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    soc2_control: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Format a security event for SIEM ingestion.

    Returns a dict suitable for logging.info(..., extra=...).

    Usage:
        logger.info(
            "User login successful",
            extra=format_security_event(
                event_type="security.auth.login_success",
                severity="info",
                description="User logged in successfully",
                user_id=user.id,
                username=user.username,
                ip_address=request.client.host,
            )
        )
    """
    event = {
        "event_type": event_type,
        "severity": severity,
        "description": description,
        "is_security_event": True,
    }

    if user_id:
        event["user_id"] = user_id
    if username:
        event["username"] = username
    if ip_address:
        event["ip_address"] = ip_address
    if tenant_id:
        event["tenant_id"] = tenant_id
    if resource_type:
        event["resource_type"] = resource_type
    if resource_id:
        event["resource_id"] = resource_id
    if soc2_control:
        event["soc2_control"] = soc2_control
    if metadata:
        event["metadata"] = metadata

    return event
