from __future__ import annotations

import hmac
import hashlib
import json

from fastapi import APIRouter, HTTPException, Request, Query

from .config import STRAVA_CLIENT_SECRET, STRAVA_VERIFY_TOKEN
from .strava_activity import process_activity

webhook_router = APIRouter()


def _verify_signature(payload: bytes, signature: str | None) -> None:
    expected = hmac.new(
        STRAVA_CLIENT_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@webhook_router.get("/strava-webhook", include_in_schema=False)
async def verify_subscription(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
) -> dict[str, str]:
    if hub_verify_token != STRAVA_VERIFY_TOKEN or hub_mode != "subscribe":
        raise HTTPException(status_code=403, detail="Invalid verification token")
    return {"hub.challenge": hub_challenge}


@webhook_router.post("/strava-webhook", include_in_schema=False)
async def strava_event(request: Request) -> dict[str, str]:
    body = await request.body()
    _verify_signature(body, request.headers.get("X-Strava-Signature"))
    event = json.loads(body)
    if event.get("object_type") == "activity" and event.get("aspect_type") in {
        "create",
        "update",
    }:
        await process_activity(int(event["object_id"]))
    return {"status": "ok"}
