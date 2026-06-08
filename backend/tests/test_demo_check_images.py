"""Unit tests for demo check-image generation.

These cover the rendering helpers that make served demo checks match each item's
synthetic data (payee/amount/MICR), without needing the full request stack.
"""

from decimal import Decimal

from app.demo.images import (
    DemoImageGenerator,
    build_demo_check_image,
    demo_bank_name_for,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_build_front_and_back_return_png():
    common = dict(
        check_number="9123",
        amount=Decimal("134795.66"),
        payee_name="Enterprise Fleet Management",
        memo="invoice 4471",
        check_date="05/25/2026",
        account_number_masked="****5203",
        routing_number="000000005",
    )
    front = build_demo_check_image(image_type="front", **common)
    back = build_demo_check_image(image_type="back", **common)
    assert front.startswith(PNG_MAGIC)
    assert back.startswith(PNG_MAGIC)
    assert len(front) > 1000


def test_thumbnail_is_smaller_than_full():
    common = dict(
        image_type="front",
        check_number="1001",
        amount=Decimal("250.00"),
        payee_name="Acme Co",
        memo="",
        check_date="01/02/2026",
        account_number_masked="****0001",
        routing_number="000000001",
    )
    full = build_demo_check_image(**common, thumbnail=False)
    thumb = build_demo_check_image(**common, thumbnail=True)
    assert thumb.startswith(PNG_MAGIC)
    assert len(thumb) < len(full)


def test_handles_missing_optional_fields():
    # payee/memo/check_number/account/routing all absent -> still renders.
    img = build_demo_check_image(
        image_type="front",
        check_number=None,
        amount=Decimal("10.00"),
        payee_name=None,
        memo=None,
        check_date="",
        account_number_masked=None,
        routing_number=None,
    )
    assert img.startswith(PNG_MAGIC)


def test_amount_to_words_legal_line():
    gen = DemoImageGenerator()
    assert gen._amount_to_words(Decimal("5000.00")) == "Five thousand and 00/100"
    assert (
        gen._amount_to_words(Decimal("134795.66"))
        == "One hundred thirty-four thousand seven hundred ninety-five and 66/100"
    )
    assert gen._amount_to_words(Decimal("16183.33")) == (
        "Sixteen thousand one hundred eighty-three and 33/100"
    )
    assert gen._amount_to_words(Decimal("0.50")) == "Zero and 50/100"


def test_bank_name_is_deterministic_and_varies():
    # Same routing -> same bank; different routings can differ.
    assert demo_bank_name_for("000000005") == demo_bank_name_for("000000005")
    names = {demo_bank_name_for(str(r)) for r in range(6)}
    assert len(names) > 1  # not all identical
