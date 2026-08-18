# Granite advisory response schemas -- Phase 6.
#
# SAFETY ARCHITECTURE:
#   Granite receives only backend-validated safe candidates.
#   Granite may rank and explain only.
#   Granite must never modify physics values, collision risk, fuel cost,
#   or robustness results.
#   Every number Granite states is validated against the backend-computed
#   value before the response is returned to the caller.
#   If Granite output conflicts with backend values, the Granite output is
#   rejected and the deterministic backend result is used.
from __future__ import annotations
from pydantic import BaseModel


class GraniteRankedCandidate(BaseModel):
    candidate_id: str
    rank: int                        # 1 = Granite top pick
    explanation: str                 # Granite-generated human-readable rationale
    # Physics values below are ALWAYS copied from backend -- never from Granite
    delta_v_ms: float
    post_maneuver_miss_distance_km: float
    fuel_cost_kg: float
    baseline_score: float


class GraniteAdvisoryResponse(BaseModel):
    scenario_id: str
    ranked_candidates: list[GraniteRankedCandidate]
    granite_summary: str             # Granite narrative paragraph
    source: str                      # "granite" or "deterministic_fallback"
    model_id: str                    # active model ID (config-driven, never hardcoded)
    validation_warnings: list[str]   # populated if any Granite value was rejected
    granite_note: str                # always shown -- marks architectural constraints
