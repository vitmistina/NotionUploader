from __future__ import annotations

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader

from .settings import Settings, get_settings

api_key_header: APIKeyHeader = APIKeyHeader(
    name="x-api-key", scheme_name="ApiKeyAuth", auto_error=False
)


def verify_api_key(
    x_api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail={"error": "Unauthorized"})
