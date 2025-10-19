"""Infrastructure adapters for the Strava integration."""

from .client import StravaAuthError, StravaClient

__all__ = ["StravaAuthError", "StravaClient"]
