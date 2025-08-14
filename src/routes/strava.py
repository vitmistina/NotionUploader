from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends

from ..redis import RedisClient, get_redis
from ..settings import Settings, get_settings
from ..strava_activity import process_activity

router: APIRouter = APIRouter()


@router.post("/strava-activity/{activity_id}", include_in_schema=False)
async def trigger_strava_processing(
    activity_id: int,
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> Dict[str, str]:
    await process_activity(activity_id, redis, settings)
    return {"status": "ok"}
