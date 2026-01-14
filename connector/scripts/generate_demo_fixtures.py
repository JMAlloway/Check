#!/usr/bin/env python3
"""
Generate demo fixtures for the Bank-Side Connector.

Creates:
- Sample TIFF images (renamed to .IMG)
- Item index JSON file

These fixtures simulate the Fiserv Director-style image storage.
"""
import io
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


# Demo data
DEMO_ITEMS = [
    {
        "trace_number": "12374628",
        "date": "2024-01-15",
        "amount_cents": 125000,
        "check_number": "1234",
        "account_last4": "5678",
        "is_onus": False,
        "check_type": "Transit",
        "volume_folder": "V406",
        "batch_folder": "580",
    },
    {
        "trace_number": "12374629",
        "date": "2024-01-15",
        "amount_cents": 50000,
        "check_number": "5678",
        "account_last4": "1234",
        "is_onus": True,
        "check_type": "OnUs",
        "volume_folder": "V406",
        "batch_folder": "123",
    },
    {
        "trace_number": "12374630",
        "date": "2024-01-16",
        "amount_cents": 250000,
        "check_number": "9012",
        "account_last4": "4321",
        "is_onus": False,
        "check_type": "Transit",
        "volume_folder": "V406",
        "batch_folder": "580",
    },
    {
        "trace_number": "12374631",
        "date": "2024-01-16",
        "amount_cents": 75000,
        "check_number": "3456",
        "account_last4": "8765",
        "is_onus": True,
        "check_type": "OnUs",
        "volume_folder": "V406",
        "batch_folder": "123",
    },
    {
        "trace_number": "12374632",
        "date": "2024-01-17",
        "amount_cents": 100000,
        "check_number": "7890",
        "account_last4": "2468",
        "is_onus": False,
        "check_type": "Transit",
        "volume_folder": "V406",
        "batch_folder": "580",
        "single_page": True,  # No back image
    },
]


