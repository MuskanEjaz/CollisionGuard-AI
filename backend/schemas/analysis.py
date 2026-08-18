# Full analysis response schemas -- Phase 7.
# Wraps propagation + evaluation + Granite advisory into one response,
# and adds display metadata (risk classification, data quality notes, etc.)
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel
from schemas.maneuver import ManeuverCandidate
from schemas.granite import GraniteAdvisoryResponse


class RiskClassification(BaseModel):
    level: str             # "CONJUNCTION" | "SAFE" | "MONITORING"
    label: str             # human display label
    color_hint: str        # "red" | "green" | "yellow" -- for UI badge


class DataQualityNote(BaseModel):
    field: str
    note: str


class FullAnalysisResponse(BaseModel):
    # Identity
    scenario_id: str
    cached: bool                       # True if result came from cache
    analysis_timestamp: datetime       # when this analysis was computed

    # Propagation results
    nominal_miss_distance_km: float
    tca_offset_seconds: float
    tca_utc: datetime
    is_conjunction: bool
    conjunction_threshold_km: float    # always 1.0 -- business rule

    # Display extras
    risk: RiskClassification
    data_quality: list[DataQualityNote]
    orbit_element_age_note: str        # e.g. "Epoch: 2025-08-01T12:00:00Z (synthetic)"

    # Maneuver candidates (all, with safety fields populated)
    candidates: list[ManeuverCandidate]
    safe_count: int
    total_count: int
    evaluation_note: str               # "SIMPLIFIED FOR PROTOTYPE" note

    # Granite advisory
    advisory: GraniteAdvisoryResponse

    # Required UI disclosure labels
    prototype_label: str = "Human-supervised decision-support prototype"
    simulation_label: str = "Simulation only — not flight software"
    risk_basis_label: str = (
        "Screening-level estimate based on two-body propagation and "
        "demonstration Pc based on synthetic covariance. "
        "Not suitable for operational conjunction screening."
    )


# ---------------------------------------------------------------------------
# Execution schemas
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    scenario_id: str
    candidate_id: str
    operator_id: str = "OPERATOR"      # placeholder; no real auth in prototype


class ExecutionStatus(BaseModel):
    scenario_id: str
    candidate_id: str
    operator_id: str
    simulated: bool = True             # ALWAYS True -- this is never real execution
    execution_label: str = "SIMULATED EXECUTION -- not flight software"
    status: str                        # "approved" | "executing" | "complete" | "rejected"
    message: str
    post_maneuver_miss_distance_km: float | None = None
    delta_v_applied_ms: float | None = None
    fuel_consumed_kg: float | None = None
    executed_at: datetime | None = None


class ExecutionApprovedResponse(BaseModel):
    # Returned when operator approves a candidate for simulated execution
    execution: ExecutionStatus
    safety_gate_passed: bool
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Incident report schema
# ---------------------------------------------------------------------------

class IncidentReport(BaseModel):
    scenario_id: str
    candidate_id: str
    generated_by: str              # "granite" | "deterministic_template"
    report_text: str
    simulated: bool = True
    report_label: str = "SIMULATED INCIDENT REPORT -- not flight documentation"
