# Suryansh Testing Report

## Role
Suryansh — Safety, Performance & Demo/Testing track.

## Completed Work

### 1. REAL 1,000-TRIAL MONTE CARLO VALIDATION
- **Test executed**: Real 1,000-trial Monte Carlo validation
- **Purpose**: To validate the robustness of the collision avoidance system under stochastic conditions
- **Command executed**: pytest tests/test_monte_carlo.py -v -m slow
- **Details**:
  - Exactly 1,000 trials were executed (n_trials=1000)
  - Fixed random seed (rng_seed=42) for reproducibility
  - Assertion: n_robust > 800 (more than 800 trials must be robust/safe)
  - Actual execution time: approximately 111.85 seconds
  - Result: PASSED
- **Production code changes**: None

### 2. APPROVAL-GATE SAFETY RE-VALIDATION TEST
- **Test name**: `test_execute_revalidates_safety_after_approval`
- **File**: `backend/tests/test_phase7.py`
- **Scenario**:
  1. A maneuver candidate is initially safe (based on current orbital data)
  2. The candidate is approved via the `/approve` endpoint
  3. The candidate's safety status is then changed to unsafe (simulating new tracking data)
  4. Execution is attempted using the previously obtained approval
  5. The backend performs server-side re-validation and rejects execution because the candidate is no longer safe
- **Expected HTTP status**: 422 (Unprocessable Entity) with detail "Safety gate: candidate 'MAN-001' is not safe."
- **Actual result**: PASS
- **New test execution time**: ~1.77 seconds
- **Approval/execution test suite**: 10/10 tests passed
- **Safety invariant demonstrated**: "An approval must never be sufficient by itself to execute a maneuver. The backend must re-validate the candidate's safety at execution time."
- **Production code changes**: None

### 3. CACHE TTL EXPIRATION TEST
- **Test name**: `test_analyse_cache_ttl_expiration_forces_refresh`
- **File**: `backend/tests/test_phase7.py`
- **Scenario**:
  1. Populate the cache by calling `/analyse` (cache miss).
  2. Verify a subsequent `/analyse` call returns a cache hit while the entry is within TTL.
  3. Simulate TTL expiration by mocking `time.monotonic()` to advance time just beyond the 300-second TTL.
  4. Make another `/analyse` call and verify it returns a cache miss due to expiration.
  5. Verify that the expired cache entry is removed and fresh analysis is computed.
- **New test result**: PASS
- **Cache-related test suite**: 10/10 tests passed
- **New test execution time**: ~1.84 seconds
- **Production code changes**: None

### 4. ENDPOINT PERFORMANCE BENCHMARK
- **Scenario**: CONJ-001 (the conjunction scenario)
- **Method**: FastAPI TestClient (simulating HTTP requests without network overhead)
- **Granite mode**: Deterministic fallback (no live service calls)
- **Procedure**:
  1. Started with a completely cold cache (via `flush_all()`)
  2. Measured the first `/scenarios/CONJ-001/analyse` request (cache miss)
  3. Confirmed the response had `cached=false`
  4. Made 5 additional requests without flushing the cache (all cache hits)
  5. Recorded elapsed time and `cached` flag for every request
- **Results**:
  - Cold/cache-miss time: 0.6820168495 seconds
  - Warm/cache-hit times:
    - Request 1: 0.0075507164 seconds (cached: True)
    - Request 2: 0.0059919357 seconds (cached: True)
    - Request 3: 0.0070683956 seconds (cached: True)
    - Request 4: 0.0082585812 seconds (cached: True)
    - Request 5: 0.0063989162 seconds (cached: True)
  - Average warm time: 0.0070537090 seconds
  - Minimum warm time: 0.0059919357 seconds
  - Maximum warm time: 0.0082585812 seconds
  - Cold vs. average-warm speedup: approximately 96.7x
- **Validation**:
  - Confirmed `cached=false` for the cold request
  - Confirmed `cached=true` for all warm requests
- **Note**: This is a LOCAL TESTCLIENT BENCHMARK. The measured cold request time (0.68s) is substantially faster than the previously documented ~20s expectation for the full pipeline. This indicates that the deterministic Granite fallback and propagation/evaluation pipelines perform faster than the original estimate in the current test environment. The ~20s figure is not invalidated; it may reflect a different configuration (e.g., live Granite service, different hardware, or inclusion of additional overhead).

### 5. TESTING METHODOLOGY
The work followed a repeatable workflow:
1. **Inspection**: Examine relevant source code, tests, and documentation to understand the current behavior.
2. **Verification**: Confirm what is already tested and working.
3. **Focused test**: Design the smallest, cleanest test that validates a specific property (safety re-validation, cache TTL behavior).
4. **Execution**: Implement the test following existing patterns and run it to verify correctness.
5. **Result recording**: Document the outcome, including test results, execution times, and any relevant metrics, in the project log (`claude-progress.txt`).
6. **Benchmarking**: For performance, follow a controlled procedure to measure cold vs. warm request times using the existing test infrastructure.

### 6. FILES CREATED OR MODIFIED

#### Test/code contribution

- `backend/tests/test_phase7.py`
  - Added `test_execute_revalidates_safety_after_approval`
  - Added `test_analyse_cache_ttl_expiration_forces_refresh`

#### Supporting artifacts

- `performance.txt`
  - Raw endpoint performance benchmark measurements
  - Contains the timestamp, environment, scenario, cold request, five warm requests, cache status, averages, and calculated speedup.

- `performance-results.txt`
  - Benchmark results summary, if this file exists.

- `SURYANSH_TESTING_REPORT.md`
  - This contribution report.

#### Process documentation

- `claude-progress.txt`
  - Development/validation log; not part of the substantive code contribution.

### 7. PRODUCTION CODE IMPACT
- No production implementation files (in `backend/routers/`, `backend/analysis_cache.py`, etc.) were modified for the safety or cache tests.
- The tests validate that the existing safety and cache behaviors are correct and serve as regression guards.
- The endpoint performance benchmark was measurement-only and did not alter any code.

### 8. FINAL CONTRIBUTION SUMMARY
This work contributed to the project by:
- Providing robustness validation via the 1,000-trial Monte Carlo test (completed in a prior session).
- Adding regression protection for the critical safety gate ensuring that approvals cannot bypass execution-time safety checks.
- Adding regression protection for cache correctness ensuring that stale analysis is not used after TTL expiration.
- Delivering measured performance evidence that demonstrates the effectiveness of the caching mechanism (approximately 96.7x speedup for warm requests) and characterizes the actual cold-path performance in the test environment.

## Summary Table

| Area                                      | Test/Measurement                                 | Result     | Production Code Changed |
|-------------------------------------------|--------------------------------------------------|------------|-------------------------|
| 1,000-Trial Monte Carlo Validation        | Real 1,000-trial Monte Carlo test                | PASSED     | No                      |
| Approval-Gate Safety Re-Validation        | `test_execute_revalidates_safety_after_approval` | PASS       | No                      |
| Cache TTL Expiration                      | `test_analyse_cache_ttl_expiration_forces_refresh` | PASS       | No                      |
| Endpoint Performance Benchmark            | Cold/warm request timing for `/analyse`          | 0.682s cold, 0.007s warm avg, 96.7x speedup | No                      |