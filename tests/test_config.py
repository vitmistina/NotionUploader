"""Configuration loading tests."""

from platform.config import Settings


def test_settings_ignores_unrelated_environment_values() -> None:
    """Shared environment files may contain settings for other integrations."""

    settings = Settings(
        api_key="test-key",
        notion_secret="notion-secret",
        notion_database_id="notion-db",
        notion_workout_database_id="workout-db",
        notion_athlete_profile_database_id="profile-db",
        wbsapi_url="https://wbs.example.com",
        upstash_redis_rest_url="https://redis.example.com",
        upstash_redis_rest_token="redis-token",
        withings_client_id="withings-client",
        withings_client_secret="withings-secret",
        intervals_api_key="intervals-secret",
        strava_client_id="unused-client-id",
        strava_client_secret="unused-client-secret",
        strava_verify_token="unused-verify-token",
    )

    assert settings.notion_workout_database_id == "workout-db"
    assert not hasattr(settings, "strava_client_id")
