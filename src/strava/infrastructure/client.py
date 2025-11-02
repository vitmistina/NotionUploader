from __future__ import annotations

from typing import Any, Optional

import httpx

from ...services.redis import RedisClient
from ...settings import Settings
from ..application.ports import StravaAuthError, StravaClientPort


class StravaClient(StravaClientPort):
    """HTTP client for Strava that manages OAuth token refresh."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        redis: RedisClient,
        settings: Settings,
    ) -> None:
        self._http_client = http_client
        self._redis = redis
        self._settings = settings

    async def get_activity(self, activity_id: int) -> dict[str, Any]:
        """Fetch an activity from Strava, refreshing auth if necessary."""

        access_token = await self._ensure_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self._http_client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers=headers,
        )
        if response.status_code == 401:
            access_token = await self._refresh_access_token()
            headers["Authorization"] = f"Bearer {access_token}"
            response = await self._http_client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers=headers,
            )
        response.raise_for_status()
        return response.json()

    async def _ensure_access_token(self) -> str:
        token = self._redis.get("strava_access_token")
        if token:
            return token
        return await self._refresh_access_token()

    async def _refresh_access_token(self) -> str:
        refresh_token = self._redis.get("strava_refresh_token")
        if not refresh_token:
            raise StravaAuthError("No Strava refresh token found in Redis")

        payload = {
            "client_id": self._settings.strava_client_id,
            "client_secret": self._settings.strava_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        response = await self._http_client.post(
            "https://www.strava.com/api/v3/oauth/token", data=payload
        )
        if response.status_code != 200:
            raise StravaAuthError("Failed to refresh Strava access token")

        data = response.json()
        access_token: Optional[str] = data.get("access_token")
        new_refresh_token: Optional[str] = data.get("refresh_token")
        expires_in: Optional[int] = data.get("expires_in")

        if not access_token:
            raise StravaAuthError("Strava token refresh response missing access token")

        if expires_in:
            self._redis.set(
                "strava_access_token",
                access_token,
                ex=int(expires_in) - 30,
            )
        else:
            self._redis.set("strava_access_token", access_token)

        if new_refresh_token:
            self._redis.set(
                "strava_refresh_token",
                new_refresh_token,
                ex=365 * 24 * 60 * 60,
            )

        return access_token
