"""
GET /scenarios, GET /scenarios/{scenario_id},
POST /scenarios/{scenario_id}/propagate

Phase 1: loads scenarios from committed JSON files.
Phase 2: adds the /propagate endpoint which runs sgp4 + skyfield propagation
         and returns TCA, miss distance, and conjunction flag.
"""
import json
import pathlib
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from schemas.scenario import PropagationResponse, Scenario, ScenarioListResponse
from propagation import propagate_scenario, CONJUNCTION_THRESHOLD_KM

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data" / "scenarios"


@lru_cache(maxsize=1)
def _load_scenarios() -> dict[str, Scenario]:
    """Load and schema-validate all scenario JSON files at first call."""
    scenarios: dict[str, Scenario] = {}
    for json_file in sorted(_DATA_DIR.glob("*.json")):
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        scenario = Scenario.model_validate(raw)
        scenarios[scenario.scenario_id] = scenario
    return scenarios


@router.get("", response_model=ScenarioListResponse)
def list_scenarios() -> ScenarioListResponse:
    """Return all available scenarios."""
    scenarios = list(_load_scenarios().values())
    return ScenarioListResponse(scenarios=scenarios, count=len(scenarios))


@router.get("/{scenario_id}", response_model=Scenario)
def get_scenario(scenario_id: str) -> Scenario:
    """Return a single scenario by ID, or 404 if not found."""
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    return scenarios[scenario_id]


@router.post("/{scenario_id}/propagate", response_model=PropagationResponse)
def propagate(scenario_id: str) -> PropagationResponse:
    """
    Propagate both objects in the scenario over a 24-hour window and return
    the time and geometry of closest approach.

    This is an on-demand endpoint; propagation is not performed on GET.
    """
    scenarios = _load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    try:
        result = propagate_scenario(scenarios[scenario_id])
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Propagation failed: {exc}",
        ) from exc

    return PropagationResponse(
        scenario_id=result.scenario_id,
        miss_distance_km=result.miss_distance_km,
        tca_offset_seconds=result.tca_offset_seconds,
        tca_utc=result.tca_utc,
        is_conjunction=result.is_conjunction,
        conjunction_threshold_km=CONJUNCTION_THRESHOLD_KM,
    )
