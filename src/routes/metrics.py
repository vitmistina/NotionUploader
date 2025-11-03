from __future__ import annotations


from fastapi import APIRouter, Depends, Query

from ..application.metrics import ListBodyMeasurementsUseCase
from ..models.body import BodyMeasurementsResponse
from ..platform.wiring import get_list_body_measurements_use_case

router: APIRouter = APIRouter()


@router.get("/body-measurements", response_model=BodyMeasurementsResponse)
async def list_body_measurements(
    days: int = Query(7, description="Number of days of measurements to retrieve."),
    use_case: ListBodyMeasurementsUseCase = Depends(
        get_list_body_measurements_use_case
    ),
) -> BodyMeasurementsResponse:
    """Get body measurements and linear regression trends."""
    return await use_case(days)
