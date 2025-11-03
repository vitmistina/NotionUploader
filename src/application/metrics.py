from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, List, Sequence

from ..domain.body_metrics.regression import linear_regression
from ..models.body import BodyMeasurement, BodyMeasurementsResponse, BodyMetricTrends
from ..withings.application import WithingsMeasurementsPort, fetch_withings_measurements

MeasurementsFetcher = Callable[[WithingsMeasurementsPort, int], Awaitable[List[BodyMeasurement]]]
TrendsCalculator = Callable[[Sequence[BodyMeasurement]], dict]


@dataclass
class ListBodyMeasurementsUseCase:
    """Return body measurements enriched with regression trends."""

    withings_port: WithingsMeasurementsPort
    measurements_fetcher: MeasurementsFetcher = fetch_withings_measurements
    trends_calculator: TrendsCalculator = linear_regression

    async def __call__(self, days: int) -> BodyMeasurementsResponse:
        measurements = await self.measurements_fetcher(self.withings_port, days)
        trends = BodyMetricTrends(**self.trends_calculator(measurements))
        return BodyMeasurementsResponse(measurements=measurements, trends=trends)


__all__ = ["ListBodyMeasurementsUseCase"]
