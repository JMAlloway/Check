"""
Security module for JWT validation and path allowlisting.

Implements:
- RS256 JWT validation with pinned public key
- Replay protection using JTI cache
- Path validation against allowed share roots
"""
import hashlib
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set, Tuple

import jwt
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
)

from .config import get_settings


@dataclass
class JWTClaims:
    """
    Validated JWT claims.

    Attributes:
        sub: Subject (user ID or service ID)
        org_id: Organization/tenant ID
        roles: List of roles
        exp: Expiration timestamp
        iat: Issued-at timestamp
        jti: JWT ID (for replay protection)
        iss: Issuer
    """
    sub: str
    org_id: str
    roles: List[str]
    exp: int
    iat: int
    jti: str
    iss: str

    def has_role(self, role: str) -> bool:
        """Check if claims include a specific role."""
        return role in self.roles

    def has_any_role(self, roles: List[str]) -> bool:
        """Check if claims include any of the specified roles."""
        return bool(set(self.roles) & set(roles))


class ReplayCache:
    """
    LRU cache for JTI replay protection.

    Stores recently seen JTIs with expiration timestamps.
    Uses OrderedDict for O(1) operations with LRU eviction.
    """

    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        """
        Initialize the replay cache.

        Args:
            max_size: Maximum number of JTIs to cache
            default_ttl: Default TTL in seconds
        """
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl

    def contains(self, jti: str) -> bool:
        """Check if a JTI is in the cache (and not expired)."""
        if jti not in self._cache:
            return False

        expiry = self._cache[jti]
        if time.time() > expiry:
            # Expired - remove and return False
            del self._cache[jti]
            return False

        return True

    def add(self, jti: str, exp_timestamp: float = None):
        """
        Add a JTI to the cache.

        Args:
            jti: The JWT ID to cache
            exp_timestamp: When this JTI expires (defaults to now + TTL)
        """
        # Evict expired entries periodically
        self._evict_expired()

        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        expiry = exp_timestamp or (time.time() + self._default_ttl)
        self._cache[jti] = expiry
        # Move to end (most recently used)
        self._cache.move_to_end(jti)

    def _evict_expired(self):
        """Remove expired entries from cache."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v < now]
        for k in expired:
            del self._cache[k]

    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)


class JWTValidator:
    """
    JWT validator for RS256 tokens.

    Validates tokens signed by the SaaS using a pinned public key.
    Includes replay protection via JTI caching.
    """

    def __init__(
        self,
        public_key: str = None,
        issuer: str = None,
        replay_cache_ttl: int = None,
        required_roles: List[str] = None
    ):
        """
        Initialize the JWT validator.

        Args:
            public_key: RSA public key in PEM format
            issuer: Expected token issuer
            replay_cache_ttl: TTL for replay cache in seconds
            required_roles: Roles required for image access
        """
        settings = get_settings()

        self._public_key = public_key or settings.JWT_PUBLIC_KEY
        self._issuer = issuer or settings.JWT_ISSUER
        self._algorithm = settings.JWT_ALGORITHM
        self._required_roles = required_roles or settings.IMAGE_ACCESS_ROLES

        # Replay protection cache
        ttl = replay_cache_ttl or settings.JWT_REPLAY_CACHE_TTL_SECONDS
        self._replay_cache = ReplayCache(default_ttl=ttl)

    def validate(self, token: str) -> Tuple[bool, Optional[JWTClaims], Optional[str]]:
        """
        Validate a JWT token.

        Args:
            token: The JWT token string

        Returns:
            Tuple of (is_valid, claims, error_message)
        """
        if not self._public_key:
            return False, None, "No public key configured"

        try:
            # Decode and verify signature
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={
                    "require": ["exp", "iat", "sub", "jti", "org_id"],
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                }
            )

            # Extract claims
            claims = JWTClaims(
                sub=payload.get("sub", ""),
                org_id=payload.get("org_id", ""),
                roles=payload.get("roles", []),
                exp=payload.get("exp", 0),
                iat=payload.get("iat", 0),
                jti=payload.get("jti", ""),
                iss=payload.get("iss", ""),
            )

            # Check for replay attack
            if self._replay_cache.contains(claims.jti):
                return False, None, "Token replay detected"

            # Add to replay cache
            self._replay_cache.add(claims.jti, claims.exp)

            return True, claims, None

        except ExpiredSignatureError:
            return False, None, "Token expired"
        except InvalidSignatureError:
            return False, None, "Invalid signature"
        except InvalidIssuerError:
            return False, None, "Invalid issuer"
        except DecodeError as e:
            return False, None, f"Token decode error: {str(e)}"
        except InvalidTokenError as e:
            return False, None, f"Invalid token: {str(e)}"
        except Exception as e:
            return False, None, f"Validation error: {str(e)}"

    def check_roles(self, claims: JWTClaims) -> Tuple[bool, Optional[str]]:
        """
        Check if claims have required roles for image access.

        Args:
            claims: Validated JWT claims

        Returns:
            Tuple of (has_access, error_message)
        """
        if claims.has_any_role(self._required_roles):
            return True, None

        return False, f"Missing required role. Need one of: {self._required_roles}"


class PathValidator:
    """
    Validates UNC paths against allowed share roots.

    Prevents path traversal attacks and ensures paths are within
    allowed directories.
    """

    def __init__(self, allowed_roots: List[str] = None):
        """
        Initialize the path validator.

        Args:
            allowed_roots: List of allowed UNC share roots
        """
        settings = get_settings()
        self._allowed_roots = allowed_roots or settings.ALLOWED_SHARE_ROOTS
        # Normalize roots for comparison
        self._normalized_roots = [
            self._normalize_path(root) for root in self._allowed_roots
        ]

    def _normalize_path(self, path: str) -> str:
        """
        Normalize a path for comparison.

        - Convert backslashes to forward slashes
        - Lowercase for case-insensitive comparison (Windows)
        - Remove trailing slashes
        - Collapse multiple slashes
        """
        normalized = path.replace("\\", "/")
        normalized = re.sub(r"/+", "/", normalized)
        normalized = normalized.rstrip("/")
        return normalized.lower()

    def validate(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a UNC path.

        Args:
            path: The UNC path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not path:
            return False, "Empty path"

        # Check for path traversal attempts
        if ".." in path:
            return False, "Path traversal detected"

        # Normalize for comparison
        normalized = self._normalize_path(path)

        # Check against allowed roots
        for root in self._normalized_roots:
            if normalized.startswith(root):
                return True, None

        return False, "Path not in allowed share roots"

    def hash_path(self, path: str) -> str:
        """
        Create a SHA256 hash of a path for audit logging.

        Never log raw paths - always use hashed version.

        Args:
            path: The path to hash

        Returns:
            SHA256 hex digest
        """
        return hashlib.sha256(path.encode()).hexdigest()

    def get_allowed_roots(self) -> List[str]:
        """Get the list of allowed share roots."""
        return self._allowed_roots.copy()


# Singleton instances
_jwt_validator: Optional[JWTValidator] = None
_path_validator: Optional[PathValidator] = None


def get_jwt_validator() -> JWTValidator:
    """Get the JWT validator singleton."""
    global _jwt_validator
    if _jwt_validator is None:
        _jwt_validator = JWTValidator()
    return _jwt_validator


def get_path_validator() -> PathValidator:
    """Get the path validator singleton."""
    global _path_validator
    if _path_validator is None:
        _path_validator = PathValidator()
    return _path_validator


def reset_validators():
    """Reset validator singletons (for testing)."""
    global _jwt_validator, _path_validator
    _jwt_validator = None
    _path_validator = None
