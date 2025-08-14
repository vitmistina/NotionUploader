from __future__ import annotations

from typing import Protocol, Optional

from fastapi import Depends
from upstash_redis import Redis

from .settings import Settings, get_settings


class RedisClient(Protocol):
    """Minimal Redis client interface used by the application."""

    def get(self, key: str) -> Optional[str]:
        ...

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        ...


def get_redis(settings: Settings = Depends(get_settings)) -> RedisClient:
    """Factory helper that provides a Redis client instance."""

    return Redis(url=settings.upstash_redis_rest_url, token=settings.upstash_redis_rest_token)
