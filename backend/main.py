"""
CollisionGuard AI — FastAPI application entry point.

CollisionGuard AI is a human-supervised decision-support prototype with
simulated auto-execution. It is NOT autonomous and is NOT flight-ready.

Run (development):
    cd backend
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import health as health_router
from routers import scenarios as scenarios_router
from routers import maneuvers as maneuvers_router
from routers import robustness as robustness_router

settings = get_settings()

app = FastAPI(
    title="CollisionGuard AI API",
    description=(
        "Human-supervised collision-avoidance decision-support prototype. "
        "Not autonomous. Not flight-ready."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Vite dev server (and any configured override) to reach the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router.router)
app.include_router(scenarios_router.router)
app.include_router(maneuvers_router.router)
app.include_router(robustness_router.router)
