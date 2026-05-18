from typing import BinaryIO, Protocol
from load_files.models.upload_result import UploadResult

class UploadService(Protocol):
    def upload_file(self, file_name: str, file_obj: BinaryIO, tipo_archivo: str, fecha: str) -> UploadResult: ...
