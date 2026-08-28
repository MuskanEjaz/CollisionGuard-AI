CollisionGuard AI

Human-supervised collision-avoidance decision support for low-Earth orbit






[!IMPORTANT]
Simulation only — not flight software.

CollisionGuard AI is a hackathon decision-support prototype. It is not autonomous, certified, flight-ready, or suitable for operational spacecraft control. Every maneuver requires explicit human approval and is executed only in simulation.

The pitch

CollisionGuard AI turns orbital-element data into a transparent conjunction-response workflow: propagate two objects, find their closest approach, disclose the uncertainty behind the risk estimate, compare avoidance maneuvers, obtain a grounded IBM Granite advisory, require human approval, verify the simulated result, and generate an incident report.

Deterministic software owns the physics and safety decisions. IBM Granite supports explanation and ranking. The human operator remains in control.

Why it matters

Low-Earth orbit is increasingly congested. When a protected satellite and another tracked object approach one another, an operator must quickly answer:

When will closest approach occur?

What are the predicted miss distance and relative velocity?

What data and uncertainty support the risk estimate?

Which maneuver improves separation without wasting excessive fuel?

Does the recommendation remain safe under perturbations?

Can the decision be reviewed, approved, verified, and documented?

Existing conjunction workflows can be information-dense and fragmented. CollisionGuard AI presents the decision chain in one explainable mission-control interface.

What the system does

For exactly two LEO objects—a protected satellite and one threat object—the system:

Loads a committed synthetic scenario or fetches public CelesTrak GP elements.

Initializes SGP4-compatible orbital records.

Propagates both objects in the TEME frame.

Searches for the time of closest approach (TCA).

Computes miss distance and relative velocity at TCA.

Labels the estimate according to its actual data and uncertainty basis.

Generates five bounded candidate delta-v maneuvers.

Re-propagates and evaluates each candidate for safety, fuel, and separation.

Performs robustness evaluation when explicitly requested.

Sends only backend-approved safe candidates to IBM Granite.

Requires human approval before simulated execution.

Verifies the post-maneuver outcome and produces an incident report.

No final analysis number is hardcoded in the React interface. Results shown to the operator come from the backend contract.

Complete decision loop

flowchart TD
    A["Synthetic scenario or CelesTrak GP data"] --> B["SGP4 propagation"]
    B --> C["TCA, miss distance and relative velocity"]
    C --> D["Risk and uncertainty disclosure"]
    D --> E["Five candidate maneuvers"]
    E --> F["Re-propagation and safety gates"]
    F --> G["Robustness evaluation"]
    G --> H["Granite advisory for safe candidates"]
    H --> I["Human approval"]
    I --> J["Simulated execution"]
    J --> K["Verification and incident report"]

Why CollisionGuard AI is different

1. Physics and AI have separate authority

SGP4 propagation, TCA, miss distance, relative velocity, delta-v, fuel estimates, safety constraints, and post-maneuver results are computed by deterministic backend modules.

IBM Granite may rank and explain safe alternatives, but it cannot:

Create orbital-mechanics values

Change a backend-computed number

Reclassify an unsafe candidate as safe

Approve or execute a maneuver

Bypass the human operator

2. AI output is numerically grounded

Granite responses are checked against backend-computed values before display. If an AI-provided number conflicts with the physics layer, the backend value remains authoritative and the response can carry a validation warning.

3. Uncertainty is shown, not hidden

The interface distinguishes between:

Synthetic demonstration data, where the uncertainty basis is explicitly labelled as synthetic

Live CelesTrak public GP elements, which do not provide operational conjunction covariance

The live-data path is therefore described as a screening-level estimate, not an operational probability of collision.

4. The system remains usable without external AI

If watsonx.ai credentials or model access are unavailable, the system uses a deterministic fallback and labels its source. Physics, safety gates, approval, simulation, and verification remain functional.

5. A committed demo prevents network dependency

