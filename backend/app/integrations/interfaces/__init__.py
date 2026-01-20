"""Interface definitions for integration adapters."""

from app.integrations.interfaces.base import (
    AccountContextProvider,
    CheckHistoryProvider,
    CheckImageProvider,
    CheckItemProvider,
)

__all__ = [
    "CheckImageProvider",
    "CheckItemProvider",
    "AccountContextProvider",
    "CheckHistoryProvider",
]
