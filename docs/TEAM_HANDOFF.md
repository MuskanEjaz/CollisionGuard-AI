# Team Handoff — CollisionGuard AI

> IBM AI Builders Challenge — August 2026
> Simulation only — not flight software.

---

## Overview

Three team members. Equal difficulty target: **8.5/10** each.
Required merge order is specified below. All work is on feature branches;
no direct commits to `main`.

---

## Member assignments

---

### Muskan — UI, Documentation and Submission

**Branch**: `muskan/ui-documentation`
**Difficulty target**: 8.5/10

#### Owned files

| File | Ownership |
|---|---|
| `frontend/src/App.jsx` | Primary |
| `frontend/src/styles.css` | Primary |
| `frontend/src/components/ConjunctionMetrics.jsx` | Primary |
| `frontend/src/components/ManeuverTable.jsx` | Primary |
| `frontend/src/components/GraniteAdvisory.jsx` | Primary |
| `frontend/src/components/TrajectoryPlot.jsx` | Primary |
| `frontend/src/components/ApprovalGate.jsx` | Primary |
| `frontend/src/components/HealthStatus.jsx` | Primary |
| `frontend/src/components/ScenarioPanel.jsx` | Primary |
| `frontend/src/api/client.js` | Primary |
| `README.md` | Primary (final update after merges) |
| `docs/ARCHITECTURE.md` | Review + update |
| `docs/SCIENTIFIC_ASSUMPTIONS.md` | Review |
| `docs/SUBMISSION_COPY.md` | Primary |
| `.env.example` | Review |

#### Files requiring coordination

| File | Coordinate with |
|---|---|
| `frontend/src/components/GraniteAdvisory.jsx` | Pushkar (live Granite badge) |
| `frontend/src/components/ManeuverTable.jsx` | Pushkar (Granite rank column) |
| `frontend/src/api/client.js` | Surya (CORS DELETE method) |
| `README.md` | All (final update after both Surya and Pushkar merge) |

#### Ordered tasks

1. **Verify the dashboard works end-to-end with the fallback path**
   - Start backend (no .env credentials needed)
   - Load CONJ-001, run analysis, step through approval gate
   - Confirm all cards render, no blank panels, no console errors
   - Document any rendering defects

2. **Verify the safe scenario (SAFE-001) renders correctly**
   - Green "Safe separation" badge
   - No conjunction-specific warnings shown
   - Maneuver table still populates (for reference)

3. **Review data quality and uncertainty panels**
   - Confirm `risk_basis_label` is shown (not silently dropped)
   - Confirm `orbit_element_age_note` is shown
   - Confirm `evaluation_note` is shown in the maneuver card

4. **Review loading and error states**
   - Test with backend stopped: confirm error message renders
   - Test with slow backend: confirm spinner shows
   - Empty scenario list: confirm "No scenarios loaded" renders

5. **Review the Granite advisory component**
   - Fallback badge: "Deterministic fallback — Granite unavailable"
   - Live badge (coordinate with Pushkar after live Granite is confirmed):
     `IBM Granite — Live (ibm/granite-3-8b-instruct)`
   - Validation warnings rendered if present
   - `granite_note` rendered

6. **TrajectoryPlot disclaimer**
   - Confirm "SIMPLIFIED FOR PROTOTYPE: Orbits shown as approximate circular
     paths. Not a real ephemeris." is visible in the plot card

7. **ApprovalGate final review**
   - Confirm all state transitions render correctly
   - Confirm the confirmation dialog shows the warning in yellow
   - Confirm incident report renders after execution

8. **Final README update** (after Surya and Pushkar merges)
   - Update the "Verified results" table with final test counts
   - Add Surya's video URL when provided
   - Update the demo run commands if any paths changed

9. **Submission copy review**
   - Review `docs/SUBMISSION_COPY.md`
   - Ensure language matches actual system capabilities
   - No invented metrics or results

10. **GitHub presentation**
    - Repository description set
    - Topics: `ibm-watsonx-ai`, `space-exploration`, `orbital-mechanics`,
      `fastapi`, `react`, `collision-avoidance`
    - Pinned repository with cover image if desired

