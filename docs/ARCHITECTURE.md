# Architecture — CollisionGuard AI

> Simulation only — not flight software.
> Human-supervised decision-support prototype.

---

## Component overview

```
+----------------------------+        HTTP (fetch)        +--------------------------------+
|  Frontend                  | <------------------------> |  Backend                       |
|  React 18 + Vite 5         |   GET, POST, DELETE        |  FastAPI + uvicorn             |
|  port 5173                 |   CORS: localhost:5173     |  port 8000                     |
+----------------------------+                            +--------------------------------+
|  App.jsx                   |                            |  main.py (entry point)         |
|  ConjunctionMetrics.jsx     |                            |  config.py (pydantic-settings) |
|  ManeuverTable.jsx         |                            |  analysis_cache.py             |
|  GraniteAdvisory.jsx       |                            +--------------------------------+
|  TrajectoryPlot.jsx        |                            |  Routers                       |
|  ApprovalGate.jsx          |                            |  health.py                     |
|  HealthStatus.jsx          |                            |  scenarios.py                  |
|  ScenarioPanel.jsx         |                            |  maneuvers.py                  |
|  api/client.js             |                            |  robustness.py                 |
+----------------------------+                            |  granite.py                    |
                                                          |  analysis.py                   |
                                                          +--------------------------------+
                                                          |  Computation modules           |
                                                          |  propagation.py                |
                                                          |  maneuver_candidates.py        |
                                                          |  maneuver_evaluator.py         |
                                                          |  monte_carlo.py                |
                                                          |  granite_client.py             |
                                                          +--------------------------------+
                                                          |  Schemas (Pydantic v2)         |
                                                          |  schemas/health.py             |
                                                          |  schemas/scenario.py           |
                                                          |  schemas/maneuver.py           |
                                                          |  schemas/monte_carlo.py        |
                                                          |  schemas/granite.py            |
                                                          |  schemas/analysis.py           |
                                                          +--------------------------------+
                                                          |  Data                          |
                                                          |  data/scenarios/*.json         |
                                                          +--------------------------------+
                                                          |  External (optional)           |
                                                          |  IBM watsonx.ai                |
                                                          |  (Granite-3-8b-instruct)       |
                                                          +--------------------------------+
```

---

## Frontend/backend boundary

The frontend never computes orbital mechanics, risk classifications, fuel costs,
or any derived physics value. Every number displayed in the UI comes from the
API response.

The frontend calls three HTTP methods:
- `GET` — fetch scenarios and health
- `POST` — trigger analysis, approval, execution, incident report
- `DELETE` — invalidate the analysis cache

The `apiDel` function in [`api/client.js`](../frontend/src/api/client.js) is
the only consumer of DELETE. CORS must include DELETE, which is enforced in
[`main.py`](../backend/main.py).

---

## Deterministic physics boundary

The deterministic backend is the single source of truth for all numeric values.

```
propagation.py      -- TCA offset, miss distance, is_conjunction
maneuver_evaluator.py -- is_safe, fuel_cost_kg, post_maneuver_miss_distance_km,
                         safety_rejection_reason, baseline_score
monte_carlo.py      -- n_robust, robustness_fraction, robustness_label
```

None of these values may be altered by Granite or by the frontend.

---

## AI boundary (IBM Granite)

Granite operates exclusively within `granite_client.py`. Its authority is:
- Rank safe candidates by advisory preference
- Produce one-sentence explanations per candidate
- Produce a summary paragraph
- Produce an incident report narrative (if credentials are available)

Granite cannot:
- Receive unsafe candidates
- Modify any backend-computed number
- Approve execution
- Override a safety rejection

The numeric grounding check in `_validate_numeric()` and `_parse_granite_response()`
enforces this at the response-parsing layer. Physics values in
`GraniteRankedCandidate` are always copied from the backend `ManeuverCandidate`
object, not from Granite output.

---

## Scenario flow

```
Client: GET /scenarios
  -> routers/scenarios.py: _load_scenarios()
     -> reads data/scenarios/*.json
     -> Pydantic validates each file into Scenario
     -> returns ScenarioListResponse

Client: POST /scenarios/{id}/analyse
  -> routers/analysis.py: analyse()
     -> check analysis_cache.py: get_cached()
        [hit] -> return cached FullAnalysisResponse with cached=True
        [miss] -> _build_analysis()
                    -> propagate_scenario()
                    -> get_maneuver_candidates()
                    -> evaluate_all_candidates()
                    -> get_granite_advisory()
                    -> build FullAnalysisResponse
              -> set_cached()
              -> return FullAnalysisResponse with cached=False
```

---

## Propagation flow

