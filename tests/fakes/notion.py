"""Helpers and doubles for Notion interactions in tests."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from src.services.interfaces import NotionAPI
from src.settings import Settings


class NotionWorkoutFake(NotionAPI):
    """In-memory Notion API tailored for workout repository tests."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._workouts: List[Dict[str, Any]] = []
        self._profile: Dict[str, Any] | None = None
        self._pages: Dict[str, Dict[str, Any]] = {}
        self._updates: List[Tuple[str, Dict[str, Any]]] = []

    def with_workouts(self, workouts: Iterable[Dict[str, Any]]) -> "NotionWorkoutFake":
        """Seed the fake with workout pages returned by the query API."""

        self._workouts = list(workouts)
        self._pages = {
            page.get("id", f"page-{index}"): page
            for index, page in enumerate(self._workouts)
        }
        return self

    def with_profile(self, profile: Dict[str, Any] | None) -> "NotionWorkoutFake":
        """Provide the athlete profile returned by profile queries."""

        self._profile = profile
        return self

    def updates(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Expose recorded update calls for assertions."""

        return list(self._updates)

    async def query(self, database_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if (
            database_id == self._settings.notion_athlete_profile_database_id
            and self._profile is not None
        ):
            return {"results": [self._profile]}
        if database_id == self._settings.notion_workout_database_id:
            return {"results": self._workouts}
        return {"results": []}

    async def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        page_id = payload.get("id", "created-page")
        self._pages[page_id] = payload
        return {"id": page_id}

    async def update(self, page_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._updates.append((page_id, payload))
        page = self._pages.setdefault(page_id, {"id": page_id, "properties": {}})
        page.setdefault("properties", {}).update(payload.get("properties", {}))
        return {"id": page_id}

    async def retrieve(self, page_id: str) -> Dict[str, Any]:
        return self._pages.get(page_id, {"id": page_id, "properties": {}})