#### Dependencies

- Surya's CORS fix must be merged before Muskan's DELETE cache button works in browser
- Pushkar's live Granite result is needed to update the Granite badge screenshot

#### Blockers

- Live Granite badge screenshot cannot be taken until Pushkar verifies live access
- Final README video URL requires Surya to record and upload

#### Acceptance criteria

- [ ] Dashboard renders correctly for both scenarios without console errors
- [ ] Safe scenario shows green badge, conjunction scenario shows red badge
- [ ] Risk basis label and orbit element age note visible for both scenarios
- [ ] Loading spinner shows while analysis is in progress
- [ ] Error state renders when backend is unreachable
- [ ] Granite fallback badge visible when no credentials
- [ ] Approval gate completes full flow: idle -> confirming -> done
- [ ] Incident report text displays after execution
- [ ] `npm run build` succeeds with no errors
- [ ] README updated with final test counts, Surya's video URL, and correct env var names

#### Required tests

- Frontend build: `npm run build` (no errors)
- Visual verification of both scenarios (screenshot evidence)
- Error-state verification (backend stopped — screenshot)

#### Required evidence

- Screenshot: CONJ-001 analysis showing red badge, miss distance, maneuver table
- Screenshot: SAFE-001 analysis showing green badge
- Screenshot: approval gate confirmation dialog
- Screenshot: execution complete + incident report
- Screenshot: `npm run build` terminal output

#### Definition of done

All 10 tasks complete, all acceptance criteria met, screenshots provided,
`README.md` updated with final data after merges.

---

### Pushkar — Granite and Grounded Intelligence

**Branch**: `pushkar/live-granite`
**Difficulty target**: 8.5/10

#### Owned files

| File | Ownership |
|---|---|
| `backend/granite_client.py` | Primary |
| `backend/granite_smoke_test.py` | Primary |
| `backend/routers/granite.py` | Primary |
| `backend/schemas/granite.py` | Primary |
| `backend/tests/test_granite.py` | Primary |
| `docs/IBM_BOB_USAGE.md` | Review + Bob evidence |

#### Files requiring coordination

| File | Coordinate with |
|---|---|
| `backend/routers/analysis.py` | Surya (incident report Granite path) |
| `frontend/src/components/GraniteAdvisory.jsx` | Muskan (live badge display) |
| `frontend/src/components/ManeuverTable.jsx` | Muskan (Granite rank column) |

#### Ordered tasks

1. **Obtain watsonx credentials**
   - IBM watsonx.ai account with a deployed Granite model
   - Create `backend/.env` with:
     ```
     WATSONX_APIKEY=<real key>
     WATSONX_PROJECT_ID=<real project ID>
     WATSONX_URL=https://<region>.ml.cloud.ibm.com
     WATSONX_MODEL_ID=ibm/granite-3-8b-instruct
     ```
   - Confirm the `.env` file is in `.gitignore` and will not be committed

2. **Run the Granite smoke test**
   ```powershell
   cd backend
   python granite_smoke_test.py
   ```
   - Expected exit code: 0
   - Expected: `[PASS] Smoke test succeeded.` with model ID and latency
   - If model ID fails (exit code 3): update `WATSONX_MODEL_ID` to an accessible model
   - Take a terminal screenshot as submission evidence

3. **Verify live Granite advisory in the full pipeline**
   - Start the backend with `.env` containing real credentials
   - Load CONJ-001 in the dashboard
   - Click "Run Deterministic Analysis"
   - Confirm the Granite advisory card shows:
     - `source: "granite"` (not `"deterministic_fallback"`)
     - Live model badge: `IBM Granite — Live (ibm/granite-3-8b-instruct)`
     - Ranked candidates with Granite explanations
   - Take a dashboard screenshot as submission evidence

4. **Review Granite prompt quality**
   - Check the explanations are coherent and reference correct candidate IDs
   - Check the summary paragraph is meaningful
   - If explanations are poor, tune the prompt in `_build_prompt()` and re-test
   - Do not change numeric fields — only the explanatory text path

