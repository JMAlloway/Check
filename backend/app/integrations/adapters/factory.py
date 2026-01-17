"""Adapter factory for creating integration adapters."""

from abc import ABC

from app.core.config import settings
from app.integrations.interfaces.base import (
    AccountContextProvider,
    CheckHistoryProvider,
    CheckImageProvider,
    CheckItemProvider,
)


class IntegrationAdapter(
    CheckItemProvider,
    CheckImageProvider,
    AccountContextProvider,
    CheckHistoryProvider,
    ABC,
):
    """Combined interface for a full integration adapter."""

    pass


class AdapterFactory:
    """Factory for creating integration adapters based on configuration."""

    _instance: IntegrationAdapter | None = None
    _adapter_type: str = "mock"

    @classmethod
    def get_adapter(cls) -> IntegrationAdapter:
        """Get the configured integration adapter (singleton)."""
        if cls._instance is None:
            cls._instance = cls._create_adapter()
        return cls._instance

    @classmethod
    def _create_adapter(cls) -> IntegrationAdapter:
        """Create a new adapter instance based on configuration."""
        adapter_type = getattr(settings, "INTEGRATION_ADAPTER", "mock")

        if adapter_type == "mock":
            from app.integrations.adapters.mock import MockAdapter

            return MockAdapter()

        elif adapter_type == "q2":
            # Q2 adapter would be implemented here
            raise NotImplementedError("Q2 adapter not yet implemented")

        elif adapter_type == "fiserv":
            # Fiserv adapter would be implemented here
            raise NotImplementedError("Fiserv adapter not yet implemented")

        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

    @classmethod
    def reset(cls) -> None:
        """Reset the adapter instance (useful for testing)."""
        cls._instance = None


def get_adapter() -> IntegrationAdapter:
    """Convenience function to get the integration adapter."""
    return AdapterFactory.get_adapter()
