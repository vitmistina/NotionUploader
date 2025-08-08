from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal

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
