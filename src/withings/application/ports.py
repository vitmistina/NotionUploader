"""Ports for interacting with Withings data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
