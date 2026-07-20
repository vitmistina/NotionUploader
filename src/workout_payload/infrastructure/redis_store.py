"""Upstash Redis implementation of workout payload retention."""

from __future__ import annotations

from platform.clients import RedisClient

from ..application.ports import WorkoutPayloadStore

DEFAULT_RETENTION_DAYS = 120


class RedisWorkoutPayloadStore(WorkoutPayloadStore):
    """Store compressed payloads under stable source and activity keys."""

    def __init__(self, redis: RedisClient, *, retention_days: int = DEFAULT_RETENTION_DAYS) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        self._redis = redis
        self._retention_seconds = retention_days * 24 * 60 * 60

    async def put(self, key: str, gzip_base64_payload: str) -> None:
        self._redis.set(key, gzip_base64_payload, ex=self._retention_seconds)

    async def get(self, key: str) -> str | None:
        return self._redis.get(key)


def workout_payload_key(source: str, external_id: str) -> str:
    """Build the versioned Redis key used by ingestion and retrieval."""
    return f"workout-payload:v1:{source}:{external_id}"


__all__ = ["DEFAULT_RETENTION_DAYS", "RedisWorkoutPayloadStore", "workout_payload_key"]
