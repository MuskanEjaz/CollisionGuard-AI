# API Reference — CollisionGuard AI

> Simulation only — not flight software.
> All endpoints return JSON. Interactive docs: http://localhost:8000/docs

---

## Base URL

Development: `http://localhost:8000`

Configure the frontend base URL via `VITE_API_BASE_URL` in `frontend/.env.local`.

---

## Implemented endpoints

---

### GET /health

**Purpose**: Backend health check and version.
**Router**: `routers/health.py`
**Auth**: None

**Request**: No body.

**Response 200** (`HealthResponse`):
```json
{
  "status": "ok",
  "version": "0.1.0",
  "components": {
    "data_layer": {
      "status": "ok",
      "detail": "Synthetic scenario files loaded"
    }
  }
}
```

**Status codes**: 200 (always — health never returns 500)
**Latency**: < 5 ms
**Cache**: None

---

### GET /scenarios

**Purpose**: List all available scenarios.
**Router**: `routers/scenarios.py`
**Auth**: None

**Request**: No body.

**Response 200** (`ScenarioListResponse`):
```json
{
  "scenarios": [
    {
      "scenario_id": "CONJ-001",
      "scenario_type": "conjunction",
      "description": "LEO conjunction scenario...",
      "epoch_utc": "2025-08-01T12:00:00Z",
      "our_satellite": { "object_id": "OUR_SAT_001", "name": "...", "tle": {...}, "mass_kg": 450.0, "cross_section_m2": 4.2 },
      "threat_object": { "object_id": "THREAT_001", "name": "...", "tle": {...}, "mass_kg": 1200.0, "cross_section_m2": 9.8 },
      "predicted_miss_distance_km": null,
      "time_to_closest_approach_s": null,
      "tca_utc": null,
      "is_conjunction": null
    }
  ],
  "count": 2
}
```

**Synthetic fields**: `predicted_miss_distance_km`, `time_to_closest_approach_s`,
`tca_utc`, `is_conjunction` are `null` — populated by propagation endpoints.

**Status codes**: 200
**Latency**: < 10 ms (JSON parsed and validated at first call; cached thereafter)

---

### GET /scenarios/{scenario_id}

**Purpose**: Single scenario by ID.
**Router**: `routers/scenarios.py`

**Path param**: `scenario_id` — e.g. `CONJ-001`, `SAFE-001`

**Response 200**: Single `Scenario` object (same schema as list item above)
**Response 404**: `{"detail": "Scenario 'X' not found."}`

---

### POST /scenarios/{scenario_id}/propagate

**Purpose**: SGP4 propagation + two-stage TCA search.
**Router**: `routers/scenarios.py`
**Request**: No body.

**Response 200** (`PropagationResponse`):
```json
{
  "scenario_id": "CONJ-001",
  "miss_distance_km": 0.0289,
  "tca_offset_seconds": 1420.5,
  "tca_utc": "2025-08-01T12:23:40Z",
  "is_conjunction": true,
  "conjunction_threshold_km": 1.0
}
```

**Computed fields**: All values computed by `propagation.py` — not hardcoded.
**Status codes**: 200, 404, 500 (propagation failed)
**Latency**: 8–12 seconds (24-hour coarse grid + Brent refinement)

---

### GET /scenarios/{scenario_id}/maneuvers

**Purpose**: Unevaluated maneuver candidate list (no propagation required).
**Router**: `routers/maneuvers.py`

**Response 200** (`ManeuverCandidateListResponse`):
```json
{
  "scenario_id": "CONJ-001",
  "candidates": [
    {
      "candidate_id": "MAN-001",
      "label": "Small prograde +0.5 m/s",
      "direction": "prograde",
      "delta_v_ms": 0.5,
      "is_safe": null,
      "safety_rejection_reason": null,
      "fuel_cost_kg": null,
      "post_maneuver_miss_distance_km": null,
      "baseline_score": null
    }
  ],
  "count": 5
}
```

**Note**: Safety fields (`is_safe`, `fuel_cost_kg`, etc.) are `null` until
`/evaluate` is called.

**Status codes**: 200, 404

---

### POST /scenarios/{scenario_id}/evaluate

**Purpose**: Propagate scenario, then safety-evaluate all 5 candidates.
**Router**: `routers/maneuvers.py`
**Request**: No body.

**Response 200** (`EvaluationResponse`):
```json
{
  "scenario_id": "CONJ-001",
  "nominal_miss_distance_km": 0.0289,
  "candidates": [
    {
      "candidate_id": "MAN-001",
      "label": "Small prograde +0.5 m/s",
      "direction": "prograde",
      "delta_v_ms": 0.5,
      "is_safe": true,
      "safety_rejection_reason": null,
      "fuel_cost_kg": 0.1038,
      "post_maneuver_miss_distance_km": 13.5,
      "baseline_score": 0.9239
    }
  ],
  "safe_count": 4,
  "total_count": 5,
  "evaluation_note": "SIMPLIFIED FOR PROTOTYPE: post-maneuver miss distance is estimated by two-body state-vector perturbation, not optimal targeting."
}
```

