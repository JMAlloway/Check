"""
TIFF Image Decoder.

Handles decoding of .IMG files (TIFF format) to PNG.
Supports single-page and multi-page TIFF files.
"""
import asyncio
import io
from typing import Tuple

from PIL import Image

from ..interfaces import (
    DecodedImage,
    DecodeError,
    ImageDecoder,
    UnsupportedFormatError,
)

# Magic bytes for image format detection
MAGIC_BYTES = {
    b"II*\x00": "TIFF",      # TIFF little-endian
    b"MM\x00*": "TIFF",      # TIFF big-endian
    b"\x89PNG": "PNG",       # PNG
    b"\xff\xd8\xff": "JPEG", # JPEG
    b"GIF8": "GIF",          # GIF
    b"BM": "BMP",            # BMP
}


class TiffImageDecoder(ImageDecoder):
    """
    Decoder for TIFF images (including .IMG files).

    Handles:
    - Single-page TIFF files
    - Multi-page TIFF files (front/back in one file)
    - Various TIFF compression formats (LZW, CCITT, etc.)
    """

    def __init__(self, max_image_dimension: int = 10000):
        """
        Initialize the decoder.

        Args:
            max_image_dimension: Maximum allowed dimension (width/height)
                                to prevent memory exhaustion
        """
        self._max_dimension = max_image_dimension

    async def decode(
        self,
        data: bytes,
        page: int = 1,
        target_format: str = "PNG"
    ) -> DecodedImage:
        """
        Decode an image file to PNG.

        Args:
            data: Raw image data
            page: Page number to extract (1-indexed)
            target_format: Output format (default PNG)

        Returns:
            DecodedImage with the decoded PNG data

        Raises:
            ValueError: If the page number is invalid
            UnsupportedFormatError: If the image format is not supported
            DecodeError: If decoding fails
        """
        if page < 1:
            raise ValueError("Page number must be >= 1")

        # Detect format
        detected_format = await self.detect_format(data)
        if detected_format == "UNKNOWN":
            raise UnsupportedFormatError("UNKNOWN", "Cannot detect image format")

        # Decode in thread pool to avoid blocking
        def _decode():
            return self._decode_sync(data, page, target_format, detected_format)

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _decode)
        except (UnsupportedFormatError, DecodeError, ValueError):
            raise
        except Exception as e:
            raise DecodeError(f"Failed to decode image: {str(e)}", e)

    def _decode_sync(
        self,
        data: bytes,
        page: int,
        target_format: str,
        detected_format: str
    ) -> DecodedImage:
        """
        Synchronous image decoding.

        Args:
            data: Raw image data
            page: Page number (1-indexed)
            target_format: Output format
            detected_format: Detected input format

        Returns:
            DecodedImage with decoded data
        """
        try:
            # Open image with Pillow
            img = Image.open(io.BytesIO(data))

            # Get page count for multi-page images
            page_count = 1
            if hasattr(img, "n_frames"):
                page_count = img.n_frames

            # Validate page number
            if page > page_count:
                raise ValueError(
                    f"Page {page} requested but image only has {page_count} page(s)"
                )

            # Seek to requested page (0-indexed)
            if page_count > 1:
                img.seek(page - 1)

            # Check dimensions
            width, height = img.size
            if width > self._max_dimension or height > self._max_dimension:
                raise DecodeError(
                    f"Image dimensions ({width}x{height}) exceed maximum "
                    f"allowed ({self._max_dimension})"
                )

            # Convert to RGB if necessary (for PNG output)
            if img.mode in ("1", "L", "P"):
                # Convert grayscale/palette to RGB for better compatibility
                img = img.convert("RGB")
            elif img.mode == "RGBA":
                # Keep RGBA as-is
                pass
            elif img.mode != "RGB":
                # Convert other modes to RGB
                img = img.convert("RGB")

            # Encode to target format
            output = io.BytesIO()
            if target_format.upper() == "PNG":
                img.save(output, format="PNG", optimize=True)
            elif target_format.upper() == "JPEG":
                # Convert RGBA to RGB for JPEG
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(output, format="JPEG", quality=95)
            else:
                raise UnsupportedFormatError(
                    target_format,
                    f"Unsupported output format: {target_format}"
                )

            output.seek(0)
            png_data = output.read()

            return DecodedImage(
                data=png_data,
                width=width,
                height=height,
                original_format=detected_format,
                page_number=page
            )

        except UnsupportedFormatError:
            raise
        except ValueError:
            raise
        except DecodeError:
            raise
        except Exception as e:
            raise DecodeError(f"Image decode error: {str(e)}", e)

    async def get_page_count(self, data: bytes) -> int:
        """
        Get the number of pages in an image file.

        Args:
            data: Raw image data

        Returns:
            Number of pages
        """
        def _count():
            try:
                img = Image.open(io.BytesIO(data))
                if hasattr(img, "n_frames"):
                    return img.n_frames
                return 1
            except Exception:
                return 1

        return await asyncio.get_event_loop().run_in_executor(None, _count)

    async def detect_format(self, data: bytes) -> str:
        """
        Detect the actual format of an image file by magic bytes.

        Args:
            data: Raw image data

        Returns:
            Format string (e.g., "TIFF", "PNG", "JPEG", "UNKNOWN")
        """
        if not data or len(data) < 4:
            return "UNKNOWN"

        # Check magic bytes
        for magic, format_name in MAGIC_BYTES.items():
            if data[:len(magic)] == magic:
                return format_name

        # Try Pillow as fallback
        def _detect():
            try:
                img = Image.open(io.BytesIO(data))
                return img.format or "UNKNOWN"
            except Exception:
                return "UNKNOWN"

        return await asyncio.get_event_loop().run_in_executor(None, _detect)

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check if the image decoder is healthy.

        Verifies Pillow is working correctly.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            # Try to create a simple test image
            def _test():
                img = Image.new("RGB", (10, 10), color="white")
                output = io.BytesIO()
                img.save(output, format="PNG")
                return True

            await asyncio.get_event_loop().run_in_executor(None, _test)
            return True, "Image decoder operational (Pillow)"
        except Exception as e:
            return False, f"Image decoder error: {str(e)}"
