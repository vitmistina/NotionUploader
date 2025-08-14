from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query, Depends

from ..models.workout import WorkoutLog
from ..services.interfaces import NotionAPI
from ..services.notion import get_notion_client
from ..settings import Settings, get_settings
from ..workout_notion import fetch_workouts_from_notion

router: APIRouter = APIRouter()


@router.get("/workout-logs", response_model=List[WorkoutLog])
async def list_logged_workouts(
    days: int = Query(7, description="Number of days of logged workouts to retrieve."),
    settings: Settings = Depends(get_settings),
    client: NotionAPI = Depends(get_notion_client),
) -> List[WorkoutLog]:
    return await fetch_workouts_from_notion(days, settings, client)


