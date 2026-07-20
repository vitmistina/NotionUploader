"""Ports for retaining raw, compressed workout detail outside Notion."""

from __future__ import annotations

from typing import Protocol


class WorkoutPayloadStore(Protocol):
    """Store and retrieve compressed base64 workout payloads."""

    async def put(self, key: str, gzip_base64_payload: str) -> None:
        """Persist a payload for the configured retention period."""

    async def get(self, key: str) -> str | None:
        """Return a payload, if it is still retained."""