```
propagate_scenario(scenario)
  -> _build_satrec(our_satellite.tle)  -- sgp4.api.Satrec.twoline2rv, WGS84
  -> _build_satrec(threat_object.tle)
  -> jday(epoch_utc)                   -- sgp4.api.jday, UTC-based
  -> _find_tca(sat_a, sat_b, jd_whole, jd_frac)
       -> coarse grid: _separation_km() at 30-second intervals (2880 steps)
          -> _propagate_single() -> sgp4() -> TEME position
          -> Euclidean norm of (pos_a - pos_b)
       -> bracket coarse minimum
       -> _brent(f, lo, hi, tol=0.01s)  -- parabolic + golden-section, 100 iter
       -> return (tca_offset_seconds, miss_distance_km)
  -> return PropagationResult
```

TEME positions for both satellites are compared at the same instant. Euclidean
separation is invariant under a common orthonormal rotation, so no frame
conversion is needed for this relative-distance screening.

---

## Risk classification flow

```
_classify_risk(miss_km)
  miss_km < 1.0  -> CONJUNCTION  (red)
  miss_km < 5.0  -> MONITORING   (yellow)
  miss_km >= 5.0 -> SAFE         (green)
```

---

## Maneuver flow

```
get_maneuver_candidates()
  -> returns 5 hardcoded ManeuverCandidate objects
     (prograde +0.5, +1.0, +2.0 m/s; retrograde -0.5 m/s; normal +1.0 m/s)

evaluate_all_candidates(candidates, scenario, nominal_miss_km)
  for each candidate:
    evaluate_candidate(c, scenario, nominal_miss_km)
      1. |dv| > 3.0 m/s  -> is_safe=False, reason recorded
      2. Tsiolkovsky fuel > 5.0 kg  -> is_safe=False
      3. _apply_delta_v() -> velocity impulse at epoch
         -> _satrec_from_rv() -> new Satrec from perturbed Keplerian elements
      4. _find_tca(sat_a_perturbed, sat_b) -> post_miss
      5. post_miss < 5.0 km  -> is_safe=False
      6. (post_miss - nominal_miss) < 1.0 km  -> is_safe=False
      7. all passed -> is_safe=True
         baseline_score = 0.7 * min(post_miss/100, 1) + 0.3 * (1 - fuel/5)
```

---

## Monte Carlo flow

```
run_monte_carlo(candidate, scenario, rng_seed=None, n_trials_override=None)
  n = n_trials_override ?? N_TRIALS (1000)
  rng = np.random.default_rng(rng_seed)
  for _ in range(n):
    pos_p = pos0 + rng.normal(0, 0.1, 3)       # 100m pos perturbation
    vel_p = vel0 + rng.normal(0, 0.00001, 3)   # 0.01 m/s vel perturbation
    sat_a_perturbed = _satrec_from_rv(pos_p, vel_p, ...)
    sat_a_maneuver = _apply_delta_v(sat_a_perturbed, ...)
    _, post_miss = _find_tca(sat_a_maneuver, sat_b, ...)
    if post_miss > 5.0: n_robust += 1
  return MonteCarloResult(n_trials=n, n_robust=n_robust, ...)
  -- n_robust is ALWAYS the real count from real trials
```

---

## Approval state flow

```
Frontend state:  idle -> confirming -> approved -> executing -> done | rejected | error

Backend state machine:
  POST /approve
    -> validates scenario exists
    -> validates candidate exists in cached evaluation (or re-evaluates)
    -> is_safe==False -> ExecutionApprovedResponse(safety_gate_passed=False, status="rejected")
    -> is_safe==True  -> _PENDING_APPROVALS[scenario_id] = candidate_id
                         ExecutionApprovedResponse(safety_gate_passed=True, status="approved")

  POST /execute
    -> _PENDING_APPROVALS.get(scenario_id) != candidate_id -> 403 error
    -> del _PENDING_APPROVALS[scenario_id]  (one-use token)
    -> final safety check against cached evaluation
    -> ExecutionStatus(simulated=True, status="complete", ...)
```

`_PENDING_APPROVALS` is a plain in-process dict — it resets on server restart.
No persisted state, no replay risk across restarts.

---

## Execution and verification flow

```
POST /execute (on success):
  returns ExecutionStatus:
    simulated: true              -- always
    status: "complete"
    post_maneuver_miss_distance_km  -- from backend-evaluated candidate
    delta_v_applied_ms              -- from backend-evaluated candidate
    fuel_consumed_kg                -- from backend-evaluated candidate
    executed_at                     -- UTC now()

All values come from the deterministic evaluator, not from user input.
```

---

## Granite/fallback flow

