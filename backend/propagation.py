"""
Orbital propagation engine — Phase 2.

Propagates two TLE objects over a search window using sgp4, converts the
output in its native TEME frame, then finds the time and geometry of closest
approach via a two-stage search
(coarse grid → Brent's method refinement).

Both objects are evaluated in TEME at the same instant. Euclidean separation
is invariant under a common orthonormal rotation, so converting both states to
GCRS is unnecessary for this Phase 2 screening calculation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sgp4.api import Satrec, WGS84, jday  # type: ignore[import-untyped]

from schemas.scenario import Scenario, TLEData

# ── Skyfield time-scale (loaded once per process) ─────────────────────────────

# ── Search parameters ─────────────────────────────────────────────────────────
_SEARCH_WINDOW_SECONDS = 86_400        # 24-hour look-ahead
_COARSE_STEP_SECONDS   = 30            # coarse grid step
_REFINE_TOLERANCE_SECONDS = 0.01       # Brent convergence tolerance


# ── Frame conversion ──────────────────────────────────────────────────────────

def _copy_teme_state_km(
    pos_teme_km: np.ndarray,
    vel_teme_km_s: np.ndarray,
    jd_whole: float,
    jd_fraction: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return copies of a TEME position and velocity for relative calculations.

    Both objects are evaluated in TEME at the same instant, so Euclidean
    separation does not require a coordinate-frame conversion.
    """

    # Both objects are compared at the same instant. Their separation and
    # relative velocity are invariant under a common orthonormal rotation, so
    # Phase 2 keeps SGP4's native TEME coordinates.  ``Time.M`` is not a public
    # TEME-to-GCRS transform and must not be used as one.
    del jd_whole, jd_fraction
    return pos_teme_km.copy(), vel_teme_km_s.copy()


# ── Core propagation primitive ────────────────────────────────────────────────

def _propagate_single(sat: Satrec, jd_whole: float, jd_frac: float) -> np.ndarray:
    """
    Propagate a single satellite to a Julian date; return TEME position in km.
    Returns np.full(3, np.nan) on sgp4 error.
    """
    e, pos_teme, vel_teme = sat.sgp4(jd_whole, jd_frac)
    if e != 0:
        return np.full(3, np.nan)

    pos_teme_arr = np.array(pos_teme, dtype=float)
    vel_teme_arr = np.array(vel_teme, dtype=float)

    # Keep both states in the same TEME frame for relative-distance screening.
    pos_teme_copy, _ = _copy_teme_state_km(
        pos_teme_arr, vel_teme_arr, jd_whole, jd_frac
    )
    return pos_teme_copy


def _separation_km(sat_a: Satrec, sat_b: Satrec, jd_whole: float, jd_frac: float) -> float:
    """Euclidean separation between two satellites in TEME, in kilometres."""
    pa = _propagate_single(sat_a, jd_whole, jd_frac)
    pb = _propagate_single(sat_b, jd_whole, jd_frac)
    if np.any(np.isnan(pa)) or np.any(np.isnan(pb)):
        return np.nan
    return float(np.linalg.norm(pa - pb))


# ── TCA search ────────────────────────────────────────────────────────────────

def _jd_from_offset(
    jd_epoch_whole: float,
    jd_epoch_frac: float,
    offset_s: float,
) -> tuple[float, float]:
    """Add an offset in seconds to a Julian date split into whole + fraction."""
    offset_day = offset_s / 86_400.0
    return jd_epoch_whole, jd_epoch_frac + offset_day


def _find_tca(
    sat_a: Satrec,
    sat_b: Satrec,
    jd_start_whole: float,
    jd_start_frac: float,
) -> tuple[float, float]:
    """
    Two-stage TCA search over _SEARCH_WINDOW_SECONDS:
      1. Coarse grid at _COARSE_STEP_SECONDS resolution → identify minimum bracket.
      2. Brent's method refinement within that bracket to _REFINE_TOLERANCE_SECONDS.

    Returns (tca_offset_seconds, miss_distance_km) from jd_start.
    """
    steps = int(_SEARCH_WINDOW_SECONDS / _COARSE_STEP_SECONDS)
    offsets = np.arange(steps + 1, dtype=float) * _COARSE_STEP_SECONDS

    # Coarse sweep
    distances = np.array([
        _separation_km(sat_a, sat_b,
                       jd_start_whole,
                       jd_start_frac + o / 86_400.0)
        for o in offsets
    ])

    # Filter NaN (sgp4 errors)
    valid = ~np.isnan(distances)
    if not valid.any():
        return 0.0, np.nan

    valid_idx = np.where(valid)[0]
    min_idx = valid_idx[np.argmin(distances[valid_idx])]

    # Bracket: one step either side of coarse minimum
    lo = offsets[max(0, min_idx - 1)]
    hi = offsets[min(len(offsets) - 1, min_idx + 1)]

    # Brent's method (manual, no scipy dependency in Phase 2)
    def f(offset_s: float) -> float:
        jw, jf = jd_start_whole, jd_start_frac + offset_s / 86_400.0
        d = _separation_km(sat_a, sat_b, jw, jf)
        return d if not math.isnan(d) else 1e9

    tca_offset = _brent(f, lo, hi, _REFINE_TOLERANCE_SECONDS)
    miss_dist = f(tca_offset)
    return tca_offset, miss_dist


