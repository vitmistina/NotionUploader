from __future__ import annotations

from datetime import datetime
from typing import Literal, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


class TimeContext(BaseModel):
    """Mixin providing local time and part of day information."""

    local_time: datetime = Field(..., description="Current local time with timezone")
    part_of_day: Literal["night", "morning", "afternoon", "evening"]


def get_local_time(timezone: str = "Europe/Prague") -> Tuple[datetime, str]:
    """Return current local time and a human-friendly part of day.

    Args:
        timezone: IANA timezone string, defaults to "Europe/Prague".

    Returns:
        Tuple of current localized datetime and part of day string.
    """

    now: datetime = datetime.now(ZoneInfo(timezone))
    hour: int = now.hour
    if 5 <= hour < 12:
        part = "morning"
    elif 12 <= hour < 17:
        part = "afternoon"
    elif 17 <= hour < 22:
        part = "evening"
    else:
        part = "night"
    return now, part
