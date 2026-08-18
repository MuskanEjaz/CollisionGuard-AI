# Safety and Responsible Use — CollisionGuard AI

> CollisionGuard AI is a simulation only — not flight software.
> It must not be used for real spacecraft command or operational conjunction screening.

---

## Human approval requirement

Every simulated execution requires **two explicit operator actions**:

1. The operator selects a safe candidate in the dashboard
2. The operator clicks "Request Simulated Execution"
3. The backend validates the candidate's safety status server-side (not trusting the UI)
4. The operator reviews the confirmation dialog (showing delta-v, fuel, post-miss)
5. The operator clicks "Confirm — Simulate Execution"
6. The backend checks the one-use approval token before running simulation

No automated or autonomous execution is possible. The system cannot execute
a maneuver without step 5. This is architecturally enforced, not a UI convention.

---

## Simulated execution

All execution in this prototype is simulated:
- `ExecutionStatus.simulated` is always `True`
- `ExecutionStatus.execution_label` is always `"SIMULATED EXECUTION -- not flight software"`
- No spacecraft command interface exists
- No telemetry uplink exists
- The "execution" returns values computed by the deterministic evaluator — it
  does not command any real hardware

---

## Unsafe-candidate rejection

The safety gate in `maneuver_evaluator.py` marks candidates `is_safe=False` when:
- Delta-v exceeds 3.0 m/s
- Fuel cost exceeds 5.0 kg (Tsiolkovsky)
- Post-maneuver orbit construction fails
- Post-maneuver miss distance < 5.0 km
- Improvement over nominal < 1.0 km

Unsafe candidates are rejected at multiple layers:
1. `evaluate_candidate()` sets `is_safe=False` with a specific rejection reason
2. `get_granite_advisory()` sends only safe candidates to Granite (unsafe never reach AI)
3. `POST /approve` re-validates safety server-side; unsafe → `safety_gate_passed=False`
4. `POST /execute` performs a final belt-and-suspenders safety check

The UI disables the approval button for unsafe candidates, but the backend
is the authoritative safety gate — not the UI.

---

## Granite authority limits

Granite (IBM) may:
- Rank safe candidates from best to worst (advisory only)
- Produce one-sentence explanations per candidate
- Produce a summary paragraph for operator context
- Produce a simulated incident report narrative (if credentials available)

Granite may NOT:
- Receive, reference, or rank unsafe candidates
- Modify any backend-computed numeric value
- Override a safety rejection
- Approve or veto execution
- Alter miss distance, fuel cost, baseline score, or robustness fraction

These limits are structurally enforced in `granite_client.py`:
- `get_granite_advisory()` filters out unsafe candidates before building the prompt
- `_parse_granite_response()` skips any reference to unknown or unsafe candidate IDs
- Physics values in `GraniteRankedCandidate` are always copied from backend objects

---

## Deterministic backend authority

The deterministic backend is the single source of truth for all numeric values.
No external system (Granite, frontend, network) can override backend-computed:
- Miss distance
- TCA timing
- Fuel cost
- Safety determination
- Robustness fraction
- Post-maneuver miss distance

If Granite returns a numeric value that differs from the backend value by more
than 1% (relative tolerance), the backend value is used and a warning is added
to `validation_warnings`. The Granite value is silently discarded.

---

## Numeric grounding

Every number Granite states is validated against the backend-computed value.
Validation is in `_validate_numeric()` (`granite_client.py`):

```python
if |granite_val - backend_val| / |backend_val| > 0.01:  # 1% relative tolerance
    warnings.append(f"{field}: Granite value differs by {rel_err:.2%} -- using backend value.")
return backend_val  # ALWAYS return backend value
```

This function is called for every numeric field Granite includes in its ranking
response. The returned value is always the backend value regardless of whether
a warning was generated.

---

## Credential handling

- Credentials (`WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`) are read
  from environment variables only
- Credentials are never logged, never included in API responses, never hardcoded
- `_validate_config()` error messages describe the problem category only —
  no credential value appears in any error message
- `granite_smoke_test.py` masks credential values in all output
- The analysis cache stores no credential values
- `_has_valid_config()` returns `(True, "")` or `(False, reason)` where
  `reason` contains no credential value

---

## Fallback behavior

When Granite is unavailable, the deterministic fallback:
1. Sorts safe candidates by `baseline_score` descending
2. Sets `source="deterministic_fallback"`
3. Sets `granite_summary` to a human-readable explanation of why Granite is unavailable
4. Adds the fallback reason to `validation_warnings`
5. Returns a fully valid `GraniteAdvisoryResponse`

The system is fully functional in fallback mode. No functionality is degraded
except the quality of ranking explanations.

---

## Error behavior

| Scenario | Response |
|---|---|
| SGP4 propagation returns `nan` for all steps | `ValueError` -> HTTP 500 |
| Single step propagation error | Step skipped; NaN filtered from grid |
| Post-maneuver orbit construction fails | Candidate `is_safe=False`; reason in response |
| Granite JSON unparseable | `_parse_granite_response` returns `None`; fallback used |
| Granite API call raises exception | Exception type logged (no credentials); fallback used |
| Approval for wrong scenario_id | HTTP 422 |
| Execute without prior approve | HTTP 403 |
| Unknown scenario_id | HTTP 404 |
| Invalid TLE length or prefix | HTTP 422 (Pydantic validation error) |

Errors do not expose credentials. Error messages describe the problem
category, not credential values or internal implementation details beyond
what is needed to diagnose the issue.

---

## Prohibited operational use

CollisionGuard AI **must not** be used for:

- Commanding real spacecraft thrusters or attitude-control systems
- Providing collision probabilities for operational risk assessment
- Replacing professional space-traffic management services
- Making operational decisions about real satellites
- Any safety-critical decision without independent verification by qualified
  space-traffic management professionals

The system is explicitly labelled at the UI level:
- Header: "Human-supervised decision-support prototype"
- Header: "Simulation only — not flight software"
- Every analysis response: `prototype_label`, `simulation_label`, `risk_basis_label`
- Every execution response: `simulated: true`, `execution_label`
- Every incident report: `simulated: true`, `report_label`

---

## Public orbital data limitations

TLE data from public sources (CelesTrak, Space-Track) has the following limitations
relevant to conjunction screening:
- Position accuracy: 1–5 km for recent TLEs (typically < 1 day old)
- No official collision probability; CDM must come from authorised sources
- Uncatalogued debris (< 10 cm diameter) is not tracked and not represented
- Manoeuvring satellites may have stale TLEs

This prototype uses synthetic committed TLEs and does not fetch live data.
All limitations above apply to any future live-data integration.

---

## No spacecraft-command capability

There is no command interface, uplink system, ground station integration, or
any mechanism to send data to a real spacecraft. The "execute" endpoint
simulates the output values of a maneuver — it does not and cannot transmit
any command to any hardware.

This is not a design limitation to be fixed in a future version. It is a
deliberate scope boundary: this prototype demonstrates the decision-support
workflow only.
