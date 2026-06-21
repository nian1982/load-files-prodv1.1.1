import socket
from typing import BinaryIO, Callable, Optional

import paramiko

from solid.sftp.config import SFTPSettings
from solid.sftp.exceptions import SFTPConnectionError, SFTPDirectoryError, SFTPTransferError
from solid.shared.logger import setup_logger

logger = setup_logger("solid.sftp")


class ParamikoSFTPClient:
    def __init__(self, settings: SFTPSettings | None = None):
        self._settings = settings or SFTPSettings()
        self._transport: paramiko.Transport | None = None
        self._client: paramiko.SFTPClient | None = None

    def connect(self) -> None:
        try:
            logger.debug(
                "Connecting to SFTP: %s:%s",
                self._settings.host, self._settings.port,
            )
            self._transport = paramiko.Transport(
                (self._settings.host, self._settings.port),
            )
            self._transport.window_size = self._settings.window_size
            self._transport.sock.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_NODELAY, 1,
            )
            self._transport.connect(
                username=self._settings.user,
                password=self._settings.password,
            )
            self._client = paramiko.SFTPClient.from_transport(self._transport)
            logger.info(
                "SFTP connected to %s:%s (window=%sMB, chunk=%sMB)",
                self._settings.host, self._settings.port,
                self._settings.window_size // 1024 // 1024,
                self._settings.chunk_size // 1024 // 1024,
            )
        except Exception as e:
            raise SFTPConnectionError(
                f"Failed to connect to {self._settings.host}:{self._settings.port}",
                original=e,
            ) from e

    def ensure_directory(self, remote_dir: str) -> None:
        try:
            self._ensure_connected()
            parts = remote_dir.rstrip("/").split("/")
            path = ""
            for part in parts:
                if not part:
                    continue
                path = f"{path}/{part}"
                try:
                    self._client.stat(path)
                except FileNotFoundError:
                    self._client.mkdir(path)
                    logger.debug("Created remote directory: %s", path)
        except SFTPConnectionError:
            raise
        except Exception as e:
            raise SFTPDirectoryError(
                f"Failed to create directory {remote_dir}", original=e,
            ) from e

    def upload_file_stream(
        self,
        remote_path: str,
        file_obj: BinaryIO,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        total_bytes: int = 0,
    ) -> int:
        try:
            self._ensure_connected()
            total = 0
            with self._client.open(remote_path, "wb") as f:
                while True:
                    chunk = file_obj.read(self._settings.chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
                    if progress_callback:
                        progress_callback(total, total_bytes)
            logger.debug(
                "Uploaded stream to SFTP: %s (%d bytes)", remote_path, total,
            )
            return total
        except SFTPConnectionError:
            raise
        except Exception as e:
            raise SFTPTransferError(
                f"Failed to upload stream to {remote_path}", original=e,
            ) from e

    def disconnect(self) -> None:
        try:
            if self._client:
                self._client.close()
            if self._transport:
                self._transport.close()
            logger.debug("SFTP disconnected")
        except Exception as e:
            logger.warning("Error during SFTP disconnect: %s", e)

    def _ensure_connected(self) -> None:
        if not self._client:
            raise SFTPConnectionError(
                "SFTP client not connected. Call connect() first.",
            )
