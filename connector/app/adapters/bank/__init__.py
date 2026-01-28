"""
Bank mode (production) adapter implementations.

These adapters interface with real bank infrastructure:
- UNC/SMB shares for image storage
- Bank's item feed or index for item resolution
"""
from .resolver import BankItemResolver
from .storage import BankStorageProvider

__all__ = ["BankStorageProvider", "BankItemResolver"]
