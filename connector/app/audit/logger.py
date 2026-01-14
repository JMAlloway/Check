"""
Structured audit logging for the Bank-Side Connector.

All requests are logged as structured JSON with:
- No raw paths (only hashed)
- No image data
- No full account numbers
- Correlation IDs for tracing
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
import uuid

from ..core.config import get_settings


class AuditAction(str, Enum):
    """Audit action types."""
    IMAGE_REQUEST = "IMAGE_REQUEST"
    IMAGE_SERVED = "IMAGE_SERVED"
    IMAGE_DENIED = "IMAGE_DENIED"
    ITEM_LOOKUP = "ITEM_LOOKUP"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILED = "AUTH_FAILED"
    PATH_BLOCKED = "PATH_BLOCKED"
    DECODE_ERROR = "DECODE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    HEALTH_CHECK = "HEALTH_CHECK"


@dataclass
class AuditEvent:
    """
    Structured audit event.

    All fields are safe for logging - no PII or sensitive data.
    """
    # Request identification
    correlation_id: str
    timestamp: str
    connector_id: str
    mode: str

    # Action details
    action: str
    endpoint: str
    allow: bool

    # Optional context (never includes raw paths/images)
    org_id: Optional[str] = None
    user_id: Optional[str] = None
    trace_number: Optional[str] = None
    check_date: Optional[str] = None
    path_hash: Optional[str] = None  # SHA256 of path
    side: Optional[str] = None

    # Response metrics
    bytes_sent: int = 0
    latency_ms: int = 0

    # Error details
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = asdict(self)
        # Remove None values for cleaner logs
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, default=str)

    @classmethod
    def create(
        cls,
        action: AuditAction,
        endpoint: str,
        allow: bool,
        correlation_id: str = None,
        **kwargs
    ) -> "AuditEvent":
        """
        Create an audit event with automatic fields.

        Args:
            action: The audit action
            endpoint: API endpoint path
            allow: Whether the request was allowed
            correlation_id: Optional correlation ID
            **kwargs: Additional event fields

        Returns:
            Configured AuditEvent
        """
        settings = get_settings()

        return cls(
            correlation_id=correlation_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            connector_id=settings.CONNECTOR_ID,
            mode=settings.MODE.value,
            action=action.value,
            endpoint=endpoint,
            allow=allow,
            **kwargs
        )


class AuditLogger:
    """
    Async-safe structured audit logger.

    Writes JSON Lines format to audit log file.
    Thread-safe and async-friendly.
    """

    def __init__(self, log_dir: str = None, log_file: str = None):
        """
        Initialize the audit logger.

        Args:
            log_dir: Directory for log files
            log_file: Log file name
        """
        settings = get_settings()
        self._log_dir = Path(log_dir or settings.LOG_DIR)
        self._log_file = log_file or settings.AUDIT_LOG_FILE
        self._log_path = self._log_dir / self._log_file

        # Ensure log directory exists
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Configure Python logger as backup
        self._logger = logging.getLogger("connector.audit")
        self._setup_logger()

        # Write lock for file operations
        self._write_lock = asyncio.Lock()

    def _setup_logger(self):
        """Configure the Python logger."""
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    async def log(self, event: AuditEvent):
        """
        Log an audit event.

        Args:
            event: The audit event to log
        """
        json_line = event.to_json()

        # Write to file
        async with self._write_lock:
            try:
                def _write():
                    with open(self._log_path, "a") as f:
                        f.write(json_line + "\n")

                await asyncio.get_event_loop().run_in_executor(None, _write)
            except Exception as e:
                # Fallback to Python logger
                self._logger.error(f"Failed to write audit log: {e}")
                self._logger.info(json_line)

    async def log_image_request(
        self,
        endpoint: str,
        correlation_id: str,
        org_id: str = None,
        user_id: str = None,
        path: str = None,
        trace_number: str = None,
        check_date: str = None,
        side: str = None
    ):
        """Log an incoming image request."""
        event = AuditEvent.create(
            action=AuditAction.IMAGE_REQUEST,
            endpoint=endpoint,
            allow=True,  # Will be updated on completion
            correlation_id=correlation_id,
            org_id=org_id,
            user_id=user_id,
            path_hash=hashlib.sha256(path.encode()).hexdigest() if path else None,
            trace_number=trace_number,
            check_date=check_date,
            side=side
        )
        await self.log(event)

    async def log_image_served(
        self,
        endpoint: str,
        correlation_id: str,
        org_id: str = None,
        user_id: str = None,
        path: str = None,
        trace_number: str = None,
        check_date: str = None,
        side: str = None,
        bytes_sent: int = 0,
        latency_ms: int = 0
    ):
        """Log a successfully served image."""
        event = AuditEvent.create(
            action=AuditAction.IMAGE_SERVED,
            endpoint=endpoint,
            allow=True,
            correlation_id=correlation_id,
            org_id=org_id,
            user_id=user_id,
            path_hash=hashlib.sha256(path.encode()).hexdigest() if path else None,
            trace_number=trace_number,
            check_date=check_date,
            side=side,
            bytes_sent=bytes_sent,
            latency_ms=latency_ms
        )
        await self.log(event)

    async def log_denied(
        self,
        endpoint: str,
        correlation_id: str,
        error_code: str,
        error_message: str,
        org_id: str = None,
        user_id: str = None,
        path: str = None,
        latency_ms: int = 0
    ):
        """Log a denied request."""
        event = AuditEvent.create(
            action=AuditAction.IMAGE_DENIED,
            endpoint=endpoint,
            allow=False,
            correlation_id=correlation_id,
            org_id=org_id,
            user_id=user_id,
            path_hash=hashlib.sha256(path.encode()).hexdigest() if path else None,
            error_code=error_code,
            error_message=error_message,
            latency_ms=latency_ms
        )
        await self.log(event)

    async def log_auth_failed(
        self,
        endpoint: str,
        correlation_id: str,
        error_message: str
    ):
        """Log an authentication failure."""
        event = AuditEvent.create(
            action=AuditAction.AUTH_FAILED,
            endpoint=endpoint,
            allow=False,
            correlation_id=correlation_id,
            error_code="AUTH_FAILED",
            error_message=error_message
        )
        await self.log(event)

    async def log_path_blocked(
        self,
        endpoint: str,
        correlation_id: str,
        path: str,
        org_id: str = None,
        user_id: str = None
    ):
        """Log a blocked path access attempt."""
        event = AuditEvent.create(
            action=AuditAction.PATH_BLOCKED,
            endpoint=endpoint,
            allow=False,
            correlation_id=correlation_id,
            org_id=org_id,
            user_id=user_id,
            path_hash=hashlib.sha256(path.encode()).hexdigest(),
            error_code="PATH_NOT_ALLOWED",
            error_message="Path not in allowed share roots"
        )
        await self.log(event)


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the audit logger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def reset_audit_logger():
    """Reset the audit logger singleton (for testing)."""
    global _audit_logger
    _audit_logger = None
