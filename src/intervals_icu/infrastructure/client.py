from __future__ import annotations

from datetime import date
from platform.config import Settings
from typing import Any

import httpx

from ..application.ports import (
    IntervalsApiError,
    IntervalsAuthError,
    IntervalsClientPort,
    IntervalsPayloadError,
)


class IntervalsClientAdapter:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http_client
        self._settings = settings
        self._base_url = settings.intervals_api_base_url.rstrip("/")

    async def list_activities(self, *, oldest: date, newest: date) -> list[dict[str, Any]]:
        path = f"/athlete/{self._settings.intervals_athlete_id}/activities"
        payload = await self._get_json(
            path, params={"oldest": oldest.isoformat(), "newest": newest.isoformat()}
        )
        if not isinstance(payload, list):
            raise IntervalsPayloadError("Intervals.icu activities response must be a list")
        if not all(isinstance(item, dict) for item in payload):
            raise IntervalsPayloadError("Intervals.icu activities response contains malformed item")
        return payload

    async def get_activity_intervals(self, activity_id: str) -> list[dict[str, Any]]:
        path = f"/activity/{activity_id}/intervals"
        try:
            payload = await self._get_json(path)
        except IntervalsApiError as exc:
            if exc.status_code == 404:
                return []
            raise
        if not isinstance(payload, dict):
            raise IntervalsPayloadError("Intervals.icu intervals response must be an object")
        intervals = payload.get("icu_intervals")
        if intervals is None:
            return []
        if not isinstance(intervals, list):
            raise IntervalsPayloadError("Intervals.icu icu_intervals must be a list")
        if not all(isinstance(item, dict) for item in intervals):
            raise IntervalsPayloadError("Intervals.icu icu_intervals contains malformed item")
        return intervals

    async def _get_json(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        try:
            response = await self._http.get(
                f"{self._base_url}{path}",
                params=params,
                auth=httpx.BasicAuth("API_KEY", self._settings.intervals_api_key),
                headers={"Accept": "application/json", "User-Agent": "NotionUploader/0.1"},
            )
        except httpx.HTTPError as exc:
            raise IntervalsApiError(f"Intervals.icu GET {path} request failed") from exc
        if response.status_code in {401, 403}:
            raise IntervalsAuthError(
                f"Intervals.icu GET {path} request failed with status {response.status_code}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise IntervalsApiError(
                f"Intervals.icu GET {path} request failed with status {response.status_code}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise IntervalsPayloadError(f"Intervals.icu GET {path} returned invalid JSON") from exc


def create_intervals_client_adapter(
    *, http_client: httpx.AsyncClient, settings: Settings
) -> IntervalsClientPort:
    return IntervalsClientAdapter(http_client, settings)
