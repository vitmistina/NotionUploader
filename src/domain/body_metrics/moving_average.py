"""Moving average helpers for body measurements."""

from __future__ import annotations

from datetime import date
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

    sorted_measurements = sorted(measurements, key=lambda m: m.measurement_time)
    daily: dict[date, List[BodyMeasurement]] = {}
    for measurement in sorted_measurements:
        daily.setdefault(measurement.measurement_time.date(), []).append(measurement)
    daily_representatives = {
        day: min(records, key=lambda item: item.measurement_time) for day, records in daily.items()
    }

    min_values = 3
    for m in sorted_measurements:
        start = m.measurement_time.date()
        recent_days = sorted(
            day for day in daily_representatives if 0 <= (start - day).days < window
        )
        recent_days = [day for day in recent_days if day <= start][-window:]
        averages: dict[str, float] = {}
        for metric in metrics:
            values = [getattr(daily_representatives[day], metric) for day in recent_days]
            values = [v for v in values if v is not None]
            if len(values) >= min_values:
                averages[metric] = sum(values) / len(values)
        m.moving_average_7d = BodyMeasurementAverages(**averages) if averages else None

    return sorted_measurements
