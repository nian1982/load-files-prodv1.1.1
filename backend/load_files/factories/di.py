from functools import lru_cache

from load_files.implementations.celery_task_queue import CeleryTaskQueue
from load_files.implementations.paramiko_sftp_client import ParamikoSFTPClient
from load_files.implementations.upload_service_impl import UploadServiceImpl
from load_files.interfaces.task_queue import TaskQueue


def create_sftp_client() -> ParamikoSFTPClient:
    return ParamikoSFTPClient()


def create_upload_service() -> UploadServiceImpl:
    return UploadServiceImpl(create_sftp_client())


def create_task_queue() -> TaskQueue:
    return CeleryTaskQueue()


@lru_cache
def get_sync_service() -> UploadServiceImpl:
    return create_upload_service()


@lru_cache
def get_task_queue() -> TaskQueue:
    return create_task_queue()
