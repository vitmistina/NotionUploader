from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import HTTPException

from src.services.notion import NotionClient, get_notion_client
from platform.config import Settings


@pytest.mark.asyncio
@respx.mock
async def test_notion_client_query_create_update_and_retrieve(
    respx_mock: respx.Router, settings: Settings
) -> None:
    respx_mock.post("https://api.notion.com/v1/databases/db/query").mock(
        return_value=httpx.Response(200, json={"object": "list"})
    )
    respx_mock.post("https://api.notion.com/v1/pages").mock(
        return_value=httpx.Response(200, json={"id": "created"})
    )
    respx_mock.patch("https://api.notion.com/v1/pages/page-id").mock(
        return_value=httpx.Response(200, json={"id": "updated"})
    )
    respx_mock.get("https://api.notion.com/v1/pages/page-id").mock(
        return_value=httpx.Response(200, json={"id": "retrieved"})
    )

    client = NotionClient(settings=settings)

    assert await client.query("db", {"filter": {}}) == {"object": "list"}
    assert await client.create({"properties": {}}) == {"id": "created"}
    assert await client.update("page-id", {"properties": {}}) == {"id": "updated"}
    assert await client.retrieve("page-id") == {"id": "retrieved"}


@pytest.mark.asyncio
@respx.mock
async def test_notion_client_raises_http_exception_for_error_status(
    respx_mock: respx.Router, settings: Settings
) -> None:
    respx_mock.get("https://api.notion.com/v1/pages/missing").mock(
        return_value=httpx.Response(404, text="not found")
    )

    client = NotionClient(settings=settings)

    with pytest.raises(HTTPException) as exc_info:
        await client.retrieve("missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"error": "not found"}


@pytest.mark.asyncio
@respx.mock
async def test_notion_client_raises_gateway_timeout_on_read_timeout(
    respx_mock: respx.Router, settings: Settings
) -> None:
    respx_mock.post("https://api.notion.com/v1/pages").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    client = NotionClient(settings=settings)

    with pytest.raises(HTTPException) as exc_info:
        await client.create({"properties": {}})

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == {"error": "Request to Notion timed out"}


def test_get_notion_client_returns_notion_client(settings: Settings) -> None:
    assert isinstance(get_notion_client(settings), NotionClient)
