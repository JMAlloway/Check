"""
Bank mode (production) storage provider.

Reads images from UNC/SMB shares using service account credentials.

NOTE: This is a stub implementation. Real implementation requires:
- smbclient or pysmb library
- Service account with read-only access to shares
- Network connectivity to file servers
"""
from typing import Tuple

from ..interfaces import ImageHandle, StorageAccessError, StorageProvider


class BankStorageProvider(StorageProvider):
    """
    Storage provider for production bank mode.

    Reads images from UNC paths using SMB protocol.

    STUB IMPLEMENTATION - Real implementation notes:
    - Use smbclient or pysmb for SMB access
    - Configure service account credentials
    - Implement connection pooling
    - Add retry logic for transient failures
    - Log access attempts for audit
    """

    def __init__(
        self,
        service_account: str = None,
        service_password: str = None,
        domain: str = None
    ):
        """
        Initialize the bank storage provider.

        Args:
            service_account: Service account username
            service_password: Service account password (use secure storage)
            domain: Windows domain for authentication
        """
        self._service_account = service_account
        self._domain = domain
        # NOTE: In production, credentials should come from secure vault
        raise NotImplementedError(
            "BankStorageProvider is a stub. Production implementation required."
        )

    async def read(self, handle: ImageHandle) -> bytes:
        """
        Read raw image data from UNC path.

        Args:
            handle: The image handle to read

        Returns:
            Raw bytes of the image file

        Raises:
            NotImplementedError: This is a stub
        """
        # Production implementation would:
        # 1. Parse UNC path to extract server/share/path
        # 2. Connect to SMB share using service account
        # 3. Read file bytes
        # 4. Return bytes
        raise NotImplementedError(
            "BankStorageProvider.read() requires production implementation"
        )

    async def exists(self, handle: ImageHandle) -> bool:
        """
        Check if an image exists at UNC path.

        Args:
            handle: The image handle to check

        Returns:
            True if file exists
        """
        raise NotImplementedError(
            "BankStorageProvider.exists() requires production implementation"
        )

    async def get_size(self, handle: ImageHandle) -> int:
        """
        Get the size of an image file.

        Args:
            handle: The image handle to check

        Returns:
            Size in bytes
        """
        raise NotImplementedError(
            "BankStorageProvider.get_size() requires production implementation"
        )

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check connectivity to file shares.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        return False, "BankStorageProvider is a stub implementation"


# Production implementation example structure:
#
# class BankStorageProviderImpl(StorageProvider):
#     """
#     Production implementation using smbclient.
#     """
#
#     def __init__(self, config: BankStorageConfig):
#         self._config = config
#         self._register_credentials()
#
#     def _register_credentials(self):
#         """Register credentials with smbclient."""
#         import smbclient
#         smbclient.register_session(
#             self._config.server,
#             username=self._config.username,
#             password=self._config.password,
#             domain=self._config.domain,
#         )
#
#     async def read(self, handle: ImageHandle) -> bytes:
#         import smbclient
#         with smbclient.open_file(handle.path, mode='rb') as f:
#             return f.read()
#
#     async def exists(self, handle: ImageHandle) -> bool:
#         import smbclient
#         try:
#             smbclient.stat(handle.path)
#             return True
#         except FileNotFoundError:
#             return False
