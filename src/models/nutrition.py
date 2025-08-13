from __future__ import annotations

from typing import Literal, List

from pydantic import BaseModel, Field


class NutritionEntry(BaseModel):
    food_item: str
    date: str  # Consider refining this to a date type later
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_type: Literal[
        "Breakfast", "Lunch", "Dinner", "Snack", "Pre-workout", "Post-workout"
    ]
    notes: str = Field(..., min_length=1)


class StatusResponse(BaseModel):
    """Simple response model indicating operation status."""

    status: str


class DailyNutritionSummary(BaseModel):
    """Aggregated nutrition information for a single day."""

    date: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    entries: List[NutritionEntry]
