"""Unit tests for Connector B commit-file generation.

Regression coverage for bugs found via end-to-end demo of the decision-commit
flow: the CSV trailer row crashed when the configured fields didn't include the
summary columns, leaving file generation (and thus the whole approve->transmit
loop) broken.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.models.connector import BankConnectorConfig, CommitDecisionType, CommitRecord
from app.services.connector_service import CSVGenerator


def _config(field_names: list[str]) -> BankConnectorConfig:
    # Transient (not persisted) config with just the attrs the generator reads.
    return BankConnectorConfig(
        bank_id="DEMO-CORE-001",
        bank_name="Demo",
        field_config={"fields": [{"name": n, "source": n} for n in field_names]},
        include_header_row=True,
        include_trailer_row=True,
        file_line_ending="LF",
        file_encoding="UTF-8",
        include_notes=False,
        max_notes_length=500,
    )


def _records(n: int) -> list[CommitRecord]:
    out = []
    for i in range(1, n + 1):
        out.append(
            CommitRecord(
                sequence_number=i,
                item_id=f"ITEM-{i}",
                account_number_masked="****1234",
                routing_number="000000001",
                transaction_amount=Decimal(f"{100 * i}.00"),
                decision_type=CommitDecisionType.RELEASE,
                decision_hash=f"hash{i}",
                decision_timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )
        )
    return out


def test_trailer_without_summary_columns_does_not_crash():
    # Fields do NOT include record_count/total_amount; the trailer must still
    # write (previously this raised "dict contains fields not in fieldnames").
    config = _config(["sequence_number", "item_id", "transaction_amount", "decision_type"])
    content = CSVGenerator(config).generate(batch=None, records=_records(3)).decode("utf-8")
    lines = [ln for ln in content.splitlines() if ln]
    assert lines[0].split(",") == [
        "sequence_number",
        "item_id",
        "transaction_amount",
        "decision_type",
    ]
    assert len([ln for ln in lines if ln.startswith("ITEM") or ln[0].isdigit()]) >= 3
    assert any(ln.startswith("TRAILER") for ln in lines)


def test_trailer_with_summary_columns_is_populated():
    config = _config(["item_id", "transaction_amount", "record_count", "total_amount"])
    content = CSVGenerator(config).generate(batch=None, records=_records(2)).decode("utf-8")
    trailer = [ln for ln in content.splitlines() if ln.startswith("TRAILER")][0]
    # record_count=2 and total_amount=100+200=300.00 appear on the trailer row.
    assert "2" in trailer
    assert "300.00" in trailer


def test_generation_is_deterministic():
    config = _config(["sequence_number", "item_id", "transaction_amount"])
    records = _records(5)
    first = CSVGenerator(config).generate(batch=None, records=records)
    # Same records in a different order, then sorted by sequence, must match.
    shuffled = list(reversed(records))
    second = CSVGenerator(config).generate(
        batch=None, records=sorted(shuffled, key=lambda r: r.sequence_number)
    )
    assert first == second