CONJ-001 and SAFE-001 provide reproducible synthetic scenarios, so the main judging flow does not depend on CelesTrak availability or network latency.

Architecture

flowchart LR
    UI["React mission-control UI"] --> API["FastAPI contract"]
    API --> PHY["SGP4 and TCA engine"]
    API --> RISK["Risk and uncertainty layer"]
    API --> MAN["Maneuver evaluator"]
    MAN --> ROB["Robustness verification"]
    MAN --> AI["IBM Granite or fallback"]
    API --> DATA["Synthetic JSON or CelesTrak OMM/JSON"]

Boundary

Responsibility

Physics layer

Propagation, states, TCA, miss distance, relative velocity

Risk layer

Classification, estimate basis, covariance disclosure

Maneuver layer

Candidate generation, fuel, constraints, post-maneuver evaluation

Robustness layer

Perturbation-based safety evidence

Granite layer

Advisory ranking and grounded explanation of safe candidates

Approval layer

Human authorization and server-side revalidation

Reporting layer

Verification result and incident narrative

Real 3D orbital visualization

The dashboard uses Three.js through React Three Fiber and Drei. It renders:

A contextual 3D Earth

A protected-satellite model

An irregular threat/debris model

Backend-derived protected and threat trajectory samples

TCA positions and the miss-distance connector

Global, protected, threat, TCA, and reset camera controls

Hover-to-highlight trajectory discovery

Click-to-pin selection

Keyboard-operable controls and textual fallbacks

The frontend does not generate a fake circular orbit for the production visualization. Trajectory geometry comes from the backend visualization contract.

Visual disclosure: Object sizes may be enlarged for visibility. Trajectory distances remain tied to propagated coordinates. Earth geography is contextual unless explicitly transformed to match the propagated frame.

Data modes

Synthetic Demo

The committed demo path is deterministic and available offline:

Scenario

Purpose

CONJ-001

Close approach requiring maneuver review

SAFE-001

Safe pass showing the no-action workflow

Synthetic metadata is intentionally explicit:

Data source: committed synthetic LEO demo scenario

Data quality: demonstration data

Uncertainty basis: synthetic covariance

Operational use: simulation only—not operational tracking data

Live CelesTrak

Users can enter two different positive NORAD catalog IDs. The backend fetches public GP elements in OMM/JSON form, preserves provenance, initializes SGP4 records, registers the scenario, and runs the same analysis pipeline.

The interface reports:

Provider and format

Retrieval timestamp

Object names and NORAD catalog IDs

Element epochs and ages

Covariance availability

Coordinate frame and estimate basis

Public GP elements do not include the operational covariance required for a certified collision-probability assessment. The application does not invent one.

Scientific integrity

Propagation

Propagator: SGP4

Analysis frame: TEME

Objects: exactly two

Regime: LEO prototype scope

TCA: bounded coarse search followed by numerical refinement

Relative velocity: difference between both propagated velocity vectors at TCA

Risk language

The system does not display an unsupported bare confidence percentage.

A risk statement is accompanied by available evidence such as:

Source and retrieval time

Element epoch and age

Covariance availability or synthetic uncertainty basis

Coordinate frame

Trial count and success fraction when robustness evaluation actually runs

NASA CARA probability tiers may be referenced as guidance only. CollisionGuard AI is not certified against NASA operational procedures.

Maneuvers

The prototype evaluates five predefined candidate maneuvers. It does not claim to be a global trajectory optimizer. Each candidate is evaluated using backend-computed safety, delta-v, fuel, and post-maneuver separation values.

IBM Granite integration

IBM Granite via watsonx.ai performs legitimate decision-support work:

Multi-factor ranking of backend-approved safe maneuvers

Plain-language explanation of the risk and recommendation

Grounded incident-report generation

The runtime response identifies whether the advisory source is live Granite or the deterministic fallback. The model ID is configurable and reported by the application rather than hardcoded into this README.

Non-negotiable Granite safety rule

Unsafe candidate → rejected by deterministic backend → never sent to Granite
Safe candidate   → may be ranked and explained by Granite
Any candidate    → cannot execute without human approval

