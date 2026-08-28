"""
CelesTrak live-data route — CollisionGuard AI Phase 8.

POST /scenarios/live

Fetches two objects from CelesTrak, validates them, builds an in-memory
Scenario, runs the existing deterministic analysis pipeline, and returns
a LiveAnalysisResponse with full source provenance.

Safety rules (all inherited from existing pipeline):
  - Never overwrites committed synthetic scenarios
  - Never bypasses human approval
  - Never triggers simulated execution automatically
  - Never calls Granite automatically
  - Never triggers robustness or Monte Carlo as part of import
  - Unsafe candidates cannot be approved (enforced by analysis router)

Provenance rules:
  - covariance_source: "Not provided by GP data"
  - risk_estimate_basis: screening-level, not operational
  - live_data: True

Human-supervised decision-support prototype. Simulation only — not flight software.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

import sgp4.omm as omm_init
from sgp4.api import Satrec
from sgp4.exporter import export_tle as sgp4_export_tle

from celestrak_client import (
    fetch_orbital_record,
    check_leo,
    OrbitalRecord,
    CelesTrakError,
    CelesTrakTimeoutError,
    CelesTrakEmptyError,
    CelesTrakNonLEOError,
)
from config import get_settings
from schemas.scenario import Scenario, ScenarioType, SpaceObject, TLEData
from schemas.celestrak import LiveScenarioRequest, LiveAnalysisResponse, CelesTrakObjectMeta
from schemas.analysis import FullAnalysisResponse, RiskClassification, DataQualityNote
from schemas.maneuver import EvaluationResponse
from granite_client import get_granite_advisory
from maneuver_candidates import get_maneuver_candidates
from maneuver_evaluator import evaluate_all_candidates
from propagation import propagate_scenario, CONJUNCTION_THRESHOLD_KM
from scenario_registry import register_runtime_scenario, delete_runtime_scenario

router = APIRouter(prefix="/scenarios", tags=["live-data"])

# Default mass and cross-section when not available in GP data (synthetic fallback)
_DEFAULT_MASS_KG         = 500.0
_DEFAULT_CROSS_SECTION_M2 = 5.0


# ── Risk classification (replicates routers/analysis._classify_risk) ──────────

def _classify_risk(miss_km: float) -> RiskClassification:
    if miss_km < CONJUNCTION_THRESHOLD_KM:
        return RiskClassification(
            level="CONJUNCTION",
            label="Conjunction Alert -- maneuver review required",
            color_hint="red",
        )
    if miss_km < 5.0:
        return RiskClassification(
            level="MONITORING",
            label="Monitoring -- within watch threshold",
            color_hint="yellow",
        )
    return RiskClassification(
        level="SAFE",
        label="Safe separation -- no action required",
        color_hint="green",
    )


# ── TLE construction from OMM ─────────────────────────────────────────────────

def _tle_lines_from_omm(record: OrbitalRecord) -> TLEData:
    """
    Build a Satrec from the OMM fields using the canonical sgp4.omm.initialize
    path, then export TLE lines using sgp4.exporter.export_tle(sat).

    sgp4.exporter.export_tle is available in sgp4 >= 2.22 (installed: 2.27).
    We do NOT reconstruct TLE lines manually or invent checksums.
    """
    sat = Satrec()
    omm_init.initialize(sat, record.raw_omm_fields)
    line1, line2 = sgp4_export_tle(sat)
    return TLEData(line1=line1, line2=line2)


# ── Scenario construction ─────────────────────────────────────────────────────

def _build_scenario(
    protected: OrbitalRecord,
    threat: OrbitalRecord,
    now_utc: datetime,
) -> Scenario:
    """
    Build an in-memory Scenario from two OrbitalRecords.

    epoch_utc is set to the earlier of the two element epochs (conservative).
    Mass and cross-section use nominal defaults (not available in GP data).

    Raises CelesTrakError on TLE construction failure.
    """
    protected_tle = _tle_lines_from_omm(protected)
    threat_tle    = _tle_lines_from_omm(threat)

    # Use the earlier element epoch as the scenario epoch (conservative)
    epoch_utc = min(protected.epoch_utc, threat.epoch_utc)

    scenario_id = f"LIVE-{protected.norad_cat_id}-{threat.norad_cat_id}"

    return Scenario(
        scenario_id=scenario_id,
        scenario_type=ScenarioType.CONJUNCTION,   # will be reclassified after propagation
        description=(
            f"Live CelesTrak GP scenario: "
            f"{protected.object_name} (NORAD {protected.norad_cat_id}) "
            f"vs {threat.object_name} (NORAD {threat.norad_cat_id}). "
            "Screening-level estimate — human operator review required."
        ),
        epoch_utc=epoch_utc,
        our_satellite=SpaceObject(
            object_id=str(protected.norad_cat_id),
            name=protected.object_name,
            tle=protected_tle,
            mass_kg=_DEFAULT_MASS_KG,
            cross_section_m2=_DEFAULT_CROSS_SECTION_M2,
        ),
        threat_object=SpaceObject(
            object_id=str(threat.norad_cat_id),
            name=threat.object_name,
            tle=threat_tle,
            mass_kg=_DEFAULT_MASS_KG,
            cross_section_m2=_DEFAULT_CROSS_SECTION_M2,
        ),
    )


# ── Full analysis pipeline for live scenario ──────────────────────────────────

def _run_analysis(scenario: Scenario, retrieved_at: datetime) -> FullAnalysisResponse:
    """
    Run the deterministic analysis pipeline on a live in-memory scenario.

    Reuses propagate_scenario, get_maneuver_candidates, evaluate_all_candidates,
    and get_granite_advisory — identical to the synthetic scenario pipeline.

    Data quality notes are updated to reflect live CelesTrak data.
    Relative velocity and covariance contract fields are populated.
    """
    try:
        prop = propagate_scenario(scenario)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Propagation failed for live scenario: {exc}",
        ) from exc

    candidates = get_maneuver_candidates()
    try:
        evaluated = evaluate_all_candidates(candidates, scenario, prop.miss_distance_km)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Maneuver evaluation failed: {exc}",
        ) from exc

    evaluation = EvaluationResponse(
        scenario_id=scenario.scenario_id,
        nominal_miss_distance_km=prop.miss_distance_km,
        candidates=evaluated,
        safe_count=sum(1 for c in evaluated if c.is_safe),
        total_count=len(evaluated),
        evaluation_note=(
            "SIMPLIFIED FOR PROTOTYPE: post-maneuver miss distance estimated by "
            "SGP4 state-vector perturbation. "
            "Based on public CelesTrak GP elements — screening-level only."
        ),
    )

    advisory = get_granite_advisory(evaluation)

    epoch_str = scenario.epoch_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return FullAnalysisResponse(
        scenario_id=scenario.scenario_id,
        cached=False,
        analysis_timestamp=datetime.now(tz=timezone.utc),
        nominal_miss_distance_km=prop.miss_distance_km,
        tca_offset_seconds=prop.tca_offset_seconds,
        tca_utc=prop.tca_utc,
        is_conjunction=prop.is_conjunction,
        conjunction_threshold_km=CONJUNCTION_THRESHOLD_KM,
        # Relative velocity — deterministic, same TEME frame, same TCA timestamp
        relative_velocity_km_s=prop.relative_velocity_km_s,
        relative_velocity_vector_km_s=prop.relative_velocity_vector_km_s,
        relative_velocity_frame=prop.relative_velocity_frame,
        relative_velocity_timestamp_utc=prop.tca_utc,
        relative_velocity_basis=prop.relative_velocity_basis,
        # Live GP covariance contract: covariance is NOT available from CelesTrak
        covariance_available=False,
        covariance_source="Unavailable — not supplied by CelesTrak GP data",
        covariance_basis="Public GP orbital elements do not include operational conjunction covariance",
        collision_probability_available=False,
        collision_probability=None,
        risk=_classify_risk(prop.miss_distance_km),
        data_quality=[
            DataQualityNote(
                field="TLE source",
                note=(
                    "Live CelesTrak public GP orbital elements. "
                    "No covariance provided."
                ),
            ),
            DataQualityNote(
                field="Probability of collision",
                note=(
                    "Screening-level estimate. No covariance available from GP data. "
                    "Not suitable for operational conjunction screening."
                ),
            ),
            DataQualityNote(
                field="Miss distance",
                note=(
                    "SGP4 propagation in TEME frame from public GP elements. "
                    "Screening-level only; element age and model simplifications "
                    "limit accuracy."
                ),
            ),
            DataQualityNote(
                field="Element age",
                note=(
                    f"Scenario epoch: {epoch_str}. "
                    "Accuracy degrades with element age."
                ),
            ),
        ],
        orbit_element_age_note=(
            f"Epoch: {epoch_str} (CelesTrak public GP data — not operational tracking)"
        ),
        candidates=evaluated,
        safe_count=sum(1 for c in evaluated if c.is_safe),
        total_count=len(evaluated),
        evaluation_note=evaluation.evaluation_note,
        advisory=advisory,
        risk_basis_label=(
            "Screening-level miss-distance assessment based on public GP elements. "
            "No covariance available from GP elements alone."
        ),
    )


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/live", response_model=LiveAnalysisResponse)
def analyse_live(body: LiveScenarioRequest) -> LiveAnalysisResponse:
    """
    Fetch two objects from CelesTrak, validate them, and run the
    deterministic collision-avoidance analysis pipeline.

    Both objects must be in LEO (mean motion > 11.25 rev/day).
    Returns a LiveAnalysisResponse with full source provenance.

    This route never:
      - overwrites committed synthetic scenarios
      - triggers simulated execution
      - calls Granite automatically
      - triggers robustness or Monte Carlo
    """
    settings = get_settings()
    timeout  = min(15.0, float(getattr(settings, "celestrak_timeout_s", 15.0)))
    now_utc  = datetime.now(tz=timezone.utc)

    # ── Fetch protected satellite ──────────────────────────────────────────────
    try:
        protected = fetch_orbital_record(body.protected_catalog_id, timeout_s=timeout)
    except CelesTrakTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"CelesTrak request timed out for protected object (ID {body.protected_catalog_id}): {exc}",
        ) from exc
    except CelesTrakEmptyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Protected object not found in CelesTrak catalog (ID {body.protected_catalog_id}): {exc}",
        ) from exc
    except CelesTrakError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"CelesTrak fetch failed for protected object (ID {body.protected_catalog_id}): {exc}",
        ) from exc

    # ── Fetch threat object ────────────────────────────────────────────────────
    try:
        threat = fetch_orbital_record(body.threat_catalog_id, timeout_s=timeout)
    except CelesTrakTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"CelesTrak request timed out for threat object (ID {body.threat_catalog_id}): {exc}",
        ) from exc
    except CelesTrakEmptyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Threat object not found in CelesTrak catalog (ID {body.threat_catalog_id}): {exc}",
        ) from exc
    except CelesTrakError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"CelesTrak fetch failed for threat object (ID {body.threat_catalog_id}): {exc}",
        ) from exc

    # ── LEO validation ─────────────────────────────────────────────────────────
    try:
        check_leo(protected)
    except CelesTrakNonLEOError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Protected object is not in LEO: {exc}",
        ) from exc

    try:
        check_leo(threat)
    except CelesTrakNonLEOError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Threat object is not in LEO: {exc}",
        ) from exc

    # ── Build in-memory scenario ───────────────────────────────────────────────
    try:
        scenario = _build_scenario(protected, threat, now_utc)
    except CelesTrakError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to construct scenario from OMM data: {exc}",
        ) from exc

    # ── Register scenario in runtime registry so downstream routes can resolve it
    try:
        register_runtime_scenario(
            scenario,
            source_meta={
                "source": "CelesTrak GP",
                "protected_norad": protected.norad_cat_id,
                "threat_norad": threat.norad_cat_id,
                "retrieved_at_utc": now_utc.isoformat(),
            },
        )
    except (ValueError, TypeError) as exc:
        # ID collision with a committed scenario — extremely unlikely for LIVE- prefix
        raise HTTPException(
            status_code=409,
            detail=f"Scenario ID conflict: {exc}",
        ) from exc

    # ── Run analysis pipeline ──────────────────────────────────────────────────
    try:
        full_analysis = _run_analysis(scenario, now_utc)
    except HTTPException:
        # Analysis failed — clean up registry entry so the ID is not stranded
        delete_runtime_scenario(scenario.scenario_id)
        raise

    # ── Compute element ages ───────────────────────────────────────────────────
    def _age_hours(epoch: datetime) -> float:
        return max(0.0, round((now_utc - epoch).total_seconds() / 3600.0, 2))

    # ── Return with provenance ─────────────────────────────────────────────────
    return LiveAnalysisResponse(
        analysis=full_analysis,
        source_retrieved_at_utc=now_utc,
        protected_object_catalog_id=protected.norad_cat_id,
        threat_object_catalog_id=threat.norad_cat_id,
        protected_object_name=protected.object_name,
        threat_object_name=threat.object_name,
        protected_element_epoch_utc=protected.epoch_utc,
        threat_element_epoch_utc=threat.epoch_utc,
        protected_element_age_hours=_age_hours(protected.epoch_utc),
        threat_element_age_hours=_age_hours(threat.epoch_utc),
    )
