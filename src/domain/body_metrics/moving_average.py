"""Moving average helpers for body measurements."""

from __future__ import annotations

from collections import deque
from typing import List

from ...models.body import BodyMeasurement, BodyMeasurementAverages


def add_moving_average(
    measurements: List[BodyMeasurement], window: int = 7
) -> List[BodyMeasurement]:
    """Attach 7-day moving averages to a list of body measurements."""

    metrics = [
        "weight_kg",
        "fat_mass_kg",
        "muscle_mass_kg",
        "bone_mass_kg",
        "hydration_kg",
        "fat_free_mass_kg",
        "body_fat_percent",
    ]

    sorted_measurements = sorted(
        measurements, key=lambda m: m.measurement_time
    )
    queues = {metric: deque(maxlen=window) for metric in metrics}

    min_values = 3
    for m in sorted_measurements:
        for metric in metrics:
            queues[metric].append(getattr(m, metric))

        averages: dict[str, float] = {}
        for metric in metrics:
            values = [v for v in queues[metric] if v is not None]
            if len(values) >= min_values:
                averages[metric] = sum(values) / len(values)
            else:
                break

        if len(averages) == len(metrics):
            m.moving_average_7d = BodyMeasurementAverages(**averages)
        else:
            m.moving_average_7d = None

    return sorted_measurements
