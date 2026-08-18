# IBM Bob Usage — CollisionGuard AI

> This document records how IBM Bob was used as the primary development tool
> for CollisionGuard AI. All claims are supported by the current repository files.

---

## What IBM Bob is

IBM Bob is an AI-powered software engineering tool that provides an interactive
development environment combining code generation, architecture planning, test
writing, debugging, and documentation — all operating directly on the repository
files.

---

## Role in this project

IBM Bob was the primary development tool for CollisionGuard AI across all
eight phases. The human team provided:
- Project requirements and constraints
- Domain knowledge (orbital mechanics, IBM challenge rules)
- Code review and approval at each phase
- Corrections when Bob's output violated project constraints
- Final decision on every merge

IBM Bob provided:
- Phase-by-phase architecture plans (plan mode)
- Complete implementation of all backend modules
- Complete implementation of all frontend components
- Test generation for every phase
- Debugging of Windows/Python-specific issues (CP-1252 encoding, sgp4 C extension)
- All documentation files (Phase 8)

---

## Planning

Bob's plan mode was used to produce the initial architecture and each
phase plan before any code was written. The session context included:
- Project requirements and scope
- Stack constraints (sgp4 not poliastro, pydantic v2, watsonx.ai)
- Safety architecture decisions (Granite authority limits)
- Windows-specific constraints (pure ASCII in .py files)

Evidence: The Phase 8 plan in this session includes a complete repository
inspection and gap analysis before any file was modified.

---

## Architecture

Bob designed the component boundaries, data flow, and safety architecture:
- Separation of deterministic physics from AI advisory
- Numeric grounding guardrail structure
- Two-step human approval protocol
- In-memory cache key design (SHA-256 of TLE + epoch)
- CORS configuration and the DELETE method gap (discovered in Phase 8)

Evidence: `docs/ARCHITECTURE.md` reflects this architecture as implemented.

---

## Implementation phases

Bob wrote the implementation for each phase in order:

| Phase | Key deliverables |
|---|---|
| Phase 1 | FastAPI skeleton, Pydantic schemas, synthetic scenarios, health endpoint |
| Phase 2 | SGP4 propagation, Brent's method TCA search, TEME frame rationale |
| Phase 3 | Maneuver candidate definitions |
| Phase 4 | Safety evaluator: Tsiolkovsky fuel, post-maneuver TCA, baseline score |
| Phase 5 | Monte Carlo 1,000-trial robustness checker |
| Phase 6 | Granite client, numeric grounding, deterministic fallback |
| Phase 6.5 | Config validation hardening, credential safety |
| Phase 7 | Cache, full analysis endpoint, approval gate, execution, incident report |
| Phase 7 | React/Vite dashboard: App.jsx + all components |
| Phase 8 | CORS fix, README rewrite, all docs/ files |

---

## Debugging

Bob identified and fixed several non-obvious issues during development:

1. **Windows CP-1252 encoding error**: Python 3.12 on Windows raised
   `SyntaxError` for non-ASCII characters (em-dashes, arrows) in source files.
   All backend `.py` files were converted to pure ASCII.

2. **`sgp4` Satrec copy issue**: C extension objects cannot be `copy.copy()`-d.
   Post-maneuver orbit construction was refactored to use `_satrec_from_rv()`
   which synthesizes a new TLE from Keplerian elements.

3. **`skyfield` Terrestrial Time offset**: `ts.tt_jd` uses TT, not UTC.
   The roughly 69-second difference would produce a ~400 km along-track error.
   `sgp4.api.jday` (UTC-based) is used instead; `skyfield` was removed from
   the propagation path.

4. **CORS DELETE method gap**: The frontend's `apiDel` calls DELETE for cache
   invalidation, but `main.py` only allowed GET and POST in CORS. Discovered
   and fixed in Phase 8.

5. **`_PENDING_APPROVALS` location**: Tests that needed to clear the approval
   store had to import from `routers.analysis`, not `analysis_cache`.

---

## Test generation

