import socket
from typing import BinaryIO, Callable, Optional

import paramiko

from load_files.config.settings import settings
from load_files.exceptions import SFTPConnectionException
from load_files.utils.logger import logger

CHUNK_SIZE = settings.SFTP_CHUNK_SIZE
WINDOW_SIZE = 64 * 1024 * 1024


class ParamikoSFTPClient:
    def __init__(self):
        self._transport: paramiko.Transport | None = None
        self._client: paramiko.SFTPClient | None = None

    def connect(self) -> None:
        try:
            logger.debug(
                "Connecting to SFTP: %s:%s",
                settings.SFTP_HOST, settings.SFTP_PORT,
            )
            self._transport = paramiko.Transport(
                (settings.SFTP_HOST, settings.SFTP_PORT),
            )

            self._transport.window_size = WINDOW_SIZE

            self._transport.sock.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_NODELAY, 1,
            )

            self._transport.connect(
                username=settings.SFTP_USER, password=settings.SFTP_PASS,
            )

            self._client = paramiko.SFTPClient.from_transport(self._transport)
            logger.info(
                "SFTP connected to %s:%s (window=%sMB, chunk=%sKB)",
                settings.SFTP_HOST, settings.SFTP_PORT,
                WINDOW_SIZE // 1024 // 1024,
                CHUNK_SIZE // 1024,
            )
        except Exception as e:
            raise SFTPConnectionException(
                f"Failed to connect to {settings.SFTP_HOST}:{settings.SFTP_PORT}",
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
        except SFTPConnectionException:
            raise
        except Exception as e:
            raise SFTPConnectionException(
                f"Failed to create directory {remote_dir}", original=e,
            ) from e

    def upload_file(self, remote_path: str, data: bytes) -> None:
        try:
            self._ensure_connected()
            with self._client.open(remote_path, "wb") as f:
                f.write(data)
            logger.debug(
                "Uploaded to SFTP: %s (%d bytes)", remote_path, len(data),
            )
        except SFTPConnectionException:
            raise
        except Exception as e:
            raise SFTPConnectionException(
                f"Failed to upload file to {remote_path}", original=e,
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
                    chunk = file_obj.read(CHUNK_SIZE)
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
        except SFTPConnectionException:
            raise
        except Exception as e:
            raise SFTPConnectionException(
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
            raise SFTPConnectionException(
                "SFTP client not connected. Call connect() first.",
            )
