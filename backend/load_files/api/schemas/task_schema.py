from uuid import UUID

from pydantic import BaseModel


class TaskResponse(BaseModel):
    task_id: UUID
    status: str
    message: str = ""
