"""
Bank mode (production) adapter implementations.

These adapters interface with real bank infrastructure:
- UNC/SMB shares for image storage
- Bank's item feed or index for item resolution
"""
from .storage import BankStorageProvider
from .resolver import BankItemResolver

__all__ = ["BankStorageProvider", "BankItemResolver"]
