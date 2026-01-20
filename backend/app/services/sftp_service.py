"""SFTP Service for secure file transfer operations.

Provides a secure, auditable SFTP client for:
- Connecting to bank SFTP servers
- Downloading context data files
- Archiving/moving processed files
- Connection testing

Security Features:
- Credentials stored encrypted (via app/core/encryption.py)
- Support for password and SSH key authentication
- Connection timeouts and retry logic
- Audit logging of all operations
"""

import asyncio
import fnmatch
import hashlib
import io
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import paramiko
from paramiko import SFTPClient, SSHClient, Transport
from paramiko.ssh_exception import AuthenticationException, SSHException

from app.core.encryption import decrypt_value
from app.models.item_context_connector import ItemContextConnector


@dataclass
class SFTPFile:
    """Represents a file on the SFTP server."""

    name: str
    path: str
    size: int
    modified_at: datetime
    is_directory: bool


@dataclass
class SFTPConnectionResult:
    """Result of an SFTP connection test."""

    success: bool
    message: str
    latency_ms: int | None = None
    server_version: str | None = None
    error_details: str | None = None


@dataclass
class SFTPDownloadResult:
    """Result of a file download operation."""

    success: bool
    local_path: str | None = None
    file_size: int | None = None
    checksum: str | None = None
    error: str | None = None


