from __future__ import annotations

from typing import List

from pydantic import BaseModel

from .time import TimeContext
from .body import BodyMeasurement, BodyMetricTrends
from .nutrition import DailyNutritionSummaryWithEntries
from .workout import WorkoutLog


class AthleteMetrics(BaseModel):
    """Latest athlete-level metrics such as FTP and max heart rate."""

    ftp: float | None = None
    weight: float | None = None
    max_hr: float | None = None


class SummaryAdvice(TimeContext):
    """Combined nutrition, body metrics, workout data, and athlete metrics."""

    nutrition: List[DailyNutritionSummaryWithEntries]
    metrics: List[BodyMeasurement]
    metric_trends: BodyMetricTrends
    workouts: List[WorkoutLog]
    athlete_metrics: AthleteMetrics
