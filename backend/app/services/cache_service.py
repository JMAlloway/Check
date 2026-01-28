"""
Redis caching service for policies and permissions.

Provides caching layer to reduce database load for frequently accessed data:
- User permissions (per session)
- Policy rules (per tenant)
- Role definitions
- Audit packet downloads (with tenant/user ownership enforcement)
"""

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis caching service for performance optimization."""

    # Cache key prefixes
    PREFIX_USER_PERMISSIONS = "perms:user:"
    PREFIX_TENANT_POLICIES = "policies:tenant:"
    PREFIX_ROLE = "role:"
    PREFIX_POLICY_VERSION = "policy:version:"
    PREFIX_RATE_LIMIT = "ratelimit:"
    PREFIX_AUDIT_PACKET = "audit:packet:"

    # Default TTLs
    TTL_USER_PERMISSIONS = timedelta(minutes=15)
    TTL_POLICIES = timedelta(minutes=30)
    TTL_ROLES = timedelta(hours=1)
    TTL_AUDIT_PACKET = timedelta(hours=1)

    def __init__(self, redis_url: str | None = None):
        """Initialize cache service.

        Args:
            redis_url: Redis connection URL. Defaults to settings.REDIS_URL.
        """
        self._redis_url = redis_url or settings.REDIS_URL
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            try:
                self._redis = await redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Test connection
                await self._redis.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning("Failed to connect to Redis cache: %s", e)
                self._redis = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis cache disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._redis is not None

    async def _ensure_connected(self) -> bool:
        """Ensure Redis is connected, attempt reconnect if needed."""
        if not self._redis:
            await self.connect()
        return self._redis is not None

    # ==========================================================================
    # User Permissions Cache
    # ==========================================================================

    async def get_user_permissions(self, user_id: str, tenant_id: str) -> list[str] | None:
        """Get cached user permissions.

        Args:
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            List of permission strings or None if not cached
        """
        if not await self._ensure_connected():
            return None

        try:
            key = f"{self.PREFIX_USER_PERMISSIONS}{tenant_id}:{user_id}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Failed to get user permissions from cache: %s", e)
            return None

    async def set_user_permissions(
        self,
        user_id: str,
        tenant_id: str,
        permissions: list[str],
        ttl: timedelta | None = None,
    ) -> bool:
        """Cache user permissions.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            permissions: List of permission strings
            ttl: Cache TTL (defaults to TTL_USER_PERMISSIONS)

        Returns:
            True if cached successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_USER_PERMISSIONS}{tenant_id}:{user_id}"
            ttl = ttl or self.TTL_USER_PERMISSIONS
            await self._redis.setex(key, ttl, json.dumps(permissions))
            return True
        except Exception as e:
            logger.warning("Failed to set user permissions in cache: %s", e)
            return False

    async def invalidate_user_permissions(self, user_id: str, tenant_id: str) -> bool:
        """Invalidate cached user permissions.

        Args:
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            True if invalidated successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_USER_PERMISSIONS}{tenant_id}:{user_id}"
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning("Failed to invalidate user permissions: %s", e)
            return False

    async def invalidate_tenant_permissions(self, tenant_id: str) -> bool:
        """Invalidate all cached permissions for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            True if invalidated successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            pattern = f"{self.PREFIX_USER_PERMISSIONS}{tenant_id}:*"
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._redis.delete(*keys)
            return True
        except Exception as e:
            logger.warning("Failed to invalidate tenant permissions: %s", e)
            return False

    # ==========================================================================
    # Policy Cache
    # ==========================================================================

    async def get_active_policy(self, tenant_id: str) -> dict[str, Any] | None:
        """Get cached active policy for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Policy data dict or None if not cached
        """
        if not await self._ensure_connected():
            return None

        try:
            key = f"{self.PREFIX_TENANT_POLICIES}{tenant_id}:active"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Failed to get active policy from cache: %s", e)
            return None

    async def set_active_policy(
        self,
        tenant_id: str,
        policy_data: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> bool:
        """Cache active policy for tenant.

        Args:
            tenant_id: Tenant ID
            policy_data: Policy data to cache
            ttl: Cache TTL (defaults to TTL_POLICIES)

        Returns:
            True if cached successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_TENANT_POLICIES}{tenant_id}:active"
            ttl = ttl or self.TTL_POLICIES
            await self._redis.setex(key, ttl, json.dumps(policy_data))
            return True
        except Exception as e:
            logger.warning("Failed to set active policy in cache: %s", e)
            return False

    async def get_policy_version(self, policy_version_id: str) -> dict[str, Any] | None:
        """Get cached policy version with rules.

        Args:
            policy_version_id: Policy version ID

        Returns:
            Policy version data or None if not cached
        """
        if not await self._ensure_connected():
            return None

        try:
            key = f"{self.PREFIX_POLICY_VERSION}{policy_version_id}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Failed to get policy version from cache: %s", e)
            return None

    async def set_policy_version(
        self,
        policy_version_id: str,
        version_data: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> bool:
        """Cache policy version with rules.

        Args:
            policy_version_id: Policy version ID
            version_data: Version data including rules
            ttl: Cache TTL (defaults to TTL_POLICIES)

        Returns:
            True if cached successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_POLICY_VERSION}{policy_version_id}"
            ttl = ttl or self.TTL_POLICIES
            await self._redis.setex(key, ttl, json.dumps(version_data))
            return True
        except Exception as e:
            logger.warning("Failed to set policy version in cache: %s", e)
            return False

    async def invalidate_policy(self, tenant_id: str, policy_id: str | None = None) -> bool:
        """Invalidate policy cache.

        Args:
            tenant_id: Tenant ID
            policy_id: Specific policy ID (optional, invalidates all if None)

        Returns:
            True if invalidated successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            # Invalidate active policy
            key = f"{self.PREFIX_TENANT_POLICIES}{tenant_id}:active"
            await self._redis.delete(key)

            # If specific policy, invalidate its versions
            if policy_id:
                pattern = f"{self.PREFIX_POLICY_VERSION}{policy_id}:*"
                keys = []
                async for k in self._redis.scan_iter(match=pattern):
                    keys.append(k)
                if keys:
                    await self._redis.delete(*keys)

            return True
        except Exception as e:
            logger.warning("Failed to invalidate policy cache: %s", e)
            return False

    # ==========================================================================
    # Role Cache
    # ==========================================================================

    async def get_role(self, role_id: str) -> dict[str, Any] | None:
        """Get cached role with permissions.

        Args:
            role_id: Role ID

        Returns:
            Role data dict or None if not cached
        """
        if not await self._ensure_connected():
            return None

        try:
            key = f"{self.PREFIX_ROLE}{role_id}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Failed to get role from cache: %s", e)
            return None

    async def set_role(
        self,
        role_id: str,
        role_data: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> bool:
        """Cache role with permissions.

        Args:
            role_id: Role ID
            role_data: Role data including permissions
            ttl: Cache TTL (defaults to TTL_ROLES)

        Returns:
            True if cached successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_ROLE}{role_id}"
            ttl = ttl or self.TTL_ROLES
            await self._redis.setex(key, ttl, json.dumps(role_data))
            return True
        except Exception as e:
            logger.warning("Failed to set role in cache: %s", e)
            return False

    async def invalidate_role(self, role_id: str) -> bool:
        """Invalidate cached role.

        Args:
            role_id: Role ID

        Returns:
            True if invalidated successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_ROLE}{role_id}"
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning("Failed to invalidate role: %s", e)
            return False

    # ==========================================================================
    # Generic Cache Operations
    # ==========================================================================

    async def get(self, key: str) -> str | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not await self._ensure_connected():
            return None

        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.warning("Failed to get from cache: %s", e)
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: timedelta | int | None = None,
    ) -> bool:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL as timedelta or seconds

        Returns:
            True if cached successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            if ttl:
                await self._redis.setex(key, ttl, value)
            else:
                await self._redis.set(key, value)
            return True
        except Exception as e:
            logger.warning("Failed to set in cache: %s", e)
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning("Failed to delete from cache: %s", e)
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        if not await self._ensure_connected():
            return False

        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.warning("Failed to check cache existence: %s", e)
            return False

    # ==========================================================================
    # Audit Packet Cache (with tenant/user ownership enforcement)
    # ==========================================================================

    async def store_audit_packet(
        self,
        packet_id: str,
        pdf_bytes: bytes,
        tenant_id: str,
        user_id: str,
        check_item_id: str,
        ttl: timedelta | None = None,
    ) -> bool:
        """Store an audit packet with ownership metadata.

        SECURITY: Packets are stored with tenant_id and user_id binding.
        On retrieval, both must match to prevent cross-tenant/cross-user access.

        Args:
            packet_id: Unique packet identifier (UUID)
            pdf_bytes: PDF content bytes
            tenant_id: Tenant ID that generated the packet
            user_id: User ID that generated the packet
            check_item_id: Check item ID for additional verification
            ttl: Cache TTL (defaults to TTL_AUDIT_PACKET = 1 hour)

        Returns:
            True if stored successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_AUDIT_PACKET}{packet_id}"
            ttl = ttl or self.TTL_AUDIT_PACKET

            # Store PDF as base64 with ownership metadata
            # Base64 is required since Redis client uses decode_responses=True
            packet_data = {
                "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "check_item_id": check_item_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            await self._redis.setex(key, ttl, json.dumps(packet_data))
            logger.debug(
                "Stored audit packet %s for tenant=%s user=%s item=%s",
                packet_id,
                tenant_id,
                user_id,
                check_item_id,
            )
            return True
        except Exception as e:
            logger.error("Failed to store audit packet %s: %s", packet_id, e)
            return False

    async def retrieve_audit_packet(
        self,
        packet_id: str,
        tenant_id: str,
        user_id: str,
    ) -> tuple[bytes | None, str | None]:
        """Retrieve an audit packet with ownership verification.

        SECURITY: Enforces that the requesting user matches the user who
        generated the packet, AND they belong to the same tenant.

        Args:
            packet_id: Unique packet identifier
            tenant_id: Tenant ID of the requesting user
            user_id: User ID of the requesting user

        Returns:
            Tuple of (pdf_bytes, check_item_id) if found and authorized,
            (None, None) if not found or unauthorized.

            IMPORTANT: Returns (None, None) for BOTH "not found" and
            "unauthorized" to prevent information disclosure about
            which packets exist.
        """
        if not await self._ensure_connected():
            return None, None

        try:
            key = f"{self.PREFIX_AUDIT_PACKET}{packet_id}"
            data = await self._redis.get(key)

            if not data:
                logger.debug("Audit packet %s not found in cache", packet_id)
                return None, None

            packet_data = json.loads(data)

            # CRITICAL: Verify ownership - must match BOTH tenant AND user
            stored_tenant_id = packet_data.get("tenant_id")
            stored_user_id = packet_data.get("user_id")

            if stored_tenant_id != tenant_id:
                logger.warning(
                    "Audit packet access denied: tenant mismatch. "
                    "packet=%s stored_tenant=%s requesting_tenant=%s",
                    packet_id,
                    stored_tenant_id,
                    tenant_id,
                )
                return None, None

            if stored_user_id != user_id:
                logger.warning(
                    "Audit packet access denied: user mismatch. "
                    "packet=%s stored_user=%s requesting_user=%s",
                    packet_id,
                    stored_user_id,
                    user_id,
                )
                return None, None

            # Ownership verified - decode and return PDF
            pdf_bytes = base64.b64decode(packet_data["pdf_base64"])
            check_item_id = packet_data.get("check_item_id")

            logger.debug(
                "Retrieved audit packet %s for tenant=%s user=%s",
                packet_id,
                tenant_id,
                user_id,
            )
            return pdf_bytes, check_item_id

        except Exception as e:
            logger.error("Failed to retrieve audit packet %s: %s", packet_id, e)
            return None, None

    async def delete_audit_packet(self, packet_id: str) -> bool:
        """Delete an audit packet from cache.

        Args:
            packet_id: Unique packet identifier

        Returns:
            True if deleted successfully
        """
        if not await self._ensure_connected():
            return False

        try:
            key = f"{self.PREFIX_AUDIT_PACKET}{packet_id}"
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning("Failed to delete audit packet %s: %s", packet_id, e)
            return False


# Global cache instance
cache_service = CacheService()


async def get_cache() -> CacheService:
    """Get the global cache service instance.

    Returns:
        CacheService instance
    """
    if not cache_service.is_connected:
        await cache_service.connect()
    return cache_service