5. **Verify numeric grounding under live conditions**
   - If Granite returns any numeric values that trigger warnings,
     confirm the warnings appear in `validation_warnings` in the response
   - Confirm backend values are always used in the displayed table

6. **Test malformed-response handling under live conditions**
   - If possible, temporarily corrupt the prompt to trigger a parse failure
   - Confirm fallback is used and `source="deterministic_fallback"`
   - Revert the prompt after testing

7. **Verify incident report with live Granite**
   - Complete a full approval and execution in the dashboard
   - Confirm incident report card shows `generated_by: "granite"`
   - Take a screenshot

8. **Document Granite evidence for submission**
   - Update `docs/IBM_BOB_USAGE.md` with Granite evidence screenshots
   - Confirm `docs/SUBMISSION_COPY.md` AI approach section is accurate

9. **Run all Granite tests with credentials present**
   ```powershell
   cd backend
   pytest tests/test_granite.py -v
   ```
   - All 42 mocked tests should still pass (they do not use credentials)
   - The smoke test is separate from pytest

10. **Review `model_id` field in advisory response**
    - Confirm `model_id` matches the deployed model in the response
    - The value must come from `settings.watsonx_model_id` — never hardcoded

#### Dependencies

- Live access to IBM watsonx.ai with a deployed Granite model
- Smoke test must pass before dashboard verification

#### Blockers

- No watsonx account or invalid credentials will block tasks 2–8
- If `ibm/granite-3-8b-instruct` is not available in the project, update
  `WATSONX_MODEL_ID` to a deployed model ID

#### Acceptance criteria

- [ ] `granite_smoke_test.py` exits with code 0 and prints `[PASS]`
- [ ] Dashboard shows `source: "granite"` advisory for CONJ-001
- [ ] Live model badge displays correct model ID
- [ ] Granite explanations are coherent and reference correct candidate IDs
- [ ] Incident report shows `generated_by: "granite"` after live execution
- [ ] All 42 `test_granite.py` tests still pass after any prompt changes
- [ ] No credential values appear in any response, log, or screenshot
- [ ] `docs/SUBMISSION_COPY.md` AI section is accurate and truthful

#### Required tests

- `pytest tests/test_granite.py -v` — 42 passed
- `python granite_smoke_test.py` — exit code 0

#### Required evidence

- Screenshot: smoke test terminal output (`[PASS]`, model ID, latency)
- Screenshot: dashboard showing live Granite badge with model ID
- Screenshot: ranked candidates with Granite explanations
- Screenshot: incident report generated by Granite

#### Definition of done

Smoke test passes, live Granite advisory confirmed in dashboard, all
mocked tests still pass, evidence screenshots provided.

---

### Surya — Safety, Performance and Demo Video

**Branch**: `surya/safety-performance-demo`
**Difficulty target**: 8.5/10

#### Owned files

| File | Ownership |
|---|---|
| `backend/main.py` | Primary (CORS) |
| `backend/tests/test_cors.py` | Primary |
| `backend/tests/test_phase7.py` | Primary (approval/execution tests) |
| `backend/routers/analysis.py` | Review (approval/execution routes) |
| `backend/analysis_cache.py` | Review (cache correctness) |
| `docs/DEMO_VIDEO_PLAN.md` | Primary (video production) |

#### Files requiring coordination

| File | Coordinate with |
|---|---|
| `backend/main.py` | All (CORS affects all HTTP methods) |
| `backend/routers/analysis.py` | Pushkar (incident report route) |

#### Ordered tasks

1. **Verify the CORS fix (already applied)**
   ```powershell
   cd backend
   pytest tests/test_cors.py -v
   ```
   - All 6 CORS preflight tests must pass
   - Confirm `main.py` `allow_methods` includes DELETE
   - Take a terminal screenshot

2. **Run the full fast test suite**
   ```powershell
   cd backend
   pytest tests/ -v -m "not slow"
   ```
   - Expected: 140 passed (134 pre-Phase 8 + 6 CORS tests)
   - Record exact pass count and duration
   - Take a terminal screenshot for submission evidence

