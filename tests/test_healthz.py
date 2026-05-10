from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from platform.clients import get_redis
from src.main import HEALTHZ_LAST_CHECK_KEY
from tests.conftest import RedisFake


pytestmark = pytest.mark.asyncio


class BrokenRedis:
    def get(self, key: str):  # noqa: ANN001, ANN201
        raise httpx.ConnectError(
            "upstash unavailable",
            request=httpx.Request("GET", "https://redis.example.com/get/healthz:last_check_at"),
        )

    def set(self, key: str, value: str, ex: int | None = None) -> None:  # noqa: ARG002
        return None


async def test_head_root(client: httpx.AsyncClient) -> None:
    response = await client.head("/")
    assert response.status_code == 200
    assert response.text == ""


async def test_head_healthz(client: httpx.AsyncClient) -> None:
    response = await client.head("/healthz")
    assert response.status_code == 200
    assert response.text == ""


async def test_healthz_returns_previous_check_and_records_current_timestamp(
    client: httpx.AsyncClient, redis_fake: RedisFake
) -> None:
    previous_check_at = "2026-05-10T12:00:00+00:00"
    redis_fake.expect_get(HEALTHZ_LAST_CHECK_KEY, returns=previous_check_at)
    redis_fake.expect_set(HEALTHZ_LAST_CHECK_KEY)

    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "previous_check_at": previous_check_at,
    }
    redis_fake.assert_last_get(HEALTHZ_LAST_CHECK_KEY)
    recorded_check_at = redis_fake.store[HEALTHZ_LAST_CHECK_KEY]
    assert datetime.fromisoformat(recorded_check_at).tzinfo == timezone.utc
    assert recorded_check_at != previous_check_at


async def test_root_returns_previous_check_and_records_current_timestamp(
    client: httpx.AsyncClient, redis_fake: RedisFake
) -> None:
    previous_check_at = "2026-05-10T12:00:00+00:00"
    redis_fake.expect_get(HEALTHZ_LAST_CHECK_KEY, returns=previous_check_at)
    redis_fake.expect_set(HEALTHZ_LAST_CHECK_KEY)

    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "previous_check_at": previous_check_at,
    }
    redis_fake.assert_last_get(HEALTHZ_LAST_CHECK_KEY)
    recorded_check_at = redis_fake.store[HEALTHZ_LAST_CHECK_KEY]
    assert datetime.fromisoformat(recorded_check_at).tzinfo == timezone.utc
    assert recorded_check_at != previous_check_at


async def test_healthz_returns_503_when_upstash_is_unreachable(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    app.dependency_overrides[get_redis] = lambda: BrokenRedis()
    try:
        response = await client.get("/healthz")
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 503
    assert response.json() == {
        "error": "UPSTREAM_CONNECTION_FAILED",
        "message": (
            "Could not connect to an upstream dependency service. "
            "Please try again shortly."
        ),
        "upstream_host": "redis.example.com",
    }
