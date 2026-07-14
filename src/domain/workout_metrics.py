from __future__ import annotations

import math
from typing import Any

from ..models.activity import MetricResults, WorkoutActivity
from .body_metrics.hr import hr_drift_from_splits
from .body_metrics.vo2 import vo2max_minutes


def _finite(value: float | int | None) -> bool:
    return value is not None and math.isfinite(float(value))


def compute_activity_metrics(activity: WorkoutActivity, athlete: dict[str, Any]) -> MetricResults:
    splits = [s.model_dump() for s in activity.splits_metric]
    laps = [lap.model_dump() for lap in activity.laps]
    max_hr = athlete.get("max_hr")
    ftp = athlete.get("ftp")

    if _finite(activity.provider_hr_drift):
        hr_drift = float(activity.provider_hr_drift)  # negative values are meaningful
    else:
        hr_drift = hr_drift_from_splits(splits) or 0.0

    splits_for_vo2 = laps if len(laps) > 2 else splits
    vo2 = vo2max_minutes(splits_for_vo2, max_hr) if max_hr else 0.0

    intensity_factor = None
    if (
        _finite(activity.provider_intensity_factor)
        and float(activity.provider_intensity_factor) >= 0
    ):
        intensity_factor = float(activity.provider_intensity_factor)
    elif ftp and activity.weighted_average_watts and activity.weighted_average_watts > 0:
        intensity_factor = activity.weighted_average_watts / ftp

    tss = None
    if _finite(activity.provider_training_load) and float(activity.provider_training_load) >= 0:
        tss = float(activity.provider_training_load)
    elif (
        ftp
        and activity.weighted_average_watts
        and activity.moving_time
        and intensity_factor is not None
    ):
        tss = (
            activity.moving_time
            * activity.weighted_average_watts
            * intensity_factor
            / (ftp * 3600)
            * 100
        )

    return MetricResults(hr_drift=hr_drift, vo2=vo2, tss=tss, intensity_factor=intensity_factor)
