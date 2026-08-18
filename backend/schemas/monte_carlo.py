# Monte Carlo response schema -- Phase 5
from pydantic import BaseModel


class MonteCarloResponse(BaseModel):
    scenario_id: str
    candidate_id: str
    n_trials: int
    n_robust: int
    robustness_fraction: float
    robustness_label: str         # e.g. "974/1000" -- real count, never hardcoded
    threshold_km: float
    pos_sigma_km: float
    vel_sigma_km_s: float
    simplified_note: str
