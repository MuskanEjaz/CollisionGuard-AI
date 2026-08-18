"""
GET /scenarios and GET /scenarios/{scenario_id} endpoints.

Phase 1: loads scenarios from committed JSON files under data/scenarios/.
Phase 2: the same loader function will be reused; propagation fields will
         be populated by the engine before the response is returned.
"""
import json
import pathlib
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from schemas.scenario import Scenario, ScenarioListResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

# Resolve path relative to this file so the app works from any cwd
_DATA_DIR = pathlib.Path(__file__).parent.parent / "data" / "scenarios"


@lru_cache(maxsize=1)
def _load_scenarios() -> dict[str, Scenario]:
    """
    Load and schema-validate all scenario JSON files at first call.
    Returns a dict keyed by scenario_id.
    """
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
