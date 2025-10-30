from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class OperationStatus(BaseModel):
    """Normalized status payload returned by mutation endpoints."""

    status: str = Field(..., description="Short status indicator for the operation outcome.")
    id: Optional[int] = Field(
        None, description="Identifier of the resource affected by the operation, when relevant."
    )
    model_config = ConfigDict(json_schema_extra={"required": ["status"]})

    @model_serializer(mode="wrap")
    def _serialize(self, handler):  # type: ignore[override]
        payload = handler(self)
        if payload.get("id") is None:
            payload.pop("id", None)
        return payload
