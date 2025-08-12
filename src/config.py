from __future__ import annotations

import os
from typing import Final, Optional, Dict
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

def get_env_var(name: str) -> str:
    """Get environment variable or raise an error if it doesn't exist."""
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"Environment variable {name} is not set")
    return value

# Notion configuration
API_KEY: str = get_env_var("API_KEY")
NOTION_SECRET: str = get_env_var("LLM_Update")
NOTION_DATABASE_ID: str = get_env_var("NOTION_DATABASE_ID")
NOTION_WORKOUT_DATABASE_ID: str = get_env_var("NOTION_WORKOUT_DATABASE_ID")
NOTION_ATHLETE_PROFILE_DATABASE_ID: str = get_env_var(
    "NOTION_ATHLETE_PROFILE_DATABASE_ID"
)
STRAVA_VERIFY_TOKEN: str = get_env_var("STRAVA_VERIFY_TOKEN")

NOTION_HEADERS: Final[Dict[str, str]] = {
    "Authorization": f"Bearer {NOTION_SECRET}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# Withings API configuration
WBSAPI_URL: Final[str] = get_env_var("WBSAPI_URL")
UPSTASH_REDIS_REST_URL: Final[str] = get_env_var('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_REST_TOKEN: Final[str] = get_env_var('UPSTASH_REDIS_REST_TOKEN')
WITHINGS_CLIENT_ID: Final[str] = get_env_var('WITHINGS_CLIENT_ID')
WITHINGS_CLIENT_SECRET: Final[str] = get_env_var('WITHINGS_CLIENT_SECRET')
CLIENT_ID: Final[str] = get_env_var('CLIENT_ID')
CUSTOMER_SECRET: Final[str] = get_env_var('CUSTOMER_SECRET')
STRAVA_CLIENT_ID: Final[str] = get_env_var('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET: Final[str] = get_env_var('STRAVA_CLIENT_SECRET')
