# CollisionGuard AI

> **CollisionGuard AI is a human-supervised decision-support prototype with
> simulated auto-execution. It is not autonomous and is not flight-ready.**

IBM AI Builders Challenge — Space Exploration theme.

---

## What it does

CollisionGuard AI ingests two-line element (TLE) data for a pair of LEO
objects (our satellite + one threat object), analyses predicted conjunction
geometry, and presents maneuver candidates to a human operator for review and
approval. The operator makes every execution decision; the system never acts
without explicit human confirmation.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.10 |
| pip | 23+ |
| Node.js | 18 |
| npm | 9+ |

---

## Quick start

### 1 — Clone and configure secrets

```bash
cp .env.example .env
# Edit .env if you need to override defaults.
# Never commit .env to source control.
```

### 2 — Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at <http://localhost:8000>.
Interactive docs: <http://localhost:8000/docs>

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI is now available at <http://localhost:5173>.

### 4 — Tests

```bash
cd backend
pytest tests/ -v
```

---

## Project structure

```
CollisionGuard AI/
├── .env.example                   Environment variable template (committed)
├── .gitignore
├── README.md
│
├── backend/
│   ├── main.py                    FastAPI application entry point
│   ├── requirements.txt           Pinned Python dependencies
│   ├── config.py                  Settings (pydantic-settings + .env)
│   ├── routers/
│   │   ├── health.py              GET /health
│   │   └── scenarios.py           GET /scenarios, GET /scenarios/{id}
│   ├── schemas/
│   │   ├── health.py              HealthResponse Pydantic model
│   │   └── scenario.py            TLE, SpaceObject, Scenario models
│   ├── data/
│   │   └── scenarios/
│   │       ├── conjunction_scenario.json   Synthetic LEO conjunction
│   │       └── safe_scenario.json          Synthetic LEO safe pass
│   └── tests/
│       ├── test_health.py
│       └── test_scenarios.py
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/client.js          Fetch wrapper; base URL from VITE_API_BASE_URL
        └── components/
            ├── HealthStatus.jsx   Renders GET /health response
            └── ScenarioPanel.jsx  Renders GET /scenarios response
```

---

## Environment variables

Copy `.env.example` to `.env` before running anything.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment label |
| `APP_VERSION` | `0.1.0` | Reported in /health and API docs |
| `BACKEND_HOST` | `0.0.0.0` | uvicorn bind host |
| `BACKEND_PORT` | `8000` | uvicorn bind port |
| `CORS_ORIGIN` | `http://localhost:5173` | Allowed frontend origin |
| `WATSONX_API_KEY` | *(blank)* | IBM watsonx.ai — Phase 2+, leave blank for Phase 1 |
| `WATSONX_PROJECT_ID` | *(blank)* | IBM watsonx.ai — Phase 2+ |
| `WATSONX_URL` | *(blank)* | IBM watsonx.ai — Phase 2+ |

The frontend reads one optional variable from `frontend/.env.local` (gitignored):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL for the API client |

---

## API endpoints (Phase 1)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend health status |
| `GET` | `/scenarios` | List all scenarios |
| `GET` | `/scenarios/{id}` | Single scenario by ID |

---

## Propagation library note

This project uses **`sgp4`** and **`skyfield`** for orbital propagation
(Phase 2+). `poliastro` is **not used** — it was archived in October 2023.

---

## Granite ranking rule

Granite (IBM) may compare and recommend only among maneuver candidates that
the deterministic backend has already marked **valid and safe**. Granite
cannot approve execution, override a safety rejection, alter computed values,
or select an invalid candidate. If Granite output conflicts with the backend,
the Granite output is rejected and the deterministic backend result is used.

---

## Scope

- Exactly two objects: our satellite + one threat object
- LEO only
- One conjunction scenario + one safe scenario (hardcoded fallback data)
- 3–5 hardcoded delta-v candidates (Phase 2)
- No asteroids, no multi-satellite coordination
