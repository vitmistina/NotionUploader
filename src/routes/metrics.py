from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query, Depends

from ..models.body import BodyMeasurement
from ..services.redis import RedisClient, get_redis
from ..settings import Settings, get_settings
from ..withings import get_measurements

router: APIRouter = APIRouter()


@router.get("/body-measurements", response_model=List[BodyMeasurement])
async def list_body_measurements(
    days: int = Query(7, description="Number of days of measurements to retrieve."),
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> List[BodyMeasurement]:
    """Get body measurements from Withings scale for the specified number of days."""
    return await get_measurements(days, redis, settings)
