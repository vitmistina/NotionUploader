from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends

from ..strava import (
    StravaActivityCoordinator,
    get_strava_activity_coordinator,
)

router: APIRouter = APIRouter()


@router.post("/strava-activity/{activity_id}", include_in_schema=False)
async def trigger_strava_processing(
    activity_id: int,
    service: StravaActivityCoordinator = Depends(get_strava_activity_coordinator),
) -> Dict[str, str]:
    await service.process_activity(activity_id)
    return {"status": "ok"}
