# Analysis endpoint -- Phase 7.
# POST /scenarios/{scenario_id}/analyse
#
# Returns the full FullAnalysisResponse: propagation + evaluation + Granite
# advisory in one call, with in-memory caching to avoid ~20s re-computation.
#
# Cache behaviour:
#   - Hit: returns cached result with cached=True, no recomputation.
#   - Miss: runs full pipeline, stores result, returns with cached=False.
#   - Invalidate: DELETE /scenarios/{scenario_id}/cache
#   - Stats: GET /cache/stats
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from schemas.analysis import (
    FullAnalysisResponse, RiskClassification, DataQualityNote,
    ApprovalRequest, ExecutionApprovedResponse, ExecutionStatus,
    IncidentReport,
)
from schemas.maneuver import EvaluationResponse
from granite_client import get_granite_advisory
from maneuver_candidates import get_maneuver_candidates
from maneuver_evaluator import evaluate_all_candidates
from propagation import propagate_scenario, CONJUNCTION_THRESHOLD_KM
from routers.scenarios import _load_scenarios
from analysis_cache import get_cached, set_cached, invalidate, cache_stats

router = APIRouter(tags=["analysis"])

# In-process approval store: {scenario_id: candidate_id}
# Only one pending approval per scenario at a time.
_PENDING_APPROVALS: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _build_analysis(scenario_id: str) -> FullAnalysisResponse:
    # Full pipeline: propagate -> evaluate -> advise (Granite or fallback).
    # Called only on cache miss.
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")
    scenario = scenarios[scenario_id]

    try:
        prop = propagate_scenario(scenario)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Propagation failed: {exc}") from exc

    candidates = get_maneuver_candidates()
    try:
        evaluated = evaluate_all_candidates(candidates, scenario,
                                            prop.miss_distance_km)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Evaluation failed: {exc}") from exc

    evaluation = EvaluationResponse(
        scenario_id=scenario_id,
        nominal_miss_distance_km=prop.miss_distance_km,
        candidates=evaluated,
        safe_count=sum(1 for c in evaluated if c.is_safe),
        total_count=len(evaluated),
        evaluation_note=(
            "SIMPLIFIED FOR PROTOTYPE: post-maneuver miss distance is estimated "
            "by two-body state-vector perturbation, not optimal targeting."
        ),
    )

    advisory = get_granite_advisory(evaluation)

    epoch_str = scenario.epoch_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return FullAnalysisResponse(
        scenario_id=scenario_id,
        cached=False,
        analysis_timestamp=datetime.now(tz=timezone.utc),
        nominal_miss_distance_km=prop.miss_distance_km,
        tca_offset_seconds=prop.tca_offset_seconds,
        tca_utc=prop.tca_utc,
        is_conjunction=prop.is_conjunction,
        conjunction_threshold_km=CONJUNCTION_THRESHOLD_KM,
        risk=_classify_risk(prop.miss_distance_km),
        data_quality=[
            DataQualityNote(
                field="TLE source",
                note="Synthetic scenario (committed fallback data -- not live CelesTrak)",
            ),
            DataQualityNote(
                field="Probability of collision",
                note=(
                    "Demonstration Pc based on synthetic covariance. "
                    "Screening-level estimate only."
                ),
            ),
            DataQualityNote(
                field="Miss distance",
                note=(
                    "Two-body propagation in TEME frame. "
                    "J2, drag, and solar-pressure perturbations not modelled."
                ),
            ),
        ],
        orbit_element_age_note=f"Epoch: {epoch_str} (synthetic -- not real telemetry)",
        candidates=evaluated,
        safe_count=sum(1 for c in evaluated if c.is_safe),
        total_count=len(evaluated),
        evaluation_note=evaluation.evaluation_note,
        advisory=advisory,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/scenarios/{scenario_id}/analyse",
             response_model=FullAnalysisResponse)
def analyse(scenario_id: str) -> FullAnalysisResponse:
    # Check cache first
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")
    scenario = scenarios[scenario_id]

    cached_result, hit = get_cached(scenario_id, scenario)
    if hit:
        # Return cached copy with cached=True flag
        cached_result.cached = True
        return cached_result

    result = _build_analysis(scenario_id)
    set_cached(scenario_id, scenario, result)
    return result


@router.delete("/scenarios/{scenario_id}/cache")
def invalidate_cache(scenario_id: str) -> dict:
    n = invalidate(scenario_id)
    return {"scenario_id": scenario_id, "entries_removed": n}


