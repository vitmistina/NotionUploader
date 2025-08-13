from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    api_key: str = Field(..., env="API_KEY")
    notion_secret: str = Field(..., env="NOTION_SECRET")
    notion_database_id: str = Field(..., env="NOTION_DATABASE_ID")
    notion_workout_database_id: str = Field(..., env="NOTION_WORKOUT_DATABASE_ID")
    notion_athlete_profile_database_id: str = Field(
        ..., env="NOTION_ATHLETE_PROFILE_DATABASE_ID"
    )
    strava_verify_token: str = Field(..., env="STRAVA_VERIFY_TOKEN")
    wbsapi_url: str = Field(..., env="WBSAPI_URL")
    upstash_redis_rest_url: str = Field(..., env="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field(..., env="UPSTASH_REDIS_REST_TOKEN")
    withings_client_id: str = Field(..., env="WITHINGS_CLIENT_ID")
    withings_client_secret: str = Field(..., env="WITHINGS_CLIENT_SECRET")
    strava_client_id: str = Field(..., env="STRAVA_CLIENT_ID")
    strava_client_secret: str = Field(..., env="STRAVA_CLIENT_SECRET")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
