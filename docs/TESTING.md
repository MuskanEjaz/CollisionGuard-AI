# Testing — CollisionGuard AI

> All test results in this document are based on actual execution unless
> explicitly marked as "not yet executed" or "deferred".

---

## Test environment

- Python: 3.12.7
- pytest: 8.4.2
- Platform: Windows 10 (win32)
- Working directory: `backend/`
- pytest config: `backend/pytest.ini`

---

## pytest marker configuration

`backend/pytest.ini`:
```ini
[pytest]
testpaths = tests

markers =
    slow: marks tests as computationally expensive (deselect with -m "not slow").
          The real 1000-trial Monte Carlo test (test_monte_carlo_real_1000_trials)
          carries this marker and is deferred to the final validation run.
          Do not run it in routine CI -- it takes ~8 minutes on this hardware.
```

---

## Compile and import checks

Before running any tests, verify Python can import the main application:

```powershell
cd backend
python -c "from main import app; print('OK')"
python -c "from granite_client import get_granite_advisory; print('OK')"
python -c "from propagation import propagate_scenario; print('OK')"
```

All three commands should print `OK` with no errors.

---

## Fast test suite

### Run command

```powershell
cd backend
pytest tests/ -v -m "not slow"
```

### Test files and counts (pre-Phase 8)

| File | Tests | Coverage area |
|---|---|---|
| `test_health.py` | 5 | GET /health response schema and fields |
| `test_scenarios.py` | 12 | GET /scenarios, GET /scenarios/{id}, validation errors |
| `test_propagation.py` | 11 | SGP4 propagation, TCA search, Brent's method |
| `test_maneuvers.py` | 8 | Candidate list, direction values, null safety fields |
| `test_evaluator.py` | 13 | Safety gate, Tsiolkovsky, post-maneuver miss, score |
| `test_monte_carlo.py` | 12 | Robustness endpoint, unit function, fast override |
| `test_granite.py` | 42 | Config validation, fallback, parse, numeric grounding, mocked live |
| `test_phase7.py` | 31 | Cache, analyse endpoint, approval, execution, incident report |
| `test_cors.py` | 6 | CORS OPTIONS preflight for DELETE, GET, POST |
| **Total** | **140** | |

### Verified result (Phase 8 verification — actually executed)

```
================ 140 passed, 1 deselected in 452.95s (0:07:32) ================
```

Platform: Python 3.12.7, pytest 8.4.2, win32.
Prior session result (pre-CORS): `134 passed, 1 deselected in 544.73s`.
The 6 CORS preflight tests bring the confirmed total to **140 passed**.

---

## CORS preflight test (Phase 8)

File: `tests/test_cors.py`

These tests verify that the browser CORS preflight works correctly for the
DELETE method used by the cache-invalidation button in the dashboard.

**Why a bare DELETE returning 200 is not sufficient proof:**
Browsers send an OPTIONS preflight request before any non-simple cross-origin
request. The server must respond with `Access-Control-Allow-Origin` and
`Access-Control-Allow-Methods: DELETE` in the OPTIONS response. Without this,
the browser will block the actual DELETE even if the server would have accepted it.

Tests:
- `test_cors_preflight_delete_cache_returns_200` — OPTIONS returns 200
- `test_cors_preflight_delete_allows_origin` — ACAO header is correct
- `test_cors_preflight_delete_allows_delete_method` — ACAM includes DELETE
- `test_cors_delete_actually_works` — bare DELETE returns 200 (sanity)
- `test_cors_preflight_get_still_works` — GET CORS not broken by change
- `test_cors_preflight_post_still_works` — POST CORS not broken by change

### How to run

```powershell
cd backend
pytest tests/test_cors.py -v
```

**Executed result (Phase 8 verification):** 6 passed in 1.51s.

---

## Mocked Granite tests

All 42 tests in `test_granite.py` use mocked Granite responses. They do not
require watsonx credentials and do not make network calls.

Tests verify:
- `_validate_config()` rejects missing or invalid credentials (4 cases)
- `_has_valid_config()` returns correct tuple in all cases
- `_deterministic_fallback()` ranks by score, uses backend values, reports model ID
- `_parse_granite_response()` handles valid JSON, preamble, malformed entries,
  unsafe candidate references, omitted candidates, numeric conflicts
- `get_granite_advisory()` falls back on missing credentials, invalid URL, API errors
- Fallback error messages contain no credential values
- `/advise` endpoint returns correct schema fields
- `model_id` is always reported (never hardcoded)

### How to run

```powershell
cd backend
pytest tests/test_granite.py -v
```

Expected: 42 passed.

---

## Cache tests

Tests in `test_phase7.py` (first 6 tests cover the cache):

