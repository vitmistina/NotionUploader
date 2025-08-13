from __future__ import annotations

import hmac
import hashlib
import json

from fastapi import APIRouter, HTTPException, Request, Query, Depends

from .settings import Settings, get_settings
from .strava_activity import process_activity

webhook_router = APIRouter()


@webhook_router.get("/strava-webhook", include_in_schema=False)
async def verify_subscription(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if hub_verify_token != settings.strava_verify_token or hub_mode != "subscribe":
        raise HTTPException(status_code=403, detail="Invalid verification token")
    return {"hub.challenge": hub_challenge}


@webhook_router.post("/strava-webhook", include_in_schema=False)
async def strava_event(
    request: Request, settings: Settings = Depends(get_settings)
) -> dict[str, str]:
    body = await request.body()
    event = json.loads(body)
    aspect = event.get("aspect_type")
    if event.get("object_type") == "activity" and aspect in {"create", "update"}:
        # Always attempt to upsert the activity to avoid duplicate Notion entries
        await process_activity(int(event["object_id"]), settings)
    return {"status": "ok"}
