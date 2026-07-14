from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class IntervalsApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IntervalsAuthError(IntervalsApiError):
    pass


class IntervalsPayloadError(ValueError):
    pass


class IntervalsClientPort(Protocol):
    async def list_activities(self, *, oldest: date, newest: date) -> list[dict[str, Any]]: ...
    async def get_activity_intervals(self, activity_id: str) -> list[dict[str, Any]]: ...