- `test_cache_miss_on_empty` — empty cache returns (None, False)
- `test_cache_hit_after_set` — stored entry returned with hit=True
- `test_cache_ttl_expiry` — entry expired after TTL
- `test_cache_invalidate_by_scenario` — invalidate removes correct entries
- `test_cache_stats_reflects_entries` — stats report correct count
- `test_cache_no_credential_values` — cache entries contain no credential strings

---

## Safety tests

Tests across `test_evaluator.py` and `test_phase7.py` verify:

- Unsafe candidates are marked `is_safe=False` with a rejection reason
- Unsafe candidates cannot be approved (POST /approve returns `safety_gate_passed=False`)
- Execution without approval returns HTTP 403
- Approval token is one-use (second execute attempt after first succeeds returns 403)
- Backend uses backend physics values in execution response, not frontend input

---

## Deferred: real 1,000-trial Monte Carlo test

**Status: not yet executed.**

```powershell
cd backend
pytest tests/test_monte_carlo.py -v -m slow
```

Test function: `test_monte_carlo_real_1000_trials` in `test_monte_carlo.py`

This test runs the full 1,000-trial Monte Carlo loop against the CONJ-001
scenario. It verifies that:
1. `n_trials == 1000` (not the override value)
2. `robustness_fraction` is a real computed value, not hardcoded
3. The result is consistent (within statistical bounds) across runs

**This test must be run and pass before final submission.**

Expected duration: approximately 8 minutes on this hardware.

---

## Manual: live Granite smoke test

**Status: not yet verified.**

```powershell
cd backend
python granite_smoke_test.py
```

Prerequisites:
- `.env` file present with:
  - `WATSONX_APIKEY=<real key>`
  - `WATSONX_PROJECT_ID=<real project ID>`
  - `WATSONX_URL=https://<region>.ml.cloud.ibm.com`
  - `WATSONX_MODEL_ID=ibm/granite-3-8b-instruct` (or deployed model)

Expected output on success:
```
[INFO] Model ID : ibm/granite-3-8b-instruct
[INFO] URL      : https://...
[INFO] Project  : ********* (32 chars)
[INFO] API key  : ******** (first chars masked)
[INFO] Sending minimal prompt to ibm/granite-3-8b-instruct ...
[INFO] Response received in X.XXs
[INFO] Raw response (first 200 chars): '{"status": "ok", ...}'
[INFO] Parsed JSON: {'status': 'ok', 'message': 'smoke test passed'}
[PASS] Smoke test succeeded.
```

Exit codes: 0=success, 1=config error, 2=auth error, 3=model unavailable,
4=network error, 5=parse error, 9=unexpected.

**Evidence requirement**: Pushkar must provide a screenshot of successful
smoke test output for the submission.

---

## Frontend tests

No automated frontend tests (Vitest/React Testing Library) are implemented.
No `test` script is present in `frontend/package.json`.

Frontend validation is by build:
```powershell
cd frontend
npm run build
```

**Executed result (Phase 8 verification):** build succeeded in 1m 16s.
Known warning: Plotly chunk `index-DSSRmjNK.js` = 4,870.32 kB / gzip 1,477.37 kB.
This exceeds Vite's 500 kB advisory threshold — expected for react-plotly.js. Not an error.

---

## Clean-clone checklist

To verify the project works on a fresh machine:

```powershell
# 1. Clone the repository
git clone <repo-url>
cd "CollisionGuard AI"

# 2. Configure environment
Copy-Item .env.example .env
# (Edit .env if you have watsonx credentials; leave blank for fallback mode)

# 3. Backend
cd backend
pip install -r requirements.txt
python -c "from main import app; print('Import OK')"

# 4. Run fast tests
pytest tests/ -v -m "not slow"
# Expected: 140 passed

# 5. Start backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Expected: Uvicorn running on http://0.0.0.0:8000

# 6. Frontend (new terminal)
cd frontend
npm install
npm run build
# Expected: build completed
npm run dev
# Expected: Local: http://localhost:5173

# 7. Verify in browser
# Navigate to http://localhost:5173
# Select CONJ-001 and click "Run Deterministic Analysis"
# Expected: full analysis loads within ~60 seconds
```

---

## Evidence requirements for submission

| Item | Who | Evidence type |
|---|---|---|
| 140 fast tests pass | Surya | **DONE** — 140 passed, 452.95 s (Phase 8 verification) |
| CORS preflight tests pass | Surya | **DONE** — 6 passed, 1.51 s (Phase 8 verification) |
| Frontend builds | Muskan | **DONE** — succeeded 1m 16s (Phase 8 verification) |
| Real 1,000-trial MC runs | Surya | Terminal screenshot with `n_trials=1000` in output |
| Granite smoke test passes | Pushkar | Terminal screenshot showing `[PASS]` and model ID |
| Live Granite advisory visible | Pushkar | Dashboard screenshot showing `source="granite"` badge |

Never label an unexecuted test as passed in any submission material.
