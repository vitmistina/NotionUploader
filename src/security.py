from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import API_KEY

api_key_header: APIKeyHeader = APIKeyHeader(
    name="x-api-key", scheme_name="ApiKeyAuth", auto_error=False
)

def verify_api_key(x_api_key: str | None = Security(api_key_header)) -> None:
    if API_KEY is None:
        raise RuntimeError("API_KEY is not set")
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
