# Monte Carlo robustness checker -- Phase 5.
#
# For a given safe maneuver candidate, runs N_TRIALS independent trials.
# Each trial perturbs the TLE epoch position/velocity by Gaussian noise
# at realistic LEO tracking uncertainty levels, then evaluates whether
# the post-maneuver miss distance stays above ROBUST_THRESHOLD_KM.
#
# THE COUNT REPORTED IS THE REAL COUNT FROM REAL TRIALS.
# This number must never be hardcoded, approximated, or estimated.
# Faking this number is the single most damaging thing this prototype
# could ship with.
#
# Uncertainty model (1-sigma, simplified for prototype):
#   - Position uncertainty: 100 m (0.1 km) -- typical LEO radar tracking
#   - Velocity uncertainty: 0.01 m/s -- typical radar Doppler accuracy
#
# SIMPLIFIED FOR PROTOTYPE:
#   - Perturbations are applied directly to the TEME state vector at epoch.
#   - Covariance cross-terms (position-velocity correlation) are ignored.
#   - Atmospheric density uncertainty is not modelled.
#   - These bounds are representative but not derived from a specific
#     conjunction data message (CDM).
from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass

from schemas.scenario import Scenario
from schemas.maneuver import ManeuverCandidate
from maneuver_evaluator import (
    _build_satrec, _apply_delta_v, _find_tca, _TS, SAFE_MISS_DISTANCE_KM
)

# Monte Carlo parameters
N_TRIALS = 1000

# 1-sigma uncertainty bounds (SIMPLIFIED FOR PROTOTYPE -- see module docstring)
POS_SIGMA_KM  = 0.1    # 100 m position uncertainty (1-sigma, each axis)
VEL_SIGMA_KMS = 0.00001  # 0.01 m/s velocity uncertainty (1-sigma, each axis)

# A trial is counted as "robust" if post-maneuver miss > this threshold
ROBUST_THRESHOLD_KM = SAFE_MISS_DISTANCE_KM  # same as safety gate


@dataclass
class MonteCarloResult:
    scenario_id: str
    candidate_id: str
    n_trials: int
    n_robust: int                 # trials where post-maneuver miss > threshold
    robustness_fraction: float    # n_robust / n_trials  (e.g. 0.974)
    robustness_label: str         # e.g. "974/1000"  -- always real count
    threshold_km: float
    pos_sigma_km: float
    vel_sigma_km_s: float
    simplified_note: str


def run_monte_carlo(
    candidate: ManeuverCandidate,
    scenario: Scenario,
    rng_seed: int | None = None,
    n_trials_override: int | None = None,
) -> MonteCarloResult:
    # Run N_TRIALS independent trials.  Each trial:
    #   1. Perturbs our_satellite state vector by Gaussian noise at epoch.
    #   2. Applies the same delta-v as the candidate.
    #   3. Propagates the perturbed post-maneuver orbit against the nominal
    #      threat object orbit to find TCA and miss distance.
    #   4. Counts the trial as robust if miss > ROBUST_THRESHOLD_KM.
    #
    # THE COUNT IS THE REAL COUNT FROM REAL TRIALS -- never hardcoded.

    # n_trials_override allows tests to run fewer trials without changing
    # the production constant.  The real N_TRIALS is always used in production.
    n = n_trials_override if n_trials_override is not None else N_TRIALS
    rng = np.random.default_rng(rng_seed)

    from datetime import timezone
    epoch = scenario.epoch_utc
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    t = _TS.from_datetime(epoch)
    jd_whole = t.whole
    jd_frac  = t.tt_fraction

    sat_b = _build_satrec(scenario.threat_object.tle)   # threat -- not perturbed
    sat_a_nominal = _build_satrec(scenario.our_satellite.tle)

    # Get nominal state vector at epoch
    e0, pos0_teme, vel0_teme = sat_a_nominal.sgp4(jd_whole, jd_frac)
    if e0 != 0:
        raise ValueError(f"Nominal propagation failed at epoch (error {e0})")

    pos0 = np.array(pos0_teme, dtype=float)   # km
    vel0 = np.array(vel0_teme, dtype=float)   # km/s

    n_robust = 0
    failed_trials = 0

    for _ in range(n):
        # Perturb position and velocity (Gaussian, independent axes)
        # SIMPLIFIED FOR PROTOTYPE: diagonal covariance, no cross-terms
        pos_perturb = rng.normal(0.0, POS_SIGMA_KM, size=3)
        vel_perturb = rng.normal(0.0, VEL_SIGMA_KMS, size=3)

        pos_p = pos0 + pos_perturb
        vel_p = vel0 + vel_perturb

        # Build perturbed Satrec from state vector
        from maneuver_evaluator import _satrec_from_rv
        sat_a_perturbed_base = _satrec_from_rv(
            pos_p, vel_p, jd_whole + jd_frac, sat_a_nominal
        )
        if sat_a_perturbed_base is None:
            failed_trials += 1
            continue

        # Apply maneuver delta-v to the perturbed satellite
        sat_a_maneuver = _apply_delta_v(
            sat_a_perturbed_base,
            candidate.delta_v_ms,
            candidate.direction,
            jd_whole,
            jd_frac,
        )
        if sat_a_maneuver is None:
            failed_trials += 1
            continue

        # Find post-maneuver TCA
        try:
            _, post_miss = _find_tca(sat_a_maneuver, sat_b, jd_whole, jd_frac)
        except Exception:
            failed_trials += 1
            continue

        if not math.isnan(post_miss) and post_miss > ROBUST_THRESHOLD_KM:
            n_robust += 1

    # The number reported is the real count from real trials.
    return MonteCarloResult(
        scenario_id=scenario.scenario_id,
        candidate_id=candidate.candidate_id,
        n_trials=n,
        n_robust=n_robust,
        robustness_fraction=round(n_robust / n, 4),
        robustness_label=f"{n_robust}/{n}",
        threshold_km=ROBUST_THRESHOLD_KM,
        pos_sigma_km=POS_SIGMA_KM,
        vel_sigma_km_s=VEL_SIGMA_KMS,
        simplified_note=(
            "SIMPLIFIED FOR PROTOTYPE: perturbation model uses diagonal "
            "position/velocity covariance only (100m pos, 0.01 m/s vel). "
            "Cross-terms and atmospheric density uncertainty are not modelled. "
            "Bounds are representative, not derived from a CDM."
        ),
    )