Human approval and simulated execution

CollisionGuard AI is deliberately human-supervised.

The operator must:

Review the computed conjunction evidence.

Select a backend-approved safe candidate.

Request approval.

Confirm the simulated action.

Review the post-maneuver verification.

The backend revalidates the candidate before simulated execution. No spacecraft command is produced.

Technology stack

Area

Technology

Frontend

React 18, Vite 5

3D visualization

Three.js, React Three Fiber, Drei

Backend API

Python, FastAPI, Pydantic

Propagation

sgp4

Numerical work

NumPy and project numerical utilities

AI

IBM Granite through watsonx.ai

Live orbital elements

CelesTrak OMM/JSON public GP data

Testing

Pytest

Local persistence

Committed JSON and lightweight application state

Repository structure

CollisionGuard AI/
├── backend/
│   ├── data/scenarios/          # Guaranteed synthetic demo inputs
│   ├── routers/                 # FastAPI route modules
│   ├── schemas/                 # Pydantic API contracts
│   ├── tests/                   # Focused and integration tests
│   ├── celestrak_client.py      # Public GP element retrieval
│   ├── scenario_registry.py     # Runtime live-scenario registration
│   ├── propagation.py           # SGP4 states and closest approach
│   ├── maneuver_candidates.py   # Five bounded candidates
│   ├── maneuver_evaluator.py    # Deterministic safety evaluation
│   ├── monte_carlo.py           # Explicit robustness evaluation
│   ├── granite_client.py        # Granite guardrails and fallback
│   └── main.py                  # Application entry point
├── frontend/
│   ├── src/api/                 # Backend client
│   ├── src/components/          # Dashboard and Three.js components
│   ├── src/App.jsx              # Workflow orchestration
│   └── src/styles.css           # Mission-control design system
├── docs/                        # Architecture, API, safety and evidence docs
├── .env.example                 # Secret-free configuration template
├── LICENSE
└── README.md

Quick start on Windows

Prerequisites

Python 3.11+

Node.js 20+

npm

Git

1. Clone

git clone https://github.com/MuskanEjaz/CollisionGuard-AI.git
cd "CollisionGuard-AI"

2. Configure the backend

Copy-Item .env.example backend\.env
cd backend
python -m pip install -r requirements.txt

The deterministic workflow works with blank watsonx values. To enable live Granite, set valid values only in backend/.env:

WATSONX_APIKEY=
WATSONX_PROJECT_ID=
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=

Never commit .env.

3. Start the backend

cd "C:\path\to\CollisionGuard AI\backend"
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

API: http://127.0.0.1:8000

Interactive API docs: http://127.0.0.1:8000/docs

4. Start the frontend

Open a second terminal:

cd "C:\path\to\CollisionGuard AI\frontend"
npm install
npm run dev -- --host 127.0.0.1

Open http://127.0.0.1:5173.

Recommended judging flow

Use the committed synthetic conjunction as the guaranteed primary demo:

Open Synthetic Demo.

Select CONJ-001.

Run deterministic analysis.

Show the backend-derived 3D paths and TCA connector.

Explain miss distance, relative velocity, source, quality, and uncertainty basis.

Compare the five maneuver candidates.

Show Granite advisory or the clearly labelled fallback.

Select a safe candidate.

Demonstrate the human approval gate.

Execute the action in simulation.

Show post-maneuver verification.

Generate the incident report.

Briefly show SAFE-001.

Present live CelesTrak as an additional capability, not the only demo path.

Validation policy

Run tests against the final merged commit before publishing results.

Frontend production build

cd frontend
npm run build

Backend fast suite

cd backend
python -m pytest tests -m "not slow"

Explicit slow robustness test

python -m pytest tests/test_monte_carlo.py -m slow -v

The slow test is intentionally separate. Do not run it during ordinary UI or documentation changes.

