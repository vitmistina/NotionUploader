from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

from .time import TimeContext


class NutritionEntry(BaseModel):
    food_item: str
    date: str
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


class NutritionSummaryResponse(TimeContext):
    """Time contextualized response containing one or more daily summaries."""

    days: List[DailyNutritionSummaryWithEntries]
