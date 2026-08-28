# Granite advisory endpoint -- Phase 6.
# POST /scenarios/{scenario_id}/advise
#
# Pipeline:
#   1. Load scenario
#   2. Propagate (get nominal miss distance)
#   3. Evaluate all candidates (deterministic safety gate)
#   4. Pass only safe candidates to Granite
#   5. Validate Granite output against backend values
#   6. Return advisory response (source="granite" or "deterministic_fallback")
from fastapi import APIRouter, HTTPException
from schemas.granite import GraniteAdvisoryResponse
from granite_client import get_granite_advisory
from maneuver_candidates import get_maneuver_candidates
from maneuver_evaluator import evaluate_all_candidates
from propagation import propagate_scenario
from scenario_registry import resolve_scenario
from schemas.maneuver import EvaluationResponse

router = APIRouter(prefix="/scenarios", tags=["granite"])


@router.post("/{scenario_id}/advise", response_model=GraniteAdvisoryResponse)
def advise(scenario_id: str) -> GraniteAdvisoryResponse:
    # Step 1: validate scenario exists (committed or live runtime)
    scenario = resolve_scenario(scenario_id)

    # Step 2: propagate
    try:
        prop_result = propagate_scenario(scenario)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Propagation failed: {exc}") from exc

    # Step 3: evaluate -- SAFETY GATE (deterministic, before Granite)
    candidates = get_maneuver_candidates()
    try:
        evaluated = evaluate_all_candidates(
            candidates, scenario, prop_result.miss_distance_km
        )
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Evaluation failed: {exc}") from exc

    evaluation = EvaluationResponse(
        scenario_id=scenario_id,
        nominal_miss_distance_km=prop_result.miss_distance_km,
        candidates=evaluated,
        safe_count=sum(1 for c in evaluated if c.is_safe),
        total_count=len(evaluated),
        evaluation_note="",
    )

    # Step 4+5: Granite advisory (safe candidates only, values validated)
    advisory = get_granite_advisory(evaluation)
    return advisory
