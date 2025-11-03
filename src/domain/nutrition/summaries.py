"""Nutrition summary orchestrators."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ...models.nutrition import DailyNutritionSummaryWithEntries, NutritionEntry
from ...notion.application.ports import NutritionRepository
from .summary import build_daily_summary


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
