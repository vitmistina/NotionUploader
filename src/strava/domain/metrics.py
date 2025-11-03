from __future__ import annotations

from typing import Any

from ...domain.body_metrics.hr import hr_drift_from_splits
from ...domain.body_metrics.vo2 import vo2max_minutes
from ...models import MetricResults, StravaActivity


def compute_activity_metrics(
    activity: StravaActivity, athlete: dict[str, Any]
) -> MetricResults:
    """Derive activity metrics from Strava data and athlete profile."""
    splits = [s.model_dump() for s in activity.splits_metric]
    laps = [lap.model_dump() for lap in activity.laps]
    max_hr = athlete.get("max_hr")
    ftp = athlete.get("ftp")

    hr_drift = hr_drift_from_splits(splits)
    splits_for_vo2 = laps if len(laps) > 2 else splits
    vo2 = vo2max_minutes(splits_for_vo2, max_hr) if max_hr else 0.0

    weighted_watts = activity.weighted_average_watts
    moving_time = activity.moving_time

    intensity_factor = None
    tss = None
    if ftp and weighted_watts:
        intensity_factor = weighted_watts / ftp
        if moving_time:
            tss = (
                moving_time
                * weighted_watts
                * intensity_factor
                / (ftp * 3600)
                * 100
            )

    return MetricResults(
        hr_drift=hr_drift,
        vo2=vo2,
        tss=tss,
        intensity_factor=intensity_factor,
    )