@router.get("/cache/stats")
def get_cache_stats() -> dict:
    return cache_stats()


# ---------------------------------------------------------------------------
# Execution endpoints
# ---------------------------------------------------------------------------

@router.post("/scenarios/{scenario_id}/approve",
             response_model=ExecutionApprovedResponse)
def approve_execution(scenario_id: str, body: ApprovalRequest) -> ExecutionApprovedResponse:
    # SAFETY GATE: validate the candidate is safe before recording approval.
    # This endpoint only records intent -- simulated execution is in /execute.
    if body.scenario_id != scenario_id:
        raise HTTPException(status_code=422,
                            detail="scenario_id in URL and body must match.")

    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")
    scenario = scenarios[scenario_id]

    # Re-evaluate to confirm the candidate is still safe (never trust the UI)
    candidates = {c.candidate_id: c for c in get_maneuver_candidates()}
    if body.candidate_id not in candidates:
        raise HTTPException(status_code=404,
                            detail=f"Candidate '{body.candidate_id}' not found.")

    cached_result, _ = get_cached(scenario_id, scenario)
    if cached_result:
        # Find candidate in cached evaluation
        cand_map = {c.candidate_id: c for c in cached_result.candidates}
    else:
        # Re-evaluate (fallback if cache expired)
        try:
            prop = propagate_scenario(scenario)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Propagation failed: {exc}")
        raw_candidates = get_maneuver_candidates()
        evaluated = evaluate_all_candidates(raw_candidates, scenario,
                                            prop.miss_distance_km)
        cand_map = {c.candidate_id: c for c in evaluated}

    candidate = cand_map.get(body.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404,
                            detail=f"Candidate '{body.candidate_id}' not found in evaluation.")

    # SAFETY GATE: unsafe candidates are rejected here, not at the UI level
    if not candidate.is_safe:
        return ExecutionApprovedResponse(
            execution=ExecutionStatus(
                scenario_id=scenario_id,
                candidate_id=body.candidate_id,
                operator_id=body.operator_id,
                status="rejected",
                message=(
                    f"Safety gate rejected candidate: "
                    f"{candidate.safety_rejection_reason}"
                ),
            ),
            safety_gate_passed=False,
            rejection_reason=candidate.safety_rejection_reason,
        )

    # Record pending approval
    _PENDING_APPROVALS[scenario_id] = body.candidate_id

    return ExecutionApprovedResponse(
        execution=ExecutionStatus(
            scenario_id=scenario_id,
            candidate_id=body.candidate_id,
            operator_id=body.operator_id,
            status="approved",
            message=(
                f"Candidate {body.candidate_id} approved by operator "
                f"{body.operator_id}. Awaiting simulated execution."
            ),
        ),
        safety_gate_passed=True,
    )


@router.post("/scenarios/{scenario_id}/execute",
             response_model=ExecutionStatus)
def execute(scenario_id: str, body: ApprovalRequest) -> ExecutionStatus:
    # SAFETY GATE: only execute if an approval is pending for this exact candidate.
    if _PENDING_APPROVALS.get(scenario_id) != body.candidate_id:
        raise HTTPException(
            status_code=403,
            detail=(
                f"No pending approval for candidate '{body.candidate_id}'. "
                f"Call /approve first."
            ),
        )

    # Clear the pending approval (one-use)
    del _PENDING_APPROVALS[scenario_id]

    scenarios = _load_scenarios()
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")

    candidates = {c.candidate_id: c for c in get_maneuver_candidates()}
    candidate = candidates.get(body.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404,
                            detail=f"Candidate '{body.candidate_id}' not found.")

    # Final safety check -- belt-and-suspenders
    cached_result, _ = get_cached(scenario_id, scenario)
    if cached_result:
        cand_map = {c.candidate_id: c for c in cached_result.candidates}
        evaluated_candidate = cand_map.get(body.candidate_id, candidate)
    else:
        evaluated_candidate = candidate

    if evaluated_candidate.is_safe is False:
        raise HTTPException(
            status_code=422,
            detail=f"Safety gate: candidate '{body.candidate_id}' is not safe.",
        )

    # Simulated execution: report what the maneuver would produce
    # Values come from the backend-evaluated candidate, never from the UI
    return ExecutionStatus(
        scenario_id=scenario_id,
        candidate_id=body.candidate_id,
        operator_id=body.operator_id,
        simulated=True,
        status="complete",
        message=(
            f"SIMULATED EXECUTION COMPLETE. "
            f"Maneuver {body.candidate_id} applied. "
            f"This is a prototype simulation -- not flight software."
        ),
        post_maneuver_miss_distance_km=evaluated_candidate.post_maneuver_miss_distance_km,
        delta_v_applied_ms=evaluated_candidate.delta_v_ms,
        fuel_consumed_kg=evaluated_candidate.fuel_cost_kg,
        executed_at=datetime.now(tz=timezone.utc),
    )