```
get_granite_advisory(evaluation)
  safe_candidates = [c for c in evaluation.candidates if c.is_safe]
  if not safe_candidates: -> deterministic_fallback("No safe candidates")
  valid, reason = _has_valid_config()
  if not valid: -> deterministic_fallback(reason)
  try:
    -> _call_granite(scenario_id, nominal_miss_km, safe_candidates)
       -> build prompt (structured JSON format, explicit constraints)
       -> ibm_watsonx_ai Credentials + ModelInference
       -> model.generate_text(prompt, max_new_tokens=800, temperature=0.0)
       -> _parse_granite_response(raw_text, scenario_id, safe_candidates)
          for each Granite ranking entry:
            if candidate_id not in safe_candidates: warn + skip
            _validate_numeric(field, granite_val, backend_val, warnings)
              if |granite - backend| / backend > 0.01: append warning
              return backend_val  -- ALWAYS
            GraniteRankedCandidate uses backend physics values only
          return GraniteAdvisoryResponse(source="granite", ...)
       if parse returns None: -> deterministic_fallback("parse failed")
  except: -> deterministic_fallback("Granite API error: <ExcType>")
  -- credentials never logged or returned
```

---

## Cache behavior

```
analysis_cache.py

Key:   SHA-256(scenario_id | tle_line1 | tle_line2 | threat_line1 | threat_line2 | epoch_utc)
       truncated to 16 hex characters
TTL:   300 seconds (5 minutes)
Store: in-process Python dict (_CACHE)

get_cached(scenario_id, scenario):
  key = _make_cache_key(...)
  entry = _CACHE.get(key)
  if None: return (None, False)
  if age > ttl: del _CACHE[key]; return (None, False)
  return (entry.analysis, True)

set_cached(...):
  _CACHE[key] = CacheEntry(scenario_id, key, analysis, created_at, ttl)

invalidate(scenario_id):
  remove all entries where entry.scenario_id == scenario_id

flush_all():
  _CACHE.clear()
```

The cache key changes if TLE data or epoch changes, invalidating stale entries
automatically. Credentials are never stored in cache entries.

---

## Failure behavior

| Failure | Behavior |
|---|---|
| SGP4 error at a single time step | Returns `nan` for that separation, skipped |
| All separations are `nan` | `propagate_scenario` raises `ValueError` -> HTTP 500 |
| Post-maneuver orbit construction fails | Candidate `is_safe=False`, reason logged |
| Monte Carlo trial propagation fails | Trial counted as failed, not robust |
| Granite API error | `deterministic_fallback` used; `source="deterministic_fallback"` |
| Granite JSON unparseable | `_parse_granite_response` returns `None` -> fallback |
| Granite references unsafe candidate | Entry skipped; warning added |
| `_PENDING_APPROVALS` mismatch on execute | HTTP 403 |
| Scenario not found | HTTP 404 |
| Pydantic validation error on input | HTTP 422 with field details |

---

## Security boundaries

- Credentials (`WATSONX_APIKEY`, `WATSONX_PROJECT_ID`) read from environment only
- Credentials never appear in logs, error messages, or API responses
- `_validate_config()` error messages describe the problem category only
- `granite_smoke_test.py` masks actual credential values in output
- Cache keys and entries contain no credential values
- `_has_valid_config()` used to gate all live Granite calls

---

## Scientific assumptions

See [`docs/SCIENTIFIC_ASSUMPTIONS.md`](SCIENTIFIC_ASSUMPTIONS.md) for full detail.

Summary:
- LEO only; two objects only
- TLE propagation with SGP4/WGS84; no J2, drag, or SRP perturbation
- TEME frame; relative distance only; no absolute frame conversion needed
- Screening-level miss distance; no Pc calculation
- Synthetic TLEs; no real CDM covariance
- Circular orbit display (frontend only; not used for physics)

---

## Module and schema relationships

```
schemas/scenario.py
  TLEData <- SpaceObject <- Scenario
  Scenario <- ScenarioListResponse
  Scenario -> PropagationResponse

schemas/maneuver.py
  ManeuverDirection <- ManeuverCandidate
  ManeuverCandidate <- ManeuverCandidateListResponse
  ManeuverCandidate <- EvaluationResponse

schemas/monte_carlo.py
  MonteCarloResponse

schemas/granite.py
  GraniteRankedCandidate <- GraniteAdvisoryResponse

schemas/analysis.py
  RiskClassification <- FullAnalysisResponse
  DataQualityNote <- FullAnalysisResponse
  ManeuverCandidate <- FullAnalysisResponse
  GraniteAdvisoryResponse <- FullAnalysisResponse
  ApprovalRequest -> approve endpoint + execute endpoint
  ExecutionStatus <- ExecutionApprovedResponse
  IncidentReport

schemas/health.py
  ComponentStatus <- HealthResponse

Data flow:
  Scenario -> propagation.py -> PropagationResult
  PropagationResult + Scenario -> maneuver_evaluator.py -> [ManeuverCandidate]
  [ManeuverCandidate] -> granite_client.py -> GraniteAdvisoryResponse
  PropagationResult + [ManeuverCandidate] + GraniteAdvisoryResponse -> FullAnalysisResponse
  FullAnalysisResponse -> analysis_cache.py
```
