from load_files.interfaces.task_queue import TaskQueue
from load_files.tasks.upload_task import upload_to_sftp


class CeleryTaskQueue(TaskQueue):
    def enqueue_upload(
        self,
        task_id: str,
        file_path: str,
        file_name: str,
        tipo_archivo: str,
        fecha: str,
        username: str,
    ) -> None:
        upload_to_sftp.delay(
            task_id=task_id,
            file_path=file_path,
            file_name=file_name,
            tipo_archivo=tipo_archivo,
            fecha=fecha,
            username=username,
        )
