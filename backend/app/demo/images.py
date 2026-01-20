"""
Demo Check Image Generation Module.

This module generates synthetic check images for demonstration purposes.
All images are clearly watermarked as "DEMO" and contain no real PII.
"""

import base64
import io
from dataclasses import dataclass
from decimal import Decimal
from typing import BinaryIO

# Try to import PIL, fall back to placeholder if not available
try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class DemoCheckImageData:
    """Data for generating a demo check image."""

    check_number: str
    amount: Decimal
    payee_name: str
    memo: str
    check_date: str
    account_number_masked: str
    routing_number: str
    image_type: str  # "front" or "back"


class DemoImageGenerator:
    """Generates demo check images with watermarks."""

    # Check dimensions (standard check size at 200 DPI)
    WIDTH = 1200
    HEIGHT = 600

    # Colors
    BG_COLOR = (255, 255, 250)  # Off-white
    TEXT_COLOR = (0, 0, 100)  # Dark blue
    WATERMARK_COLOR = (200, 200, 200, 128)  # Semi-transparent gray
    MICR_COLOR = (50, 50, 50)  # Dark gray for MICR
    LINE_COLOR = (100, 100, 150)  # Blue-gray for lines

    def __init__(self):
        """Initialize the image generator."""
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow is required for demo image generation. " "Install with: pip install Pillow"
            )

    def generate_check_front(self, data: DemoCheckImageData) -> bytes:
        """Generate a front check image."""
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Try to use a built-in font, fall back to default
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            font_micr = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 24
            )
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_medium = font_large
            font_small = font_large
            font_micr = font_large

        # Draw border
        draw.rectangle(
            [(10, 10), (self.WIDTH - 10, self.HEIGHT - 10)], outline=self.LINE_COLOR, width=2
        )

        # Bank name area (top left)
        draw.text((50, 30), "DEMO COMMUNITY BANK", fill=self.TEXT_COLOR, font=font_large)
        draw.text((50, 65), "123 Demo Street", fill=self.TEXT_COLOR, font=font_small)
        draw.text((50, 85), "Demo City, DS 12345", fill=self.TEXT_COLOR, font=font_small)

        # Check number (top right)
        draw.text(
            (self.WIDTH - 200, 30),
            f"Check #{data.check_number}",
            fill=self.TEXT_COLOR,
            font=font_medium,
        )

        # Date
        draw.text(
            (self.WIDTH - 300, 100),
            f"Date: {data.check_date}",
            fill=self.TEXT_COLOR,
            font=font_medium,
        )

        # Pay to line
        draw.text((50, 160), "PAY TO THE", fill=self.TEXT_COLOR, font=font_small)
        draw.text((50, 180), "ORDER OF:", fill=self.TEXT_COLOR, font=font_small)
        draw.line([(150, 200), (self.WIDTH - 300, 200)], fill=self.LINE_COLOR, width=1)
        draw.text((160, 175), data.payee_name, fill=self.TEXT_COLOR, font=font_medium)

        # Amount box
        draw.rectangle(
            [(self.WIDTH - 280, 160), (self.WIDTH - 50, 210)], outline=self.LINE_COLOR, width=2
        )
        draw.text(
            (self.WIDTH - 270, 170), f"$ {data.amount:,.2f}", fill=self.TEXT_COLOR, font=font_large
        )

        # Amount in words
        amount_words = self._amount_to_words(data.amount)
        draw.line([(50, 280), (self.WIDTH - 50, 280)], fill=self.LINE_COLOR, width=1)
        draw.text((60, 250), amount_words, fill=self.TEXT_COLOR, font=font_medium)

        # Memo line
        draw.text((50, 320), "MEMO:", fill=self.TEXT_COLOR, font=font_small)
        draw.line([(120, 350), (500, 350)], fill=self.LINE_COLOR, width=1)
        draw.text((130, 325), data.memo[:40], fill=self.TEXT_COLOR, font=font_small)

        # Signature line
        draw.line([(600, 350), (self.WIDTH - 50, 350)], fill=self.LINE_COLOR, width=1)
        draw.text(
            (self.WIDTH - 300, 360), "Authorized Signature", fill=self.TEXT_COLOR, font=font_small
        )

        # Demo signature scribble
        self._draw_demo_signature(draw, 700, 310)

        # MICR line at bottom
        micr_text = f"⑆{data.routing_number}⑆ ⑈{data.account_number_masked.replace('*', '0')}⑈ {data.check_number}"
        draw.text((100, self.HEIGHT - 80), micr_text, fill=self.MICR_COLOR, font=font_micr)

        # Add DEMO watermark
        self._add_watermark(img, draw)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def generate_check_back(self, data: DemoCheckImageData) -> bytes:
        """Generate a back check image (endorsement area)."""
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        try:
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except (OSError, IOError):
            font_medium = ImageFont.load_default()
            font_small = font_medium

        # Draw border
        draw.rectangle(
            [(10, 10), (self.WIDTH - 10, self.HEIGHT - 10)], outline=self.LINE_COLOR, width=2
        )

        # Endorsement area
        draw.text((50, 50), "ENDORSE HERE", fill=self.TEXT_COLOR, font=font_medium)
        draw.line([(50, 100), (500, 100)], fill=self.LINE_COLOR, width=1)
        draw.line([(50, 150), (500, 150)], fill=self.LINE_COLOR, width=1)
        draw.line([(50, 200), (500, 200)], fill=self.LINE_COLOR, width=1)

        # Demo endorsement
        draw.text((70, 110), "FOR DEPOSIT ONLY", fill=self.TEXT_COLOR, font=font_small)
        draw.text((70, 155), "DEMO ACCOUNT", fill=self.TEXT_COLOR, font=font_small)

        # Processing stamps area
        draw.rectangle([(550, 50), (self.WIDTH - 50, 250)], outline=self.LINE_COLOR, width=1)
        draw.text((560, 60), "BANK USE ONLY", fill=self.TEXT_COLOR, font=font_small)
        draw.text(
            (560, 100), f"Processed: {data.check_date}", fill=self.TEXT_COLOR, font=font_small
        )
        draw.text((560, 130), "Demo Branch", fill=self.TEXT_COLOR, font=font_small)

        # Do not write below line
        draw.line(
            [(50, self.HEIGHT - 150), (self.WIDTH - 50, self.HEIGHT - 150)],
            fill=self.LINE_COLOR,
            width=2,
        )
        draw.text(
            (50, self.HEIGHT - 140),
            "DO NOT WRITE, STAMP, OR SIGN BELOW THIS LINE",
            fill=self.TEXT_COLOR,
            font=font_small,
        )

        # Add DEMO watermark
        self._add_watermark(img, draw)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def _add_watermark(self, img: Image.Image, draw: ImageDraw.ImageDraw):
        """Add DEMO watermark to the image."""
        try:
            font_watermark = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72
            )
        except (OSError, IOError):
            font_watermark = ImageFont.load_default()

        # Create watermark layer
        watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
        watermark_draw = ImageDraw.Draw(watermark)

        # Draw diagonal DEMO text
        text = "DEMO - NOT A REAL CHECK"

        # Position in center, rotated
        watermark_draw.text(
            (self.WIDTH // 2 - 300, self.HEIGHT // 2 - 30),
            text,
            fill=(200, 50, 50, 100),
            font=font_watermark,
        )

        # Composite
        img.paste(watermark, (0, 0), watermark)

        # Also add corner watermarks
        try:
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except (OSError, IOError):
            font_small = ImageFont.load_default()

        draw.text(
            (20, self.HEIGHT - 30),
            "DEMO DATA - FOR DEMONSTRATION ONLY",
            fill=(150, 150, 150),
            font=font_small,
        )
        draw.text(
            (self.WIDTH - 250, self.HEIGHT - 30),
            "NO REAL PII",
            fill=(150, 150, 150),
            font=font_small,
        )

    def _draw_demo_signature(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        """Draw a simple demo signature scribble."""
        # Simple wavy line for demo signature
        points = [
            (x, y + 20),
            (x + 30, y),
            (x + 60, y + 15),
            (x + 90, y + 5),
            (x + 120, y + 20),
            (x + 150, y + 10),
        ]
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=self.TEXT_COLOR, width=2)

    def _amount_to_words(self, amount: Decimal) -> str:
        """Convert amount to words (simplified)."""
        dollars = int(amount)
        cents = int((amount - dollars) * 100)

        # Simple word conversion for demo
        word_map = {
            0: "zero",
            1: "one",
            2: "two",
            3: "three",
            4: "four",
            5: "five",
            6: "six",
            7: "seven",
            8: "eight",
            9: "nine",
            10: "ten",
            11: "eleven",
            12: "twelve",
            13: "thirteen",
            14: "fourteen",
            15: "fifteen",
            16: "sixteen",
            17: "seventeen",
            18: "eighteen",
            19: "nineteen",
            20: "twenty",
            30: "thirty",
            40: "forty",
            50: "fifty",
            60: "sixty",
            70: "seventy",
            80: "eighty",
            90: "ninety",
        }

        if dollars < 1000:
            return f"**{dollars:,} and {cents}/100 DOLLARS**"
        elif dollars < 1000000:
            thousands = dollars // 1000
            remainder = dollars % 1000
            return f"**{thousands:,} thousand {remainder:,} and {cents}/100**"
        else:
            return f"**{dollars:,} and {cents}/100 DOLLARS**"


def generate_demo_check_image(data: DemoCheckImageData) -> bytes:
    """Generate a demo check image."""
    generator = DemoImageGenerator()

    if data.image_type == "front":
        return generator.generate_check_front(data)
    else:
        return generator.generate_check_back(data)


def get_demo_image_base64(data: DemoCheckImageData) -> str:
    """Generate demo check image and return as base64 string."""
    image_bytes = generate_demo_check_image(data)
    return base64.b64encode(image_bytes).decode("utf-8")


# Fallback for when PIL is not available
def get_placeholder_image() -> bytes:
    """Return a simple placeholder image when PIL is not available."""
    # 1x1 transparent PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
