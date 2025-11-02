import httpx
import pytest


pytestmark = pytest.mark.asyncio


async def test_head_root(client: httpx.AsyncClient) -> None:
    response = await client.head("/")
    assert response.status_code == 200
    assert response.text == ""


async def test_head_healthz(client: httpx.AsyncClient) -> None:
    response = await client.head("/healthz")
    assert response.status_code == 200
    assert response.text == ""
