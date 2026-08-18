# Scientific Assumptions — CollisionGuard AI

> Simulation only — not flight software.
> This document describes the scientific assumptions and limitations of the
> prototype. These limitations must be communicated to any user.

---

## Scope

CollisionGuard AI is scoped to:

- Exactly **two objects**: one maneuverable satellite (`our_satellite`) and one
  non-maneuverable threat object (`threat_object`)
- **LEO only** — both synthetic scenarios represent approximately 400 km altitude
  circular orbits (~6778 km semi-major axis)
- **One conjunction scenario** (CONJ-001) and **one safe-pass scenario** (SAFE-001)
- **3–5 hardcoded candidate delta-v maneuvers** (5 implemented)
- **Human approval required** before any simulated execution

The prototype does not handle:
- Multi-satellite coordination
- Asteroids or natural bodies
- GEO, MEO, HEO, or cislunar orbits
- Fragments or uncheckpointed debris clouds
- Live telemetry or operational tracking data

---

## TLE/OMM limitations

Both scenarios use **synthetic committed TLEs** — not live data from CelesTrak,
Space-Track, or any other operational tracking source.

TLE format limitations that apply:
- Two-line element sets represent a mean orbital state, not instantaneous truth
- SGP4 propagation accuracy degrades with TLE age (typically < 1 day for LEO)
- No differential correction is applied
- TLE epochs in both scenarios are fixed at 2025-08-01 (CONJ-001) and
  2025-08-02 (SAFE-001)
- No live data fetch is implemented; the prototype operates entirely from
  committed fallback data

---

## Coordinate frame

**Frame used**: TEME (True Equator Mean Equinox) — the native output frame of
the SGP4 algorithm.

**Rationale for not converting to GCRS**: The prototype computes only the
*relative* Euclidean distance between two objects. When both objects are
propagated at the same instant using the same frame, the relative vector and its
norm are invariant under any common orthonormal rotation (including the
TEME-to-GCRS transform). Frame conversion is therefore unnecessary for the
relative-distance screening calculation performed here.

The comment in `propagation.py` notes: "Both objects are evaluated in TEME at
the same instant. Euclidean separation is invariant under a common orthonormal
rotation, so converting both states to GCRS is unnecessary for this Phase 2
screening calculation."

**Note**: This reasoning applies only to relative distance. Absolute position
in an Earth-fixed frame (e.g. for ground-track display or ground-station
passes) would require a proper TEME-to-GCRS-to-ITRF conversion.

---

## Propagation method

- Library: `sgp4` 2.x, WGS84 gravity model
- Method: Simplified General Perturbations 4 (SGP4)
- SGP4 accounts for: mean-motion secular decay, drag (BSTAR term from TLE),
  Earth's oblateness (J2 and J3 terms via Kozai mean-motion correction)
- SGP4 does **not** account for: higher-order gravity harmonics (J4+), precise
  atmospheric drag variations, solar radiation pressure, third-body effects
  (Moon, Sun), ocean tides
- For LEO objects with propagation intervals under 24 hours, SGP4 typically
  achieves position accuracy of 1–5 km, depending on TLE age and solar activity

---

## Julian date conversion

`sgp4.api.jday(year, month, day, hour, minute, second)` is used.

This function computes a UTC-based Julian date. It is appropriate for SGP4
because the TLE epoch is defined in UTC.

Skyfield's `ts.tt_jd` is Terrestrial Time (TT), which differs from UTC by
approximately 69.2 seconds (as of 2025) due to accumulated leap seconds. Using
TT would introduce an error of over one minute in the propagation epoch —
approximately 400 km along-track at LEO velocities. `skyfield` is not used
in the propagation path.

---

## TCA search method

### Stage 1 — Coarse grid

```
Search window: 86,400 seconds (24 hours)
Step size:     30 seconds
Evaluations:   2,880 points per TCA search
Identifies:    the 30-second bracket containing the minimum separation
```

### Stage 2 — Brent's method refinement

```
Input:   the one-step bracket [t_i-1, t_i+1] around the coarse minimum
Method:  Brent's algorithm (parabolic interpolation + golden-section fallback)
         100 maximum iterations
Tolerance: 0.01 seconds (absolute time)
Result:  TCA offset in seconds from epoch, accurate to 0.01 s
```

Brent's method is implemented manually in `propagation.py` without `scipy`.
This avoids an additional runtime dependency and is correct for the unimodal
separation minimum within the bracket.

**Limitation**: The coarse grid may miss a TCA if the miss distance has a very
narrow minimum (full width < 30 seconds). This is unlikely for typical LEO
conjunctions (orbital separation rates of 0.1–15 km/s), but the 30-second grid
is not guaranteed to find all local minima.

---

## Conjunction threshold

The conjunction threshold (`CONJUNCTION_THRESHOLD_KM = 1.0`) is a hardcoded
business rule. It represents the miss distance below which the scenario is
classified as a conjunction requiring operator review.