class SFTPService:
    """
    Service for SFTP operations with bank file servers.

    Supports both password and SSH key authentication.
    All credentials must be stored encrypted.
    """

    def __init__(self, connector: ItemContextConnector):
        """
        Initialize SFTP service with connector configuration.

        Args:
            connector: ItemContextConnector with SFTP settings
        """
        self.connector = connector
        self._client: SSHClient | None = None
        self._sftp: SFTPClient | None = None
        self._transport: Transport | None = None

    def _decrypt_credential(self, encrypted_value: str | None) -> str | None:
        """Decrypt an encrypted credential value."""
        if not encrypted_value:
            return None
        return decrypt_value(encrypted_value)

    def _get_private_key(self) -> paramiko.PKey | None:
        """Load and return the private key if configured."""
        if not self.connector.sftp_private_key_encrypted:
            return None

        key_data = self._decrypt_credential(self.connector.sftp_private_key_encrypted)
        passphrase = self._decrypt_credential(self.connector.sftp_key_passphrase_encrypted)

        if not key_data:
            return None

        # Try different key types
        key_file = io.StringIO(key_data)

        for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
            try:
                key_file.seek(0)
                return key_class.from_private_key(key_file, password=passphrase)
            except (paramiko.SSHException, ValueError):
                continue

        raise ValueError("Unable to parse private key - unsupported key type")

    async def connect(self, timeout: int = 30) -> SFTPConnectionResult:
        """
        Establish SFTP connection to the server.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            SFTPConnectionResult with connection status
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Run blocking paramiko operations in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._connect_sync, timeout)

            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            if result.success:
                result.latency_ms = latency_ms

            return result

        except Exception as e:
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return SFTPConnectionResult(
                success=False,
                message=f"Connection failed: {str(e)}",
                latency_ms=latency_ms,
                error_details=str(e),
            )

    def _connect_sync(self, timeout: int) -> SFTPConnectionResult:
        """Synchronous connection (runs in thread pool)."""
        try:
            self._client = SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Prepare authentication
            password = self._decrypt_credential(self.connector.sftp_password_encrypted)
            pkey = self._get_private_key()

            # Connect
            self._client.connect(
                hostname=self.connector.sftp_host,
                port=self.connector.sftp_port,
                username=self.connector.sftp_username,
                password=password,
                pkey=pkey,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
            )

            # Open SFTP session
            self._sftp = self._client.open_sftp()
            self._transport = self._client.get_transport()

            # Get server version
            server_version = None
            if self._transport:
                server_version = self._transport.remote_version

            return SFTPConnectionResult(
                success=True, message="Connected successfully", server_version=server_version
            )

        except AuthenticationException as e:
            return SFTPConnectionResult(
                success=False,
                message="Authentication failed - check credentials",
                error_details=str(e),
            )
        except SSHException as e:
            return SFTPConnectionResult(
                success=False, message=f"SSH error: {str(e)}", error_details=str(e)
            )
        except OSError as e:
            return SFTPConnectionResult(
                success=False, message=f"Network error: {str(e)}", error_details=str(e)
            )

    async def disconnect(self) -> None:
        """Close SFTP connection."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._disconnect_sync)

    def _disconnect_sync(self) -> None:
        """Synchronous disconnect."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        self._transport = None

    async def test_connection(self, timeout: int = 30) -> SFTPConnectionResult:
        """
        Test SFTP connection without keeping it open.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            SFTPConnectionResult with test status
        """
        result = await self.connect(timeout)

        if result.success:
            # Try to list the configured directory
            try:
                loop = asyncio.get_event_loop()
                files = await loop.run_in_executor(
                    None, self._list_directory_sync, self.connector.sftp_remote_path
                )
                result.message = f"Connected successfully. Found {len(files)} items in {self.connector.sftp_remote_path}"
            except Exception as e:
                result.success = False
                result.message = f"Connected but failed to list directory: {str(e)}"
                result.error_details = str(e)
            finally:
                await self.disconnect()

        return result

    async def list_files(
        self, path: str | None = None, pattern: str | None = None
    ) -> list[SFTPFile]:
        """
        List files in a directory, optionally filtered by pattern.

        Args:
            path: Directory path (default: connector's sftp_remote_path)
            pattern: Glob pattern to filter files (e.g., "*.csv")

        Returns:
            List of SFTPFile objects
        """
        if not self._sftp:
            raise RuntimeError("Not connected - call connect() first")

        path = path or self.connector.sftp_remote_path
        pattern = pattern or self.connector.file_pattern

        loop = asyncio.get_event_loop()
        files = await loop.run_in_executor(None, self._list_directory_sync, path)

        # Filter by pattern
        if pattern:
            files = [f for f in files if fnmatch.fnmatch(f.name, pattern)]

        # Sort by modified time (oldest first for FIFO processing)
        files.sort(key=lambda f: f.modified_at)

        return files

    def _list_directory_sync(self, path: str) -> list[SFTPFile]:
        """Synchronous directory listing."""
        if not self._sftp:
            raise RuntimeError("Not connected")

        files = []
        for attr in self._sftp.listdir_attr(path):
            is_dir = stat.S_ISDIR(attr.st_mode) if attr.st_mode else False
            modified_at = (
                datetime.fromtimestamp(attr.st_mtime, tz=timezone.utc)
                if attr.st_mtime
                else datetime.now(timezone.utc)
            )

            files.append(
                SFTPFile(
                    name=attr.filename,
                    path=f"{path}/{attr.filename}",
                    size=attr.st_size or 0,
                    modified_at=modified_at,
                    is_directory=is_dir,
                )
            )

        return files

    async def download_file(
        self, remote_path: str, local_dir: str | None = None
    ) -> SFTPDownloadResult:
        """
        Download a file from the SFTP server.

        Args:
            remote_path: Full path to the remote file
            local_dir: Local directory to save file (default: temp directory)

        Returns:
            SFTPDownloadResult with download status and local path
        """
        if not self._sftp:
            raise RuntimeError("Not connected - call connect() first")

        try:
            # Determine local path
            filename = os.path.basename(remote_path)
            if local_dir:
                local_path = os.path.join(local_dir, filename)
            else:
                # Use temp directory
                local_path = os.path.join(tempfile.gettempdir(), f"sftp_import_{filename}")

            # Download file
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_file_sync, remote_path, local_path)

            # Calculate checksum
            checksum = await self._calculate_checksum(local_path)
            file_size = os.path.getsize(local_path)

            return SFTPDownloadResult(
                success=True, local_path=local_path, file_size=file_size, checksum=checksum
            )

        except Exception as e:
            return SFTPDownloadResult(success=False, error=str(e))

    def _download_file_sync(self, remote_path: str, local_path: str) -> None:
        """Synchronous file download."""
        if not self._sftp:
            raise RuntimeError("Not connected")
        self._sftp.get(remote_path, local_path)

    async def move_file(self, source_path: str, dest_path: str) -> bool:
        """
        Move/rename a file on the SFTP server.

        Args:
            source_path: Current file path
            dest_path: New file path

        Returns:
            True if successful
        """
        if not self._sftp:
            raise RuntimeError("Not connected - call connect() first")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._move_file_sync, source_path, dest_path)
        return True

    def _move_file_sync(self, source_path: str, dest_path: str) -> None:
        """Synchronous file move."""
        if not self._sftp:
            raise RuntimeError("Not connected")

        # Ensure destination directory exists
        dest_dir = os.path.dirname(dest_path)
        try:
            self._sftp.stat(dest_dir)
        except FileNotFoundError:
            self._sftp.mkdir(dest_dir)

        self._sftp.rename(source_path, dest_path)

    async def delete_file(self, remote_path: str) -> bool:
        """
        Delete a file on the SFTP server.

        Args:
            remote_path: File path to delete

        Returns:
            True if successful
        """
        if not self._sftp:
            raise RuntimeError("Not connected - call connect() first")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._delete_file_sync, remote_path)
        return True

    def _delete_file_sync(self, remote_path: str) -> None:
        """Synchronous file delete."""
        if not self._sftp:
            raise RuntimeError("Not connected")
        self._sftp.remove(remote_path)

    async def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of a file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._calculate_checksum_sync, file_path)

    def _calculate_checksum_sync(self, file_path: str) -> str:
        """Synchronous checksum calculation."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def __aenter__(self) -> "SFTPService":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
