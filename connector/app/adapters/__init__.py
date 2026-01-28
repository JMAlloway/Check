"""
Adapter interfaces and implementations for the Bank-Side Connector.

Adapters provide abstraction layers for:
- ItemResolver: Maps (trace, date) to image handle(s)
- StorageProvider: Reads raw bytes from storage
- ImageDecoder: Converts .IMG files to PNG
"""
from .interfaces import (
    DecodedImage,
    ImageDecoder,
    ImageHandle,
    ImageSide,
    ItemMetadata,
    ItemResolver,
    StorageProvider,
)

__all__ = [
    "ItemResolver",
    "StorageProvider",
    "ImageDecoder",
    "ImageHandle",
    "ItemMetadata",
    "DecodedImage",
    "ImageSide",
]
