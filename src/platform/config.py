from __future__ import annotations

from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    api_key: str
    notion_secret: str
    notion_database_id: str
    notion_workout_database_id: str
    notion_athlete_profile_database_id: str
    wbsapi_url: str
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    withings_client_id: str
    withings_client_secret: str
    intervals_api_key: str
    intervals_athlete_id: str = "0"
    intervals_api_base_url: str = "https://intervals.icu/api/v1"
    intervals_sync_lookback_days: int = 7
    intervals_rouvy_start_date: date | None = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
