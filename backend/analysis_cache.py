# analysis_cache.py -- Phase 7 in-memory analysis cache.
#
# Caches the expensive combined propagation+evaluation+advisory result so that
# the /advise endpoint does not re-run the full ~20s pipeline on every call.
#
# Cache key: scenario_id + a digest of the scenario's TLE epoch and orbital
# elements, ensuring that any change to input data invalidates the entry.
#
# Rules enforced:
#   - Only deterministic computed analysis is cached.
#   - Credentials and raw secrets are NEVER stored.
#   - Each entry records whether it was a cache hit.
#   - Invalidation: by scenario_id, or flush the entire cache.
#   - No external database or Redis -- pure in-memory dict.
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    scenario_id: str
    cache_key: str
    analysis: Any          # the FullAnalysisResponse object
    created_at: float      # time.monotonic() when stored
    ttl_seconds: float     # max age before considered stale


# Single process-level cache dict -- keyed by cache_key string.
_CACHE: dict[str, CacheEntry] = {}

# Default TTL: 5 minutes. Synthetic scenarios don't change, but live
# TLE data can age. For this prototype, 300s is a safe balance.
DEFAULT_TTL_SECONDS = 300.0


def _make_cache_key(scenario_id: str, scenario) -> str:
    # Derive a stable key from the scenario's TLE lines and epoch.
    # Any change to orbital elements or epoch invalidates the entry.
    # The key never contains credential values.
    raw = (
        f"{scenario_id}|"
        f"{scenario.our_satellite.tle.line1}|"
        f"{scenario.our_satellite.tle.line2}|"
        f"{scenario.threat_object.tle.line1}|"
        f"{scenario.threat_object.tle.line2}|"
        f"{scenario.epoch_utc.isoformat()}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_cached(scenario_id: str, scenario) -> tuple[Any, bool]:
    # Returns (analysis, was_cache_hit).
    # Returns (None, False) on miss or expired entry.
    key = _make_cache_key(scenario_id, scenario)
    entry = _CACHE.get(key)
    if entry is None:
        return None, False
    age = time.monotonic() - entry.created_at
    if age > entry.ttl_seconds:
        del _CACHE[key]
        return None, False
    return entry.analysis, True


def set_cached(scenario_id: str, scenario, analysis: Any,
               ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
    # Store a computed analysis result.
    # The analysis object must not contain any credential values.
    key = _make_cache_key(scenario_id, scenario)
    _CACHE[key] = CacheEntry(
        scenario_id=scenario_id,
        cache_key=key,
        analysis=analysis,
        created_at=time.monotonic(),
        ttl_seconds=ttl_seconds,
    )


def invalidate(scenario_id: str) -> int:
    # Remove all cache entries for a given scenario_id.
    # Returns the number of entries removed.
    to_remove = [k for k, v in _CACHE.items() if v.scenario_id == scenario_id]
    for k in to_remove:
        del _CACHE[k]
    return len(to_remove)


def flush_all() -> int:
    # Remove all cache entries. Returns the count removed.
    count = len(_CACHE)
    _CACHE.clear()
    return count


def cache_stats() -> dict:
    # Return current cache state (no credential values).
    now = time.monotonic()
    entries = []
    for entry in _CACHE.values():
        age = now - entry.created_at
        entries.append({
            "scenario_id": entry.scenario_id,
            "cache_key": entry.cache_key,
            "age_seconds": round(age, 1),
            "ttl_seconds": entry.ttl_seconds,
            "expires_in_seconds": round(max(0, entry.ttl_seconds - age), 1),
        })
    return {"count": len(_CACHE), "entries": entries}
