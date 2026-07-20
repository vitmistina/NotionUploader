from datetime import datetime, timezone

import pytest

from src.domain.advice.window import build_analysis_window, exclusive_end_utc, local_midnight_utc


def test_window_uses_requested_timezone_and_dst_boundaries() -> None:
    def clock() -> datetime:
        return datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc)

    window = build_analysis_window(days=2, timezone_name="Europe/Prague", clock=clock)

    assert window.current_local_date.isoformat() == "2026-03-29"
    assert window.calendar_days == [datetime(2026, 3, 28).date(), datetime(2026, 3, 29).date()]
    assert local_midnight_utc(window.start_date, window.timezone).hour == 23
    assert exclusive_end_utc(window.end_date, window.timezone).hour == 22


@pytest.mark.parametrize("days", [0, 91])
def test_window_rejects_out_of_range_days(days: int) -> None:
    with pytest.raises(ValueError):
        build_analysis_window(
            days=days,
            timezone_name="UTC",
            clock=lambda: datetime(2026, 7, 16, tzinfo=timezone.utc),
        )
