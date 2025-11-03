from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, List, Sequence, Tuple

from ..domain.nutrition.summary import build_daily_summary
from ..domain.nutrition.summaries import get_daily_nutrition_summaries
from ..models.nutrition import (
    DailyNutritionSummary,
    DailyNutritionSummaryWithEntries,
    NutritionEntry,
    NutritionSummaryResponse,
)
from ..models.responses import OperationStatus
from ..models.time import get_local_time
from ..notion.application.ports import NutritionRepository

SummaryBuilder = Callable[[str, Sequence[NutritionEntry]], DailyNutritionSummary]
SummariesFetcher = Callable[
    [str, str, NutritionRepository],
    Awaitable[List[DailyNutritionSummaryWithEntries]],
]
TimeProvider = Callable[[str], Tuple[str, str]]


@dataclass
class CreateNutritionEntryUseCase:
    """Persist a nutrition entry using the configured repository."""

    repository: NutritionRepository

    async def __call__(self, entry: NutritionEntry) -> OperationStatus:
        await self.repository.create_entry(entry)
        return OperationStatus(status="ok")


@dataclass
class GetDailyNutritionEntriesUseCase:
    """Return a summary and entries for a single day."""

    repository: NutritionRepository
    summary_builder: SummaryBuilder = build_daily_summary
    time_provider: TimeProvider = get_local_time

    async def __call__(self, date: str, timezone: str) -> NutritionSummaryResponse:
        entries = await self.repository.list_entries_on_date(date)
        summary = self.summary_builder(date, entries)
        day_summary = DailyNutritionSummaryWithEntries(
            **summary.model_dump(), entries=entries
        )
        local_time, part = self.time_provider(timezone)
        return NutritionSummaryResponse(
            days=[day_summary], local_time=local_time, part_of_day=part
        )


@dataclass
class GetNutritionEntriesByPeriodUseCase:
    """Return nutrition summaries for a given period."""

    repository: NutritionRepository
    summaries_fetcher: SummariesFetcher = get_daily_nutrition_summaries
    time_provider: TimeProvider = get_local_time

    async def __call__(
        self, start_date: str, end_date: str, timezone: str
    ) -> NutritionSummaryResponse:
        summaries = await self.summaries_fetcher(start_date, end_date, self.repository)
        local_time, part = self.time_provider(timezone)
        return NutritionSummaryResponse(
            days=summaries,
            local_time=local_time,
            part_of_day=part,
        )


__all__ = [
    "CreateNutritionEntryUseCase",
    "GetDailyNutritionEntriesUseCase",
    "GetNutritionEntriesByPeriodUseCase",
]