def _brent(f, xa: float, xb: float, tol: float) -> float:
    """
    Minimal Brent's method for a unimodal minimum on [xa, xb].
    Uses golden-section + parabolic interpolation.
    """
    golden = 0.3819660112501051
    x = w = v = xa + golden * (xb - xa)
    fx = fw = fv = f(x)
    d = e = 0.0

    for _ in range(100):
        midpoint = 0.5 * (xa + xb)
        # Absolute time tolerance in seconds. A relative tolerance here would
        # permit hundreds of seconds of error late in the search window.
        tol1 = tol + 1e-10
        tol2 = 2.0 * tol1
        if abs(x - midpoint) <= tol2 - 0.5 * (xb - xa):
            break
        if abs(e) > tol1:
            r = (x - w) * (fx - fv)
            q = (x - v) * (fx - fw)
            p = (x - v) * q - (x - w) * r
            q = 2.0 * (q - r)
            if q > 0:
                p = -p
            q = abs(q)
            r = e
            e = d
            if abs(p) < abs(0.5 * q * r) and p > q * (xa - x) and p < q * (xb - x):
                d = p / q
                u = x + d
                if (u - xa) < tol2 or (xb - u) < tol2:
                    d = math.copysign(tol1, midpoint - x)
            else:
                e = (xa if x >= midpoint else xb) - x
                d = golden * e
        else:
            e = (xa if x >= midpoint else xb) - x
            d = golden * e
        u = x + (math.copysign(tol1, d) if abs(d) < tol1 else d)
        fu = f(u)
        if fu <= fx:
            if u < x:
                xb = x
            else:
                xa = x
            v, fv = w, fw
            w, fw = x, fx
            x, fx = u, fu
        else:
            if u < x:
                xa = u
            else:
                xb = u
            if fu <= fw or w == x:
                v, fv = w, fw
                w, fw = u, fu
            elif fu <= fv or v == x or v == w:
                v, fv = u, fu
    return x


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class PropagationResult:
    """Result of propagating a scenario to find TCA and miss distance."""
    scenario_id: str
    tca_offset_seconds: float          # seconds from epoch_utc
    miss_distance_km: float
    tca_utc: datetime                  # UTC datetime of TCA
    is_conjunction: bool               # True if miss_distance_km < CONJUNCTION_THRESHOLD_KM


CONJUNCTION_THRESHOLD_KM = 1.0        # business rule: miss distance < 1 km is a conjunction


def propagate_scenario(scenario: Scenario) -> PropagationResult:
    """
    Propagate both objects in scenario and return TCA + miss distance.

    Raises ValueError on sgp4 parse errors.
    """
    sat_a = _build_satrec(scenario.our_satellite.tle)
    sat_b = _build_satrec(scenario.threat_object.tle)

    # Convert epoch_utc to Julian date
    epoch = scenario.epoch_utc
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    # SGP4 expects a UTC-based Julian date. Skyfield's ``tt_fraction`` is
    # Terrestrial Time and would shift propagation by roughly one minute.
    second = epoch.second + epoch.microsecond / 1_000_000.0
    jd_whole, jd_frac = jday(
        epoch.year,
        epoch.month,
        epoch.day,
        epoch.hour,
        epoch.minute,
        second,
    )

    tca_offset, miss_dist = _find_tca(sat_a, sat_b, jd_whole, jd_frac)

    # Convert TCA offset back to UTC datetime
    tca_utc = datetime.fromtimestamp(
        epoch.timestamp() + tca_offset, tz=timezone.utc
    )

    if not math.isfinite(miss_dist):
        raise ValueError("SGP4 could not produce a valid state in the search window")

    return PropagationResult(
        scenario_id=scenario.scenario_id,
        tca_offset_seconds=round(tca_offset, 2),
        miss_distance_km=round(miss_dist, 4),
        tca_utc=tca_utc,
        is_conjunction=miss_dist < CONJUNCTION_THRESHOLD_KM,
    )


def _build_satrec(tle: TLEData) -> Satrec:
    """Parse a TLEData into an sgp4 Satrec object."""
    sat = Satrec.twoline2rv(tle.line1, tle.line2, WGS84)
    return sat