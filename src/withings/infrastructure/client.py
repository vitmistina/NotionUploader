"""HTTP-backed implementation of the Withings measurements port."""
from __future__ import annotations

import time
from datetime import datetime
from typing import List, Sequence

import httpx

from ...models.body import BodyMeasurement
from ...services.redis import RedisClient
from ...settings import Settings
from ..application.ports import WithingsMeasurementsPort


class WithingsMeasurementsAdapter(WithingsMeasurementsPort):
    """Interact with the Withings API using tokens stored in Redis."""

    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def refresh_access_token(self) -> str:
        """Refresh the Withings access token using the stored refresh token."""
        refresh_token = self._redis.get("withings_refresh_token")
        if not refresh_token:
            raise ValueError("No Withings refresh token found in Redis")

        payload = {
            "action": "requesttoken",
            "client_id": self._settings.withings_client_id,
            "client_secret": self._settings.withings_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._settings.wbsapi_url}/v2/oauth2", data=payload
            )

        if response.status_code != 200:
            raise RuntimeError("Failed to refresh Withings access token")

        data = response.json()
        if data.get("status") != 0:
            raise RuntimeError(f"Withings API error: {data.get('error')}")

        body = data.get("body", {})
        new_access_token = body.get("access_token")
        new_refresh_token = body.get("refresh_token")
        expires_in = body.get("expires_in")

        if not new_access_token:
            raise RuntimeError("Withings refresh response missing access token")

        # Access token expires in specified time minus 30s buffer
        if expires_in:
            self._redis.set(
                "withings_access_token", new_access_token, ex=int(expires_in) - 30
            )
        else:
            self._redis.set("withings_access_token", new_access_token)

        # Refresh token expires in 1 year
        if new_refresh_token:
            self._redis.set("withings_refresh_token", new_refresh_token, ex=365 * 24 * 60 * 60)

        return new_access_token

    async def fetch_measurements(self, days: int) -> Sequence[BodyMeasurement]:
        """Fetch Withings measurements for the provided day range."""
        access_token = self._redis.get("withings_access_token")
        if not access_token:
            access_token = await self.refresh_access_token()

        startdate = int(time.time()) - (days * 24 * 60 * 60)
        enddate = int(time.time())
        payload = {
            "action": "getmeas",
            "startdate": startdate,
            "enddate": enddate,
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._settings.wbsapi_url}/v2/measure",
                headers=headers,
                params=payload,
            )

        if response.status_code == 401:
            access_token = await self.refresh_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._settings.wbsapi_url}/v2/measure",
                    headers=headers,
                    params=payload,
                )

        data = response.json()
        if data.get("status") != 0:
            raise RuntimeError(f"Withings API error: {data.get('error')}")

        measuregroups = data.get("body", {}).get("measuregrps", [])
        measurements: List[BodyMeasurement] = []
        for group in measuregroups:
            measurement_time = datetime.fromtimestamp(group.get("date", 0))
            measures = {
                m["type"]: m["value"] * (10 ** m["unit"])
                for m in group.get("measures", [])
            }
            measurements.append(
                BodyMeasurement(
                    measurement_time=measurement_time,
                    weight_kg=measures.get(1, 0),
                    fat_mass_kg=measures.get(8, 0),
                    muscle_mass_kg=measures.get(76, 0),
                    bone_mass_kg=measures.get(88, 0),
                    hydration_kg=measures.get(77, 0),
                    fat_free_mass_kg=measures.get(5, 0),
                    body_fat_percent=measures.get(6, 0),
                    device_name=group.get("device", "Withings Device"),
                )
            )

        return measurements


def create_withings_measurements_adapter(
    *, redis: RedisClient, settings: Settings
) -> WithingsMeasurementsPort:
    """Create a Withings measurements adapter without FastAPI dependencies."""
    return WithingsMeasurementsAdapter(redis=redis, settings=settings)
