from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Split(BaseModel):
    average_heartrate: Optional[float] = None
    moving_time: Optional[int] = None
    average_speed: Optional[float] = None
    distance: Optional[float] = None


class Lap(Split):
    max_heartrate: Optional[float] = None


class StravaActivity(BaseModel):
    """Subset of fields returned by the Strava activity detail endpoint."""

    id: int
    name: str
    start_date: Optional[str] = None
    elapsed_time: Optional[int] = None
    distance: Optional[float] = None
    total_elevation_gain: Optional[float] = None
    type: Optional[str] = None
    splits_metric: List[Split] = Field(default_factory=list)
    laps: List[Lap] = Field(default_factory=list)
    average_cadence: Optional[float] = None
    average_watts: Optional[float] = None
    weighted_average_watts: Optional[float] = None
    kilojoules: Optional[float] = None
    calories: Optional[float] = None
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[float] = None
    moving_time: Optional[int] = None
    description: Optional[str] = None


class MetricResults(BaseModel):
    hr_drift: float
    vo2: float
    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
