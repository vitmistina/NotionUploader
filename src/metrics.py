from __future__ import annotations

from collections import deque
from typing import List

from .models import BodyMeasurement, BodyMeasurementAverages


def add_moving_average(
    measurements: List[BodyMeasurement], window: int = 7
) -> List[BodyMeasurement]:
    """Attach 7-day moving averages to a list of body measurements.

    Measurements are first sorted by ``measurement_time`` and a simple moving
    average is computed for each metric. If fewer than ``window`` measurements
    are available so far, the moving average field is left as ``None``.

    Args:
        measurements: Raw body measurements.
        window: Number of measurements to average over. Defaults to 7.

    Returns:
        The list of measurements with ``moving_average_7d`` populated when
        enough data is available.
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

        if len(queues[metrics[0]]) == window:
            averages = {
                metric: sum(queues[metric]) / window for metric in metrics
            }
            m.moving_average_7d = BodyMeasurementAverages(**averages)
        else:
            m.moving_average_7d = None

    return sorted_measurements
