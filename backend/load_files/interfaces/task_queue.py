from typing import Protocol


class TaskQueue(Protocol):
    def enqueue_upload(
        self,
        task_id: str,
        file_path: str,
        file_name: str,
        tipo_archivo: str,
        fecha: str,
        username: str,
    ) -> None: ...
