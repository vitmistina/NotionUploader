from __future__ import annotations

from typing import Any, Dict

import httpx
from fastapi import Depends, HTTPException

from ..settings import Settings, get_settings
from .interfaces import NotionAPI


class NotionClient(NotionAPI):
    """Minimal Notion HTTP client with shared error handling."""

    def __init__(self, *, settings: Settings) -> None:
        self._base_url: str = "https://api.notion.com/v1"
        self._headers: Dict[str, str] = {
            "Authorization": f"Bearer {settings.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        self._timeout: float = 30.0

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(method, url, headers=self._headers, **kwargs)
        except httpx.ReadTimeout as exc:  # pragma: no cover - network failure
            raise HTTPException(status_code=504, detail="Request to Notion timed out") from exc
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp

    async def query(self, database_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._request("POST", f"/databases/{database_id}/query", json=payload)
        return resp.json()

    async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._request("POST", "/pages", json=payload)
        return resp.json()

    async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._request("PATCH", f"/pages/{page_id}", json=payload)
        return resp.json()

    async def retrieve(self, page_id: str) -> Dict[str, Any]:
        resp = await self._request("GET", f"/pages/{page_id}")
        return resp.json()

def get_notion_client(settings: Settings = Depends(get_settings)) -> NotionAPI:
    """Dependency that provides a configured Notion API client."""

    return NotionClient(settings=settings)
