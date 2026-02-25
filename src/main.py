from __future__ import annotations

from platform import verify_api_key
from platform.clients import RedisClient, get_redis
from typing import Any, Dict

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from .routes.advice import router as advice_router
from .routes.metrics import router as metrics_router
from .routes.nutrition import router as nutrition_router
from .routes.strava import router as strava_router
from .routes.workouts import router as workouts_router
from .strava_webhook import webhook_router

app: FastAPI = FastAPI(
    title="Nutrition Logger",
    version="2.0.0",
    description="Logs food and macro data to Vit's Notion table",
)


@app.exception_handler(httpx.ConnectError)
async def handle_httpx_connect_error(_: Request, exc: httpx.ConnectError) -> JSONResponse:
    """Return a user-friendly response when an upstream service cannot be reached."""
    host = _extract_upstream_host(exc)
    detail: Dict[str, str] = {
        "error": "UPSTREAM_CONNECTION_FAILED",
        "message": (
            "Could not connect to an upstream dependency service. "
            "Please try again shortly."
        ),
    }
    if host:
        detail["upstream_host"] = host

    return JSONResponse(status_code=503, content=detail)


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
async def healthz(redis: RedisClient = Depends(get_redis)) -> dict[str, str]:
    """Health check endpoint that verifies API process and Upstash Redis connectivity."""
    redis.get("healthz:upstash")
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


def _extract_upstream_host(exc: httpx.ConnectError) -> str | None:
    request = getattr(exc, "request", None)
    if request is None:
        return None

    url = getattr(request, "url", None)
    if url is None:
        return None

    return url.host
