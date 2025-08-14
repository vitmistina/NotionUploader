from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Split(BaseModel):
    average_heartrate: Optional[float] = None
    moving_time: Optional[int] = None
    average_speed: Optional[float] = None
    distance: Optional[float] = None


class Lap(Split):
    max_heartrate: Optional[float] = None


class StravaActivity(BaseModel):
    splits_metric: List[Split] = []
    laps: List[Lap] = []
    weighted_average_watts: Optional[float] = None
    moving_time: Optional[int] = None
    description: Optional[str] = None


class MetricResults(BaseModel):
    hr_drift: float
    vo2: float
    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