3. **Run the real 1,000-trial Monte Carlo test**
   ```powershell
   cd backend
   pytest tests/test_monte_carlo.py -v -m slow
   ```
   - This is the deferred slow test
   - Expected: 1 passed; `n_trials=1000` in the output (not the override value)
   - Duration: approximately 8 minutes
   - Take a terminal screenshot showing `n_trials=1000` and `PASSED`
   - Record `robustness_label` value from the response for submission

4. **Verify approval gate safety**
   - Run the approval/execution tests manually against a live backend
   - Confirm unsafe candidates produce `safety_gate_passed: false`
   - Confirm execution without approval returns 403
   - Confirm one-use approval token: second execute fails with 403

5. **Run the endpoint performance check**
   - Time the `/analyse` endpoint:
     ```powershell
     $start = Get-Date
     Invoke-RestMethod -Uri "http://localhost:8000/scenarios/CONJ-001/analyse" -Method POST
     $end = Get-Date
     ($end - $start).TotalSeconds
     ```
   - Cache miss should be 20–60 seconds (acceptable for prototype)
   - Cache hit should be < 1 second
   - Note both durations for submission / demo narration

6. **Verify cache invalidation in the browser**
   - With backend running and CORS fix active, open the dashboard
   - Run analysis on CONJ-001 (cached flag should be false on first run)
   - Click "Refresh" (calls DELETE /scenarios/CONJ-001/cache)
   - Re-run analysis (cached flag should be false again)
   - Confirm no CORS error in browser DevTools Network tab

7. **Read `docs/DEMO_VIDEO_PLAN.md`** and prepare for recording
   - Follow the pre-recording checklist
   - Practice the click sequence until it can be completed in under 3 minutes
   - Confirm which path to record: live Granite or fallback
   - Coordinate with Pushkar on Granite availability before recording

8. **Record the demo video**
   - Follow the script in `docs/DEMO_VIDEO_PLAN.md` exactly
   - Maximum duration: 3 minutes
   - Recommended filename: `CollisionGuard_AI_Demo.mp4`
   - Do not show credentials on screen at any point

9. **Upload the video**
   - Upload to a public-access platform (YouTube unlisted or equivalent)
   - Verify the link is publicly accessible without login
   - Note the public URL

10. **Provide video URL to Muskan**
    - Muskan updates `README.md` with the final URL
    - Muskan updates `docs/SUBMISSION_COPY.md` with the final URL

#### Dependencies

- CORS fix already applied to `main.py` (Phase 8)
- Real 1,000-trial Monte Carlo must complete before recording (for honest narration)
- Pushkar's Granite availability must be confirmed before choosing recording path

#### Blockers

- Real 1,000-trial test takes ~8 minutes — plan accordingly
- Video upload requires a public hosting account

#### Acceptance criteria

- [ ] 6 CORS preflight tests pass
- [ ] Full fast suite: 140 tests pass
- [ ] Real 1,000-trial Monte Carlo passes with `n_trials=1000`
- [ ] Cache invalidation works in browser (no CORS error in DevTools)
- [ ] Demo video is under 3 minutes
- [ ] Video link is publicly accessible without login
- [ ] Video shows complete decision loop: select scenario -> analysis -> approval -> execution
- [ ] Video does not call the system "autonomous" or "flight-ready"
- [ ] Video does not show any credential values

#### Required tests

- `pytest tests/test_cors.py -v` — 6 passed
- `pytest tests/ -v -m "not slow"` — 140 passed
- `pytest tests/test_monte_carlo.py -v -m slow` — 1 passed, `n_trials=1000`

#### Required evidence

- Screenshot: CORS test terminal output
- Screenshot: full fast test suite terminal output (140 passed)
- Screenshot: slow Monte Carlo terminal output (`n_trials=1000`, `PASSED`)
- Screenshot: browser DevTools Network tab showing DELETE /cache with 200 (no CORS error)
- Public URL: `CollisionGuard_AI_Demo.mp4`

#### Definition of done

All tests pass, real MC executed, demo video recorded and publicly uploaded,
link provided to Muskan.

