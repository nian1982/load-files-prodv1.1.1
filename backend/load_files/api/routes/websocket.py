from fastapi import APIRouter, WebSocket, Depends, Query

from load_files.api.controllers.websocket_controller import UploadProgressWebSocket
from load_files.api.dependencies import get_websocket_handler

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{task_id}")
async def upload_progress(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
    handler: UploadProgressWebSocket = Depends(get_websocket_handler),
):
    await handler.handle(websocket, task_id, token)
