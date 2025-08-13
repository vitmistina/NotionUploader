from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Allow loading variables provided by the hosting environment even when
    # they use the conventional upper-case naming. Previously `case_sensitive`
    # was set to ``True`` which meant environment variables needed to match the
    # exact lower-case field names (e.g. ``notion_secret``). In production the
    # variables are defined in Render using upper-case names (e.g.
    # ``NOTION_SECRET``), causing pydantic to treat them as missing and raise
    # ``Field required`` errors. Disabling case sensitivity lets pydantic match
    # these variables regardless of case, resolving the configuration loading
    # issue when no `.env` file is present.
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

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