---

## Shared-file ownership table

| File | Primary | Reviewer |
|---|---|---|
| `backend/main.py` | Surya | All |
| `backend/routers/analysis.py` | Surya (approval/execute) | Pushkar (incident report) |
| `README.md` | Muskan (final update) | All |
| `docs/SUBMISSION_COPY.md` | Muskan | Pushkar |
| `docs/DEMO_VIDEO_PLAN.md` | Surya | All |
| `.env.example` | Muskan (review) | Pushkar (credential names) |

---

## API contract freeze

The following API contracts are **frozen**. Do not change method, path, or
response schema without notifying all team members:

- `POST /scenarios/{id}/analyse` → `FullAnalysisResponse`
- `POST /scenarios/{id}/approve` → `ExecutionApprovedResponse`
- `POST /scenarios/{id}/execute` → `ExecutionStatus`
- `POST /scenarios/{id}/incident-report` → `IncidentReport`
- `DELETE /scenarios/{id}/cache` → `{"scenario_id": str, "entries_removed": int}`
- `GET /health` → `HealthResponse`

Adding new optional fields is allowed (backward-compatible). Removing or
renaming existing fields is not allowed without team agreement.

---

## Merge order

```
1. surya/safety-performance-demo  (CORS fix + all backend safety tests)
       |
       v
2. pushkar/live-granite            (live Granite verification + prompt tuning)
       |
       v
3. muskan/ui-documentation         (UI integration against final APIs)
       |
       v
4. muskan/ui-documentation         (README final update with test counts + video URL)
       |
       v
5. Surya records demo video against the fully merged main branch
       |
       v
6. All members conduct final review before submission
```

No member may merge to `main` until the branch above them is merged. Step 4
(README update) is a second commit on Muskan's branch or a separate
`muskan/readme-final` branch.

---

## Pull-request rules

1. Every PR requires at least one approved review from another team member
2. All CI fast tests (140) must pass before merge
3. No credential values may appear in any file in the PR
4. PR description must list: files changed, purpose of change, test evidence
5. The merging member is responsible for resolving any conflicts

---

## Review assignments

| PR from | Reviewed by |
|---|---|
| `surya/safety-performance-demo` | Pushkar (logic review) + Muskan (README impact) |
| `pushkar/live-granite` | Surya (security: no credentials in code) + Muskan (UI impact) |
| `muskan/ui-documentation` | Surya (frontend build) + Pushkar (Granite badge accuracy) |

---

## Daily status format

Each member sends a one-line status daily in the team channel:

```
[NAME] [DATE] — Done: [X]. In progress: [Y]. Blocked: [Z or "nothing"].
```

Example:
```
[Pushkar] 2025-08-10 — Done: smoke test passing. In progress: prompt tuning.
Blocked: nothing.
```

---

## Conflict resolution

1. Technical disagreements: raise in team channel with specific file/line reference
2. Unresolved after 24 hours: default to the implementation already in `main`
3. Safety-critical disagreements (anything affecting the approval gate or Granite
   authority): default to the more restrictive option
4. Never weaken a safety invariant to resolve a merge conflict

---

## Final integration checklist

Before submitting to the IBM AI Builders Challenge:

- [ ] `surya/safety-performance-demo` merged to `main`
- [ ] `pushkar/live-granite` merged to `main`
- [ ] `muskan/ui-documentation` merged to `main`
- [ ] `pytest tests/ -v -m "not slow"` passes: 140 tests
- [ ] `pytest tests/test_monte_carlo.py -v -m slow` passes: `n_trials=1000`
- [ ] `python granite_smoke_test.py` exits 0 (Pushkar provides evidence)
- [ ] `npm run build` completes with no errors
- [ ] Demo video recorded, under 3 minutes, publicly accessible
- [ ] `README.md` updated with final test count, video URL, and correct env var names
- [ ] No `.env` file committed
- [ ] No credential values in any committed file
- [ ] `docs/SUBMISSION_COPY.md` reviewed by all members
- [ ] Challenge submission form completed
- [ ] GitHub repository description and topics set
