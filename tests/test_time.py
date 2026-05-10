from __future__ import annotations

from datetime import datetime

import pytest

from src.models import time as time_model


@pytest.mark.parametrize(
    ("hour", "expected_part"),
    [
        (2, "night"),
        (8, "morning"),
        (13, "afternoon"),
        (19, "evening"),
    ],
)
def test_get_local_time_classifies_part_of_day(
    monkeypatch: pytest.MonkeyPatch, hour: int, expected_part: str
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return cls(2026, 5, 10, hour, 30, tzinfo=tz)

    monkeypatch.setattr(time_model, "datetime", FixedDateTime)

    local_time, part_of_day = time_model.get_local_time("UTC")

    assert local_time.hour == hour
    assert local_time.tzinfo is not None
    assert part_of_day == expected_part