**Status codes**: 200, 404, 500
**Latency**: 20–60 seconds (propagation x 1 + maneuver evaluations x 5, each with TCA search)

---

### POST /scenarios/{scenario_id}/maneuvers/{candidate_id}/robustness

**Purpose**: Monte Carlo robustness check for a single safe candidate.
**Router**: `routers/robustness.py`
**Request**: No body.

**Response 200** (`MonteCarloResponse`):
```json
{
  "scenario_id": "CONJ-001",
  "candidate_id": "MAN-001",
  "n_trials": 1000,
  "n_robust": 974,
  "robustness_fraction": 0.974,
  "robustness_label": "974/1000",
  "threshold_km": 5.0,
  "pos_sigma_km": 0.1,
  "vel_sigma_km_s": 0.00001,
  "simplified_note": "SIMPLIFIED FOR PROTOTYPE: ..."
}
```

**Note**: `n_trials` is always the real count from real trials — never hardcoded.
**Status codes**: 200, 404, 422 (candidate not safe), 500
**Latency**: 6–10 minutes for the real 1,000-trial run

---

### POST /scenarios/{scenario_id}/advise

**Purpose**: IBM Granite advisory ranking of safe candidates (or deterministic fallback).
**Router**: `routers/granite.py`
**Request**: No body.

**Response 200** (`GraniteAdvisoryResponse`):
```json
{
  "scenario_id": "CONJ-001",
  "ranked_candidates": [
    {
      "candidate_id": "MAN-001",
      "rank": 1,
      "explanation": "Advisory explanation from Granite.",
      "delta_v_ms": 0.5,
      "post_maneuver_miss_distance_km": 13.5,
      "fuel_cost_kg": 0.1038,
      "baseline_score": 0.9239
    }
  ],
  "granite_summary": "...",
  "source": "granite",
  "model_id": "ibm/granite-3-8b-instruct",
  "validation_warnings": [],
  "granite_note": "ADVISORY ONLY -- human operator approval required before execution."
}
```

**Granite-generated fields**: `ranked_candidates[*].explanation`, `granite_summary`
**Backend-enforced fields**: All numeric values in `ranked_candidates` (delta_v_ms,
post_maneuver_miss_distance_km, fuel_cost_kg, baseline_score)
**Fallback fields**: When `source="deterministic_fallback"`, `granite_summary`
and `explanation` are generated by the deterministic fallback function.

**Status codes**: 200, 404, 500
**Latency**: 2–15 seconds (plus Granite API latency if live); ~100 ms in fallback mode

---

### POST /scenarios/{scenario_id}/analyse

**Purpose**: Full pipeline in one call — propagation + evaluation + Granite advisory.
Result is cached for 300 seconds.
**Router**: `routers/analysis.py`
**Request**: No body.

**Response 200** (`FullAnalysisResponse`):
```json
{
  "scenario_id": "CONJ-001",
  "cached": false,
  "analysis_timestamp": "2025-08-01T13:00:00Z",
  "nominal_miss_distance_km": 0.0289,
  "tca_offset_seconds": 1420.5,
  "tca_utc": "2025-08-01T12:23:40Z",
  "is_conjunction": true,
  "conjunction_threshold_km": 1.0,
  "risk": {
    "level": "CONJUNCTION",
    "label": "Conjunction Alert -- maneuver review required",
    "color_hint": "red"
  },
  "data_quality": [
    { "field": "TLE source", "note": "Synthetic scenario (committed fallback data -- not live CelesTrak)" },
    { "field": "Probability of collision", "note": "Demonstration Pc based on synthetic covariance. Screening-level estimate only." },
    { "field": "Miss distance", "note": "Two-body propagation in TEME frame. J2, drag, and solar-pressure perturbations not modelled." }
  ],
  "orbit_element_age_note": "Epoch: 2025-08-01T12:00:00Z (synthetic -- not real telemetry)",
  "candidates": [...],
  "safe_count": 4,
  "total_count": 5,
  "evaluation_note": "SIMPLIFIED FOR PROTOTYPE: ...",
  "advisory": { ... },
  "prototype_label": "Human-supervised decision-support prototype",
  "simulation_label": "Simulation only — not flight software",
  "risk_basis_label": "Screening-level estimate based on two-body propagation and demonstration Pc based on synthetic covariance. Not suitable for operational conjunction screening."
}
```

**Cache behavior**: Second call returns same object with `cached: true`.
**Status codes**: 200, 404, 500
**Latency**: 20–60 seconds on cache miss; < 5 ms on cache hit

