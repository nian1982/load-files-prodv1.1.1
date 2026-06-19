import json

import redis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from load_files.api.controllers.upload_controller import UploadController
from load_files.api.dependencies import get_upload_controller
from load_files.api.schemas.task_schema import TaskResponse, UploadResultResponse
from load_files.api.security import require_client_role
from load_files.config.settings import settings

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=TaskResponse)
def upload_file(
    tipo_archivo: str = Form(...),
    fecha: str = Form(...),
    file: UploadFile = File(...),
    controller: UploadController = Depends(get_upload_controller),
    user: dict = Depends(require_client_role("api-load-files", "load_files.upload")),
):
    result = controller.upload_async(
        file, tipo_archivo, fecha,
        username=user.get("preferred_username", "unknown"),
    )
    return result


@router.get("/{task_id}/result", response_model=UploadResultResponse)
def get_upload_result(
    task_id: str,
    user: dict = Depends(require_client_role("api-load-files", "load_files.upload")),
):
    r = redis.Redis.from_url(settings.REDIS_URL)
    try:
        state = r.get(f"upload:{task_id}:state")
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found or expired",
            )
        return json.loads(state)
    finally:
        r.close()
