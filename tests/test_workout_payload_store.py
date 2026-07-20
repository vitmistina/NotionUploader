import pytest

from src.workout_payload.infrastructure.redis_store import (
    RedisWorkoutPayloadStore,
    workout_payload_key,
)


class Redis:
    def __init__(self) -> None:
        self.values = {}
        self.expirations = {}

    def set(self, key, value, ex=None):
        self.values[key] = value
        self.expirations[key] = ex

    def get(self, key):
        return self.values.get(key)


@pytest.mark.asyncio
async def test_payload_store_uses_versioned_key_and_retention() -> None:
    redis = Redis()
    store = RedisWorkoutPayloadStore(redis, retention_days=120)
    key = workout_payload_key("intervals_icu", "activity-1")

    await store.put(key, "compressed")

    assert await store.get(key) == "compressed"
    assert key == "workout-payload:v1:intervals_icu:activity-1"
    assert redis.expirations[key] == 120 * 24 * 60 * 60
