# Submission Copy — CollisionGuard AI

> Draft submission content for the IBM AI Builders Challenge.
> All claims are based on the actual repository state.
> Replace all [PLACEHOLDER] markers with real values before submitting.

---

## Project title

CollisionGuard AI

---

## One-line pitch

A human-supervised satellite collision-avoidance decision-support prototype
that delivers physics-grounded maneuver recommendations, IBM Granite advisory
ranking, and a mandatory human approval gate — all within a mission-control
dashboard.

---

## Short description (150 words max)

CollisionGuard AI helps a human satellite operator respond to a predicted
conjunction alert. Given TLE orbital data for two LEO objects, it propagates
both orbits using SGP4, finds the closest approach via Brent's method, evaluates
candidate avoidance maneuvers through a deterministic safety gate, and presents
IBM Granite's advisory ranking to the operator.

The system enforces human oversight architecturally: unsafe candidates never
reach Granite; Granite output is validated against backend physics values and
cannot override a safety rejection; and every simulated execution requires two
explicit operator confirmation steps.

The complete decision loop — detect, predict, assess, plan, advise, approve,
simulate, verify, report — runs end-to-end in a dark mission-control React
dashboard backed by a FastAPI Python service. The prototype is honest about its
limitations: all results are labelled as screening-level estimates from synthetic
data.

---

## Problem

More than 27,000 tracked objects orbit Earth today, with hundreds of thousands
of smaller untracked fragments. Every tracked satellite faces hundreds of
conjunction screening events per year. A typical operator has minutes to review
each alert, interpret propagation geometry, evaluate candidate maneuvers, and
decide whether to command a burn.

A wrong choice either wastes propellant (a limited resource) or allows a
potentially catastrophic collision. The Kessler cascade scenario — where one
collision generates thousands of new debris fragments threatening further
satellites — makes this problem critical for the long-term health of the LEO
environment and the services it supports.

---

## Solution

CollisionGuard AI compresses the conjunction decision loop into a single
dashboard screen:

