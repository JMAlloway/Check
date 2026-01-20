"""
Image Connector Service.

Manages bank-side image connectors from the SaaS side.
Handles:
- Connector CRUD operations
- JWT token generation for image requests
- Health check polling
- Key rotation
- Request logging
"""

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.image_connector import (
    ConnectorAuditLog,
    ConnectorRequestLog,
    ConnectorStatus,
    ImageConnector,
)


class ImageConnectorError(Exception):
    """Base exception for connector errors."""

    pass


class ConnectorNotFoundError(ImageConnectorError):
    """Raised when connector is not found."""

    pass


class ConnectorUnavailableError(ImageConnectorError):
    """Raised when connector is unavailable."""

    pass


class ImageConnectorService:
    """
    Service for managing image connectors.
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self._db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_connector(
        self,
        tenant_id: str,
        connector_id: str,
        name: str,
        base_url: str,
        public_key_pem: str,
        created_by_user_id: str,
        description: str = None,
        token_expiry_seconds: int = 120,
    ) -> ImageConnector:
        """
        Create a new image connector.

        Args:
            tenant_id: Tenant ID
            connector_id: Unique connector identifier
            name: Human-friendly name
            base_url: Base URL for the connector
            public_key_pem: RSA public key in PEM format
            created_by_user_id: User creating the connector
            description: Optional description
            token_expiry_seconds: JWT token expiry (60-300)

        Returns:
            Created ImageConnector
        """
        # Generate key ID
        key_id = f"key-{secrets.token_hex(8)}"

        connector = ImageConnector(
            tenant_id=tenant_id,
            connector_id=connector_id,
            name=name,
            description=description,
            base_url=base_url.rstrip("/"),
            status=ConnectorStatus.INACTIVE,
            is_enabled=False,
            public_key_pem=public_key_pem,
            public_key_id=key_id,
            token_expiry_seconds=max(60, min(300, token_expiry_seconds)),
            created_by_user_id=created_by_user_id,
        )

        self._db.add(connector)
        await self._db.flush()

        # Log creation
        await self._log_audit(
            connector_id=connector.id,
            action="created",
            user_id=created_by_user_id,
            changes={"new": True},
        )

        return connector

    async def get_connector(
        self, tenant_id: str, connector_id: str = None, id: str = None
    ) -> Optional[ImageConnector]:
        """
        Get a connector by ID or connector_id.

        Args:
            tenant_id: Tenant ID
            connector_id: Connector's unique identifier
            id: Database ID

        Returns:
            ImageConnector if found
        """
        if id:
            stmt = select(ImageConnector).where(
                and_(ImageConnector.tenant_id == tenant_id, ImageConnector.id == id)
            )
        else:
            stmt = select(ImageConnector).where(
                and_(
                    ImageConnector.tenant_id == tenant_id,
                    ImageConnector.connector_id == connector_id,
                )
            )

        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_connectors(
        self, tenant_id: str, enabled_only: bool = False
    ) -> List[ImageConnector]:
        """
        List all connectors for a tenant.

        Args:
            tenant_id: Tenant ID
            enabled_only: If True, only return enabled connectors

        Returns:
            List of ImageConnectors
        """
        stmt = select(ImageConnector).where(ImageConnector.tenant_id == tenant_id)

        if enabled_only:
            stmt = stmt.where(ImageConnector.is_enabled == True)

        stmt = stmt.order_by(ImageConnector.priority, ImageConnector.name)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update_connector(
        self, tenant_id: str, connector_id: str, user_id: str, **updates
    ) -> ImageConnector:
        """
        Update a connector.

        Args:
            tenant_id: Tenant ID
            connector_id: Connector's unique identifier
            user_id: User making the update
            **updates: Fields to update

        Returns:
            Updated ImageConnector
        """
        connector = await self.get_connector(tenant_id, connector_id=connector_id)
        if not connector:
            raise ConnectorNotFoundError(f"Connector not found: {connector_id}")

        # Track changes
        changes = {}
        allowed_fields = {
            "name",
            "description",
            "base_url",
            "token_expiry_seconds",
            "timeout_seconds",
            "max_retries",
            "priority",
            "circuit_breaker_threshold",
            "circuit_breaker_timeout_seconds",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                old_value = getattr(connector, field)
                if old_value != value:
                    changes[field] = {"old": old_value, "new": value}
                    setattr(connector, field, value)

        if changes:
            connector.last_modified_by_user_id = user_id
            await self._log_audit(
                connector_id=connector.id, action="updated", user_id=user_id, changes=changes
            )

        return connector

    async def enable_connector(
        self, tenant_id: str, connector_id: str, user_id: str
    ) -> ImageConnector:
        """Enable a connector."""
        connector = await self.get_connector(tenant_id, connector_id=connector_id)
        if not connector:
            raise ConnectorNotFoundError(f"Connector not found: {connector_id}")

        connector.is_enabled = True
        connector.status = ConnectorStatus.ACTIVE
        connector.last_modified_by_user_id = user_id

        await self._log_audit(
            connector_id=connector.id,
            action="enabled",
            user_id=user_id,
            changes={"is_enabled": {"old": False, "new": True}},
        )

        return connector

    async def disable_connector(
        self, tenant_id: str, connector_id: str, user_id: str
    ) -> ImageConnector:
        """Disable a connector."""
        connector = await self.get_connector(tenant_id, connector_id=connector_id)
        if not connector:
            raise ConnectorNotFoundError(f"Connector not found: {connector_id}")

        connector.is_enabled = False
        connector.status = ConnectorStatus.INACTIVE
        connector.last_modified_by_user_id = user_id

        await self._log_audit(
            connector_id=connector.id,
            action="disabled",
            user_id=user_id,
            changes={"is_enabled": {"old": True, "new": False}},
        )

        return connector

    async def delete_connector(self, tenant_id: str, connector_id: str, user_id: str):
        """Delete a connector."""
        connector = await self.get_connector(tenant_id, connector_id=connector_id)
        if not connector:
            raise ConnectorNotFoundError(f"Connector not found: {connector_id}")

        await self._log_audit(
            connector_id=connector.id, action="deleted", user_id=user_id, changes={"deleted": True}
        )

        await self._db.delete(connector)

    # =========================================================================
    # Key Rotation
    # =========================================================================

    async def rotate_public_key(
        self,
        tenant_id: str,
        connector_id: str,
        new_public_key_pem: str,
        user_id: str,
        overlap_hours: int = 24,
    ) -> ImageConnector:
        """
        Rotate the public key for a connector.

        The old key becomes secondary and remains valid for overlap_hours.

        Args:
            tenant_id: Tenant ID
            connector_id: Connector's unique identifier
            new_public_key_pem: New RSA public key in PEM format
            user_id: User performing rotation
            overlap_hours: Hours to keep old key valid

        Returns:
            Updated ImageConnector
        """
        connector = await self.get_connector(tenant_id, connector_id=connector_id)
        if not connector:
            raise ConnectorNotFoundError(f"Connector not found: {connector_id}")

        # Move current key to secondary
        connector.secondary_public_key_pem = connector.public_key_pem
        connector.secondary_public_key_id = connector.public_key_id
        connector.secondary_public_key_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=overlap_hours
        )

        # Set new primary key
        connector.public_key_pem = new_public_key_pem
        connector.public_key_id = f"key-{secrets.token_hex(8)}"
        connector.public_key_expires_at = None  # Primary never expires

        connector.status = ConnectorStatus.ROTATING
        connector.last_modified_by_user_id = user_id

        await self._log_audit(
            connector_id=connector.id,
            action="key_rotated",
            user_id=user_id,
            changes={
                "new_key_id": connector.public_key_id,
                "old_key_id": connector.secondary_public_key_id,
                "overlap_hours": overlap_hours,
            },
        )

        return connector

    # =========================================================================
    # Health Check
    # =========================================================================

    async def test_connection(self, tenant_id: str, connector_id: str, user_id: str) -> dict:
        """
        Test connection to a connector.

        Args:
            tenant_id: Tenant ID
            connector_id: Connector's unique identifier
            user_id: User performing test

        Returns:
            Health check response
        """
        connector = await self.get_connector(tenant_id, connector_id=connector_id)
        if not connector:
            raise ConnectorNotFoundError(f"Connector not found: {connector_id}")

        start_time = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=connector.timeout_seconds, verify=True  # Require valid TLS in production
            ) as client:
                response = await client.get(f"{connector.base_url}/healthz")
                latency_ms = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    health_data = response.json()

                    # Update connector metadata
                    connector.last_health_check_at = datetime.now(timezone.utc)
                    connector.last_health_check_status = "healthy"
                    connector.last_health_check_latency_ms = latency_ms
                    connector.health_check_failure_count = 0
                    connector.connector_version = health_data.get("version")
                    connector.connector_mode = health_data.get("mode")
                    connector.allowed_roots = health_data.get("allowed_roots")
                    connector.last_connection_test_at = datetime.now(timezone.utc)
                    connector.last_connection_test_success = True
                    connector.last_connection_test_result = "Connection successful"

                    if connector.status == ConnectorStatus.UNREACHABLE:
                        connector.status = ConnectorStatus.ACTIVE

                    return {"success": True, "latency_ms": latency_ms, "data": health_data}
                else:
                    connector.last_health_check_at = datetime.now(timezone.utc)
                    connector.last_health_check_status = "error"
                    connector.last_health_check_latency_ms = latency_ms
                    connector.health_check_failure_count += 1
                    connector.last_connection_test_at = datetime.now(timezone.utc)
                    connector.last_connection_test_success = False
                    connector.last_connection_test_result = f"HTTP {response.status_code}"

                    return {
                        "success": False,
                        "latency_ms": latency_ms,
                        "error": f"HTTP {response.status_code}",
                    }

        except httpx.ConnectError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            connector.last_health_check_at = datetime.now(timezone.utc)
            connector.last_health_check_status = "unreachable"
            connector.last_health_check_latency_ms = latency_ms
            connector.health_check_failure_count += 1
            connector.status = ConnectorStatus.UNREACHABLE
            connector.last_connection_test_at = datetime.now(timezone.utc)
            connector.last_connection_test_success = False
            connector.last_connection_test_result = str(e)

            return {
                "success": False,
                "latency_ms": latency_ms,
                "error": f"Connection failed: {str(e)}",
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            connector.last_connection_test_at = datetime.now(timezone.utc)
            connector.last_connection_test_success = False
            connector.last_connection_test_result = str(e)

            return {"success": False, "latency_ms": latency_ms, "error": str(e)}

    # =========================================================================
    # JWT Token Generation
    # =========================================================================

    def generate_image_token(
        self, connector: ImageConnector, user_id: str, org_id: str, roles: List[str]
    ) -> str:
        """
        Generate a JWT token for image requests.

        Args:
            connector: The connector to generate token for
            user_id: User ID (subject)
            org_id: Organization/tenant ID
            roles: User roles

        Returns:
            JWT token string
        """
        now = int(time.time())

        payload = {
            "sub": user_id,
            "org_id": org_id,
            "roles": roles,
            "iat": now,
            "exp": now + connector.token_expiry_seconds,
            "jti": str(uuid.uuid4()),
            "iss": connector.jwt_issuer,
            "connector_id": connector.connector_id,
        }

        # Sign with the SaaS private key
        # NOTE: In production, the SaaS has a private key that corresponds
        # to the public key configured on each connector
        token = jwt.encode(payload, settings.CONNECTOR_JWT_PRIVATE_KEY, algorithm="RS256")

        return token

    # =========================================================================
    # Request Logging
    # =========================================================================

    async def log_request(
        self,
        connector: ImageConnector,
        tenant_id: str,
        user_id: str,
        request_type: str,
        trace_number: str = None,
        check_date: str = None,
        path: str = None,
        side: str = None,
        success: bool = True,
        status_code: int = None,
        error_code: str = None,
        error_message: str = None,
        latency_ms: int = None,
        bytes_received: int = None,
        from_cache: bool = None,
        correlation_id: str = None,
    ):
        """Log an image request."""
        log_entry = ConnectorRequestLog(
            requested_at=datetime.now(timezone.utc),
            connector_id=connector.id if connector else None,
            connector_name=connector.name if connector else "unknown",
            tenant_id=tenant_id,
            user_id=user_id,
            request_type=request_type,
            trace_number=trace_number,
            check_date=check_date,
            path_hash=hashlib.sha256(path.encode()).hexdigest() if path else None,
            side=side,
            success=success,
            status_code=status_code,
            error_code=error_code,
            error_message=error_message[:500] if error_message else None,
            latency_ms=latency_ms,
            bytes_received=bytes_received,
            from_cache=from_cache,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )

        self._db.add(log_entry)

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _log_audit(
        self,
        connector_id: str,
        action: str,
        user_id: str,
        changes: dict,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log an audit event."""
        log_entry = ConnectorAuditLog(
            connector_id=connector_id,
            action=action,
            user_id=user_id,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._db.add(log_entry)


def generate_key_pair() -> tuple:
    """
    Generate a new RSA key pair.

    Returns:
        Tuple of (private_key_pem, public_key_pem)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    return private_pem, public_pem
