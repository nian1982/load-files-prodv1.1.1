import json

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from load_files.api.security import verify_token
from load_files.config.settings import settings
from load_files.utils.logger import logger

CLIENT_ID = "api-load-files"
REQUIRED_ROLE = "load_files.upload"


class UploadProgressWebSocket:
    def __init__(self) -> None:
        self._redis_url = settings.REDIS_URL

    async def handle(self, websocket: WebSocket, task_id: str, token: str | None = None) -> None:
        payload = verify_token(token) if token else None
        if not payload:
            await websocket.close(code=4001, reason="Token invalido o expirado")
            return
        resource_access = payload.get("resource_access", {})
        client_roles = resource_access.get(CLIENT_ID, {}).get("roles", [])
        if REQUIRED_ROLE not in client_roles:
            await websocket.close(code=4002, reason=f"Se requiere el rol '{REQUIRED_ROLE}'")
            return

        await websocket.accept()
        logger.debug("WebSocket connected for task %s (user: %s)", task_id, payload.get("preferred_username"))

        try:
            redis_client = aioredis.from_url(self._redis_url)

            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"upload:{task_id}")

            state = await redis_client.get(f"upload:{task_id}:state")
            if state:
                data = json.loads(state)
                if data.get("type") in ("complete", "error"):
                    logger.warning("REPUBLISH: task=%s state=%s", task_id, data.get("type"))
                    await redis_client.publish(f"upload:{task_id}", state)
                else:
                    logger.warning("SENDING_STORED_STATE: task=%s type=%s", task_id, data.get("type"))
                    await websocket.send_text(state)
            else:
                logger.warning("NO_STORED_STATE: task=%s", task_id)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"].decode()
                    await websocket.send_text(data)

        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected for task %s", task_id)
        except Exception as e:
            logger.error("WebSocket error for task %s: %s", task_id, e)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal server error",
                })
            except Exception:
                pass
        finally:
            try:
                await pubsub.unsubscribe(f"upload:{task_id}")
                await pubsub.close()
                await redis_client.close()
            except Exception:
                pass
