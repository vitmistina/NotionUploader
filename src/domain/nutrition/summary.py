"""Daily nutrition summary builders."""

from __future__ import annotations

from typing import List, Union

from ...models.nutrition import (
    DailyNutritionSummary,
    DailyNutritionSummaryWithEntries,
    NutritionEntry,
)


def build_daily_summary(
    date: str, items: List[NutritionEntry], *, include_entries: bool = False
) -> Union[DailyNutritionSummary, DailyNutritionSummaryWithEntries]:
    """Aggregate a list of entries into a daily nutrition summary."""
    base = {
        "date": date,
        "daily_calories_sum": sum(e.calories for e in items),
        "daily_protein_g_sum": sum(e.protein_g for e in items),
        "daily_carbs_g_sum": sum(e.carbs_g for e in items),
        "daily_fat_g_sum": sum(e.fat_g for e in items),
    }
    if include_entries:
        return DailyNutritionSummaryWithEntries(entries=items, **base)
    return DailyNutritionSummary(**base)
