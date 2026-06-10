"""
Demo Check Image Generation Module.

This module generates synthetic check images for demonstration purposes.
All images are clearly watermarked as "DEMO" and contain no real PII.
"""

import base64
import io
from dataclasses import dataclass
from decimal import Decimal

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
    bank_name: str | None = None  # falls back to a deterministic demo bank


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
        bank_name = data.bank_name or "DEMO COMMUNITY BANK"
        draw.text((50, 30), bank_name, fill=self.TEXT_COLOR, font=font_large)
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

        # MICR line at bottom. Real MICR uses transit/on-us symbols, but the
        # bundled mono font has no glyphs for them (they render as tofu boxes),
        # so use ASCII separators that still read as a MICR line in the demo.
        account_digits = data.account_number_masked.replace("*", "0")
        micr_text = f"C{data.routing_number}C  A{account_digits}A  {data.check_number}"
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
        """Mark the image as synthetic without obscuring it.

        A faint, rotated "DEMO" sits behind the check content (light gray, low
        alpha) so the image still reads as a realistic check in a sales demo,
        while a small footer line keeps it honest that this is synthetic data
        with no real PII.
        """
        try:
            font_watermark = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64
            )
        except (OSError, IOError):
            font_watermark = ImageFont.load_default()

        # Faint, rotated single "DEMO" composited behind the content.
        layer = Image.new("RGBA", (360, 120), (255, 255, 255, 0))
        ImageDraw.Draw(layer).text((0, 0), "DEMO", fill=(120, 120, 140, 28), font=font_watermark)
        layer = layer.rotate(28, expand=True)
        img.paste(
            layer,
            (self.WIDTH // 2 - layer.width // 2, self.HEIGHT // 2 - layer.height // 2),
            layer,
        )

        # Subtle, honest footer marker.
        try:
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        except (OSError, IOError):
            font_small = ImageFont.load_default()

        draw.text(
            (20, self.HEIGHT - 26),
            "Demo — synthetic check, no real PII",
            fill=(170, 170, 175),
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

    _ONES = [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    ]
    _TENS = [
        "",
        "",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
    ]

    def _three_digits_to_words(self, n: int) -> str:
        """Spell a number in 0..999."""
        parts: list[str] = []
        if n >= 100:
            parts.append(f"{self._ONES[n // 100]} hundred")
            n %= 100
        if n >= 20:
            tens = self._TENS[n // 10]
            ones = n % 10
            parts.append(f"{tens}-{self._ONES[ones]}" if ones else tens)
        elif n > 0:
            parts.append(self._ONES[n])
        return " ".join(parts)

    def _amount_to_words(self, amount: Decimal) -> str:
        """Render the legal (written) amount line, e.g. 'Five thousand and 00/100'."""
        dollars = int(amount)
        cents = int(round((amount - dollars) * 100))

        if dollars == 0:
            words = "zero"
        else:
            groups = [("", 1), ("thousand", 1_000), ("million", 1_000_000)]
            segments: list[str] = []
            for label, scale in reversed(groups):
                count = (dollars // scale) % 1000
                if count:
                    spelled = self._three_digits_to_words(count)
                    segments.append(f"{spelled} {label}".strip())
            words = " ".join(segments)

        # Capitalize like a written check and append the cents fraction.
        return f"{words.capitalize()} and {cents:02d}/100"


# A small roster of fictional banks so demo checks vary instead of all reading
# the same name. Chosen deterministically from the routing number so a given
# account always shows the same bank.
DEMO_BANK_NAMES = [
    "DEMO COMMUNITY BANK",
    "FIRST DEMO NATIONAL BANK",
    "RIVERBEND DEMO BANK & TRUST",
    "SUMMIT DEMO CREDIT UNION",
    "HARBOR DEMO SAVINGS BANK",
    "PRAIRIE DEMO STATE BANK",
]


def demo_bank_name_for(routing_number: str | None) -> str:
    """Pick a stable demo bank name for a routing number."""
    if not routing_number:
        return DEMO_BANK_NAMES[0]
    digits = "".join(ch for ch in routing_number if ch.isdigit()) or "0"
    return DEMO_BANK_NAMES[int(digits) % len(DEMO_BANK_NAMES)]


def generate_demo_check_image(data: DemoCheckImageData) -> bytes:
    """Generate a demo check image."""
    generator = DemoImageGenerator()

    if data.image_type == "front":
        return generator.generate_check_front(data)
    else:
        return generator.generate_check_back(data)


def build_demo_check_image(
    *,
    image_type: str,
    check_number: str | None,
    amount: Decimal,
    payee_name: str | None,
    memo: str | None,
    check_date: str,
    account_number_masked: str | None,
    routing_number: str | None,
    bank_name: str | None = None,
    thumbnail: bool = False,
) -> bytes:
    """Render a check image (front/back) from an item's fields.

    Wraps DemoCheckImageData construction so callers (e.g. the image-serving
    endpoint) can pass a CheckItem's data directly. When ``thumbnail`` is set the
    full-resolution render is downscaled, keeping the layout proportional.
    """
    data = DemoCheckImageData(
        check_number=str(check_number or "1001"),
        amount=Decimal(amount),
        payee_name=payee_name or "Payee",
        memo=memo or "",
        check_date=check_date,
        account_number_masked=account_number_masked or "****0000",
        routing_number=routing_number or "000000000",
        image_type=image_type,
        bank_name=bank_name or demo_bank_name_for(routing_number),
    )
    image_bytes = generate_demo_check_image(data)

    if thumbnail:
        thumb = Image.open(io.BytesIO(image_bytes))
        thumb.thumbnail((400, 200))
        buffer = io.BytesIO()
        thumb.save(buffer, format="PNG")
        return buffer.getvalue()

    return image_bytes


# Fallback for when PIL is not available
def get_placeholder_image() -> bytes:
    """Return a simple placeholder image when PIL is not available."""
    # 1x1 transparent PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
