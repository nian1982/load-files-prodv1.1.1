import json

from fastapi import WebSocket, WebSocketDisconnect

from load_files.api.security import verify_token
from load_files.utils.logger import logger
from solid.ws.redis_subscriber import RedisProgressSubscriber

CLIENT_ID = "api-load-files"
REQUIRED_ROLE = "load_files.upload"


class UploadProgressWebSocket:
    def __init__(self) -> None:
        self._subscriber: RedisProgressSubscriber | None = None

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

        channel = f"upload:{task_id}"
        subscriber = RedisProgressSubscriber()

        try:
            await subscriber.connect()
            await subscriber.subscribe(channel)

            state = await subscriber.get_state(f"upload:{task_id}:state")
            if state:
                if state.get("type") in ("complete", "error"):
                    await subscriber.publish(channel, state)
                else:
                    await websocket.send_text(json.dumps(state))

            async for data in subscriber.listen():
                await websocket.send_text(json.dumps(data))

        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected for task %s", task_id)
        except Exception as e:
            logger.error("WebSocket error for task %s: %s", task_id, e)
            try:
                await websocket.send_json({"type": "error", "message": "Internal server error"})
            except Exception:
                pass
        finally:
            try:
                await subscriber.unsubscribe(channel)
                await subscriber.close()
            except Exception:
                pass
