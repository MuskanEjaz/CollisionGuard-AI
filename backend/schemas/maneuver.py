# Maneuver candidate schemas -- Phase 3+4.
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from typing import Annotated


class ManeuverDirection(str, Enum):
    PROGRADE   = "prograde"    # along velocity vector -- raises apogee
    RETROGRADE = "retrograde"  # against velocity vector -- lowers orbit
    RADIAL_OUT = "radial_out"  # away from Earth centre
    NORMAL     = "normal"      # normal to orbital plane (inclination change)


class ManeuverCandidate(BaseModel):
    candidate_id: str
    label: str                  # human-readable, e.g. "Small Prograde +0.5 m/s"
    direction: ManeuverDirection
    delta_v_ms: Annotated[float, Field(description="Delta-v magnitude in m/s")]
    # Populated by Phase 4 safety evaluator
    is_safe: bool | None = None
    safety_rejection_reason: str | None = None
    fuel_cost_kg: float | None = None
    post_maneuver_miss_distance_km: float | None = None
    baseline_score: float | None = None    # 0..1, higher is better


class ManeuverCandidateListResponse(BaseModel):
    scenario_id: str
    candidates: list[ManeuverCandidate]
    count: int


class EvaluationResponse(BaseModel):
    scenario_id: str
    nominal_miss_distance_km: float
    candidates: list[ManeuverCandidate]
    safe_count: int
    total_count: int
    evaluation_note: str   # always shown in UI -- marks simplified areas
