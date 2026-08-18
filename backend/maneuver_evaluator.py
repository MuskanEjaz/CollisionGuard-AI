# Maneuver safety evaluator -- Phase 4.
#
# For each maneuver candidate, computes:
#   1. Post-maneuver miss distance (via re-propagation with velocity perturbation)
#   2. Fuel cost (Tsiolkovsky rocket equation, simplified)
#   3. Safety constraints (miss distance, delta-v budget, fuel budget)
#   4. Baseline score (deterministic, 0..1 -- higher is better)
#
# SAFETY ARCHITECTURE (enforced here):
#   The evaluator marks each candidate is_safe=True or is_safe=False.
#   Only candidates marked is_safe=True may be passed to Granite (Phase 6).
#   Granite cannot override this determination.
#
# SIMPLIFIED FOR PROTOTYPE:
#   Post-maneuver miss distance is estimated by applying the delta-v as a
#   direct velocity perturbation in the propagation frame at the epoch, then
#   re-running the TCA search using a new Satrec built from the perturbed
#   two-body orbital elements.  This ignores finite burn arcs, drag changes,
#   and J2 drift.  Labelled in the /evaluate response "evaluation_note".
from __future__ import annotations

import math
import numpy as np
from sgp4.api import Satrec, WGS84, jday
from skyfield.api import load

from schemas.scenario import Scenario
from schemas.maneuver import ManeuverCandidate, ManeuverDirection
from propagation import (
    _build_satrec, _find_tca, _TS, CONJUNCTION_THRESHOLD_KM,
)

# Safety thresholds
SAFE_MISS_DISTANCE_KM = 5.0     # post-maneuver miss distance must exceed this
MAX_DELTA_V_MS        = 3.0     # absolute delta-v budget limit (m/s)
MAX_FUEL_KG           = 5.0     # fuel budget limit (kg)
MIN_MISS_IMPROVEMENT  = 1.0     # must improve miss distance by at least 1 km

# Satellite specific impulse -- SIMPLIFIED FOR PROTOTYPE: fixed Isp
ISP_S = 220.0                   # typical cold-gas thruster Isp (s)
G0    = 9.80665                 # m/s^2


def _tsiolkovsky_fuel(delta_v_abs_ms: float, dry_mass_kg: float) -> float:
    # Tsiolkovsky: m_fuel = m_dry * (exp(dv / Ve) - 1)
    exhaust_v = ISP_S * G0
    return dry_mass_kg * (math.exp(delta_v_abs_ms / exhaust_v) - 1.0)


def _tle_checksum(line: str) -> int:
    total = 0
    for ch in line[:-1]:
        if ch.isdigit():
            total += int(ch)
        elif ch == "-":
            total += 1
    return total % 10


