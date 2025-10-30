from __future__ import annotations

from datetime import datetime, timezone
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


class ManualWorkoutSubmission(BaseModel):
    """Payload describing a manually logged workout extracted by a GPT agent."""

    name: str = Field(..., description="Human-readable workout name or summary.")
    start_time: datetime = Field(
        ..., description="UTC timestamp when the workout began."
    )
    duration_minutes: float = Field(
        ..., gt=0, description="Total session duration expressed in minutes."
    )
    average_heartrate: Optional[float] = Field(
        None, description="Average heart rate recorded for the session."
    )
    max_heartrate: Optional[float] = Field(
        None, description="Maximum heart rate recorded for the session."
    )
    distance_meters: Optional[float] = Field(
        None, description="Optional distance covered in meters."
    )
    elevation_meters: Optional[float] = Field(
        None, description="Optional elevation gain in meters."
    )
    calories: Optional[float] = Field(
        None, description="Estimated calories expended during the session."
    )
    notes: Optional[str] = Field(
        None, description="Free-form notes or description of the workout."
    )
    id: Optional[int] = Field(
        None,
        description="Optional numeric identifier used for deduplicating entries.",
    )
    average_cadence: Optional[float] = Field(
        None, description="Optional average cadence data."
    )
    average_watts: Optional[float] = Field(
        None, description="Optional average power in watts."
    )
    weighted_average_watts: Optional[float] = Field(
        None, description="Optional weighted average power in watts."
    )
    kilojoules: Optional[float] = Field(
        None, description="Optional total work in kilojoules."
    )
    tss: Optional[float] = Field(
        None, description="Optional Training Stress Score if already calculated."
    )
    intensity_factor: Optional[float] = Field(
        None, description="Optional intensity factor if already calculated."
    )
    hr_drift_percent: Optional[float] = Field(
        None, description="Optional heart rate drift percentage estimate."
    )
    vo2max_minutes: Optional[float] = Field(
        None, description="Optional minutes spent at/above VO₂ max intensity."
    )

    def _generate_identifier(self) -> int:
        if self.id is not None:
            return self.id
        start = self.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return int(start.timestamp())

    def duration_seconds(self) -> int:
        """Return the workout duration expressed in seconds."""

        return int(round(self.duration_minutes * 60))

    def to_notion_detail(self) -> Dict[str, Any]:
        """Convert the submission into the payload expected by Notion storage."""

        duration_s = self.duration_seconds()
        detail: Dict[str, Any] = {
            "id": self._generate_identifier(),
            "name": self.name,
            "start_date": self.start_time.isoformat(),
            "elapsed_time": duration_s,
            "moving_time": duration_s,
            "distance": self.distance_meters,
            "total_elevation_gain": self.elevation_meters,
            "type": "Gym",
            "description": self.notes,
            "average_heartrate": self.average_heartrate,
            "max_heartrate": self.max_heartrate,
            "average_cadence": self.average_cadence,
            "average_watts": self.average_watts,
            "weighted_average_watts": self.weighted_average_watts,
            "kilojoules": self.kilojoules,
            "calories": self.calories,
        }

        if detail["distance"] is None:
            detail["distance"] = 0.0
        if detail["total_elevation_gain"] is None:
            detail["total_elevation_gain"] = 0.0

        return detail


class ManualWorkoutResponse(BaseModel):
    """API response returned after storing a manual workout submission."""

    id: int
    name: str
    start_time: datetime
    duration_s: int
    type: str = Field("Gym", description="Stored workout type.")
    intensity_factor: Optional[float] = Field(
        None, description="Estimated or provided intensity factor."
    )
    tss: Optional[float] = Field(
        None, description="Estimated or provided Training Stress Score."
    )
