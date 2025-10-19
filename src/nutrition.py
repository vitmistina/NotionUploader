from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Union

from .models.nutrition import (
    DailyNutritionSummary,
    DailyNutritionSummaryWithEntries,
    NutritionEntry,
)
from .notion.application.ports import NutritionRepository


async def get_daily_nutrition_summaries(
    start_date: str, end_date: str, repository: NutritionRepository
) -> List[DailyNutritionSummaryWithEntries]:
    """Retrieve nutrition entries for a date range and aggregate by day."""
    entries: List[NutritionEntry] = await repository.list_entries_in_range(
        start_date, end_date
    )
    grouped: Dict[str, List[NutritionEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.date].append(entry)
    summaries: List[DailyNutritionSummaryWithEntries] = []
    for date, items in sorted(grouped.items()):
        summaries.append(build_daily_summary(date, items, include_entries=True))
    return summaries


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
