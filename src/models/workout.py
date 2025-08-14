from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class Workout(BaseModel):
    """Simplified representation of a Strava workout."""

    id: int
    name: str
    start_date: datetime
    type: str
    distance_m: float = Field(..., description="Distance in meters")
    moving_time_s: int = Field(..., description="Moving time in seconds")
    elapsed_time_s: int = Field(..., description="Elapsed time in seconds")
    total_elevation_gain_m: float = Field(
        ..., description="Total elevation gain in meters"
    )
    average_speed_mps: Optional[float] = Field(
        None, description="Average speed in meters per second"
    )
    max_speed_mps: Optional[float] = Field(
        None, description="Maximum speed in meters per second"
    )
    average_watts: Optional[float] = Field(
        None, description="Average power output in watts"
    )
    kilojoules: Optional[float] = Field(
        None, description="Total work done in kilojoules"
    )
    device_watts: Optional[bool] = Field(
        None, description="True if power data comes from a power meter"
    )
    average_heartrate: Optional[float] = Field(
        None, description="Average heart rate in beats per minute"
    )
    max_heartrate: Optional[float] = Field(
        None, description="Maximum heart rate in beats per minute"
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Workout":
        """Create a Workout model from Strava API activity data."""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            start_date=data.get("start_date"),
            type=data.get("type", ""),
            distance_m=data.get("distance", 0.0),
            moving_time_s=data.get("moving_time", 0),
            elapsed_time_s=data.get("elapsed_time", 0),
            total_elevation_gain_m=data.get("total_elevation_gain", 0.0),
            average_speed_mps=data.get("average_speed"),
            max_speed_mps=data.get("max_speed"),
            average_watts=data.get("average_watts"),
            kilojoules=data.get("kilojoules"),
            device_watts=data.get("device_watts"),
            average_heartrate=data.get("average_heartrate"),
            max_heartrate=data.get("max_heartrate"),
        )


class StravaEvent(BaseModel):
    """Payload sent by Strava webhook."""

    aspect_type: str
    event_time: int
    object_id: int
    object_type: str
    owner_id: int
    subscription_id: int
    updates: Dict[str, Any] | None = None


class WorkoutLog(BaseModel):
    """Representation of a workout stored in Notion for LLM consumption."""

    name: str
    date: str
    duration_s: float
    distance_m: float
    elevation_m: float
    type: str
    average_cadence: Optional[float] = None
    average_watts: Optional[float] = None
    weighted_average_watts: Optional[float] = None
    kilojoules: Optional[float] = None
    kcal: Optional[float] = None
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[float] = None
    hr_drift_percent: Optional[float] = None
    vo2max_minutes: Optional[float] = None
    tss: Optional[float] = None
    intensity_factor: Optional[float] = None
    notes: Optional[str] = None
