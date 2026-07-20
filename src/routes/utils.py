from __future__ import annotations

from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Query
from fastapi.exceptions import RequestValidationError


def _timezone_validation_error(value: object) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "timezone",
                "loc": ("query", "timezone"),
                "msg": "Unknown IANA timezone",
                "input": value,
            }
        ]
    )


async def validated_timezone(
    timezone: str = Query(
        default="Europe/Prague",
        description="IANA timezone for local time, defaults to Prague.",
        examples=["Europe/Prague"],
    ),
) -> str:
    if not timezone:
        raise _timezone_validation_error(timezone)
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise _timezone_validation_error(timezone) from exc
    return timezone


timezone_query = Annotated[str, Depends(validated_timezone)]
