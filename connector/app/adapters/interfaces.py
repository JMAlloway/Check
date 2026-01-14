"""
Abstract interfaces for Bank-Side Connector adapters.

These interfaces define contracts that must be implemented by both
DEMO and BANK mode adapters.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from io import BytesIO
from typing import Optional, List, Tuple


class ImageSide(str, Enum):
    """Side of the check image."""
    FRONT = "front"
    BACK = "back"


@dataclass
class ImageHandle:
    """
    Handle to an image in storage.

    Attributes:
        path: UNC path or storage identifier
        trace_number: Check trace number
        check_date: Date of the check
        is_multi_page: Whether the image file contains multiple pages (front/back)
        page_count: Number of pages in the image file
    """
    path: str
    trace_number: Optional[str] = None
    check_date: Optional[date] = None
    is_multi_page: bool = False
    page_count: int = 1


@dataclass
class ItemMetadata:
    """
    Minimal metadata for a check item.

    Attributes:
        trace_number: Unique trace number
        check_date: Date of the check
        amount_cents: Check amount in cents
        check_number: Check number (may be blank)
        account_last4: Last 4 digits of account number
        is_onus: True if ONUS, False if Transit
        image_handle: Handle to the image file
        has_back_image: Whether a back image exists
    """
    trace_number: str
    check_date: date
    amount_cents: int
    check_number: Optional[str]
    account_last4: str
    is_onus: bool
    image_handle: ImageHandle
    has_back_image: bool = True


@dataclass
class DecodedImage:
    """
    Decoded image ready for streaming.

    Attributes:
        data: PNG image data as bytes
        width: Image width in pixels
        height: Image height in pixels
        original_format: Original image format (e.g., "TIFF")
        page_number: Page number (1 for front, 2 for back)
        file_size: Size in bytes
    """
    data: bytes
    width: int
    height: int
    original_format: str
    page_number: int
    file_size: int = field(default=0, init=False)

    def __post_init__(self):
        self.file_size = len(self.data)


class ItemResolver(ABC):
    """
    Abstract interface for resolving check items to image handles.

    Implementations:
    - DemoItemResolver: Uses JSON/SQLite index for demo mode
    - BankItemResolver: Queries bank's item feed or index
    """

    @abstractmethod
    async def resolve(
        self,
        trace_number: str,
        check_date: date
    ) -> Optional[ItemMetadata]:
        """
        Resolve a check item by trace number and date.

        Args:
            trace_number: The check's trace number
            check_date: The date of the check

        Returns:
            ItemMetadata if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_image_handle(
        self,
        trace_number: str,
        check_date: date,
        side: ImageSide
    ) -> Optional[ImageHandle]:
        """
        Get the image handle for a specific side of a check.

        Args:
            trace_number: The check's trace number
            check_date: The date of the check
            side: Which side of the check (front or back)

        Returns:
            ImageHandle if found, None otherwise

        Note:
            For multi-page images, returns the same handle for both sides.
            The page number is determined by the side parameter.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Tuple[bool, str]:
        """
        Check if the item resolver is healthy.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        pass


class StorageProvider(ABC):
    """
    Abstract interface for reading raw image data from storage.

    Implementations:
    - DemoStorageProvider: Reads from local filesystem
    - BankStorageProvider: Reads from UNC paths using SMB
    """

    @abstractmethod
    async def read(self, handle: ImageHandle) -> bytes:
        """
        Read raw image data from storage.

        Args:
            handle: The image handle to read

        Returns:
            Raw bytes of the image file

        Raises:
            FileNotFoundError: If the image doesn't exist
            PermissionError: If access is denied
            IOError: For other I/O errors
        """
        pass

    @abstractmethod
    async def exists(self, handle: ImageHandle) -> bool:
        """
        Check if an image exists in storage.

        Args:
            handle: The image handle to check

        Returns:
            True if the image exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_size(self, handle: ImageHandle) -> int:
        """
        Get the size of an image file in bytes.

        Args:
            handle: The image handle to check

        Returns:
            Size in bytes

        Raises:
            FileNotFoundError: If the image doesn't exist
        """
        pass

    @abstractmethod
    async def health_check(self) -> Tuple[bool, str]:
        """
        Check if the storage provider is healthy.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        pass


class ImageDecoder(ABC):
    """
    Abstract interface for decoding .IMG files to PNG.

    Handles:
    - Single-page TIFF files
    - Multi-page TIFF files (front/back in one file)
    - Various TIFF compression formats
    """

    @abstractmethod
    async def decode(
        self,
        data: bytes,
        page: int = 1,
        target_format: str = "PNG"
    ) -> DecodedImage:
        """
        Decode an image file to the target format.

        Args:
            data: Raw image data
            page: Page number to extract (1-indexed)
            target_format: Output format (default PNG)

        Returns:
            DecodedImage with the decoded data

        Raises:
            ValueError: If the page number is invalid
            UnsupportedFormatError: If the image format is not supported
            DecodeError: If decoding fails
        """
        pass

    @abstractmethod
    async def get_page_count(self, data: bytes) -> int:
        """
        Get the number of pages in an image file.

        Args:
            data: Raw image data

        Returns:
            Number of pages (1 for single-page, 2+ for multi-page)
        """
        pass

    @abstractmethod
    async def detect_format(self, data: bytes) -> str:
        """
        Detect the actual format of an image file by magic bytes.

        Args:
            data: Raw image data (first few bytes are sufficient)

        Returns:
            Format string (e.g., "TIFF", "PNG", "JPEG", "UNKNOWN")
        """
        pass

    @abstractmethod
    async def health_check(self) -> Tuple[bool, str]:
        """
        Check if the image decoder is healthy.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        pass


# Custom exceptions for adapters

class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class UnsupportedFormatError(AdapterError):
    """Raised when an unsupported image format is encountered."""
    def __init__(self, format: str, message: str = None):
        self.format = format
        self.message = message or f"Unsupported image format: {format}"
        super().__init__(self.message)


class DecodeError(AdapterError):
    """Raised when image decoding fails."""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class StorageAccessError(AdapterError):
    """Raised when storage access fails."""
    def __init__(self, path: str, message: str, original_error: Exception = None):
        self.path = path
        self.message = message
        self.original_error = original_error
        super().__init__(f"{message}: {path}")


class ItemNotFoundError(AdapterError):
    """Raised when an item cannot be resolved."""
    def __init__(self, trace_number: str, check_date: date):
        self.trace_number = trace_number
        self.check_date = check_date
        super().__init__(f"Item not found: trace={trace_number}, date={check_date}")
