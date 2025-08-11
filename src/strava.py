import time
from typing import List, Optional

import httpx
from upstash_redis import Redis

from .models import Workout
from .config import (
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
)

redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)

async def refresh_access_token() -> Optional[str]:
    """Refresh the Strava access token using the refresh token stored in Redis."""
    refresh_token = redis.get("strava_refresh_token")
    if not refresh_token:
        raise ValueError("No Strava refresh token found in Redis")

    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.strava.com/api/v3/oauth/token", data=payload
        )

    if response.status_code == 200:
        data = response.json()
        access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in")

        # Store new tokens with expiration (buffer 30s for access token)
        redis.set(
            "strava_access_token",
            access_token,
            ex=int(expires_in) - 30 if expires_in else None,
        )
        # Refresh token valid for 1 year
        redis.set(
            "strava_refresh_token",
            new_refresh_token,
            ex=365 * 24 * 60 * 60,
        )
        return access_token
    return None

async def get_activities(days: int = 7) -> List[Workout]:
    """Fetch Strava activities for the last ``days`` days."""
    access_token = redis.get("strava_access_token")
    if not access_token:
        access_token = await refresh_access_token()
        if not access_token:
            raise ValueError("No valid access token available and refresh failed")

    after = int(time.time()) - days * 24 * 60 * 60
    headers = {"Authorization": f"Bearer {access_token}"}
    page = 1
    per_page = 30
    activities: List[Workout] = []

    async with httpx.AsyncClient() as client:
        while True:
            params = {"after": after, "page": page, "per_page": per_page}
            response = await client.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers=headers,
                params=params,
            )

            if response.status_code == 401:
                new_access_token = await refresh_access_token()
                if not new_access_token:
                    raise RuntimeError("Failed to refresh authentication token")
                headers["Authorization"] = f"Bearer {new_access_token}"
                response = await client.get(
                    "https://www.strava.com/api/v3/athlete/activities",
                    headers=headers,
                    params=params,
                )

            response.raise_for_status()
            page_data = response.json()
            if not page_data:
                break
            activities.extend(Workout.from_api(a) for a in page_data)
            if len(page_data) < per_page:
                break
            page += 1

    return activities
