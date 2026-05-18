from fastapi import APIRouter, Depends, File, Form, UploadFile
from load_files.api.controllers.upload_controller import UploadController
from load_files.api.dependencies import get_upload_controller
from load_files.api.schemas.task_schema import TaskResponse
from load_files.api.security import require_client_role

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
