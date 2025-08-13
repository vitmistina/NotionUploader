from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BodyMeasurementAverages(BaseModel):
    """7-day moving averages for body measurements."""

    weight_kg: float = Field(
        ..., description="7-day average of body weight in kilograms"
    )
    fat_mass_kg: float = Field(
        ..., description="7-day average of total fat mass in kilograms"
    )
    muscle_mass_kg: float = Field(
        ..., description="7-day average of skeletal muscle mass in kilograms"
    )
    bone_mass_kg: float = Field(
        ..., description="7-day average of bone mass in kilograms"
    )
    hydration_kg: float = Field(
        ..., description="7-day average of body water content in kilograms"
    )
    fat_free_mass_kg: float = Field(
        ..., description="7-day average of fat-free mass (muscles, bones, tissues) in kilograms"
    )
    body_fat_percent: float = Field(
        ..., description="7-day average of body fat percentage"
    )


class BodyMeasurement(BaseModel):
    """A human-readable representation of body measurements from a smart scale."""

    measurement_time: datetime
    weight_kg: float = Field(..., description="Body weight in kilograms")
    fat_mass_kg: float = Field(..., description="Total fat mass in kilograms")
    muscle_mass_kg: float = Field(..., description="Skeletal muscle mass in kilograms")
    bone_mass_kg: float = Field(..., description="Bone mass in kilograms")
    hydration_kg: float = Field(..., description="Body water content in kilograms")
    fat_free_mass_kg: float = Field(
        ..., description="Fat-free mass (muscles, bones, tissues) in kilograms"
    )
    body_fat_percent: float = Field(..., description="Body fat percentage")
    device_name: str = Field(..., description="Name of the measuring device")
    moving_average_7d: Optional[BodyMeasurementAverages] = Field(
        None, description="7-day moving averages for the measurement metrics"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "measurement_time": "2025-08-09T08:01:06",
                "weight_kg": 68.816,
                "fat_mass_kg": 14.80,
                "muscle_mass_kg": 51.27,
                "bone_mass_kg": 3.845,
                "hydration_kg": 54.016,
                "fat_free_mass_kg": 21.507,
                "body_fat_percent": 21.5,
                "device_name": "Withings Body+",
            }
        }
