from typing import Optional

import httpx

from .services.redis import RedisClient
from .settings import Settings


async def refresh_access_token(redis: RedisClient, settings: Settings) -> Optional[str]:
    """Refresh the Strava access token using the refresh token stored in Redis."""
    refresh_token = redis.get("strava_refresh_token")
    if not refresh_token:
        raise ValueError("No Strava refresh token found in Redis")

    payload = {
        "client_id": settings.strava_client_id,
        "client_secret": settings.strava_client_secret,
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
