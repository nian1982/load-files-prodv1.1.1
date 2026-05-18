from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(slots=True)
class UploadResult:
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
