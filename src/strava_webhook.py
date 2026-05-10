from __future__ import annotations

import hashlib
import hmac
import json
import logging
from platform import Settings, get_settings

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from .platform.wiring import provide_strava_activity_coordinator
from .strava import StravaActivityCoordinator

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
    x_strava_signature: str | None = Header(default=None, alias="X-Strava-Signature"),
    settings: Settings = Depends(get_settings),
    service: StravaActivityCoordinator = Depends(
        provide_strava_activity_coordinator
    ),
) -> dict[str, str]:
    body = await request.body()

    if x_strava_signature is None:
        raise HTTPException(
            status_code=401, detail={"error": "Missing Strava signature"}
        )

    expected_signature = hmac.new(
        settings.strava_client_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(x_strava_signature, expected_signature):
        raise HTTPException(
            status_code=403, detail={"error": "Invalid Strava signature"}
        )

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
