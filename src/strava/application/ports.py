"""Ports for the Strava application layer."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class StravaAuthError(RuntimeError):
    """Raised when Strava authentication fails."""


@runtime_checkable
class StravaClientPort(Protocol):
    """Port that exposes the Strava client behaviour used by the application."""

    async def get_activity(self, activity_id: int) -> dict[str, Any]:
        """Return the raw payload for a Strava activity."""


__all__ = ["StravaAuthError", "StravaClientPort"]
