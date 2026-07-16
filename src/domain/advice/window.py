"""Timezone-aware analysis window construction."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from ...models.advice_context import AnalysisWindow

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC timestamp suitable for dependency injection."""
    return datetime.now(timezone.utc)


def build_analysis_window(
    *, days: int, timezone_name: str, clock: Clock = utc_now
) -> AnalysisWindow:
    """Build an inclusive local-calendar window from one injected instant."""
    if not 1 <= days <= 90:
        raise ValueError("days must be between 1 and 90")
    zone = ZoneInfo(timezone_name)
    now = clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    current_date = now.astimezone(zone).date()
    start_date = current_date - timedelta(days=days - 1)
    calendar_days = [start_date + timedelta(days=offset) for offset in range(days)]
    return AnalysisWindow(
        timezone=timezone_name,
        start_date=start_date,
        end_date=current_date,
        requested_days=days,
        calendar_days=calendar_days,
        current_local_date=current_date,
        includes_current_day=True,
    )


def local_midnight_utc(day: date, timezone_name: str) -> datetime:
    """Return the UTC instant at local midnight for a calendar date."""
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(timezone_name)).astimezone(timezone.utc)


def exclusive_end_utc(day: date, timezone_name: str) -> datetime:
    """Return the UTC instant immediately after a local calendar date."""
    return local_midnight_utc(day + timedelta(days=1), timezone_name)


__all__ = ["build_analysis_window", "exclusive_end_utc", "local_midnight_utc", "utc_now"]
