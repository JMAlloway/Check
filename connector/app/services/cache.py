"""
In-memory image cache with TTL.

Caches decoded PNG images to reduce CPU usage for repeated requests.
"""
import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Tuple

from ..core.config import get_settings


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: bytes
    width: int
    height: int
    created_at: float
    expires_at: float
    hits: int = 0


class ImageCache:
    """
    LRU cache for decoded images with TTL.

    Features:
    - TTL-based expiration
    - LRU eviction when at capacity
    - Memory-aware (tracks total bytes)
    - Thread-safe via asyncio Lock
    """

    def __init__(
        self,
        ttl_seconds: int = None,
        max_items: int = None,
        max_bytes: int = None
    ):
        """
        Initialize the image cache.

        Args:
            ttl_seconds: Time-to-live for cache entries
            max_items: Maximum number of cached images
            max_bytes: Maximum total bytes to cache (default 100MB)
        """
        settings = get_settings()

        self._ttl = ttl_seconds or settings.CACHE_TTL_SECONDS
        self._max_items = max_items or settings.CACHE_MAX_ITEMS
        self._max_bytes = max_bytes or (100 * 1024 * 1024)  # 100MB default

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._total_bytes = 0
        self._lock = asyncio.Lock()

        # Stats
        self._hits = 0
        self._misses = 0

    def _make_key(self, path: str, page: int) -> str:
        """Create a cache key from path and page number."""
        key_str = f"{path}:{page}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get(self, path: str, page: int) -> Optional[Tuple[bytes, int, int]]:
        """
        Get a cached image.

        Args:
            path: Image path
            page: Page number

        Returns:
            Tuple of (data, width, height) if cached, None otherwise
        """
        key = self._make_key(path, page)

        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if time.time() > entry.expires_at:
                self._total_bytes -= len(entry.data)
                del self._cache[key]
                self._misses += 1
                return None

            # Update hit count and move to end (LRU)
            entry.hits += 1
            self._cache.move_to_end(key)
            self._hits += 1

            return entry.data, entry.width, entry.height

    async def put(
        self,
        path: str,
        page: int,
        data: bytes,
        width: int,
        height: int
    ):
        """
        Cache an image.

        Args:
            path: Image path
            page: Page number
            data: PNG image data
            width: Image width
            height: Image height
        """
        key = self._make_key(path, page)
        data_size = len(data)

        async with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._total_bytes -= len(old_entry.data)

            # Evict expired entries
            self._evict_expired()

            # Evict LRU entries until we have space
            while self._total_bytes + data_size > self._max_bytes:
                if not self._cache:
                    break
                oldest_key, oldest_entry = self._cache.popitem(last=False)
                self._total_bytes -= len(oldest_entry.data)

            # Evict if at item limit
            while len(self._cache) >= self._max_items:
                oldest_key, oldest_entry = self._cache.popitem(last=False)
                self._total_bytes -= len(oldest_entry.data)

            # Add new entry
            now = time.time()
            entry = CacheEntry(
                data=data,
                width=width,
                height=height,
                created_at=now,
                expires_at=now + self._ttl
            )
            self._cache[key] = entry
            self._total_bytes += data_size

    def _evict_expired(self):
        """Remove expired entries (called under lock)."""
        now = time.time()
        expired_keys = [
            k for k, v in self._cache.items()
            if v.expires_at < now
        ]
        for key in expired_keys:
            entry = self._cache.pop(key)
            self._total_bytes -= len(entry.data)

    async def clear(self):
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()
            self._total_bytes = 0

    async def stats(self) -> dict:
        """Get cache statistics."""
        async with self._lock:
            total_hits = sum(e.hits for e in self._cache.values())
            return {
                "items": len(self._cache),
                "bytes": self._total_bytes,
                "max_items": self._max_items,
                "max_bytes": self._max_bytes,
                "ttl_seconds": self._ttl,
                "cache_hits": self._hits,
                "cache_misses": self._misses,
                "hit_rate": self._hits / (self._hits + self._misses)
                           if (self._hits + self._misses) > 0 else 0.0
            }


# Singleton instance
_image_cache: Optional[ImageCache] = None


def get_image_cache() -> ImageCache:
    """Get the image cache singleton."""
    global _image_cache
    if _image_cache is None:
        _image_cache = ImageCache()
    return _image_cache


def reset_image_cache():
    """Reset the image cache singleton (for testing)."""
    global _image_cache
    _image_cache = None
