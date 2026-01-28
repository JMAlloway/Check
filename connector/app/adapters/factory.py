"""
Adapter factory for creating mode-appropriate adapters.

Creates DEMO or BANK mode adapters based on configuration.
"""
from typing import Tuple

from ..core.config import ConnectorMode, get_settings
from .demo import DemoItemResolver, DemoStorageProvider, TiffImageDecoder
from .interfaces import ImageDecoder, ItemResolver, StorageProvider


class AdapterFactory:
    """
    Factory for creating connector adapters.

    Creates appropriate adapter implementations based on the configured mode.
    """

    _instance = None
    _adapters: Tuple[ItemResolver, StorageProvider, ImageDecoder] = None

    def __new__(cls):
        """Singleton pattern for adapter factory."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_adapters(self) -> Tuple[ItemResolver, StorageProvider, ImageDecoder]:
        """
        Get adapter instances for the current mode.

        Returns:
            Tuple of (ItemResolver, StorageProvider, ImageDecoder)
        """
        if self._adapters is not None:
            return self._adapters

        settings = get_settings()

        if settings.MODE == ConnectorMode.DEMO:
            self._adapters = self._create_demo_adapters()
        elif settings.MODE == ConnectorMode.BANK:
            self._adapters = self._create_bank_adapters()
        else:
            raise ValueError(f"Unknown connector mode: {settings.MODE}")

        return self._adapters

    def _create_demo_adapters(self) -> Tuple[ItemResolver, StorageProvider, ImageDecoder]:
        """Create adapters for DEMO mode."""
        settings = get_settings()

        resolver = DemoItemResolver(index_path=settings.ITEM_INDEX_PATH)
        storage = DemoStorageProvider(demo_repo_root=settings.DEMO_REPO_ROOT)
        decoder = TiffImageDecoder()

        return resolver, storage, decoder

    def _create_bank_adapters(self) -> Tuple[ItemResolver, StorageProvider, ImageDecoder]:
        """
        Create adapters for BANK mode.

        NOTE: Bank adapters are stubs. This will raise NotImplementedError.
        """
        from .bank import BankItemResolver, BankStorageProvider

        # These will raise NotImplementedError since they're stubs
        resolver = BankItemResolver()
        storage = BankStorageProvider()
        decoder = TiffImageDecoder()

        return resolver, storage, decoder

    def reset(self):
        """Reset adapters (useful for testing)."""
        self._adapters = None


def get_adapters() -> Tuple[ItemResolver, StorageProvider, ImageDecoder]:
    """
    Get adapter instances for the current mode.

    Returns:
        Tuple of (ItemResolver, StorageProvider, ImageDecoder)
    """
    return AdapterFactory().get_adapters()


def get_resolver() -> ItemResolver:
    """Get the item resolver for the current mode."""
    resolver, _, _ = get_adapters()
    return resolver


def get_storage() -> StorageProvider:
    """Get the storage provider for the current mode."""
    _, storage, _ = get_adapters()
    return storage


def get_decoder() -> ImageDecoder:
    """Get the image decoder."""
    _, _, decoder = get_adapters()
    return decoder