def _satrec_from_rv(
    pos_km: np.ndarray,
    vel_km_s: np.ndarray,
    jd_epoch: float,
    original_sat: Satrec,
) -> Satrec | None:
    # Build a new Satrec from a state vector (pos in km, vel in km/s, TEME)
    # at the given Julian date, by deriving two-body Keplerian elements and
    # constructing a synthetic TLE.
    #
    # SIMPLIFIED FOR PROTOTYPE: uses two-body Keplerian elements only.
    # Ignores J2, drag, and other perturbations.
    MU = 398600.4418    # km^3/s^2

    r = np.linalg.norm(pos_km)
    v = np.linalg.norm(vel_km_s)

    energy = 0.5 * v**2 - MU / r
    if energy >= 0:
        return None   # not elliptic
    sma_km = -MU / (2.0 * energy)
    if sma_km < 6378.137 + 100:
        return None   # below 100 km altitude

    h_vec = np.cross(pos_km, vel_km_s)
    h = np.linalg.norm(h_vec)
    e_vec = np.cross(vel_km_s, h_vec) / MU - pos_km / r
    ecc = float(np.linalg.norm(e_vec))
    ecc = min(ecc, 0.99)

    if h > 1e-12:
        inc_rad = math.acos(max(-1.0, min(1.0, h_vec[2] / h)))
    else:
        inc_rad = original_sat.inclo

    # Node vector
    K = np.array([0.0, 0.0, 1.0])
    N = np.cross(K, h_vec)
    N_mag = np.linalg.norm(N)

    if N_mag > 1e-12:
        raan_rad = math.acos(max(-1.0, min(1.0, N[0] / N_mag)))
        if N[1] < 0:
            raan_rad = 2 * math.pi - raan_rad
    else:
        raan_rad = float(original_sat.nodeo)

    if N_mag > 1e-12 and ecc > 1e-10:
        e_unit = e_vec / ecc
        N_unit = N / N_mag
        argp_rad = math.acos(max(-1.0, min(1.0, np.dot(N_unit, e_unit))))
        if e_vec[2] < 0:
            argp_rad = 2 * math.pi - argp_rad
    else:
        argp_rad = float(original_sat.argpo)

    # True anomaly
    if ecc > 1e-10:
        e_unit = e_vec / ecc
        cos_nu = np.dot(e_unit, pos_km / r)
        cos_nu = max(-1.0, min(1.0, cos_nu))
        nu = math.acos(cos_nu)
        if np.dot(pos_km, vel_km_s) < 0:
            nu = 2 * math.pi - nu
        E = math.atan2(math.sqrt(1 - ecc**2) * math.sin(nu),
                       ecc + math.cos(nu))
        M0 = (E - ecc * math.sin(E)) % (2 * math.pi)
    else:
        M0 = float(original_sat.mo)

    # Mean motion in rev/day
    n_rad_s = math.sqrt(MU / sma_km**3)
    n_rev_day = n_rad_s * 86400.0 / (2.0 * math.pi)

    # Build TLE strings from these elements
    # BSTAR (drag) copied from original satellite
    bstar = original_sat.bstar

    # TLE epoch: fractional year format (YYDDD.DDDDDDDD)
    # jd_epoch is a Julian date
    # Convert to year and day-of-year
    import datetime
    jd_ref = jd_epoch
    # Julian date to calendar date
    a = int(jd_ref + 0.5) + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    yr2 = year % 100

    dt = datetime.datetime(year, month, day, 0, 0, 0)
    doy = dt.timetuple().tm_yday
    frac_day = (jd_ref + 0.5) - int(jd_ref + 0.5)
    tle_epoch = f"{yr2:02d}{doy:03d}{doy + frac_day - doy:.8f}"[:-1]
    tle_epoch = f"{yr2:02d}{(doy + frac_day - 1):.8f}"
    epoch_str = f"{yr2:02d}{doy + frac_day - 1:012.8f}"

    # Format TLE line 1 and 2
    # We reuse the original satellite catalog number and designator
    cat_no = str(original_sat.satnum).rjust(5)
    bstar_exp = 0
    bstar_mant = bstar
    if bstar_mant != 0:
        while abs(bstar_mant) < 0.1 and bstar_exp > -9:
            bstar_mant *= 10
            bstar_exp -= 1
        while abs(bstar_mant) >= 1.0:
            bstar_mant /= 10
            bstar_exp += 1
    bstar_str = f"{bstar_mant:+.4f}{bstar_exp:+01d}"
    bstar_str = bstar_str.replace("+0.", " ").replace("-0.", "-")
    # sgp4 twoline2rv is robust to imprecise TLE format --
    # use a simplified construction that sgp4 can parse
    # This is internal and only used for post-maneuver propagation estimate.

    ecc_str = f"{ecc:.7f}"[2:]   # strip "0."

    line2 = (
        f"2 {cat_no} "
        f"{math.degrees(inc_rad):8.4f} "
        f"{math.degrees(raan_rad) % 360:8.4f} "
        f"{ecc_str} "
        f"{math.degrees(argp_rad) % 360:8.4f} "
        f"{math.degrees(M0) % 360:8.4f} "
        f"{n_rev_day:11.8f}"
        f"00001"
    )
    # Pad/trim to 68 chars and add checksum
    line2 = line2[:68].ljust(68)
    line2 = line2 + str(_tle_checksum(line2 + "0"))

    line1 = (
        f"1 {cat_no}U 00001A   "
        f"{epoch_str[:14]} "
        f" .00000000  00000-0  00000-0 0  9990"
    )
    line1 = line1[:68].ljust(68)
    line1 = line1 + str(_tle_checksum(line1 + "0"))

    try:
        new_sat = Satrec.twoline2rv(line1, line2, WGS84)
        if new_sat.error != 0:
            return None
        return new_sat
    except Exception:
        return None


def _apply_delta_v(
    original_sat: Satrec,
    delta_v_ms: float,
    direction: ManeuverDirection,
    jd_whole: float,
    jd_frac: float,
) -> Satrec | None:
    # Apply velocity impulse and return perturbed Satrec, or None on failure.
    e, pos_teme, vel_teme = original_sat.sgp4(jd_whole, jd_frac)
    if e != 0:
        return None

    pos = np.array(pos_teme, dtype=float)
    vel = np.array(vel_teme, dtype=float)
    vel_ms = vel * 1000.0

    vel_unit = vel / np.linalg.norm(vel)
    pos_unit = pos / np.linalg.norm(pos)
    normal_unit = np.cross(pos_unit, vel_unit)
    nm = np.linalg.norm(normal_unit)
    if nm > 1e-12:
        normal_unit /= nm

    if direction == ManeuverDirection.PROGRADE:
        dv_vec = delta_v_ms * vel_unit
    elif direction == ManeuverDirection.RETROGRADE:
        dv_vec = abs(delta_v_ms) * (-vel_unit)
    elif direction == ManeuverDirection.RADIAL_OUT:
        dv_vec = abs(delta_v_ms) * pos_unit
    else:  # NORMAL
        dv_vec = abs(delta_v_ms) * normal_unit

    new_vel_km_s = (vel_ms + dv_vec) / 1000.0
    jd_epoch = jd_whole + jd_frac
    return _satrec_from_rv(pos, new_vel_km_s, jd_epoch, original_sat)


