"""Health-check response schemas."""
from typing import Literal
from pydantic import BaseModel


class ComponentStatus(BaseModel):
    """Status of a single backend component."""

    status: Literal["ok", "degraded", "unavailable"]
    detail: str | None = None


class HealthResponse(BaseModel):
    """
    Response model for GET /health.

    Later phases add fields (e.g. propagation, granite) without breaking
    existing consumers — new fields use Optional / default values.
    """

    status: Literal["ok", "degraded"]
    version: str
    components: dict[str, ComponentStatus]
