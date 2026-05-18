from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID

class UploadResponse(BaseModel):
    id: UUID
    success: bool
    file_name: str
    extension: str
    size_bytes: int
    size_display: str
    upload_path: str
    upload_time_seconds: float
    tipo_archivo: str
    fecha: str
    uploaded_at: datetime | None = None
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)
