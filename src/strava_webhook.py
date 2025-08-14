from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .settings import Settings, get_settings
from .services.strava_activity import (
    StravaActivityService,
    get_strava_activity_service,
)

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
    request: Request,
    service: StravaActivityService = Depends(get_strava_activity_service),
) -> dict[str, str]:
    body = await request.body()
    event = json.loads(body)
    aspect = event.get("aspect_type")
    if event.get("object_type") == "activity" and aspect in {"create", "update"}:
        # Always attempt to upsert the activity to avoid duplicate Notion entries
        await service.process_activity(int(event["object_id"]))
    return {"status": "ok"}