Historical test counts are not used as a current badge because substantial live-data and Three.js changes were added afterward. Publish a final count only after running validation on the final merged commit.

See docs/TESTING.md and docs/CURRENT_STATUS.md for the latest evidence.

API

The interactive OpenAPI specification at http://127.0.0.1:8000/docs is the authoritative route contract.

Core workflows include:

Scenario listing and detail

Synthetic and live-scenario analysis

CelesTrak catalog retrieval

Propagation and TCA results

Candidate generation and evaluation

Explicit robustness evaluation

Granite advisory

Cache inspection and invalidation

Human approval

Simulated execution

Incident reporting

See docs/API_REFERENCE.md for the maintained endpoint reference.

Responsible use

CollisionGuard AI must not be used to:

Command a spacecraft

Replace certified flight-dynamics software

Make operational collision-avoidance decisions

Present public GP data as precision tracking data

Present synthetic covariance as measured covariance

Treat Granite output as authoritative physics

Bypass human review

See docs/SAFETY_AND_RESPONSIBLE_USE.md.

Known limitations

Exactly two objects are evaluated per scenario.

The prototype scope is limited to LEO.

CelesTrak public GP data does not include operational covariance.

Live network calls can time out or be unavailable.

Candidate maneuvers are predefined options, not globally optimized burns.

Higher-fidelity operational force models and certified validation are out of scope.

Maneuver execution is simulated only.

Object models are enlarged for visibility.

Earth orientation is contextual unless explicitly frame-aligned.

The in-memory live-scenario registry and cache reset with the backend process.

The prototype does not provide authentication suitable for operational use.

Future work

Authorized conjunction data-message and covariance ingestion

Independent probability-of-collision validation

Higher-fidelity force modelling

Geometry-aware maneuver optimization

Multi-object screening

Persistent audit logs and authenticated operator roles

Independent aerospace-software verification

These items are future work and are not claimed as implemented.

IBM AI Builders Challenge

CollisionGuard AI was built for the IBM AI Builders Challenge — August 2026, under the Advance Space Exploration with AI theme.

IBM technology contributes directly through:

IBM Granite advisory ranking

Grounded operator explanations

Incident-report generation

Guardrail validation against deterministic backend values

IBM Bob-assisted architecture, implementation, debugging, testing, and documentation

The project uses AI where judgment and explanation add value while retaining deterministic control over physics and safety.

Judging-criteria alignment

Criterion

Evidence

Challenge fit

Direct application to conjunction assessment and space sustainability

Technical execution

SGP4 pipeline, typed API contracts, Three.js visualization, safety gates

Meaningful IBM AI

Granite ranks and explains safe options within explicit authority limits

Innovation

Numerically grounded AI plus mandatory human approval and verification

Feasibility

Laptop-runnable stack with committed offline scenarios and deterministic fallback

Responsible AI

Transparent uncertainty, no invented physics, no autonomous execution

Presentation

Mission-control workflow from input through verified simulated outcome

Evidence and documentation

Architecture

API reference

Scientific assumptions

Safety and responsible use

Testing

Current status

IBM Bob usage

Team handoff

Demo plan

Required final evidence

Full 3D conjunction scene

TCA and risk evidence

Maneuver comparison

Granite live or fallback source badge

Human approval and simulated execution

Post-maneuver verification

Incident report

CelesTrak provenance

Final build and test output

Team

Member

Primary ownership

Muskan Ejaz

Product integration, UI, documentation, evidence, and submission

Pushkar

IBM Granite integration, grounding, and AI evidence

Surya

Backend validation, performance, final robustness evidence, and demo production

Demo video

Public demo URL: [ADD FINAL PUBLIC VIDEO URL]

Do not replace this placeholder with a private or inaccessible link.

License

See LICENSE.

Final statement

CollisionGuard AI does not claim to replace professional conjunction-assessment systems. It demonstrates how deterministic orbital analysis, transparent uncertainty handling, IBM Granite, and mandatory human oversight can be combined into an explainable collision-avoidance decision-support workflow.