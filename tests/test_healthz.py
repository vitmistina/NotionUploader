import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import main


@pytest.mark.asyncio
async def test_head_root() -> None:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.head("/")
    assert response.status_code == 200
    assert response.text == ""


@pytest.mark.asyncio
async def test_head_healthz() -> None:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.head("/healthz")
    assert response.status_code == 200
    assert response.text == ""
