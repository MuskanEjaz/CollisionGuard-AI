# Maneuver routes -- Phase 3 (list) + Phase 4 (evaluate)
from fastapi import APIRouter, HTTPException
from schemas.maneuver import ManeuverCandidateListResponse, EvaluationResponse
from maneuver_candidates import get_maneuver_candidates
from maneuver_evaluator import evaluate_all_candidates
from propagation import propagate_scenario
from routers.scenarios import _load_scenarios

router = APIRouter(prefix="/scenarios", tags=["maneuvers"])


@router.get("/{scenario_id}/maneuvers", response_model=ManeuverCandidateListResponse)
def list_maneuver_candidates(scenario_id: str) -> ManeuverCandidateListResponse:
    # Phase 3: return unevaluated candidates
    if scenario_id not in _load_scenarios():
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")
    candidates = get_maneuver_candidates()
    return ManeuverCandidateListResponse(
        scenario_id=scenario_id,
        candidates=candidates,
        count=len(candidates),
    )


@router.post("/{scenario_id}/evaluate", response_model=EvaluationResponse)
def evaluate_maneuvers(scenario_id: str) -> EvaluationResponse:
    # Phase 4: propagate scenario, then evaluate all candidates.
    # Only candidates marked is_safe=True may be passed to Granite (Phase 6).
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")
    scenario = scenarios[scenario_id]

    try:
        prop_result = propagate_scenario(scenario)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Propagation failed: {exc}") from exc

    nominal_miss = prop_result.miss_distance_km
    candidates = get_maneuver_candidates()

    try:
        evaluated = evaluate_all_candidates(candidates, scenario, nominal_miss)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Evaluation failed: {exc}") from exc

    safe_count = sum(1 for c in evaluated if c.is_safe)

    return EvaluationResponse(
        scenario_id=scenario_id,
        nominal_miss_distance_km=round(nominal_miss, 4),
        candidates=evaluated,
        safe_count=safe_count,
        total_count=len(evaluated),
        evaluation_note=(
            "SIMPLIFIED FOR PROTOTYPE: post-maneuver miss distance is estimated "
            "by two-body state-vector perturbation, not optimal targeting. "
            "Baseline score uses linear weighting, not multi-objective optimisation."
        ),
    )