def create_check_image(
    check_number: str,
    amount_cents: int,
    date_str: str,
    is_front: bool = True,
    width: int = 1200,
    height: int = 600
) -> Image.Image:
    """
    Create a sample check image.

    Args:
        check_number: Check number to display
        amount_cents: Amount in cents
        date_str: Date string
        is_front: True for front, False for back
        width: Image width
        height: Image height

    Returns:
        PIL Image object
    """
    # Create image with light background
    if is_front:
        bg_color = (255, 255, 245)  # Cream color for front
    else:
        bg_color = (245, 245, 255)  # Light blue for back

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to use a font, fall back to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except (OSError, IOError):
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    if is_front:
        # Draw check front
        # Bank name
        draw.text((50, 30), "DEMO NATIONAL BANK", fill=(0, 51, 102), font=font_large)

        # Check number
        draw.text((width - 150, 30), f"#{check_number}", fill=(0, 0, 0), font=font_medium)

        # Date
        draw.text((width - 200, 80), f"Date: {date_str}", fill=(0, 0, 0), font=font_medium)

        # Pay to the order of
        draw.text((50, 150), "PAY TO THE", fill=(0, 0, 0), font=font_small)
        draw.text((50, 170), "ORDER OF:", fill=(0, 0, 0), font=font_small)
        draw.line([(150, 190), (width - 50, 190)], fill=(0, 0, 0), width=1)

        # Amount
        amount_dollars = amount_cents / 100
        draw.text((width - 200, 150), f"${amount_dollars:,.2f}", fill=(0, 0, 0), font=font_large)

        # Amount in words line
        draw.line([(50, 250), (width - 50, 250)], fill=(0, 0, 0), width=1)

        # Memo line
        draw.text((50, 350), "MEMO:", fill=(0, 0, 0), font=font_small)
        draw.line([(120, 370), (400, 370)], fill=(0, 0, 0), width=1)

        # Signature line
        draw.line([(width - 350, 370), (width - 50, 370)], fill=(0, 0, 0), width=1)
        draw.text((width - 250, 375), "SIGNATURE", fill=(128, 128, 128), font=font_small)

        # MICR line (simulated)
        micr_text = f"⑆{check_number}⑆  ⑈123456789⑈  1234567890⑉"
        draw.text((50, height - 60), micr_text, fill=(0, 0, 0), font=font_medium)

        # Demo watermark
        draw.text(
            (width // 2 - 100, height // 2 - 20),
            "DEMO CHECK",
            fill=(200, 200, 200),
            font=font_large
        )

    else:
        # Draw check back (endorsement area)
        draw.text((50, 30), "ENDORSEMENT AREA", fill=(0, 0, 0), font=font_medium)

        # Endorsement box
        draw.rectangle([(50, 70), (width - 50, 200)], outline=(0, 0, 0), width=2)
        draw.text((60, 80), "Endorse check here", fill=(128, 128, 128), font=font_small)

        # Do not write below this line
        draw.line([(50, 300), (width - 50, 300)], fill=(0, 0, 0), width=1)
        draw.text((50, 310), "DO NOT WRITE, STAMP, OR SIGN BELOW THIS LINE", fill=(128, 128, 128), font=font_small)

        # Financial institution use
        draw.text((50, 400), "FOR FINANCIAL INSTITUTION USE ONLY", fill=(128, 128, 128), font=font_small)

        # Demo watermark
        draw.text(
            (width // 2 - 100, height // 2),
            "DEMO - BACK",
            fill=(200, 200, 200),
            font=font_large
        )

    return img


def create_multi_page_tiff(
    front_image: Image.Image,
    back_image: Image.Image,
    output_path: Path
):
    """
    Create a multi-page TIFF file with front and back images.

    Args:
        front_image: Front side image
        back_image: Back side image
        output_path: Path to save the TIFF file
    """
    # Convert to grayscale for smaller file size (typical for check images)
    front_gray = front_image.convert("L")
    back_gray = back_image.convert("L")

    # Save as multi-page TIFF
    front_gray.save(
        output_path,
        format="TIFF",
        save_all=True,
        append_images=[back_gray],
        compression="tiff_lzw"
    )


def create_single_page_tiff(image: Image.Image, output_path: Path):
    """
    Create a single-page TIFF file.

    Args:
        image: Image to save
        output_path: Path to save the TIFF file
    """
    gray = image.convert("L")
    gray.save(output_path, format="TIFF", compression="tiff_lzw")


def generate_fixtures(demo_repo_root: Path):
    """
    Generate all demo fixtures.

    Args:
        demo_repo_root: Root directory for demo files
    """
    print(f"Generating demo fixtures in: {demo_repo_root}")

    # Create directory structure
    for check_type in ["Transit", "OnUs"]:
        for volume in ["V406"]:
            for batch in ["580", "123"]:
                path = demo_repo_root / "Checks" / check_type / volume / batch
                path.mkdir(parents=True, exist_ok=True)

    # Generate items
    items_for_index = []

    for item in DEMO_ITEMS:
        # Determine path
        check_type = item["check_type"]
        volume = item["volume_folder"]
        batch = item["batch_folder"]
        trace = item["trace_number"]

        # UNC-style path (simulated)
        unc_path = f"\\\\tn-director-pro\\Checks\\{check_type}\\{volume}\\{batch}\\{trace}.IMG"

        # Local path
        local_path = demo_repo_root / "Checks" / check_type / volume / batch / f"{trace}.IMG"

        # Create images
        front = create_check_image(
            check_number=item["check_number"],
            amount_cents=item["amount_cents"],
            date_str=item["date"],
            is_front=True
        )

        is_single_page = item.get("single_page", False)

        if is_single_page:
            create_single_page_tiff(front, local_path)
            has_back = False
        else:
            back = create_check_image(
                check_number=item["check_number"],
                amount_cents=item["amount_cents"],
                date_str=item["date"],
                is_front=False
            )
            create_multi_page_tiff(front, back, local_path)
            has_back = True

        print(f"  Created: {local_path}")

        # Add to index
        items_for_index.append({
            "trace_number": item["trace_number"],
            "date": item["date"],
            "image_path": unc_path,
            "amount_cents": item["amount_cents"],
            "check_number": item["check_number"],
            "account_last4": item["account_last4"],
            "is_onus": item["is_onus"],
            "is_multi_page": not is_single_page,
            "has_back_image": has_back
        })

    # Write item index
    index_path = demo_repo_root / "item_index.json"
    with open(index_path, "w") as f:
        json.dump({"items": items_for_index}, f, indent=2)
    print(f"  Created: {index_path}")

    print(f"\nGenerated {len(items_for_index)} demo items")


def main():
    """Main entry point."""
    # Determine demo_repo path
    script_dir = Path(__file__).parent
    connector_dir = script_dir.parent
    demo_repo_root = connector_dir / "demo_repo"

    # Generate fixtures
    generate_fixtures(demo_repo_root)

    print("\nDemo fixtures generated successfully!")
    print(f"Demo repo root: {demo_repo_root}")
    print(f"Item index: {demo_repo_root / 'item_index.json'}")


if __name__ == "__main__":
    main()