1. **Propagation**: SGP4 propagation of both objects over 24 hours; two-stage
   TCA search (coarse 30-second grid + Brent's method refinement)
2. **Risk assessment**: Miss distance vs 1 km conjunction threshold;
   three-level risk classification (Conjunction / Monitoring / Safe)
3. **Maneuver evaluation**: 5 candidate delta-v maneuvers evaluated by a
   deterministic safety gate — fuel cost (Tsiolkovsky), post-maneuver miss
   distance, improvement threshold
4. **IBM Granite advisory**: Ranking of safe candidates with explanations;
   all physics values validated against backend and corrected if wrong
5. **Human approval gate**: Two-step confirmation; backend re-validates safety
   at each step; one-use approval token
6. **Simulated execution**: Reports the physics result of the selected maneuver;
   produces a simulated incident report

The operator makes every consequential decision. The system supports, not
replaces, human judgment.

---

## Innovation

**Numeric grounding guardrail**: Every numeric value IBM Granite returns is
validated against the backend-computed value at 1% relative tolerance. If
Granite states a conflicting value, the backend value is used and a warning
is shown. Granite cannot alter mission-critical numbers — only advisory text.

**Two-stage TCA search**: Custom Brent's parabolic interpolation implemented
without `scipy`, achieving 0.01-second TCA accuracy within a 24-hour window.

**Architecturally enforced human oversight**: The safety gate, approval token,
and Granite authority limits are not UI conventions — they are structural
constraints in the code that Granite cannot circumvent.

**Honest uncertainty labelling**: Every metric carries a basis label
("screening-level estimate", "demonstration Pc based on synthetic covariance").
The prototype does not overstate its capabilities.

---

## Technical execution

- **Backend**: Python 3.12, FastAPI 0.111, Pydantic v2, sgp4 2.x, NumPy
- **Frontend**: React 18, Vite 5, react-plotly.js for 3D trajectory
- **AI**: IBM Granite (ibm/granite-3-8b-instruct) via watsonx.ai;
  full deterministic fallback when credentials are absent
- **Tests**: 140 fast backend tests (verified); real 1,000-trial Monte Carlo
  deferred per pytest.mark.slow convention
- **CORS**: GET, POST, DELETE methods permitted; browser preflight verified
- **No external optimisation libraries**: Brent's method implemented manually;
  no scipy dependency

---

## AI approach

IBM Granite (ibm/granite-3-8b-instruct, configurable via `WATSONX_MODEL_ID`)
is used for:
- Advisory ranking of safe maneuver candidates (rank + one-sentence explanation)
- Operator-facing summary paragraph
- Simulated incident report narrative

Granite's authority is explicitly constrained by the system design:
- Receives only backend-validated safe candidates
- Cannot modify miss distance, fuel cost, or safety determination
- Cannot approve or veto execution
- All numeric values validated at 1% tolerance; conflicts override to backend value

When Granite is unavailable, a deterministic score-based fallback produces
equivalent output. The `source` field in every response distinguishes live
Granite from fallback.

**Live Granite verification status**: [PLACEHOLDER — Pushkar to confirm after
smoke test and update this section with evidence before submission.]

---

## IBM Bob usage

IBM Bob was the primary development tool for all eight phases of this project.
Bob performed architecture planning, complete backend and frontend implementation,
test generation, debugging (Windows encoding issues, sgp4 C extension handling),
and documentation writing.

Human team members provided requirements, domain knowledge, code review, and
approved or corrected every Bob output. All files in this repository reflect
human-reviewed, human-approved content.

See `docs/IBM_BOB_USAGE.md` for detailed evidence and session log templates.

---

## Challenge fit

The IBM AI Builders Challenge theme is "Advance Space Exploration with AI."
CollisionGuard AI directly addresses the LEO orbital safety challenge — a
critical barrier to sustainable space exploration — using IBM Granite as an
advisory intelligence layer within a human-supervised decision loop.

The prototype demonstrates responsible AI integration in a safety-critical
domain: AI provides advisory value but cannot override human judgment or
deterministic safety constraints.

---

## Feasibility

The prototype runs on a laptop with Python 3.12 and Node.js 18:
- Backend: `pip install -r requirements.txt && uvicorn main:app --reload`
- Frontend: `npm install && npm run dev`
- No cloud infrastructure required
- No watsonx credentials required for the complete workflow (deterministic fallback)
- Both scenarios produce a full analysis within 60 seconds of a fresh install

---

## Real-world impact

CollisionGuard AI demonstrates that the conjunction decision loop — currently
a slow, expert-intensive process — can be augmented by AI to deliver clearer,
faster, better-supported operator decisions.

Key impact areas:
- **Collision prevention**: Earlier, better-informed maneuver decisions reduce
  collision risk and propellant waste
- **Kessler cascade prevention**: Each avoided collision eliminates thousands
  of potential new debris fragments
- **Operator support**: Reduces cognitive load during high-pressure conjunction
  response windows
- **Responsible AI**: Demonstrates how AI advisory systems can be constrained
  to advisory-only roles in safety-critical workflows

The prototype is intentionally scoped to two-object LEO scenarios to demonstrate
the concept clearly. The architecture is designed to be extensible to multi-object
screening and live data integration.

---

## Limitations

- Synthetic TLEs only — no live CelesTrak or Space-Track data ingestion
- Two-object scope — no multi-satellite coordination
- Screening-level miss distance — no Pc calculation
- Circular orbit visualisation — the 3D display approximates orbits as circles
- No user authentication — placeholder operator_id only
- In-memory cache — resets on server restart
- Live Granite has not been verified in automated tests — all Granite tests use mocked responses
- Real 1,000-trial Monte Carlo deferred to final validation

---

## Future work

- Live OMM/CDM ingestion from CelesTrak or Space-Track
- Real covariance data and Pc calculation
- Multi-object conjunction screening
- Optimal delta-v targeting (differential correction)
- User authentication and audit trail
- Persistent approval database
- J2 and atmospheric drag perturbation modelling
- Frontend automated testing (Vitest)

---

## Team contributions

| Member | Contribution |
|---|---|
| **Muskan** | Mission-control dashboard UI, all React components, final README, architecture review, documentation coordination, challenge submission |
| **Pushkar** | IBM Granite integration, numeric grounding guardrail, deterministic fallback, Granite live verification, AI submission evidence |
| **Surya** | CORS correctness, approval/execution safety gate, backend performance, real 1,000-trial Monte Carlo, demo video recording and upload |

---

## GitHub repository URL

[PLACEHOLDER — insert final public GitHub URL before submitting]

---

## Demo video URL

[PLACEHOLDER — Surya will record and upload CollisionGuard_AI_Demo.mp4]

Maximum duration: 3 minutes.
The video demonstrates both scenarios and the complete approval gate workflow.
