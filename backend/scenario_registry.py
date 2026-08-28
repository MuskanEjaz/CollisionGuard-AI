"""
Shared runtime scenario registry — CollisionGuard AI Phase 9.

Provides a single resolver that handles both committed JSON scenarios and
runtime CelesTrak live scenarios.

Committed scenarios: loaded from JSON files by routers.scenarios._load_scenarios()
Runtime scenarios:   registered here after live CelesTrak fetch

All ID-based routes (analyse, approve, execute, incident-report, cache, etc.)
must use resolve_scenario() instead of _load_scenarios() directly so that
live-scenario IDs are correctly resolved.

Design constraints:
  - In-memory only: cleared on process restart (process-lifetime limitation)
  - Bounded: MAX_RUNTIME_ENTRIES enforced; oldest entry evicted on overflow
  - TTL-controlled: default 3600 s (1 hour); expired entries return a useful
    expiry message, not a generic 404
  - Thread-safe for single-process FastAPI (dict operations are GIL-protected)
  - Cannot overwrite committed scenario IDs
  - Stores complete validated Scenario + source metadata
  - Never stores credentials or arbitrary URLs

Human-supervised decision-support prototype. Simulation only — not flight software.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from schemas.scenario import Scenario

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_RUNTIME_ENTRIES = 50          # hard cap — older entries evicted first
DEFAULT_TTL_SECONDS = 3600.0      # 1 hour

# ── Registry entry ────────────────────────────────────────────────────────────

@dataclass
class RuntimeEntry:
    scenario_id: str
    scenario: Scenario
    created_at: float                      # monotonic time
    expires_at: float                      # monotonic time
    # Source metadata (live CelesTrak provenance — no credentials)
    source_meta: dict = field(default_factory=dict)


# ── Registry state ────────────────────────────────────────────────────────────

_REGISTRY: dict[str, RuntimeEntry] = {}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _evict_oldest() -> None:
    """Remove the single oldest entry to stay within MAX_RUNTIME_ENTRIES."""
    if not _REGISTRY:
        return
    oldest_key = min(_REGISTRY, key=lambda k: _REGISTRY[k].created_at)
    del _REGISTRY[oldest_key]


def _is_expired(entry: RuntimeEntry) -> bool:
    return time.monotonic() > entry.expires_at


# ── Public interface ──────────────────────────────────────────────────────────

def register_runtime_scenario(
    scenario: Scenario,
    source_meta: dict | None = None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
) -> str:
    """
    Register a live in-memory scenario.

    Returns the scenario_id (same as scenario.scenario_id).

    Raises:
        ValueError — if the ID matches a committed scenario (call
                     resolve_scenario or _load_scenarios to check first)
        ValueError — if scenario_id is empty or not a Scenario instance
    """
    if not isinstance(scenario, Scenario):
        raise TypeError("scenario must be a validated Scenario instance")
    if not scenario.scenario_id:
        raise ValueError("scenario.scenario_id must not be empty")

    scenario_id = scenario.scenario_id

    # Check for committed-scenario collision (avoid import cycle: lazy import)
    from routers.scenarios import _load_scenarios
    if scenario_id in _load_scenarios():
        raise ValueError(
            f"Cannot register runtime scenario: ID '{scenario_id}' "
            "is already a committed synthetic scenario."
        )

    # Enforce capacity bound
    if len(_REGISTRY) >= MAX_RUNTIME_ENTRIES:
        _evict_oldest()

    now = time.monotonic()
    _REGISTRY[scenario_id] = RuntimeEntry(
        scenario_id=scenario_id,
        scenario=scenario,
        created_at=now,
        expires_at=now + ttl_seconds,
        source_meta=dict(source_meta or {}),
    )
    return scenario_id


def is_runtime_scenario(scenario_id: str) -> bool:
    """Return True if the ID is registered as a runtime scenario (may be expired)."""
    return scenario_id in _REGISTRY


def resolve_scenario(scenario_id: str) -> Scenario:
    """
    Return the validated Scenario for a given ID.

    Resolution order:
      1. Committed JSON scenarios (via _load_scenarios)
      2. Live runtime scenarios (registry)

    Raises:
      HTTPException 404 — ID not found in either source
      HTTPException 410 — live scenario exists but has expired
    """
    from fastapi import HTTPException
    from routers.scenarios import _load_scenarios

    # Committed scenarios take priority
    committed = _load_scenarios()
    if scenario_id in committed:
        return committed[scenario_id]

    # Runtime registry
    entry = _REGISTRY.get(scenario_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    if _is_expired(entry):
        # Don't delete here — let callers decide; return useful message
        raise HTTPException(
            status_code=410,
            detail=(
                f"Live scenario '{scenario_id}' has expired. "
                "Fetch and analyse the CelesTrak objects again to create a new session."
            ),
        )
    return entry.scenario


def get_runtime_meta(scenario_id: str) -> dict:
    """Return source_meta for a runtime entry, or empty dict if not found."""
    entry = _REGISTRY.get(scenario_id)
    if entry is None:
        return {}
    return dict(entry.source_meta)


def delete_runtime_scenario(scenario_id: str) -> bool:
    """
    Remove a runtime entry.  Returns True if removed, False if not found.
    Also clears associated analysis cache and approval state.
    """
    if scenario_id not in _REGISTRY:
        return False
    del _REGISTRY[scenario_id]
    # Clear associated cache
    try:
        from analysis_cache import invalidate
        invalidate(scenario_id)
    except Exception:
        pass
    # Clear associated pending approval
    try:
        from routers.analysis import _PENDING_APPROVALS
        _PENDING_APPROVALS.pop(scenario_id, None)
    except Exception:
        pass
    return True


def clear_expired_runtime_scenarios() -> int:
    """Remove all expired entries. Returns count removed."""
    expired = [k for k, v in _REGISTRY.items() if _is_expired(v)]
    for k in expired:
        delete_runtime_scenario(k)
    return len(expired)


def registry_stats() -> dict:
    """Return current registry state (no credentials)."""
    now = time.monotonic()
    entries = []
    for entry in _REGISTRY.values():
        age = now - entry.created_at
        ttl_remaining = max(0.0, entry.expires_at - now)
        entries.append({
            "scenario_id": entry.scenario_id,
            "age_seconds": round(age, 1),
            "ttl_remaining_seconds": round(ttl_remaining, 1),
            "expired": _is_expired(entry),
        })
    return {
        "count": len(_REGISTRY),
        "max_entries": MAX_RUNTIME_ENTRIES,
        "entries": entries,
    }
