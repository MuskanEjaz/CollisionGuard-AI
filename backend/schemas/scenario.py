"""
Scenario-related Pydantic schemas.

Phase 1: schema definitions + JSON file loading.
Phase 2: predicted_miss_distance_km and time_to_closest_approach_s are
         populated by the propagation engine; they are None here until
         the /propagate endpoint is called.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# ── TLE ───────────────────────────────────────────────────────────────────────

class TLEData(BaseModel):
    """
    Two-line element set.

    Phase 1 validates line length and line-number prefix.
    Phase 2 validates that sgp4 can parse the lines (done in _build_satrec).
    """

    line1: str
    line2: str

    @field_validator("line1")
    @classmethod
    def validate_line1(cls, v: str) -> str:
        v = v.strip()
        if len(v) != 69:
            raise ValueError(
                f"TLE line 1 must be exactly 69 characters, got {len(v)}"
            )
        if not v.startswith("1 "):
            raise ValueError("TLE line 1 must start with '1 '")
        return v

    @field_validator("line2")
    @classmethod
    def validate_line2(cls, v: str) -> str:
        v = v.strip()
        if len(v) != 69:
            raise ValueError(
                f"TLE line 2 must be exactly 69 characters, got {len(v)}"
            )
        if not v.startswith("2 "):
            raise ValueError("TLE line 2 must start with '2 '")
        return v


# ── Space Object ─────────────────────────────────────────────────────────────

class SpaceObject(BaseModel):
    """A tracked space object with orbital elements and physical properties."""

    object_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    tle: TLEData
    mass_kg: Annotated[float, Field(gt=0, description="Object mass in kilograms")]
    cross_section_m2: Annotated[
        float, Field(gt=0, description="Average cross-sectional area in m²")
    ]


# ── Scenario ──────────────────────────────────────────────────────────────────

class ScenarioType(str, Enum):
    CONJUNCTION = "conjunction"
    SAFE = "safe"


class Scenario(BaseModel):
    """
    A single two-object conjunction scenario.

    Scope: exactly our satellite + one threat object, LEO only.
    predicted_miss_distance_km and time_to_closest_approach_s are None until
    the propagation engine populates them via the /propagate endpoint.
    """

    scenario_id: str = Field(..., min_length=1)
    scenario_type: ScenarioType
    description: str = Field(..., min_length=1)
    epoch_utc: datetime

    # Data provenance and uncertainty disclosure.
    # Optional at contract level for backwards compatibility with runtime
    # scenarios, but committed demo scenarios provide all four values.
    data_source: str | None = None
    data_quality: str | None = None
    uncertainty_basis: str | None = None
    operational_use: str | None = None

    our_satellite: SpaceObject
    threat_object: SpaceObject

    # Populated by propagation engine (Phase 2+)
    predicted_miss_distance_km: float | None = None
    time_to_closest_approach_s: float | None = None
    tca_utc: datetime | None = None
    is_conjunction: bool | None = None


class ScenarioListResponse(BaseModel):
    """Paginated list of scenarios returned by GET /scenarios."""

    scenarios: list[Scenario]
    count: int


# ── Propagation response ──────────────────────────────────────────────────────

class PropagationResponse(BaseModel):
    """Returned by POST /scenarios/{id}/propagate."""
    scenario_id: str
    miss_distance_km: float
    tca_offset_seconds: float
    tca_utc: datetime
    is_conjunction: bool
    conjunction_threshold_km: float
