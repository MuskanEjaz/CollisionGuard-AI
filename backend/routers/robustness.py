# Monte Carlo endpoint -- Phase 5
# POST /scenarios/{scenario_id}/maneuvers/{candidate_id}/robustness
from fastapi import APIRouter, HTTPException
from schemas.monte_carlo import MonteCarloResponse
from monte_carlo import run_monte_carlo, N_TRIALS
from maneuver_candidates import get_maneuver_candidates
from maneuver_evaluator import evaluate_candidate
from propagation import propagate_scenario
from routers.scenarios import _load_scenarios

router = APIRouter(prefix="/scenarios", tags=["monte_carlo"])


@router.post(
    "/{scenario_id}/maneuvers/{candidate_id}/robustness",
    response_model=MonteCarloResponse,
)
def robustness_check(scenario_id: str, candidate_id: str) -> MonteCarloResponse:
    # Phase 5: run Monte Carlo robustness check for a single safe candidate.
    # Returns the real count of trials passing the miss-distance threshold.
    # This count is NEVER hardcoded -- it comes from real trial execution.
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(status_code=404,
                            detail=f"Scenario '{scenario_id}' not found.")
    scenario = scenarios[scenario_id]

    candidates = {c.candidate_id: c for c in get_maneuver_candidates()}
    if candidate_id not in candidates:
        raise HTTPException(status_code=404,
                            detail=f"Candidate '{candidate_id}' not found.")
    candidate = candidates[candidate_id]

    # Must evaluate candidate safety first
    try:
        prop_result = propagate_scenario(scenario)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Propagation failed: {exc}") from exc

    evaluated = evaluate_candidate(candidate, scenario, prop_result.miss_distance_km)
    if not evaluated.is_safe:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Candidate '{candidate_id}' failed safety evaluation: "
                f"{evaluated.safety_rejection_reason}. "
                f"Monte Carlo is only run on safe candidates."
            ),
        )

    try:
        result = run_monte_carlo(evaluated, scenario)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Monte Carlo failed: {exc}") from exc

    return MonteCarloResponse(
        scenario_id=result.scenario_id,
        candidate_id=result.candidate_id,
        n_trials=result.n_trials,
        n_robust=result.n_robust,
        robustness_fraction=result.robustness_fraction,
        robustness_label=result.robustness_label,
        threshold_km=result.threshold_km,
        pos_sigma_km=result.pos_sigma_km,
        vel_sigma_km_s=result.vel_sigma_km_s,
        simplified_note=result.simplified_note,
    )
