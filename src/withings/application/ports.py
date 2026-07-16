"""Ports for interacting with Withings data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from ...models.body import BodyMeasurement


class WithingsMeasurementsPort(ABC):
    """Interface describing Withings measurement operations."""

    @abstractmethod
    async def refresh_access_token(self) -> str:
        """Refresh and persist a new access token."""

    @abstractmethod
    async def fetch_measurements(self, days: int) -> Sequence[BodyMeasurement]:
        """Return measurements covering the requested time span."""

    async def fetch_measurements_in_range(
        self, start_at: datetime, end_at: datetime
    ) -> Sequence[BodyMeasurement]:
        """Return measurements for explicit UTC boundaries.

        The default keeps older integrations source-compatible while allowing new
        callers to use one shared window.
        """
        days = max(1, (end_at.date() - start_at.date()).days)
        return await self.fetch_measurements(days)
