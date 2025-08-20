from __future__ import annotations


from fastapi import APIRouter, Query, Depends

from ..metrics import linear_regression
from ..models.body import BodyMeasurementsResponse, BodyMetricTrends
from ..services.redis import RedisClient, get_redis
from ..settings import Settings, get_settings
from ..withings import get_measurements

router: APIRouter = APIRouter()


@router.get("/body-measurements", response_model=BodyMeasurementsResponse)
async def list_body_measurements(
    days: int = Query(7, description="Number of days of measurements to retrieve."),
    redis: RedisClient = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> BodyMeasurementsResponse:
    """Get body measurements and linear regression trends."""
    measurements = await get_measurements(days, redis, settings)
    trends = BodyMetricTrends(**linear_regression(measurements))
    return BodyMeasurementsResponse(measurements=measurements, trends=trends)
