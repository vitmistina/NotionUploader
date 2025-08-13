from __future__ import annotations

from fastapi import Depends, FastAPI

from .routes import router
from .security import verify_api_key
from .strava_webhook import webhook_router

app: FastAPI = FastAPI(
    title="Nutrition Logger",
    version="2.0.0",
    description="Logs food and macro data to Vit's Notion table",
)


@app.get("/", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Lightweight endpoint used for health checks."""
    return {"status": "ok"}

# API endpoints secured by API key
app.include_router(router, dependencies=[Depends(verify_api_key)])

# Strava webhook endpoints (no API key security)
app.include_router(webhook_router)
