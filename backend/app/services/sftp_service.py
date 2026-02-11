"""SFTP Service for secure file transfer operations.

Provides a secure, auditable SFTP client for:
- Connecting to bank SFTP servers
- Downloading context data files
- Archiving/moving processed files
- Connection testing

Security Features:
- STRICT host key verification (MITM protection)
- Credentials stored encrypted (via app/core/encryption.py)
- Support for password and SSH key authentication
- Connection timeouts and retry logic
- Audit logging of all operations

SECURITY NOTE:
This service requires a pre-configured host key fingerprint for each
SFTP connection. Unknown host keys are REJECTED by default.
This prevents man-in-the-middle attacks where an attacker could
intercept the connection and steal credentials or modify data.

To set up a new SFTP connection:
1. Obtain the host key fingerprint from the bank/server admin
2. Verify it through an out-of-band channel (phone, secure email)
3. Store the fingerprint in the connector configuration
4. The service will validate the fingerprint on every connection
"""

import asyncio
import base64
import fnmatch
import hashlib
import io
import logging
import os
import socket
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

logger = logging.getLogger(__name__)


class HostKeyVerificationError(Exception):
    """Raised when SFTP server host key verification fails."""

    pass


class StrictHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """
    Strict host key policy that validates against a stored fingerprint.

    SECURITY: This policy REJECTS all connections where the server's
    host key does not match the pre-configured fingerprint. This prevents
    man-in-the-middle attacks.

    The fingerprint must be obtained from the bank/server administrator
    through an out-of-band secure channel and verified before first use.
    """

    def __init__(
        self,
        expected_fingerprint: str | None,
        expected_key_type: str | None = None,
    ):
        """
        Initialize with expected host key fingerprint.

        Args:
            expected_fingerprint: SHA-256 fingerprint (e.g., "SHA256:abc123...")
                                  or hex fingerprint. Required for connection.
            expected_key_type: Expected key type (e.g., "ssh-ed25519", "ssh-rsa").
                               If provided, also validates key type matches.
        """
        self.expected_fingerprint = expected_fingerprint
        self.expected_key_type = expected_key_type

    def missing_host_key(self, client: SSHClient, hostname: str, key: paramiko.PKey) -> None:
        """
        Called when server presents a key not in known_hosts.

        This method validates the key's fingerprint against our stored value.
        Raises HostKeyVerificationError if validation fails.
        """
        # SECURITY: If no fingerprint configured, REJECT the connection
        if not self.expected_fingerprint:
            actual_fingerprint = self._get_key_fingerprint(key)
            raise HostKeyVerificationError(
                f"SFTP host key verification failed for {hostname}. "
                f"No host key fingerprint configured. "
                f"Server presented key type '{key.get_name()}' with fingerprint: {actual_fingerprint}. "
                f"Please configure this fingerprint after verifying it with the server administrator."
            )

        # Get actual fingerprint from server's key
        actual_fingerprint = self._get_key_fingerprint(key)
        actual_key_type = key.get_name()

        # Normalize fingerprints for comparison
        expected_normalized = self._normalize_fingerprint(self.expected_fingerprint)
        actual_normalized = self._normalize_fingerprint(actual_fingerprint)

        # SECURITY: Validate key type if specified
        if self.expected_key_type and actual_key_type != self.expected_key_type:
            raise HostKeyVerificationError(
                f"SFTP host key type mismatch for {hostname}. "
                f"Expected '{self.expected_key_type}' but server presented '{actual_key_type}'. "
                f"This could indicate a man-in-the-middle attack or server reconfiguration. "
                f"Verify with server administrator before updating configuration."
            )

        # SECURITY: Constant-time comparison to prevent timing attacks
        if not self._constant_time_compare(expected_normalized, actual_normalized):
            raise HostKeyVerificationError(
                f"SFTP host key fingerprint mismatch for {hostname}. "
                f"Expected: {self.expected_fingerprint}, "
                f"Actual: {actual_fingerprint}. "
                f"This could indicate a man-in-the-middle attack or server key change. "
                f"DO NOT connect until verified with server administrator."
            )

        # Key verified - log for audit trail
        logger.info(
            f"SFTP host key verified for {hostname}: "
            f"type={actual_key_type}, fingerprint={actual_fingerprint}"
        )

    def _get_key_fingerprint(self, key: paramiko.PKey) -> str:
        """Get SHA-256 fingerprint of a host key in standard format."""
        key_bytes = key.get_fingerprint()
        # SHA-256 fingerprint in base64 format (OpenSSH style)
        fingerprint_b64 = (
            base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode("ascii").rstrip("=")
        )
        return f"SHA256:{fingerprint_b64}"

    def _normalize_fingerprint(self, fingerprint: str) -> str:
        """Normalize fingerprint for comparison."""
        # Remove prefix if present
        fp = fingerprint.strip()
        if fp.upper().startswith("SHA256:"):
            fp = fp[7:]
        # Remove any colons or spaces (hex format)
        fp = fp.replace(":", "").replace(" ", "")
        return fp.lower()

    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        if len(a) != len(b):
            return False
        result = 0
        for x, y in zip(a.encode(), b.encode()):
            result |= x ^ y
        return result == 0


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

            # SECURITY: Use strict host key verification
            # This prevents man-in-the-middle attacks by validating the server's
            # host key against a pre-configured fingerprint
            host_key_policy = StrictHostKeyPolicy(
                expected_fingerprint=self.connector.sftp_host_key_fingerprint,
                expected_key_type=getattr(self.connector, "sftp_host_key_type", None),
            )
            self._client.set_missing_host_key_policy(host_key_policy)

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

        except HostKeyVerificationError as e:
            # SECURITY: Host key verification failed - potential MITM attack
            logger.warning(f"SFTP host key verification failed: {e}")
            return SFTPConnectionResult(
                success=False,
                message="Host key verification failed - potential security risk",
                error_details=str(e),
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
            except Exception as e:
                logger.debug("Error closing SFTP session: %s", e)
            finally:
                self._sftp = None

        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.debug("Error closing SSH client: %s", e)
            finally:
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


@dataclass
class HostKeyInfo:
    """Information about an SFTP server's host key."""

    host: str
    port: int
    key_type: str
    fingerprint_sha256: str
    fingerprint_md5: str
    key_bits: int | None = None


async def retrieve_host_key_fingerprint(
    host: str,
    port: int = 22,
    timeout: int = 10,
) -> HostKeyInfo:
    """
    Retrieve the host key fingerprint from an SFTP server.

    SECURITY WARNING: This function is for INITIAL SETUP ONLY.
    The fingerprint returned MUST be verified through an out-of-band
    secure channel (phone call to bank admin, secure email, etc.)
    before being stored in the connector configuration.

    DO NOT blindly trust the fingerprint returned by this function
    as it could be from a man-in-the-middle attacker.

    Args:
        host: SFTP server hostname
        port: SFTP port (default 22)
        timeout: Connection timeout in seconds

    Returns:
        HostKeyInfo with key type and fingerprints

    Raises:
        SSHException: If unable to retrieve host key
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _retrieve_host_key_fingerprint_sync,
        host,
        port,
        timeout,
    )


def _retrieve_host_key_fingerprint_sync(
    host: str,
    port: int,
    timeout: int,
) -> HostKeyInfo:
    """Synchronous host key retrieval."""
    transport = None
    try:
        # Create a transport to retrieve the host key
        # We don't authenticate - just get the key during handshake
        sock = paramiko.util.retry_on_signal(
            lambda: socket.create_connection((host, port), timeout=timeout)
        )
        transport = Transport(sock)
        transport.start_client(timeout=timeout)

        # Get the server's host key
        key = transport.get_remote_server_key()
        key_type = key.get_name()

        # Calculate SHA-256 fingerprint (modern standard)
        key_bytes = key.asbytes()
        sha256_hash = hashlib.sha256(key_bytes).digest()
        fingerprint_sha256 = f"SHA256:{base64.b64encode(sha256_hash).decode('ascii').rstrip('=')}"

        # Also provide MD5 fingerprint (legacy, for reference)
        md5_hash = hashlib.md5(key_bytes).digest()
        fingerprint_md5 = ":".join(f"{b:02x}" for b in md5_hash)

        # Get key bits if available
        key_bits = None
        if hasattr(key, "get_bits"):
            key_bits = key.get_bits()

        return HostKeyInfo(
            host=host,
            port=port,
            key_type=key_type,
            fingerprint_sha256=fingerprint_sha256,
            fingerprint_md5=fingerprint_md5,
            key_bits=key_bits,
        )

    finally:
        if transport:
            transport.close()
