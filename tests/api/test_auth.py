"""Authentication and schema contract tests."""

from __future__ import annotations

import httpx
import pytest

from platform.config import Settings

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        pytest.param({}, 401, id="missing"),
        pytest.param({"x-api-key": "wrong"}, 401, id="invalid"),
        pytest.param("valid", 200, id="valid"),
    ],
)
async def test_api_schema_auth_contract(
    client: httpx.AsyncClient, settings: Settings, headers: dict[str, str] | str, expected_status: int
) -> None:
    """The API schema endpoint enforces the x-api-key contract."""

    request_headers = (
        {"x-api-key": settings.api_key} if isinstance(headers, str) else headers
    )

    response = await client.get("/v2/api-schema", headers=request_headers)

    assert response.status_code == expected_status


async def test_openapi_schema(client: httpx.AsyncClient, settings: Settings) -> None:
    """The generated schema defines the API key security scheme only once."""

    response = await client.get("/v2/api-schema", headers={"x-api-key": settings.api_key})

    assert response.status_code == 200
    schema = response.json()

    assert schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "x-api-key"
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "parameters" in operation:
                assert all(parameter["name"] != "x-api-key" for parameter in operation["parameters"])