This threshold is illustrative, not calibrated to any specific operational
standard (e.g., the USSPACECOM 1:10,000 Pc threshold or the European Space
Agency's 1:1,000 threshold).

---

## Collision risk basis

**What is computed**: Euclidean miss distance at the predicted TCA.

**What is NOT computed**: Probability of collision (Pc). No covariance data is
available. The `risk_basis_label` field in all analysis responses reads:
"Screening-level estimate based on two-body propagation and demonstration Pc
based on synthetic covariance. Not suitable for operational conjunction screening."

A real conjunction screening system would:
1. Use a Conjunction Data Message (CDM) containing covariance matrices for both
   objects at TCA
2. Compute Pc using the Alfriend-Akella formula (or equivalent), integrating
   the combined covariance over the hard-body collision cross-section
3. Compare Pc against an operational threshold (typically 1:10,000 to 1:1,000)

None of these steps are implemented in this prototype.

---

## Covariance and uncertainty

Monte Carlo perturbations use a **diagonal covariance model**:
- Position uncertainty: 100 m (0.1 km) per axis, 1-sigma
- Velocity uncertainty: 0.01 m/s (0.00001 km/s) per axis, 1-sigma

These are representative of LEO radar tracking accuracy but are:
- Not derived from a real CDM or tracking data source
- Applied as independent Gaussian perturbations per axis
- Missing cross-terms (position-velocity correlation)
- Missing atmospheric density uncertainty
- Missing systematic biases

The `simplified_note` field in `MonteCarloResponse` explicitly documents these
limitations.

---

## Hard-body radius

No hard-body radius check is implemented. The conjunction threshold (1.0 km
miss distance) implicitly provides a large safety margin, but no explicit
physical collision cross-section is computed.

---

## Delta-v assumptions

The 5 candidate maneuvers use **hardcoded delta-v magnitudes**:
- +0.5, +1.0, +2.0 m/s prograde
- -0.5 m/s retrograde
- +1.0 m/s normal (out of orbital plane)

These are representative of LEO station-keeping and avoidance maneuvers.
They are **not** computed from the specific conjunction geometry, TCA time,
or target miss distance. In a real system, candidates would be computed using
differential correction targeting a specific post-maneuver miss distance.

The `evaluation_note` field in all evaluation responses states: "SIMPLIFIED FOR
PROTOTYPE: post-maneuver miss distance is estimated by two-body state-vector
perturbation, not optimal targeting."

---

## Maneuver simplifications

**Post-maneuver orbit construction** (`_satrec_from_rv()`):
- Delta-v is applied as an instantaneous velocity impulse at the epoch
- No finite burn arc is modelled
- The perturbed state vector is used to derive two-body Keplerian elements
- A synthetic TLE is constructed from those elements for re-propagation
- Drag coefficient (BSTAR) is copied from the original TLE
- J2, drag, and solar radiation pressure effects on the post-maneuver orbit
  are not modelled during the TCA search

**Safety gate thresholds** (from `maneuver_evaluator.py`):
- Delta-v budget: |dv| <= 3.0 m/s (absolute)
- Fuel budget: <= 5.0 kg (Tsiolkovsky, Isp=220 s cold-gas thruster)
- Post-maneuver miss: >= 5.0 km
- Improvement over nominal: >= 1.0 km

**Baseline score formula** (simplified, not multi-objective):
`score = 0.7 * min(post_miss_km / 100, 1) + 0.3 * (1 - fuel_kg / 5)`

---

## Monte Carlo seed and trial configuration

- Default trial count: `N_TRIALS = 1000` (constant in `monte_carlo.py`)
- `n_trials_override` parameter: used by fast tests only; never changes the
  production constant
- `rng_seed`: optional; if `None`, results vary between runs (expected)
- Reproducible results require a fixed seed; the production path uses `None`
- The `robustness_label` format is `"{n_robust}/{n_trials}"` (always real count)

---

## Screening-level vs operational analysis

| Aspect | This prototype | Operational system |
|---|---|---|
| Propagation | SGP4, 24-hour window | High-fidelity force model, multiple days |
| Covariance | None (representative diagonal) | CDM covariance from tracking data |
| Risk metric | Miss distance only | Pc with covariance |
| Maneuver targeting | Hardcoded dv | Differential correction |
| Confidence | Screening-level estimate | Calibrated to tracking data quality |
| Data source | Synthetic TLEs | Live OMM/CDM from Space-Track or equivalent |

---

## Conclusions the prototype cannot make

The following statements must never be made based on this prototype's output:

- "The probability of collision is [X]%"
- "No collision will occur"
- "This maneuver guarantees safe separation"
- "These results are suitable for flight operations"
- "This analysis meets conjunction screening standards"

All output should be accompanied by the disclaimer: "Screening-level estimate
based on two-body propagation and demonstration Pc based on synthetic covariance.
Not suitable for operational conjunction screening."