def evaluate_candidate(
    candidate: ManeuverCandidate,
    scenario: Scenario,
    nominal_miss_km: float,
) -> ManeuverCandidate:
    # Evaluate a single candidate against safety constraints.
    # This function is deterministic -- Granite may not alter its output.
    import copy
    c = candidate.model_copy(deep=True)

    from datetime import timezone
    epoch = scenario.epoch_utc
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    t = _TS.from_datetime(epoch)
    jd_whole = t.whole
    jd_frac  = t.tt_fraction

    sat_a_orig = _build_satrec(scenario.our_satellite.tle)
    sat_b      = _build_satrec(scenario.threat_object.tle)

    dv_abs = abs(c.delta_v_ms)

    # Constraint: delta-v budget
    if dv_abs > MAX_DELTA_V_MS:
        c.is_safe = False
        c.safety_rejection_reason = (
            f"delta-v {dv_abs:.2f} m/s exceeds budget {MAX_DELTA_V_MS} m/s"
        )
        c.fuel_cost_kg = None
        c.post_maneuver_miss_distance_km = None
        c.baseline_score = 0.0
        return c

    # Fuel cost
    fuel_kg = _tsiolkovsky_fuel(dv_abs, scenario.our_satellite.mass_kg)
    c.fuel_cost_kg = round(fuel_kg, 4)

    # Constraint: fuel budget
    if fuel_kg > MAX_FUEL_KG:
        c.is_safe = False
        c.safety_rejection_reason = (
            f"fuel cost {fuel_kg:.3f} kg exceeds budget {MAX_FUEL_KG} kg"
        )
        c.post_maneuver_miss_distance_km = None
        c.baseline_score = 0.0
        return c

    # Apply delta-v perturbation
    sat_a_perturbed = _apply_delta_v(
        sat_a_orig, c.delta_v_ms, c.direction, jd_whole, jd_frac
    )
    if sat_a_perturbed is None:
        c.is_safe = False
        c.safety_rejection_reason = "Post-maneuver orbit construction failed"
        c.post_maneuver_miss_distance_km = None
        c.baseline_score = 0.0
        return c

    # Post-maneuver TCA search
    try:
        _, post_miss = _find_tca(sat_a_perturbed, sat_b, jd_whole, jd_frac)
    except Exception:
        post_miss = float("nan")

    if math.isnan(post_miss):
        c.is_safe = False
        c.safety_rejection_reason = "Post-maneuver propagation failed"
        c.post_maneuver_miss_distance_km = None
        c.baseline_score = 0.0
        return c

    c.post_maneuver_miss_distance_km = round(post_miss, 4)

    # Constraint: post-maneuver miss distance must be safe
    if post_miss < SAFE_MISS_DISTANCE_KM:
        c.is_safe = False
        c.safety_rejection_reason = (
            f"Post-maneuver miss {post_miss:.3f} km < required {SAFE_MISS_DISTANCE_KM} km"
        )
        c.baseline_score = 0.0
        return c

    # Constraint: must improve on nominal
    improvement = post_miss - nominal_miss_km
    if improvement < MIN_MISS_IMPROVEMENT:
        c.is_safe = False
        c.safety_rejection_reason = (
            f"Improvement {improvement:.3f} km < required {MIN_MISS_IMPROVEMENT} km"
        )
        c.baseline_score = 0.0
        return c

    # All constraints passed
    c.is_safe = True
    c.safety_rejection_reason = None

    # Baseline score: miss distance (70%) + fuel economy (30%)
    # SIMPLIFIED FOR PROTOTYPE: linear weighting, not multi-objective.
    miss_score = min(post_miss / 100.0, 1.0)
    fuel_score = 1.0 - (fuel_kg / MAX_FUEL_KG)
    c.baseline_score = round(0.7 * miss_score + 0.3 * fuel_score, 4)
    return c


def evaluate_all_candidates(
    candidates: list[ManeuverCandidate],
    scenario: Scenario,
    nominal_miss_km: float,
) -> list[ManeuverCandidate]:
    return [evaluate_candidate(c, scenario, nominal_miss_km) for c in candidates]
