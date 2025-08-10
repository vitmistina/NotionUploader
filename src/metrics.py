from __future__ import annotations

from collections import deque
from typing import List

from .models import BodyMeasurement, BodyMeasurementAverages


def add_moving_average(
    measurements: List[BodyMeasurement], window: int = 7
) -> List[BodyMeasurement]:
    """Attach 7-day moving averages to a list of body measurements.

    Measurements are first sorted by ``measurement_time`` and a simple moving
    average is computed for each metric. ``None`` values are ignored so missing
    data does not dilute the average. A moving average is always calculated
    from the values available within the ``window`` size, even if fewer than
    ``window`` non-missing values are present.

    Args:
        measurements: Raw body measurements.
        window: Number of measurements to consider for the moving window.
            Defaults to 7.

    Returns:
        The list of measurements with ``moving_average_7d`` populated when all
        metrics have at least one non-missing value in the current window.
    """

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

    for m in sorted_measurements:
        for metric in metrics:
            queues[metric].append(getattr(m, metric))

        averages: dict[str, float] = {}
        for metric in metrics:
            values = [v for v in queues[metric] if v is not None]
            if values:
                averages[metric] = sum(values) / len(values)
            else:
                break

        if len(averages) == len(metrics):
            m.moving_average_7d = BodyMeasurementAverages(**averages)
        else:
            m.moving_average_7d = None

    return sorted_measurements
