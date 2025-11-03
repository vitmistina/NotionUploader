from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from platform import Settings, get_settings
from .strava import (
    StravaActivityCoordinator,
    get_strava_activity_coordinator,
)

logger = logging.getLogger(__name__)

webhook_router = APIRouter()


@webhook_router.get("/strava-webhook", include_in_schema=False)
async def verify_subscription(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if hub_verify_token != settings.strava_verify_token or hub_mode != "subscribe":
        raise HTTPException(
            status_code=403, detail={"error": "Invalid verification token"}
        )
    return {"hub.challenge": hub_challenge}


@webhook_router.post("/strava-webhook", include_in_schema=False)
async def strava_event(
    request: Request,
    service: StravaActivityCoordinator = Depends(get_strava_activity_coordinator),
) -> dict[str, str]:
    body = await request.body()

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        logger.exception("Invalid Strava webhook payload: %s", body.decode("utf-8", "replace"))
        raise HTTPException(status_code=400, detail={"error": "Invalid payload"})

    aspect = event.get("aspect_type")

    if event.get("object_type") == "activity" and aspect in {"create", "update"}:
        try:
            # Always attempt to upsert the activity to avoid duplicate Notion entries
            await service.process_activity(int(event["object_id"]))
        except Exception:
            logger.exception("Error processing Strava webhook event: %s", event)
            raise HTTPException(
                status_code=400, detail={"error": "Error processing webhook"}
            )

    return {"status": "ok"}
