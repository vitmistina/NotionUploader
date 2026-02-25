import httpx
import pytest
from fastapi import FastAPI

from platform.clients import get_redis


pytestmark = pytest.mark.asyncio


class BrokenRedis:
    def get(self, key: str):  # noqa: ANN001, ANN201
        raise httpx.ConnectError(
            "upstash unavailable",
            request=httpx.Request("GET", "https://redis.example.com/get/healthz:upstash"),
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
