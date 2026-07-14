from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ActivitySplit(BaseModel):
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[float] = None
    moving_time: Optional[int] = None
    elapsed_time: Optional[int] = None
    average_speed: Optional[float] = None
    distance: Optional[float] = None


class ActivityLap(ActivitySplit):
    pass


class WorkoutActivity(BaseModel):
    id: int
    external_id: str
    source: Literal["intervals_icu"] = "intervals_icu"
    provider_source: Optional[str] = None
    provider_client_name: Optional[str] = None
    device_name: Optional[str] = None

    name: str
    start_date: Optional[str] = None
    start_date_local: Optional[str] = None
    elapsed_time: Optional[int] = None
    moving_time: Optional[int] = None
    distance: Optional[float] = None
    total_elevation_gain: Optional[float] = None
    type: Optional[str] = None

    splits_metric: list[ActivitySplit] = Field(default_factory=list)
    laps: list[ActivityLap] = Field(default_factory=list)

    average_cadence: Optional[float] = None
    average_watts: Optional[float] = None
    weighted_average_watts: Optional[float] = None
    kilojoules: Optional[float] = None
    calories: Optional[float] = None
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[float] = None
    description: Optional[str] = None

    provider_training_load: Optional[float] = None
    provider_intensity_factor: Optional[float] = None
    provider_hr_drift: Optional[float] = None


class MetricResults(BaseModel):
    hr_drift: float
    vo2: float
    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
