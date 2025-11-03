"""Protocol interfaces for external service clients."""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable

import httpx


@runtime_checkable
class NotionAPI(Protocol):
    """Minimal interface for Notion API clients."""

    async def query(
        self, database_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Query a database and return the raw response."""

    async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new page and return the created object."""

    async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing page and return the updated object."""

    async def retrieve(self, page_id: str) -> Dict[str, Any]:
        """Fetch a page by its identifier."""


@runtime_checkable
class StravaAPI(Protocol):
    """HTTP client interface used for Strava requests."""

    async def get(
        self,
        url: str,
        *,
        headers: Dict[str, str],
    ) -> httpx.Response:  # pragma: no cover - thin wrapper
        """Perform a GET request."""


@runtime_checkable
class WithingsAPI(Protocol):
    """HTTP client interface used for Withings requests."""

    async def get(
        self, url: str, *, headers: Dict[str, str], params: Dict[str, Any]
    ) -> httpx.Response:  # pragma: no cover - thin wrapper
        """Perform a GET request."""

    async def post(
        self, url: str, *, data: Dict[str, Any]
    ) -> httpx.Response:  # pragma: no cover - thin wrapper
        """Perform a POST request."""

