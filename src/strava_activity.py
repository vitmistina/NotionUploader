from __future__ import annotations

import base64
import gzip
import json
from typing import Any

import httpx
from fastapi import HTTPException

from .strava import redis, refresh_access_token
from .metrics import hr_drift_from_splits, vo2max_minutes
from .workout_notion import fetch_latest_athlete_profile, save_workout_to_notion


async def fetch_activity(activity_id: int) -> dict[str, Any]:
    """Fetch a Strava activity by ID."""
    access_token = redis.get("strava_access_token")
    if not access_token:
        access_token = await refresh_access_token()
        if not access_token:
            raise HTTPException(status_code=500, detail="Auth failure")
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers=headers,
        )
        if resp.status_code == 401:
            access_token = await refresh_access_token()
            headers["Authorization"] = f"Bearer {access_token}"
            resp = await client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers=headers,
            )
        resp.raise_for_status()
        return resp.json()


async def process_activity(activity_id: int) -> None:
    """Fetch an activity, compute metrics and upload to Notion."""
    detail = await fetch_activity(activity_id)
    splits = detail.get("splits_metric", [])
    athlete = await fetch_latest_athlete_profile()
    max_hr = athlete.get("max_hr")
    hr_drift = hr_drift_from_splits(splits)
    vo2 = vo2max_minutes(splits, max_hr) if max_hr else 0.0
    minified = json.dumps(detail, separators=(",", ":"))
    compressed = gzip.compress(minified.encode("utf-8"))
    attachment = base64.b64encode(compressed).decode("utf-8")
    await save_workout_to_notion(detail, attachment, hr_drift, vo2)

