"""Demo metadata key/value store (demo/dev only).

Holds small operational markers for demo environments - currently the seed
version stamp that lets startup detect stale demo data (seeded by older code)
and reseed automatically. Never written in production: all writers run behind
``require_non_production()``.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class DemoMeta(Base, TimestampMixin):
    """Tiny key/value table for demo bookkeeping (e.g. seed version)."""

    __tablename__ = "demo_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
