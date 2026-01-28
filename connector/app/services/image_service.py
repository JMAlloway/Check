"""
Image service that orchestrates storage, decoding, and caching.

Main entry point for image retrieval operations.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from ..adapters import DecodedImage, ImageHandle, ImageSide
from ..adapters.factory import get_adapters
from ..adapters.interfaces import (
    DecodeError,
    ItemNotFoundError,
    StorageAccessError,
    UnsupportedFormatError,
)
from .cache import get_image_cache


@dataclass
class ImageResult:
    """Result of an image retrieval operation."""
    data: bytes
    width: int
    height: int
    content_type: str = "image/png"
    from_cache: bool = False


class ImageServiceError(Exception):
    """Base exception for image service errors."""
    error_code: str = "INTERNAL_ERROR"


class ImageNotFoundError(ImageServiceError):
    """Raised when an image is not found."""
    error_code = "NOT_FOUND"


class NoBackImageError(ImageServiceError):
    """Raised when back image is requested but doesn't exist."""
    error_code = "NO_BACK_IMAGE"


class PathNotAllowedError(ImageServiceError):
    """Raised when path is not in allowed roots."""
    error_code = "PATH_NOT_ALLOWED"


class ImageDecodeFailedError(ImageServiceError):
    """Raised when image decoding fails."""
    error_code = "IMAGE_DECODE_FAILED"


class UnsupportedImageFormatError(ImageServiceError):
    """Raised when image format is not supported."""
    error_code = "UNSUPPORTED_FORMAT"


class UpstreamIOError(ImageServiceError):
    """Raised when upstream storage fails."""
    error_code = "UPSTREAM_IO_ERROR"


class ImageService:
    """
    Service for retrieving and processing check images.

    Orchestrates:
    - Item resolution (by trace/date)
    - Storage access (by path)
    - Image decoding (TIFF to PNG)
    - Caching
    """

    def __init__(self):
        """Initialize the image service."""
        self._resolver, self._storage, self._decoder = get_adapters()
        self._cache = get_image_cache()

    async def get_by_handle(
        self,
        path: str,
        side: ImageSide = ImageSide.FRONT
    ) -> ImageResult:
        """
        Get an image by its storage path (UNC handle).

        Args:
            path: UNC path to the image file
            side: Which side of the check (front or back)

        Returns:
            ImageResult with PNG data

        Raises:
            ImageNotFoundError: If image doesn't exist
            NoBackImageError: If back requested but not available
            ImageDecodeFailedError: If decoding fails
            UpstreamIOError: If storage access fails
        """
        # Determine page number
        page = 1 if side == ImageSide.FRONT else 2

        # Check cache first
        cached = await self._cache.get(path, page)
        if cached:
            data, width, height = cached
            return ImageResult(
                data=data,
                width=width,
                height=height,
                from_cache=True
            )

        # Create handle for storage access
        handle = ImageHandle(path=path)

        # Read raw data from storage
        try:
            raw_data = await self._storage.read(handle)
        except FileNotFoundError:
            raise ImageNotFoundError(f"Image not found at path")
        except StorageAccessError as e:
            raise UpstreamIOError(str(e))
        except Exception as e:
            raise UpstreamIOError(f"Storage access failed: {str(e)}")

        # Check page count for back side requests
        page_count = await self._decoder.get_page_count(raw_data)
        if page > page_count:
            raise NoBackImageError("No back image available")

        # Decode image
        try:
            decoded = await self._decoder.decode(raw_data, page=page)
        except UnsupportedFormatError as e:
            raise UnsupportedImageFormatError(str(e))
        except DecodeError as e:
            raise ImageDecodeFailedError(str(e))
        except ValueError as e:
            raise NoBackImageError(str(e))

        # Cache the result
        await self._cache.put(
            path=path,
            page=page,
            data=decoded.data,
            width=decoded.width,
            height=decoded.height
        )

        return ImageResult(
            data=decoded.data,
            width=decoded.width,
            height=decoded.height,
            from_cache=False
        )

    async def get_by_item(
        self,
        trace_number: str,
        check_date: date,
        side: ImageSide = ImageSide.FRONT
    ) -> ImageResult:
        """
        Get an image by trace number and date.

        Args:
            trace_number: Check trace number
            check_date: Check date
            side: Which side of the check

        Returns:
            ImageResult with PNG data

        Raises:
            ImageNotFoundError: If item not found
            NoBackImageError: If back requested but not available
            ImageDecodeFailedError: If decoding fails
            UpstreamIOError: If storage access fails
        """
        # Resolve the item
        metadata = await self._resolver.resolve(trace_number, check_date)
        if not metadata:
            raise ImageNotFoundError(
                f"Item not found: trace={trace_number}, date={check_date}"
            )

        # Check if back image exists
        if side == ImageSide.BACK and not metadata.has_back_image:
            raise NoBackImageError("No back image available for this item")

        # Get the image by handle
        return await self.get_by_handle(metadata.image_handle.path, side)

    async def lookup_item(
        self,
        trace_number: str,
        check_date: date
    ) -> Optional[dict]:
        """
        Look up item metadata.

        Args:
            trace_number: Check trace number
            check_date: Check date

        Returns:
            Dict with masked metadata if found, None otherwise
        """
        metadata = await self._resolver.resolve(trace_number, check_date)
        if not metadata:
            return None

        return {
            "trace_number": metadata.trace_number,
            "check_date": metadata.check_date.isoformat(),
            "amount_cents": metadata.amount_cents,
            "check_number": metadata.check_number,
            "account_last4": metadata.account_last4,
            "is_onus": metadata.is_onus,
            "has_back_image": metadata.has_back_image
        }

    async def health_check(self) -> Tuple[bool, dict]:
        """
        Check health of all dependencies.

        Returns:
            Tuple of (all_healthy, status_dict)
        """
        resolver_ok, resolver_msg = await self._resolver.health_check()
        storage_ok, storage_msg = await self._storage.health_check()
        decoder_ok, decoder_msg = await self._decoder.health_check()

        cache_stats = await self._cache.stats()

        all_ok = resolver_ok and storage_ok and decoder_ok

        return all_ok, {
            "resolver": {"healthy": resolver_ok, "message": resolver_msg},
            "storage": {"healthy": storage_ok, "message": storage_msg},
            "decoder": {"healthy": decoder_ok, "message": decoder_msg},
            "cache": cache_stats
        }


# Singleton instance
_image_service: Optional[ImageService] = None


def get_image_service() -> ImageService:
    """Get the image service singleton."""
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service


def reset_image_service():
    """Reset the image service singleton (for testing)."""
    global _image_service
    _image_service = None
