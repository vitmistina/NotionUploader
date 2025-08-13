from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    api_key: str
    notion_secret: str
    notion_database_id: str
    notion_workout_database_id: str
    notion_athlete_profile_database_id: str
    strava_verify_token: str
    wbsapi_url: str
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    withings_client_id: str
    withings_client_secret: str
    strava_client_id: str
    strava_client_secret: str


@lru_cache()
def get_settings() -> Settings:
    return Settings()
