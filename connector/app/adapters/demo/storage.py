"""
Demo mode storage provider.

Reads image files from local filesystem, simulating UNC share access.
"""
import asyncio
from pathlib import Path
from typing import Tuple

from ..interfaces import StorageProvider, ImageHandle, StorageAccessError
from ...core.config import get_settings


class DemoStorageProvider(StorageProvider):
    """
    Storage provider for demo mode.

    Translates UNC paths to local filesystem paths and reads image files.
    """

    def __init__(self, demo_repo_root: str = None):
        """
        Initialize the demo storage provider.

        Args:
            demo_repo_root: Root directory for demo files.
                           Defaults to settings.DEMO_REPO_ROOT
        """
        settings = get_settings()
        self._root = Path(demo_repo_root or settings.DEMO_REPO_ROOT).resolve()
        self._settings = settings

    def _resolve_path(self, handle: ImageHandle) -> Path:
        """
        Resolve an image handle to a local filesystem path.

        Args:
            handle: The image handle containing the UNC path

        Returns:
            Resolved local Path object

        Raises:
            StorageAccessError: If path is outside allowed roots
        """
        try:
            local_path = self._settings.get_demo_path(handle.path)
            resolved = local_path.resolve()

            # Security: Ensure path is within demo root
            root_resolved = self._root.resolve()
            if not str(resolved).startswith(str(root_resolved)):
                raise StorageAccessError(
                    handle.path,
                    "Path traversal attempt detected"
                )

            return resolved
        except ValueError as e:
            raise StorageAccessError(handle.path, str(e))

    async def read(self, handle: ImageHandle) -> bytes:
        """
        Read raw image data from local filesystem.

        Args:
            handle: The image handle to read

        Returns:
            Raw bytes of the image file

        Raises:
            FileNotFoundError: If the image doesn't exist
            StorageAccessError: If access is denied or path is invalid
        """
        path = self._resolve_path(handle)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        if not path.is_file():
            raise StorageAccessError(handle.path, "Not a file")

        # Check file size limit
        max_bytes = self._settings.MAX_IMAGE_MB * 1024 * 1024
        size = path.stat().st_size
        if size > max_bytes:
            raise StorageAccessError(
                handle.path,
                f"File exceeds maximum size of {self._settings.MAX_IMAGE_MB}MB"
            )

        # Read file asynchronously
        def _read():
            return path.read_bytes()

        return await asyncio.get_event_loop().run_in_executor(None, _read)

    async def exists(self, handle: ImageHandle) -> bool:
        """
        Check if an image exists in storage.

        Args:
            handle: The image handle to check

        Returns:
            True if the image exists, False otherwise
        """
        try:
            path = self._resolve_path(handle)
            return path.exists() and path.is_file()
        except (StorageAccessError, ValueError):
            return False

    async def get_size(self, handle: ImageHandle) -> int:
        """
        Get the size of an image file in bytes.

        Args:
            handle: The image handle to check

        Returns:
            Size in bytes

        Raises:
            FileNotFoundError: If the image doesn't exist
        """
        path = self._resolve_path(handle)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        return path.stat().st_size

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check if the storage provider is healthy.

        Verifies:
        - Demo root directory exists
        - Demo root is readable

        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            if not self._root.exists():
                return False, f"Demo root does not exist: {self._root}"

            if not self._root.is_dir():
                return False, f"Demo root is not a directory: {self._root}"

            # Try to list directory to verify read access
            list(self._root.iterdir())

            return True, f"Demo storage accessible at {self._root}"
        except PermissionError:
            return False, f"Permission denied for demo root: {self._root}"
        except Exception as e:
            return False, f"Storage health check failed: {str(e)}"
