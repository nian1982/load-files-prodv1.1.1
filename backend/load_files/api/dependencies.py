from functools import lru_cache

from load_files.api.controllers.upload_controller import UploadController
from load_files.api.controllers.websocket_controller import (
    UploadProgressWebSocket,
)
from load_files.factories.di import (
    get_sync_service,
    get_task_queue,
)


@lru_cache
def get_upload_controller() -> UploadController:
    return UploadController(get_sync_service(), get_task_queue())


@lru_cache
def get_websocket_handler() -> UploadProgressWebSocket:
    return UploadProgressWebSocket()
