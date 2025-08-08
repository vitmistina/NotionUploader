from __future__ import annotations

from fastapi import Depends, FastAPI

from .routes import router
from .security import verify_api_key

app: FastAPI = FastAPI(
    title="Nutrition Logger",
    version="2.0.0",
    description="Logs food and macro data to Vit's Notion table",
    dependencies=[Depends(verify_api_key)],
)

app.include_router(router)
