import os
import time
from typing import BinaryIO
from datetime import datetime
from uuid import uuid4

from load_files.config.settings import settings
from load_files.exceptions import (
    FileTypeNotAllowedException,
    ValidationException,
)
from load_files.implementations.paramiko_sftp_client import ParamikoSFTPClient
from load_files.interfaces.upload_service import UploadService
from load_files.models.upload_result import UploadResult
from load_files.utils.logger import logger

MAGIC_BYTE_CHECKS: dict[str, list[tuple[bytes, int]]] = {
    ".pdf": [(b"%PDF", 0)],
    ".xlsx": [(b"PK\x03\x04", 0)],
    ".xls": [(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", 0)],
}


class UploadServiceImpl(UploadService):
    def __init__(self, sftp_client: ParamikoSFTPClient):
        self._sftp_client = sftp_client

    def upload_file(
        self,
        file_name: str,
        file_obj: BinaryIO,
        tipo_archivo: str,
        fecha: str,
    ) -> UploadResult:
        tipo_archivo = tipo_archivo.strip().upper()
        self._validate_file_type(tipo_archivo)
        self._validate_fecha(fecha)

        extension = self._get_extension(file_name)
        self._validate_extension(extension)
        self._validate_magic_bytes(file_obj, extension)

        date_compressed = fecha.replace("-", "")
        hour = datetime.now().strftime("%H")
        remote_dir = (
            f"{settings.SFTP_UPLOAD_DIR.rstrip('/')}"
            f"/{tipo_archivo}/{date_compressed}/{hour}"
        )
        remote_path = f"{remote_dir}/{file_name}"

        logger.info(
            "Starting upload: type=%s, date=%s, file=%s",
            tipo_archivo, fecha, file_name,
        )

        start_time = time.perf_counter()
        total_bytes = 0
        try:
            self._validate_file_size(file_obj)
            self._sftp_client.connect()
            self._sftp_client.ensure_directory(remote_dir)
            total_bytes = self._sftp_client.upload_file_stream(
                remote_path, file_obj,
            )
            elapsed = time.perf_counter() - start_time
            logger.info(
                "Upload successful: %s (%d bytes) in %.2fs",
                remote_path, total_bytes, elapsed,
            )
            return UploadResult(
                id=uuid4(),
                success=True,
                file_name=file_name,
                extension=extension,
                size_bytes=total_bytes,
                size_display=self._format_size(total_bytes),
                upload_path=remote_path,
                upload_time_seconds=round(elapsed, 2),
                tipo_archivo=tipo_archivo,
                fecha=fecha,
                uploaded_at=datetime.now(),
            )
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error("Upload failed: %s - %s", file_name, e)
            return UploadResult(
                id=uuid4(),
                success=False,
                file_name=file_name,
                extension=extension,
                size_bytes=total_bytes,
                size_display=self._format_size(total_bytes),
                upload_path=remote_path,
                upload_time_seconds=round(elapsed, 2),
                tipo_archivo=tipo_archivo,
                fecha=fecha,
                error=self._safe_error(e),  # type: ignore[arg-type]
            )
        finally:
            self._sftp_client.disconnect()

    def validate_upload_request(
        self,
        file_name: str,
        tipo_archivo: str,
        fecha: str,
        file_obj: BinaryIO | None = None,
    ) -> tuple[str, str, str]:
        tipo_archivo = tipo_archivo.strip().upper()
        self._validate_file_type(tipo_archivo)
        self._validate_fecha(fecha)
        extension = self._get_extension(file_name)
        self._validate_extension(extension)
        if file_obj:
            self._validate_magic_bytes(file_obj, extension)
        return tipo_archivo, extension, fecha

    def _safe_error(self, error: Exception) -> str:
        if settings.ENVIRONMENT.lower() == "production":
            return "An internal error occurred. Contact the administrator."
        return str(error)

    def _validate_extension(self, extension: str) -> None:
        allowed = settings.ALLOWED_EXTENSIONS_LIST
        if extension not in allowed:
            raise ValidationException(
                f"Extension '{extension}' not allowed. "
                f"Allowed: {', '.join(allowed)}",
            )

    def _validate_magic_bytes(self, file_obj: BinaryIO, extension: str) -> None:
        checks = MAGIC_BYTE_CHECKS.get(extension)
        if not checks:
            return

        pos = file_obj.tell()
        try:
            header = file_obj.read(16)
            file_obj.seek(pos)

            for magic, offset in checks:
                if not header[offset:].startswith(magic):
                    raise ValidationException(
                        f"File content does not match extension '{extension}'. "
                        "The file appears to be corrupted or renamed.",
                    )
        except (OSError, AttributeError):
            pass

    def _validate_file_size(self, file_obj: BinaryIO) -> None:
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if max_bytes <= 0:
            return
        try:
            pos = file_obj.tell()
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(pos)
            if size > max_bytes:
                raise ValidationException(
                    f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
                )
        except (OSError, AttributeError):
            pass

    def _validate_file_type(self, tipo_archivo: str) -> None:
        allowed = settings.ALLOWED_FILE_TYPES_LIST
        if tipo_archivo not in allowed:
            raise FileTypeNotAllowedException(tipo_archivo, allowed)

    def _validate_fecha(self, fecha: str) -> None:
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            raise ValidationException(
                f"Invalid date format '{fecha}'. Expected YYYY-MM-DD",
            )

    def _get_extension(self, file_name: str) -> str:
        idx = file_name.rfind(".")
        return file_name[idx:].lower() if idx != -1 else ""

    def _format_size(self, bytes_: int) -> str:
        size = float(bytes_)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
