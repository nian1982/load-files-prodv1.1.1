from uuid import UUID

from pydantic import BaseModel


class TaskResponse(BaseModel):
    task_id: UUID
    status: str
    message: str = ""
    file_name: str = ""
    extension: str = ""
    size_bytes: int = 0
    size_display: str = ""
    tipo_archivo: str = ""
    fecha: str = ""
    uploaded_by: str = ""
    enqueued_at: str = ""


class UploadResultResponse(BaseModel):
    type: str
    task_id: str
    result: dict | None = None
    message: str | None = None
    percentage: float | None = None
    elapsed: float | None = None
    file_name: str | None = None
    total_bytes: int | None = None
    size_display: str | None = None
    username: str | None = None
    timestamp: str | None = None
    bytes_sent: int | None = None
    speed_mbps: float | None = None
    eta_seconds: int | None = None
