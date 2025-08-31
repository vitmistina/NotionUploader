from __future__ import annotations

from typing import Literal, List

from .time import TimeContext

from pydantic import BaseModel, Field


class NutritionEntry(BaseModel):
    food_item: str
    date: str  # Consider refining this to a date type later
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_type: Literal[
        "Breakfast",
        "Lunch",
        "Dinner",
        "Snack",
        "Pre-workout",
        "During-workout",
        "Post-workout",
    ]
    notes: str = Field(..., min_length=1)


class StatusResponse(BaseModel):
    """Simple response model indicating operation status."""

    status: str


class DailyNutritionSummary(BaseModel):
    """Aggregated nutrition information for a single day."""

    date: str
    daily_calories_sum: int
    daily_protein_g_sum: float
    daily_carbs_g_sum: float
    daily_fat_g_sum: float


class DailyNutritionSummaryWithEntries(DailyNutritionSummary):
    """Daily summary extended with the list of individual entries."""

    entries: List[NutritionEntry]


class NutritionEntriesResponse(TimeContext):
    """Response wrapper for a list of nutrition entries with timing context."""

    entries: List[NutritionEntry]
    summary: DailyNutritionSummary


class NutritionPeriodResponse(TimeContext):
    """Response wrapper for a range of daily nutrition summaries with timing context."""

    nutrition: List[DailyNutritionSummaryWithEntries]
