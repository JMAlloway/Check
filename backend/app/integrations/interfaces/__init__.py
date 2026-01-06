"""Interface definitions for integration adapters."""

from app.integrations.interfaces.base import (
    CheckImageProvider,
    CheckItemProvider,
    AccountContextProvider,
    CheckHistoryProvider,
)

__all__ = [
    "CheckImageProvider",
    "CheckItemProvider",
    "AccountContextProvider",
    "CheckHistoryProvider",
]
