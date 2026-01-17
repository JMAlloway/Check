"""
Demo mode adapter implementations.

These adapters use local filesystem to simulate the bank's UNC share environment.
"""
from .storage import DemoStorageProvider
from .resolver import DemoItemResolver
from .decoder import TiffImageDecoder

__all__ = ["DemoStorageProvider", "DemoItemResolver", "TiffImageDecoder"]