---

### DELETE /scenarios/{scenario_id}/cache

**Purpose**: Invalidate cached analysis for a scenario.
**Router**: `routers/analysis.py`

**Response 200**:
```json
{"scenario_id": "CONJ-001", "entries_removed": 1}
```

**Status codes**: 200 (even if no cache entry existed — 0 removed)

---

### GET /cache/stats

**Purpose**: Inspect current cache state.
**Router**: `routers/analysis.py`

**Response 200**:
```json
{
  "count": 1,
  "entries": [
    {
      "scenario_id": "CONJ-001",
      "cache_key": "a3f9b1c2d4e5f678",
      "age_seconds": 42.1,
      "ttl_seconds": 300.0,
      "expires_in_seconds": 257.9
    }
  ]
}
```

**Status codes**: 200

---

### POST /scenarios/{scenario_id}/approve

**Purpose**: Human approval of a candidate for simulated execution.
Backend re-validates safety — the frontend's `is_safe` state is not trusted.
**Router**: `routers/analysis.py`

**Request** (`ApprovalRequest`):
```json
{
  "scenario_id": "CONJ-001",
  "candidate_id": "MAN-001",
  "operator_id": "OPERATOR"
}
```

**Response 200 — approved** (`ExecutionApprovedResponse`):
```json
{
  "execution": {
    "scenario_id": "CONJ-001",
    "candidate_id": "MAN-001",
    "operator_id": "OPERATOR",
    "simulated": true,
    "execution_label": "SIMULATED EXECUTION -- not flight software",
    "status": "approved",
    "message": "Candidate MAN-001 approved by operator OPERATOR. Awaiting simulated execution.",
    "post_maneuver_miss_distance_km": null,
    "delta_v_applied_ms": null,
    "fuel_consumed_kg": null,
    "executed_at": null
  },
  "safety_gate_passed": true,
  "rejection_reason": null
}
```

**Response 200 — rejected** (`ExecutionApprovedResponse`):
```json
{
  "execution": { "status": "rejected", "message": "Safety gate rejected candidate: ..." },
  "safety_gate_passed": false,
  "rejection_reason": "Post-maneuver miss 2.1 km < required 5.0 km"
}
```

**Status codes**: 200, 404, 422 (scenario_id mismatch in URL vs body)
**Approval requirements**: Stores one-use token in `_PENDING_APPROVALS[scenario_id]`

---

### POST /scenarios/{scenario_id}/execute

**Purpose**: Simulated execution of an approved candidate.
**Router**: `routers/analysis.py`
**Request** (`ApprovalRequest`): Same schema as `/approve`.

**Response 200** (`ExecutionStatus`):
```json
{
  "scenario_id": "CONJ-001",
  "candidate_id": "MAN-001",
  "operator_id": "OPERATOR",
  "simulated": true,
  "execution_label": "SIMULATED EXECUTION -- not flight software",
  "status": "complete",
  "message": "SIMULATED EXECUTION COMPLETE. Maneuver MAN-001 applied. This is a prototype simulation -- not flight software.",
  "post_maneuver_miss_distance_km": 13.5,
  "delta_v_applied_ms": 0.5,
  "fuel_consumed_kg": 0.1038,
  "executed_at": "2025-08-01T13:05:00Z"
}
```

**Status codes**: 200, 403 (no pending approval), 404, 422 (candidate not safe)
**Approval requirements**: Consumes `_PENDING_APPROVALS[scenario_id]` (one-use)

---

### POST /scenarios/{scenario_id}/incident-report

**Purpose**: Generate a simulated incident report after execution.
**Router**: `routers/analysis.py`
**Request** (`ApprovalRequest`): Same schema as `/approve`.

**Response 200** (`IncidentReport`):
```json
{
  "scenario_id": "CONJ-001",
  "candidate_id": "MAN-001",
  "generated_by": "deterministic_template",
  "report_text": "SIMULATED INCIDENT REPORT\n================================\n...",
  "simulated": true,
  "report_label": "SIMULATED INCIDENT REPORT -- not flight documentation"
}
```

**Granite-generated fields**: `report_text` (if `generated_by="granite"`)
**Fallback fields**: `report_text` (if `generated_by="deterministic_template"`)
**Status codes**: 200, 404

---

## Not implemented

The following routes are not implemented in the current codebase:

| Method | Path | Notes |
|---|---|---|
| `GET` | `/scenarios/{id}/propagation` | Propagation result without re-running; not implemented |
| `POST` | `/scenarios` | Creating new scenarios via API; data files are committed |
| `GET` | `/scenarios/{id}/analysis/history` | Analysis history; no persistent store |
| `DELETE` | `/scenarios/{id}/approve` | Cancelling a pending approval; only reset via server restart |

Do not document or test these routes as implemented.
