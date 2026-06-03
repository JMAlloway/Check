"""Shared synthetic check-image renderer.

Used by the simulated core-banking adapters (and the legacy mock adapter) to
produce realistic-looking check images without any external dependency. Real
adapters would instead fetch TIFF/JPEG images from the vendor image service
(e.g. Fiserv Director Image, Jack Henry ItemImageInq); only the transport
differs - the downstream contract (CheckImageData bytes) stays the same.
"""

import io
import random

from PIL import Image, ImageDraw


def is_front_image(image_id: str) -> bool:
    """Determine whether an image id refers to the front of a check."""
    if image_id.startswith("DEMO-IMG-"):
        return image_id.endswith("-front")
    return "FRONT" in image_id.upper()


def render_check_image(
    image_id: str,
    is_front: bool = True,
    width: int = 1200,
    height: int = 600,
) -> bytes:
    """Render a synthetic check image and return PNG bytes."""
    img = Image.new("RGB", (width, height), color=(255, 255, 250))
    draw = ImageDraw.Draw(img)

    if is_front:
        # Check border
        draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(200, 200, 200), width=2)

        # Bank name area
        draw.rectangle([(20, 20), (300, 80)], outline=(100, 100, 100))
        draw.text((30, 35), "COMMUNITY BANK", fill=(0, 0, 100))
        draw.text((30, 55), "Member FDIC", fill=(100, 100, 100))

        # Check number area (top right)
        draw.text((width - 150, 30), "1234", fill=(0, 0, 0))

        # Date line
        draw.text((width - 250, 80), "DATE: __________", fill=(0, 0, 0))

        # Pay to the order of
        draw.text((30, 150), "PAY TO THE", fill=(0, 0, 0))
        draw.text((30, 170), "ORDER OF", fill=(0, 0, 0))
        draw.line([(150, 180), (width - 300, 180)], fill=(0, 0, 0))

        # Dollar amount box
        draw.rectangle([(width - 200, 140), (width - 30, 190)], outline=(0, 0, 0))
        draw.text((width - 190, 155), "$ ________", fill=(0, 0, 0))

        # Legal amount line
        draw.line([(30, 250), (width - 200, 250)], fill=(0, 0, 0))
        draw.text((width - 180, 240), "DOLLARS", fill=(0, 0, 0))

        # Memo line
        draw.text((30, 350), "MEMO", fill=(100, 100, 100))
        draw.line([(100, 360), (400, 360)], fill=(0, 0, 0))

        # Signature line
        draw.line([(width - 400, 360), (width - 50, 360)], fill=(0, 0, 0))
        draw.text((width - 350, 370), "AUTHORIZED SIGNATURE", fill=(100, 100, 100))

        # MICR line at bottom
        draw.rectangle([(30, height - 80), (width - 30, height - 30)], fill=(240, 240, 240))
        draw.text((50, height - 65), "C123456789C A0123456789A 1234", fill=(0, 0, 0))

        # Handwriting simulation
        draw.text((160, 145), "Sample Payee Name", fill=(0, 0, 100))
        draw.text((width - 180, 155), "5,000.00", fill=(0, 0, 100))
        draw.text((30, 220), "Five Thousand and 00/100", fill=(0, 0, 100))

        # Signature simulation
        points = [(width - 350, 340)]
        for _ in range(20):
            last = points[-1]
            points.append((last[0] + random.randint(10, 20), last[1] + random.randint(-10, 10)))
        draw.line(points, fill=(0, 0, 150), width=2)
    else:
        # Back of check - endorsement area
        draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(200, 200, 200), width=2)
        draw.rectangle([(30, 30), (400, 200)], outline=(0, 0, 0))
        draw.text((40, 40), "ENDORSE HERE", fill=(100, 100, 100))
        draw.text((40, 60), "X _______________", fill=(0, 0, 0))
        draw.text((40, 100), "DO NOT WRITE, STAMP, OR", fill=(100, 100, 100))
        draw.text((40, 120), "SIGN BELOW THIS LINE", fill=(100, 100, 100))

        # Processing stamps simulation
        draw.text((500, 100), "DEPOSITED", fill=(255, 0, 0))
        draw.text((500, 130), "01/05/2026", fill=(255, 0, 0))
        draw.text((500, 160), "COMMUNITY BANK", fill=(255, 0, 0))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
