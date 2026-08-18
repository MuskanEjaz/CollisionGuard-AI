# Current Status — CollisionGuard AI

> Last updated: Phase 8 verification run (CORS tests executed, fast tests re-run, README condensed)
> This document reflects the repository state after Phase 8 verification.

---

## Completed and verified

| Item | Evidence |
|---|---|
| FastAPI backend, all routes | 140 fast tests passed in Phase 8 verification session (452.95 s) |
| Pydantic v2 schemas | Validated by test suite and import checks |
| SGP4 propagation (TEME frame) | 11 propagation tests passed |
| Brent TCA search (24-hour, tol=0.01 s) | Tested in test_propagation.py |
| Maneuver safety evaluation (5 candidates) | 13 evaluator tests passed |
| Granite numeric grounding guardrail | 42 Granite tests passed (mocked) |
| Deterministic fallback ranking | Tested in test_granite.py |
| In-memory TTL cache (SHA-256 key, 300 s) | 6 cache tests passed |
| Human approval gate (two-step, server-side) | 10 approval/execution tests passed |
| Simulated execution + incident report | 5 incident report tests passed |
| React/Vite dark mission-control dashboard | npm run build succeeded — 1m 16s, Plotly chunk warning only |
| CORS DELETE fix applied to main.py | 6 CORS preflight tests executed: 6 passed in 1.51 s |
| README.md condensed (Phase 8 verification) | 832 lines → 439 lines; all required content preserved |
| docs/ directory created (Phase 8) | 10 documentation files created |

---

## Completed with mocked tests only

| Item | Status |
|---|---|
| IBM Granite live API call | Implemented; tested with mocked responses only |
| Granite prompt construction | Implemented; never sent to real Granite in tests |
| Granite response parsing | Implemented and unit-tested with synthetic JSON |
| Granite incident report generation | Implemented; mocked in tests |
| Granite numeric conflict detection | Implemented; tested with synthetic discrepancies |

All Granite tests pass with mocked responses. **No live watsonx response has
been confirmed in this repository.** Live verification is Pushkar's task.

---

## Deferred

| Item | Command to run | Notes |
|---|---|---|
| Real 1,000-trial Monte Carlo | `pytest tests/test_monte_carlo.py -v -m slow` | ~8 min; must run before submission |
| Live Granite smoke test | `python granite_smoke_test.py` | Requires .env with real credentials |

Neither of these tests may be labelled "passed" without actual execution.

---

## Partially implemented

| Item | Notes |
|---|---|
| 3D trajectory visualisation | Circular orbit approximation only; labelled "SIMPLIFIED FOR PROTOTYPE" |
| TrajectoryPlot orbital elements | Hardcoded approximate values; not derived from TLE parse |

---

## Not started

| Item | Owner | Notes |
|---|---|---|
| Demo video recording | Surya | Script ready in docs/DEMO_VIDEO_PLAN.md |
| GitHub repository description and topics | Muskan | Post-submission task |
| Challenge submission form | Muskan | Pending final video URL |

---

## Fast-test count

| Session | Count | Duration | Command |
|---|---|---|---|
| Pre-Phase 8 (verified) | 134 passed | 544.73 s | `pytest tests/ -v -m "not slow"` |
| Phase 8 verification (executed) | **140 passed, 1 deselected** | **452.95 s** | `pytest tests/ -v -m "not slow"` |

The 6 CORS tests (`test_cors.py`) are confirmed. Total is now 140 passed, 1 deselected.

---

## Frontend build status

Phase 8 verification session: `npm run build` succeeded in 1m 16s with no errors.
Known warning: Plotly bundle chunk `index-DSSRmjNK.js` = 4,870.32 kB (expected for react-plotly.js prototype).

---

## CORS status

**Fixed in Phase 8.**

Before fix: `allow_methods=["GET", "POST"]` — DELETE missing.
After fix: `allow_methods=["GET", "POST", "DELETE"]` — browser cache invalidation works.

Preflight test added: `tests/test_cors.py` (6 tests).

---

## Live Granite status

**Not verified.**

The Granite integration is implemented and thoroughly mocked-tested. No live
watsonx.ai response has been confirmed. Pushkar owns this verification task.

---

## Real 1,000-trial Monte Carlo status

**Not yet executed.**

The test exists as `test_monte_carlo_real_1000_trials` in `test_monte_carlo.py`
and is decorated `@pytest.mark.slow`. It has never been run in this session.
Surya owns this execution task.

---

## README/documentation status

**Completed in Phase 8.**

- `README.md` — full rewrite; reflects Phase 1–8 system; all 14 endpoints listed;
  correct env var names; WATSONX_APIKEY (no underscore); live Granite marked unverified;
  slow test marked deferred
- `docs/ARCHITECTURE.md` — complete
- `docs/API_REFERENCE.md` — complete; all 14 endpoints; planned routes in separate section
- `docs/SCIENTIFIC_ASSUMPTIONS.md` — complete
- `docs/SAFETY_AND_RESPONSIBLE_USE.md` — complete
- `docs/TESTING.md` — complete; no unexecuted test labelled as passed
- `docs/IBM_BOB_USAGE.md` — complete
- `docs/TEAM_HANDOFF.md` — complete; equal 8.5/10 difficulty assignments
- `docs/SUBMISSION_COPY.md` — complete; all placeholders clearly marked
- `docs/CURRENT_STATUS.md` — this file
- `docs/DEMO_VIDEO_PLAN.md` — complete; full 3-minute script for Surya

---

## Demo video status

**Not recorded.**

Script is in `docs/DEMO_VIDEO_PLAN.md`. Surya will record after:
1. Real 1,000-trial Monte Carlo is verified
2. Pushkar confirms live Granite availability (or records fallback path)
3. All branches are merged to `main`

---

## Next priorities

### Competition-critical blockers (in order)

1. ~~**Surya**: Run `pytest tests/ -v -m "not slow"` — **DONE**: 140 passed, 452.95 s~~
2. **Surya**: Run `pytest tests/test_monte_carlo.py -v -m slow` — confirm
   `n_trials=1000`, take screenshot
3. **Pushkar**: Obtain watsonx credentials, run smoke test, verify live Granite
   in dashboard, provide evidence screenshots
4. **Muskan**: Verify UI end-to-end with both scenarios, confirm all cards render,
   take evidence screenshots
5. **Surya**: Record demo video against final merged build, upload publicly
6. **Muskan**: Update README with final test counts and video URL
7. **Muskan**: Complete challenge submission form

### Non-blocking improvements

- Consider Plotly `manualChunks` in `vite.config.js` to reduce chunk size warning
- Add GitHub repository description and topics after submission
