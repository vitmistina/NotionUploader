from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from ..settings import Settings


class NotionClient:
    """Lightweight asynchronous client for interacting with the Notion API."""

    def __init__(
        self,
        settings: Settings,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.settings = settings
        self._client = http_client
        self._own_client = http_client is None

    async def __aenter__(self) -> NotionClient:  # pragma: no cover - convenience
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - convenience
        await self.close()

    async def close(self) -> None:
        if self._client is not None and self._own_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            self._own_client = True
        headers = kwargs.pop("headers", {})
        headers = {**self._headers(), **headers}
        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
        except httpx.ReadTimeout as exc:  # pragma: no cover - network failure
            raise HTTPException(status_code=504, detail="Request to Notion timed out") from exc
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response

    # ------------------------------------------------------------------
    # public methods
    # ------------------------------------------------------------------
    async def query_database(
        self, database_id: str, payload: Dict[str, Any]
    ) -> httpx.Response:
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        return await self._request("POST", url, json=payload)

    async def create_page(self, payload: Dict[str, Any]) -> httpx.Response:
        url = "https://api.notion.com/v1/pages"
        return await self._request("POST", url, json=payload)

    async def update_page(self, page_id: str, payload: Dict[str, Any]) -> httpx.Response:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        return await self._request("PATCH", url, json=payload)
