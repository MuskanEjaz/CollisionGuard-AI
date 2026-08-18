"""
Scenario-related Pydantic schemas.

Phase 1: schema definitions + JSON file loading.
Phase 2: predicted_miss_distance_km and time_to_closest_approach_s are
         populated by the propagation engine; they are None here.
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
    Full SGP4 checksum validation is deferred to Phase 2 when sgp4 is first
    exercised against these values.
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
    predicted_miss_distance_km and time_to_closest_approach_s are None in
    Phase 1 and populated by the propagation engine in Phase 2.
    """

    scenario_id: str = Field(..., min_length=1)
    scenario_type: ScenarioType
    description: str = Field(..., min_length=1)
    epoch_utc: datetime
    our_satellite: SpaceObject
    threat_object: SpaceObject

    # Populated by propagation engine in Phase 2
    predicted_miss_distance_km: float | None = None
    time_to_closest_approach_s: float | None = None


class ScenarioListResponse(BaseModel):
    """Paginated list of scenarios returned by GET /scenarios."""

    scenarios: list[Scenario]
    count: int
