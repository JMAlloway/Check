"""
Unit tests for image decoder.
"""
import io
import pytest
from PIL import Image

from app.adapters.demo.decoder import TiffImageDecoder
from app.adapters.interfaces import UnsupportedFormatError, DecodeError


class TestTiffImageDecoder:
    """Tests for TIFF image decoder."""

    @pytest.fixture
    def decoder(self):
        return TiffImageDecoder()

    @pytest.mark.asyncio
    async def test_decode_single_page_tiff(self, decoder, single_page_tiff):
        """Test decoding a single-page TIFF."""
        result = await decoder.decode(single_page_tiff, page=1)

        assert result.data is not None
        assert len(result.data) > 0
        assert result.width == 800
        assert result.height == 400
        assert result.original_format == "TIFF"
        assert result.page_number == 1

        # Verify it's valid PNG
        img = Image.open(io.BytesIO(result.data))
        assert img.format == "PNG"

    @pytest.mark.asyncio
    async def test_decode_multi_page_tiff_front(self, decoder, multi_page_tiff):
        """Test decoding front (page 1) of multi-page TIFF."""
        result = await decoder.decode(multi_page_tiff, page=1)

        assert result.page_number == 1
        assert result.width == 800
        assert result.height == 400

    @pytest.mark.asyncio
    async def test_decode_multi_page_tiff_back(self, decoder, multi_page_tiff):
        """Test decoding back (page 2) of multi-page TIFF."""
        result = await decoder.decode(multi_page_tiff, page=2)

        assert result.page_number == 2
        assert result.width == 800
        assert result.height == 400

    @pytest.mark.asyncio
    async def test_decode_invalid_page_number(self, decoder, single_page_tiff):
        """Test that requesting a non-existent page raises an error."""
        with pytest.raises(ValueError) as exc_info:
            await decoder.decode(single_page_tiff, page=2)

        assert "page 2" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_decode_page_zero_invalid(self, decoder, single_page_tiff):
        """Test that page 0 is invalid."""
        with pytest.raises(ValueError):
            await decoder.decode(single_page_tiff, page=0)

    @pytest.mark.asyncio
    async def test_decode_negative_page_invalid(self, decoder, single_page_tiff):
        """Test that negative page numbers are invalid."""
        with pytest.raises(ValueError):
            await decoder.decode(single_page_tiff, page=-1)

    @pytest.mark.asyncio
    async def test_get_page_count_single(self, decoder, single_page_tiff):
        """Test getting page count for single-page TIFF."""
        count = await decoder.get_page_count(single_page_tiff)
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_page_count_multi(self, decoder, multi_page_tiff):
        """Test getting page count for multi-page TIFF."""
        count = await decoder.get_page_count(multi_page_tiff)
        assert count == 2

    @pytest.mark.asyncio
    async def test_detect_format_tiff_little_endian(self, decoder, single_page_tiff):
        """Test TIFF format detection (little endian)."""
        format_name = await decoder.detect_format(single_page_tiff)
        assert format_name == "TIFF"

    @pytest.mark.asyncio
    async def test_detect_format_png(self, decoder, png_image):
        """Test PNG format detection."""
        format_name = await decoder.detect_format(png_image)
        assert format_name == "PNG"

    @pytest.mark.asyncio
    async def test_detect_format_unknown(self, decoder):
        """Test unknown format detection."""
        format_name = await decoder.detect_format(b"random bytes here")
        assert format_name == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_detect_format_empty(self, decoder):
        """Test format detection with empty data."""
        format_name = await decoder.detect_format(b"")
        assert format_name == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_decode_png_passthrough(self, decoder, png_image):
        """Test that PNG images can be decoded."""
        result = await decoder.decode(png_image, page=1)

        assert result.data is not None
        assert result.original_format == "PNG"

    @pytest.mark.asyncio
    async def test_decode_unsupported_format(self, decoder):
        """Test that unsupported formats raise an error."""
        with pytest.raises(UnsupportedFormatError):
            await decoder.decode(b"not an image", page=1)

    @pytest.mark.asyncio
    async def test_health_check(self, decoder):
        """Test health check."""
        is_healthy, message = await decoder.health_check()

        assert is_healthy
        assert "pillow" in message.lower()

    @pytest.mark.asyncio
    async def test_decode_jpeg_target_format(self, decoder, single_page_tiff):
        """Test decoding to JPEG format."""
        result = await decoder.decode(
            single_page_tiff,
            page=1,
            target_format="JPEG"
        )

        assert result.data is not None

        # Verify it's valid JPEG
        img = Image.open(io.BytesIO(result.data))
        assert img.format == "JPEG"

    @pytest.mark.asyncio
    async def test_file_size_tracking(self, decoder, single_page_tiff):
        """Test that file size is tracked correctly."""
        result = await decoder.decode(single_page_tiff, page=1)

        assert result.file_size == len(result.data)
        assert result.file_size > 0
