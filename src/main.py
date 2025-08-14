from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from .routes.nutrition import router as nutrition_router
from .routes.metrics import router as metrics_router
from .routes.workouts import router as workouts_router
from .routes.advice import router as advice_router
from .routes.strava import router as strava_router
from .security import verify_api_key
from .strava_webhook import webhook_router

app: FastAPI = FastAPI(
    title="Nutrition Logger",
    version="2.0.0",
    description="Logs food and macro data to Vit's Notion table",
)


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Lightweight endpoint used for health checks."""
    return {"status": "ok"}


@app.get("/v2/api-schema")
async def get_api_schema(request: Request, _: Any = Depends(verify_api_key)) -> JSONResponse:
    """Return the OpenAPI schema for this API version."""
    openapi_schema: Dict[str, Any] = request.app.openapi()
    openapi_schema["servers"] = [
        {"url": "https://notionuploader-groa.onrender.com"}
    ]
    return JSONResponse(openapi_schema)


for router in (
    nutrition_router,
    metrics_router,
    workouts_router,
    advice_router,
    strava_router,
):
    app.include_router(router, prefix="/v2", dependencies=[Depends(verify_api_key)])

# Strava webhook endpoints (no API key security)
app.include_router(webhook_router)
