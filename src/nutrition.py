from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .models.nutrition import DailyNutritionSummary, NutritionEntry
from .notion import entries_in_range
from .services.interfaces import NotionAPI
from .settings import Settings


async def get_daily_nutrition_summaries(
    start_date: str, end_date: str, settings: Settings, client: NotionAPI
) -> List[DailyNutritionSummary]:
    """Retrieve nutrition entries for a date range and aggregate by day."""
    entries: List[NutritionEntry] = await entries_in_range(
        start_date, end_date, settings, client
    )
    grouped: Dict[str, List[NutritionEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.date].append(entry)
    summaries: List[DailyNutritionSummary] = []
    for date, items in sorted(grouped.items()):
        summaries.append(
            DailyNutritionSummary(
                date=date,
                calories=sum(e.calories for e in items),
                protein_g=sum(e.protein_g for e in items),
                carbs_g=sum(e.carbs_g for e in items),
                fat_g=sum(e.fat_g for e in items),
                entries=items,
            )
        )
    return summaries
