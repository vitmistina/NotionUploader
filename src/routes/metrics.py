from __future__ import annotations


from fastapi import APIRouter, Depends, Query

from ..domain.body_metrics.regression import linear_regression
from ..models.body import BodyMeasurementsResponse, BodyMetricTrends
from ..withings.application import WithingsMeasurementsPort, fetch_withings_measurements
from ..withings.infrastructure import get_withings_port

router: APIRouter = APIRouter()


@router.get("/body-measurements", response_model=BodyMeasurementsResponse)
async def list_body_measurements(
    days: int = Query(7, description="Number of days of measurements to retrieve."),
    withings_port: WithingsMeasurementsPort = Depends(get_withings_port),
) -> BodyMeasurementsResponse:
    """Get body measurements and linear regression trends."""
    measurements = await fetch_withings_measurements(withings_port, days)
    trends = BodyMetricTrends(**linear_regression(measurements))
    return BodyMeasurementsResponse(measurements=measurements, trends=trends)
