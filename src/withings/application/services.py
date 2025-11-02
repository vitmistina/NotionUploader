"""Application services orchestrating Withings data flows."""

from __future__ import annotations

from typing import List

from ...metrics import add_moving_average
from ...models.body import BodyMeasurement
from .ports import WithingsMeasurementsPort


async def fetch_withings_measurements(
    port: WithingsMeasurementsPort, days: int
) -> List[BodyMeasurement]:
    """Fetch Withings measurements and enrich them with moving averages."""

    measurements = await port.fetch_measurements(days)
    return add_moving_average(list(measurements))
