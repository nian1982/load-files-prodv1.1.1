import json
from typing import Any

import redis

from solid.ws.config import WSSettings
from solid.ws.exceptions import WSPublishError
from solid.shared.logger import setup_logger

logger = setup_logger("solid.ws")


class RedisProgressPublisher:
    def __init__(self, settings: WSSettings | None = None):
        self._settings = settings or WSSettings()
        self._client: redis.Redis | None = None

    def _ensure_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(self._settings.redis_url)
        return self._client

    def publish(self, channel: str, data: dict[str, Any]) -> None:
        try:
            client = self._ensure_client()
            payload = json.dumps(data, default=str)
            client.publish(channel, payload)
        except Exception as e:
            raise WSPublishError(
                f"Failed to publish to channel {channel}", original=e,
            ) from e

    def save_state(self, key: str, data: dict[str, Any], ttl: int | None = None) -> None:
        try:
            client = self._ensure_client()
            payload = json.dumps(data, default=str)
            client.set(key, payload, ex=ttl or self._settings.state_ttl)
        except Exception as e:
            logger.warning("Failed to save state for %s: %s", key, e)

    def get_state(self, key: str) -> dict[str, Any] | None:
        try:
            client = self._ensure_client()
            data = client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning("Failed to get state for %s: %s", key, e)
            return None

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning("Error closing Redis: %s", e)