Bob generated the complete test suite across all phases:
- Every test file in `backend/tests/` was Bob-generated
- Tests cover happy paths, error paths, boundary conditions, and safety invariants
- Mocked Granite tests use `unittest.mock.patch` correctly
- The `@pytest.mark.slow` decoration and `pytest.ini` registration were
  implemented to defer the real 1,000-trial test

---

## Documentation

Phase 8 documentation was written entirely by Bob:
- `README.md` — full rewrite from Phase 1 stub to comprehensive project document
- `docs/ARCHITECTURE.md`
- `docs/API_REFERENCE.md`
- `docs/SCIENTIFIC_ASSUMPTIONS.md`
- `docs/SAFETY_AND_RESPONSIBLE_USE.md`
- `docs/TESTING.md`
- `docs/IBM_BOB_USAGE.md` (this file)
- `docs/TEAM_HANDOFF.md`
- `docs/SUBMISSION_COPY.md`
- `docs/CURRENT_STATUS.md`
- `docs/DEMO_VIDEO_PLAN.md`

---

## Human corrections applied

The following corrections were applied by the human team during development:

- **TEME-to-GCRS removal**: The human team manually edited `propagation.py`
  to remove the skyfield GCRS conversion, with the correct rationale that
  relative distance is frame-invariant when both objects are in the same frame.
- **`_TS` removal**: The skyfield timescale object was removed from
  `propagation.py` after the GCRS conversion was removed.
- **Scope constraints**: The human team rejected any Bob-proposed feature that
  exceeded the two-object LEO prototype scope (no multi-satellite, no asteroids).
- **Language constraints**: The human team enforced correct framing language
  ("human-supervised decision-support prototype", never "autonomous" or "flight-ready").

---

## Limitations encountered

- Bob's initial suggestions sometimes used non-ASCII characters that caused
  Windows CP-1252 encoding errors.
- Bob's first implementation used `copy.copy()` on sgp4 Satrec objects, which
  fails with C extensions — corrected to `model_copy(deep=True)` and
  `_satrec_from_rv()`.
- Bob's initial README was Phase-1-level and required a complete rewrite in Phase 8.
- Bob correctly identified the CORS DELETE gap in Phase 8 and did not attempt
  to discover it earlier without being asked.

---

## Evidence template

When preparing submission materials, take screenshots of:

1. **Bob session showing planning dialogue** — the phase plan output with
   architecture decisions visible
2. **Bob session showing implementation** — Bob writing a non-trivial module
   (e.g., `maneuver_evaluator.py` or `granite_client.py`)
3. **Bob session showing test generation** — Bob writing test assertions
4. **Bob session showing Phase 8 documentation writing** — this session
5. **git log or diff** — showing the volume of Bob-assisted commits

---

## Recommended screenshots

For IBM Bob usage proof in the submission:

1. Screenshot of Bob's plan-mode output for Phase 1 or Phase 8
2. Screenshot of Bob writing `granite_client.py` with the numeric grounding section
3. Screenshot of Bob writing tests that cover the safety gate
4. Screenshot of Bob's CORS gap identification and fix
5. Screenshot of Bob writing `TEAM_HANDOFF.md` with equal-difficulty assignments
6. Any screenshot showing Bob reading source code and producing a grounded answer
   (not speculating about code it hasn't inspected)

---

## Truthful log template

For submission, use this format for the Bob usage log:

```
Phase [N] — [date]
Tool: IBM Bob (agent mode / plan mode)
Task: [brief description]
Bob action: [what Bob produced]
Human review: [accepted / corrected / rejected with reason]
Evidence: [file or screenshot reference]
```

Example:
```
Phase 8 — 2025-08-XX
Tool: IBM Bob (agent mode)
Task: CORS bug fix and Phase 8 documentation
Bob action: Identified missing DELETE in allow_methods; wrote test_cors.py;
            rewrote README.md; created all docs/ files
Human review: Accepted; verified against source code
Evidence: git diff main.py; docs/ directory created
```
