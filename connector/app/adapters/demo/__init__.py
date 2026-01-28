"""
Demo mode adapter implementations.

These adapters use local filesystem to simulate the bank's UNC share environment.
"""
from .decoder import TiffImageDecoder
from .resolver import DemoItemResolver
from .storage import DemoStorageProvider

__all__ = ["DemoStorageProvider", "DemoItemResolver", "TiffImageDecoder"]
