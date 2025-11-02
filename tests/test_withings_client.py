import sys
from pathlib import Path
from typing import Dict, Optional

import httpx
import pytest
import respx

# Ensure repository root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.body import BodyMeasurement
from src.settings import Settings
from src.withings.infrastructure.client import WithingsAPIClient


class RecordingRedis:
    def __init__(self, initial: Optional[Dict[str, str]] = None) -> None:
        self.store: Dict[str, str] = dict(initial or {})
        self.expirations: Dict[str, Optional[int]] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self.store[key] = value
        self.expirations[key] = ex


TEST_SETTINGS = Settings(
    api_key="key",
    notion_secret="secret",
    notion_database_id="db",
    notion_workout_database_id="workout-db",
    notion_athlete_profile_database_id="profile-db",
    strava_verify_token="verify",
    wbsapi_url="https://withings.example.com",
    upstash_redis_rest_url="https://redis.example.com",
    upstash_redis_rest_token="token",
    withings_client_id="withings-client",
    withings_client_secret="withings-secret",
    strava_client_id="strava-client",
    strava_client_secret="strava-secret",
)


@pytest.mark.asyncio
@respx.mock
async def test_refresh_access_token_success(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_refresh_token": "refresh-token"})

    respx_mock.post(f"{TEST_SETTINGS.wbsapi_url}/v2/oauth2").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": 0,
                "body": {
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 120,
                },
            },
        )
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)
    token = await client.refresh_access_token()

    assert token == "new-access"
    assert redis.store["withings_access_token"] == "new-access"
    assert redis.expirations["withings_access_token"] == 90
    assert redis.store["withings_refresh_token"] == "new-refresh"
    assert redis.expirations["withings_refresh_token"] == 365 * 24 * 60 * 60


@pytest.mark.asyncio
@respx.mock
async def test_refresh_access_token_without_refresh_token(respx_mock: respx.Router) -> None:
    client = WithingsAPIClient(redis=RecordingRedis(), settings=TEST_SETTINGS)

    with pytest.raises(ValueError):
        await client.refresh_access_token()


@pytest.mark.asyncio
@respx.mock
async def test_refresh_access_token_http_error(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_refresh_token": "refresh-token"})

    respx_mock.post(f"{TEST_SETTINGS.wbsapi_url}/v2/oauth2").mock(
        return_value=httpx.Response(500, json={"status": 42})
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)

    with pytest.raises(RuntimeError):
        await client.refresh_access_token()


@pytest.mark.asyncio
@respx.mock
async def test_refresh_access_token_error_status(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_refresh_token": "refresh-token"})

    respx_mock.post(f"{TEST_SETTINGS.wbsapi_url}/v2/oauth2").mock(
        return_value=httpx.Response(
            200,
            json={"status": 42, "error": "boom", "body": {}},
        )
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)

    with pytest.raises(RuntimeError):
        await client.refresh_access_token()


@pytest.mark.asyncio
@respx.mock
async def test_refresh_access_token_missing_access_token(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_refresh_token": "refresh-token"})

    respx_mock.post(f"{TEST_SETTINGS.wbsapi_url}/v2/oauth2").mock(
        return_value=httpx.Response(200, json={"status": 0, "body": {}})
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)

    with pytest.raises(RuntimeError):
        await client.refresh_access_token()


@pytest.mark.asyncio
@respx.mock
async def test_refresh_access_token_without_expires_sets_token(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_refresh_token": "refresh-token"})

    respx_mock.post(f"{TEST_SETTINGS.wbsapi_url}/v2/oauth2").mock(
        return_value=httpx.Response(
            200,
            json={"status": 0, "body": {"access_token": "token"}},
        )
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)
    token = await client.refresh_access_token()

    assert token == "token"
    assert redis.expirations["withings_access_token"] is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_measurements_success(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_access_token": "token"})

    respx_mock.get(f"{TEST_SETTINGS.wbsapi_url}/v2/measure").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": 0,
                "body": {
                    "measuregrps": [
                        {
                            "date": 1,
                            "device": "Scale",
                            "measures": [
                                {"type": 1, "value": 700, "unit": -1},
                                {"type": 6, "value": 15, "unit": 0},
                            ],
                        }
                    ]
                },
            },
        )
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)
    measurements = await client.fetch_measurements(days=1)

    assert len(measurements) == 1
    assert isinstance(measurements[0], BodyMeasurement)
    assert measurements[0].weight_kg == 70.0
    assert measurements[0].body_fat_percent == 15


@pytest.mark.asyncio
@respx.mock
async def test_fetch_measurements_refreshes_on_401(respx_mock: respx.Router) -> None:
    redis = RecordingRedis(
        {
            "withings_access_token": "stale",
            "withings_refresh_token": "refresh-token",
        }
    )

    respx_mock.get(f"{TEST_SETTINGS.wbsapi_url}/v2/measure").mock(
        side_effect=[
            httpx.Response(401, json={"status": 401}),
            httpx.Response(200, json={"status": 0, "body": {"measuregrps": []}}),
        ]
    )
    respx_mock.post(f"{TEST_SETTINGS.wbsapi_url}/v2/oauth2").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": 0,
                "body": {
                    "access_token": "new-token",
                    "refresh_token": "next-refresh",
                    "expires_in": 180,
                },
            },
        )
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)
    measurements = await client.fetch_measurements(days=1)

    assert measurements == []
    assert redis.store["withings_access_token"] == "new-token"
    assert redis.store["withings_refresh_token"] == "next-refresh"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_measurements_raises_on_api_error(respx_mock: respx.Router) -> None:
    redis = RecordingRedis({"withings_access_token": "token"})

    respx_mock.get(f"{TEST_SETTINGS.wbsapi_url}/v2/measure").mock(
        return_value=httpx.Response(200, json={"status": 42, "error": "boom"})
    )

    client = WithingsAPIClient(redis=redis, settings=TEST_SETTINGS)

    with pytest.raises(RuntimeError):
        await client.fetch_measurements(days=1)
