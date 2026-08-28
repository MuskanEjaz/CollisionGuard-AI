# Full analysis response schemas -- Phase 7/9.
# Wraps propagation + evaluation + Granite advisory into one response,
# and adds display metadata (risk classification, data quality notes, etc.)
#
# Phase 9 additions:
#   - relative_velocity_km_s + related fields (deterministic, from propagation)
#   - covariance_available, covariance_source, covariance_basis
#   - collision_probability_available, collision_probability
#   - risk_estimate_basis (was only a display label; now also a machine field)
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
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


# ── Visualization data contract (Phase 10) ─────────────────────────────────────
# Provides backend-propagated trajectory samples for accurate 3D rendering
# All positions in TEME frame, units in km, timestamps in UTC ISO format

class VisualizationSample(BaseModel):
    """Single trajectory sample point with aligned timestamps for both objects."""
    timestamp_utc: str
    protected_position_km: List[float]  # [x, y, z] in TEME frame
    threat_position_km: List[float]     # [x, y, z] in TEME frame


class VisualizationTCA(BaseModel):
    """TCA geometry with both object positions and miss distance."""
    timestamp_utc: str
    protected_position_km: List[float]
    threat_position_km: List[float]
    miss_distance_km: float
    relative_velocity_km_s: Optional[float] = None
    relative_velocity_vector_km_s: Optional[List[float]] = None
    coordinate_frame: str = "TEME"


class VisualizationData(BaseModel):
    """Complete visualization payload returned by the analysis endpoint."""
    coordinate_frame: str = "TEME"
    position_units: str = "km"
    visualization_start_utc: str
    visualization_end_utc: str
    samples: List[VisualizationSample]
    tca: VisualizationTCA
    # Post-maneuver trajectory — only present when a candidate has been evaluated
    post_maneuver: Optional[dict] = None  # {candidate_id, positions_km, timestamps_utc}


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

    # ── Relative velocity at TCA (Phase 9) ───────────────────────────────────
    # Computed from SGP4 velocity vectors of both objects at the exact TCA
    # timestamp in the TEME frame.  None if SGP4 propagation failed at TCA.
    relative_velocity_km_s: Optional[float] = None
    relative_velocity_vector_km_s: Optional[tuple[float, float, float]] = None
    relative_velocity_frame: str = "TEME"
    relative_velocity_timestamp_utc: Optional[datetime] = None
    relative_velocity_basis: str = (
        "Difference of both SGP4 velocity vectors at TCA in the TEME frame"
    )

    # ── Covariance availability contract (Phase 9) ───────────────────────────
    # Explicit machine-readable covariance contract. Never fabricated.
    covariance_available: bool = False
    covariance_source: str = "Synthetic covariance"
    covariance_basis: str = "Committed demonstration uncertainty model"
    # Pc fields — null means unavailable (distinct from 0.0 = computed zero)
    collision_probability_available: bool = False
    collision_probability: Optional[float] = None

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

    # Visualization data — backend-propagated trajectory for accurate 3D rendering
    visualization: Optional[VisualizationData] = None

    # Required UI disclosure labels
    prototype_label: str = "Human-supervised decision-support prototype"
    simulation_label: str = "Simulation only — not flight software"
    risk_basis_label: str = (
        "SGP4 propagation in the TEME frame using public CelesTrak GP elements. "
        "Results remain screening-level because public GP data does not include "
        "operational conjunction covariance and accuracy degrades with element age."
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
