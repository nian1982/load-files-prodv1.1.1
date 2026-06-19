import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from load_files.config.settings import settings
from load_files.exceptions import (
    DomainException,
    FileTypeNotAllowedException,
    ValidationException,
)
from load_files.implementations.upload_service_impl import UploadServiceImpl
from load_files.interfaces.task_queue import TaskQueue
from load_files.utils.logger import logger
from load_files.utils.path_utils import build_upload_path


class UploadController:
    def __init__(
        self,
        sync_service: UploadServiceImpl,
        task_queue: TaskQueue,
    ):
        self._sync_service = sync_service
        self._task_queue = task_queue

    def upload_sync(
        self,
        file: UploadFile,
        tipo_archivo: str,
        fecha: str,
    ) -> dict:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided",
            )
        try:
            result = self._sync_service.upload_file(
                file.filename, file.file, tipo_archivo, fecha,
            )
            return {
                "success": result.success,
                "id": str(result.id),
                "file_name": result.file_name,
                "extension": result.extension,
                "size_bytes": result.size_bytes,
                "size_display": result.size_display,
                "upload_path": result.upload_path,
                "upload_time_seconds": result.upload_time_seconds,
                "tipo_archivo": result.tipo_archivo,
                "fecha": result.fecha,
                "uploaded_at": (
                    result.uploaded_at.isoformat()
                    if result.uploaded_at else None
                ),
                "error": result.error,
            }
        except FileTypeNotAllowedException as e:
            logger.warning("File type not allowed: %s", e.message)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.message,
            )
        except ValidationException as e:
            logger.warning("Validation error: %s", e.message)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.message,
            )
        except DomainException as e:
            logger.error("Domain error: %s - %s", e.code, e.message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.message,
            )

    def upload_async(
        self,
        file: UploadFile,
        tipo_archivo: str,
        fecha: str,
        username: str,
    ) -> dict:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided",
            )

        try:
            self._sync_service.validate_upload_request(
                file.filename, tipo_archivo, fecha,
                file_obj=file.file,
            )
        except FileTypeNotAllowedException as e:
            logger.warning("File type not allowed: %s", e.message)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.message,
            )
        except ValidationException as e:
            logger.warning("Validation error: %s", e.message)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.message,
            )

        file.file.seek(0)
        task_id = str(uuid4())
        temp_dir = Path(settings.TEMP_UPLOAD_DIR) / task_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file.filename

        try:
            with open(temp_path, "wb") as dest:
                shutil.copyfileobj(file.file, dest)
            logger.info(
                "File saved to temp: %s (%s bytes)",
                temp_path, os.path.getsize(temp_path),
            )
        except OSError as e:
            logger.error("Failed to save temp file: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process uploaded file",
            )

        try:
            self._task_queue.enqueue_upload(
                task_id=task_id,
                file_path=str(temp_path),
                file_name=file.filename,
                tipo_archivo=tipo_archivo,
                fecha=fecha,
                username=username,
            )
            logger.info(
                "Task enqueued: task_id=%s file=%s user=%s",
                task_id, file.filename, username,
            )
        except Exception as e:
            logger.error("Failed to enqueue task: %s", e)
            _cleanup_temp(str(temp_path))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload queue unavailable. Try again later.",
            )

        extension = self._get_extension(file.filename)
        size_bytes = os.path.getsize(temp_path)
        upload_path = build_upload_path(
            settings.SFTP_UPLOAD_DIR, tipo_archivo, fecha, file.filename,
        )

        return {
            "task_id": task_id,
            "status": "queued",
            "message": "File received and queued for upload",
            "file_name": file.filename,
            "extension": extension,
            "size_bytes": size_bytes,
            "size_display": self._format_size(size_bytes),
            "tipo_archivo": tipo_archivo,
            "fecha": fecha,
            "upload_path": upload_path,
            "uploaded_by": username,
            "enqueued_at": datetime.now().isoformat(),
        }

    def _get_extension(self, file_name: str) -> str:
        idx = file_name.rfind(".")
        return file_name[idx:].lower() if idx != -1 else ""

    @staticmethod
    def _format_size(bytes_: int) -> str:
        size = float(bytes_)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"


def _cleanup_temp(file_path: str) -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        parent = os.path.dirname(file_path)
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    except OSError:
        pass
