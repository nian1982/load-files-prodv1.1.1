from functools import lru_cache

from solid.sftp.config import SFTPSettings
from solid.sftp.paramiko_client import ParamikoSFTPClient
from solid.upload.service import UploadService

from load_files.config.settings import settings
from load_files.implementations.celery_task_queue import CeleryTaskQueue
from load_files.interfaces.task_queue import TaskQueue


def create_sftp_client() -> ParamikoSFTPClient:
    sftp_settings = SFTPSettings(
        host=settings.SFTP_HOST,
        port=settings.SFTP_PORT,
        user=settings.SFTP_USER,
        password=settings.SFTP_PASS,
        upload_dir=settings.SFTP_UPLOAD_DIR,
        chunk_size=settings.SFTP_CHUNK_SIZE,
    )
    return ParamikoSFTPClient(sftp_settings)


def create_upload_service() -> UploadService:
    return UploadService(
        create_sftp_client(),
        upload_dir=settings.SFTP_UPLOAD_DIR,
    )


def create_task_queue() -> TaskQueue:
    return CeleryTaskQueue()


@lru_cache
def get_sync_service() -> UploadService:
    return create_upload_service()


@lru_cache
def get_task_queue() -> TaskQueue:
    return create_task_queue()