@router.post("/scenarios/{scenario_id}/incident-report",
             response_model=IncidentReport)
def incident_report(scenario_id: str, body: ApprovalRequest) -> IncidentReport:
    # Generate an incident report using Granite if available, else template.
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")

    cached_result, _ = get_cached(scenario_id, scenarios[scenario_id])
    advisory_source = "deterministic_template"
    report_text = _deterministic_report(scenario_id, body.candidate_id, cached_result)

    # If Granite was used for the advisory, attempt a Granite-generated report
    if cached_result and cached_result.advisory.source == "granite":
        granite_text = _try_granite_report(scenario_id, body.candidate_id, cached_result)
        if granite_text:
            report_text = granite_text
            advisory_source = "granite"

    return IncidentReport(
        scenario_id=scenario_id,
        candidate_id=body.candidate_id,
        generated_by=advisory_source,
        report_text=report_text,
        simulated=True,
    )


def _deterministic_report(scenario_id: str, candidate_id: str, analysis) -> str:
    if analysis is None:
        return (
            f"SIMULATED INCIDENT REPORT\n"
            f"Scenario: {scenario_id} | Candidate: {candidate_id}\n"
            f"Analysis data not available -- run /analyse first.\n"
            f"[SIMULATED INCIDENT REPORT -- not flight documentation]"
        )
    cand = next((c for c in analysis.candidates
                 if c.candidate_id == candidate_id), None)
    cand_str = (
        f"Candidate {candidate_id}: "
        f"delta-v {cand.delta_v_ms:.2f} m/s, "
        f"post-maneuver miss {cand.post_maneuver_miss_distance_km:.3f} km, "
        f"fuel {cand.fuel_cost_kg:.4f} kg"
    ) if cand else f"Candidate {candidate_id}: details unavailable"
    return (
        f"SIMULATED INCIDENT REPORT\n"
        f"================================\n"
        f"Scenario          : {scenario_id}\n"
        f"Risk level        : {analysis.risk.level}\n"
        f"Nominal miss dist : {analysis.nominal_miss_distance_km:.4f} km\n"
        f"TCA               : {analysis.tca_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"Selected maneuver : {cand_str}\n"
        f"Advisory source   : {analysis.advisory.source}\n"
        f"Data quality      : {analysis.data_quality[0].note}\n"
        f"--------------------------------\n"
        f"{analysis.simulation_label}\n"
        f"{analysis.prototype_label}\n"
        f"[SIMULATED INCIDENT REPORT -- not flight documentation]"
    )


def _try_granite_report(scenario_id: str, candidate_id: str, analysis) -> str | None:
    # Attempt to generate a Granite narrative for the incident report.
    # Returns None on any failure -- caller falls back to deterministic template.
    from granite_client import _has_valid_config, _call_granite
    valid, _ = _has_valid_config()
    if not valid:
        return None
    try:
        from config import get_settings
        from ibm_watsonx_ai import Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        s = get_settings()
        cands = [c for c in analysis.candidates if c.candidate_id == candidate_id]
        if not cands:
            return None
        cand = cands[0]
        prompt = (
            f"Write a brief 3-sentence incident report for a simulated "
            f"collision-avoidance maneuver.\n"
            f"Scenario: {scenario_id}, Risk: {analysis.risk.level}, "
            f"Nominal miss: {analysis.nominal_miss_distance_km:.4f} km, "
            f"Maneuver: {cand.label}, delta-v: {cand.delta_v_ms:.2f} m/s, "
            f"Post-maneuver miss: {cand.post_maneuver_miss_distance_km:.3f} km.\n"
            f"State that this is a simulation and not flight software."
        )
        creds = Credentials(url=s.watsonx_url, api_key=s.watsonx_apikey)
        model = ModelInference(
            model_id=s.watsonx_model_id,
            credentials=creds,
            project_id=s.watsonx_project_id,
        )
        text = model.generate_text(
            prompt=prompt,
            params={"max_new_tokens": 200, "temperature": 0.3},
        )
        return str(text) if text else None
    except Exception:
        return None
