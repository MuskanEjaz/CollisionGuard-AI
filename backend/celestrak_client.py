"""
CelesTrak GP client — CollisionGuard AI Phase 8.

Fetches public OMM/JSON orbital elements from the CelesTrak General
Perturbations catalog for exactly one object per call, then returns
strongly-typed internal data.

Official endpoint pattern used:
    https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_number}&FORMAT=JSON

The caller (router/service) is responsible for making two separate calls
(protected satellite + threat object) and composing the two-object scenario.

Limitations (truthful):
  - Public GP data has no covariance. Pc estimates remain screening-level only.
  - Element age and propagation accuracy vary by object.
  - Network availability is not guaranteed. Cache reduces but does not
    eliminate this dependency.

Human-supervised decision-support prototype. Simulation only — not flight software.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

# ── Constants ─────────────────────────────────────────────────────────────────

# Fixed official HTTPS host — never accept an arbitrary URL.
_CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php"

# CollisionGuard AI user-agent for courtesy identification.
_USER_AGENT = "CollisionGuard-AI/0.1 (human-supervised prototype; https://github.com)"

# LEO screening threshold: mean motion > ~11.25 rev/day corresponds to
# roughly ≤2000 km altitude.  This is a screening rule, not a certification.
# 11.25 rev/day × (2π/1440) rad/s ≈ 0.04905 rad/min
_LEO_MIN_MEAN_MOTION_REV_PER_DAY = 11.25

# Required OMM fields consumed by sgp4.omm.initialize (verified against sgp4 2.27 source).
# OBJECT_NAME is metadata — not consumed by initialize — and is treated as optional.
_REQUIRED_OMM_FIELDS = frozenset({
    "NORAD_CAT_ID",
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
    "BSTAR",
    "EPHEMERIS_TYPE",
    "CLASSIFICATION_TYPE",
    "OBJECT_ID",
    "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
})

# ── Short in-memory cache ──────────────────────────────────────────────────────
# Key: norad_cat_id (int) → (OrbitalRecord, stored_at monotonic)
# TTL: configurable (default 300 s).  Avoids hammering CelesTrak during tests.
_CACHE: dict[int, tuple["OrbitalRecord", float]] = {}
_CACHE_TTL_SECONDS: float = 300.0


def _cache_get(norad_cat_id: int) -> "OrbitalRecord | None":
    entry = _CACHE.get(norad_cat_id)
    if entry is None:
        return None
    record, stored_at = entry
    if time.monotonic() - stored_at > _CACHE_TTL_SECONDS:
        del _CACHE[norad_cat_id]
        return None
    return record


def _cache_set(record: "OrbitalRecord") -> None:
    _CACHE[record.norad_cat_id] = (record, time.monotonic())


def flush_cache() -> int:
    """Remove all cached entries. Returns count removed. Used in tests."""
    count = len(_CACHE)
    _CACHE.clear()
    return count


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class OrbitalRecord:
    """
    Typed orbital elements for one object, retrieved from CelesTrak GP data.

    raw_omm_fields: the original dict returned by CelesTrak, consumed by
        sgp4.omm.initialize.  Never modified.
    """
    norad_cat_id: int
    object_name: str
    cospar_id: str                        # OBJECT_ID in OMM (e.g. "1998-067A")
    epoch_utc: datetime                   # element epoch, UTC
    mean_motion_rev_per_day: float        # MEAN_MOTION as returned
    is_leo: bool                          # True if mean motion > LEO threshold
    retrieved_at_utc: datetime            # when this record was fetched
    raw_omm_fields: dict                  # complete OMM dict for sgp4.omm.initialize


# ── Errors ────────────────────────────────────────────────────────────────────

class CelesTrakError(Exception):
    """Base class for all CelesTrak client errors."""


class CelesTrakTimeoutError(CelesTrakError):
    """Request timed out."""


class CelesTrakHTTPError(CelesTrakError):
    """Non-2xx HTTP response from CelesTrak."""


class CelesTrakEmptyError(CelesTrakError):
    """CelesTrak returned an empty catalog for this ID."""


class CelesTrakMalformedError(CelesTrakError):
    """Response is not valid JSON or missing required OMM fields."""


class CelesTrakIDMismatchError(CelesTrakError):
    """The returned NORAD_CAT_ID does not match the requested ID."""


class CelesTrakNonLEOError(CelesTrakError):
    """Object is not in LEO (mean motion below screening threshold)."""


# ── Private helpers ───────────────────────────────────────────────────────────

def _parse_epoch(epoch_str: str) -> datetime:
    """
    Parse the CelesTrak EPOCH string into an aware UTC datetime.
    CelesTrak returns ISO-8601 with microseconds: "2025-08-01T12:00:00.000000"
    """
    # Try with microseconds first (most common)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(epoch_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise CelesTrakMalformedError(
        f"Cannot parse EPOCH field: {epoch_str!r}. "
        "Expected ISO-8601 with or without microseconds."
    )


def _validate_and_parse(
    data: list,
    requested_id: int,
) -> OrbitalRecord:
    """
    Validate the CelesTrak JSON response list and return an OrbitalRecord.

    Raises:
        CelesTrakEmptyError      — empty list
        CelesTrakMalformedError  — missing required fields
        CelesTrakIDMismatchError — returned NORAD_CAT_ID ≠ requested
        CelesTrakNonLEOError     — object not in LEO
    """
    if not data:
        raise CelesTrakEmptyError(
            f"CelesTrak returned no records for catalog ID {requested_id}. "
            "The object may be classified, decayed, or the ID is invalid."
        )

    record_dict = data[0]  # always one object when querying by CATNR

    # Validate required fields
    missing = _REQUIRED_OMM_FIELDS - set(record_dict.keys())
    if missing:
        raise CelesTrakMalformedError(
            f"CelesTrak response missing required OMM fields: {sorted(missing)}. "
            "The GP data format may have changed."
        )

    # Validate catalog ID matches
    try:
        returned_id = int(record_dict["NORAD_CAT_ID"])
    except (ValueError, TypeError) as exc:
        raise CelesTrakMalformedError(
            f"NORAD_CAT_ID is not an integer: {record_dict.get('NORAD_CAT_ID')!r}"
        ) from exc

    if returned_id != requested_id:
        raise CelesTrakIDMismatchError(
            f"Requested NORAD ID {requested_id} but CelesTrak returned {returned_id}."
        )

    # Parse epoch
    epoch_utc = _parse_epoch(str(record_dict["EPOCH"]))

    # Parse mean motion
    try:
        mean_motion = float(record_dict["MEAN_MOTION"])
    except (ValueError, TypeError) as exc:
        raise CelesTrakMalformedError(
            f"MEAN_MOTION is not numeric: {record_dict.get('MEAN_MOTION')!r}"
        ) from exc

    # LEO screening: mean motion > _LEO_MIN_MEAN_MOTION_REV_PER_DAY rev/day
    is_leo = mean_motion > _LEO_MIN_MEAN_MOTION_REV_PER_DAY

    return OrbitalRecord(
        norad_cat_id=returned_id,
        object_name=str(record_dict.get("OBJECT_NAME", "")).strip() or f"NORAD-{returned_id}",
        cospar_id=str(record_dict.get("OBJECT_ID", "")).strip(),
        epoch_utc=epoch_utc,
        mean_motion_rev_per_day=mean_motion,
        is_leo=is_leo,
        retrieved_at_utc=datetime.now(tz=timezone.utc),
        raw_omm_fields=dict(record_dict),   # defensive copy
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_orbital_record(
    norad_cat_id: int,
    timeout_s: float = 15.0,
    *,
    _http_client: "httpx.Client | None" = None,  # injection point for tests
) -> OrbitalRecord:
    """
    Fetch OMM/JSON orbital elements for one object from CelesTrak.

    Uses in-memory cache to avoid repeated requests.

    Parameters
    ----------
    norad_cat_id : int
        Positive NORAD catalog number.
    timeout_s : float
        Combined connect+read timeout.  Must be ≤ 15.0 (enforced by caller).
    _http_client : httpx.Client | None
        Injection point for tests — pass a mock client to avoid live requests.

    Returns
    -------
    OrbitalRecord
        Validated orbital data ready for sgp4.omm.initialize.

    Raises
    ------
    ValueError               — norad_cat_id ≤ 0
    CelesTrakTimeoutError    — request timed out
    CelesTrakHTTPError       — non-2xx HTTP response
    CelesTrakEmptyError      — catalog returned no records
    CelesTrakMalformedError  — response not parseable / missing fields
    CelesTrakIDMismatchError — returned ID ≠ requested ID
    CelesTrakNonLEOError     — object not in LEO (raised only if caller checks)
    """
    if norad_cat_id <= 0:
        raise ValueError(f"NORAD catalog ID must be a positive integer, got {norad_cat_id}")

    # Cache hit
    cached = _cache_get(norad_cat_id)
    if cached is not None:
        return cached

    url = f"{_CELESTRAK_BASE}?CATNR={norad_cat_id}&FORMAT=JSON"
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

    try:
        if _http_client is not None:
            response = _http_client.get(url, headers=headers, timeout=timeout_s)
        else:
            # Real HTTP request — only called in live operation, never in tests
            with httpx.Client(timeout=timeout_s) as client:
                response = client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise CelesTrakTimeoutError(
            f"CelesTrak request timed out after {timeout_s}s for NORAD ID {norad_cat_id}."
        ) from exc
    except httpx.RequestError as exc:
        raise CelesTrakError(
            f"CelesTrak request failed for NORAD ID {norad_cat_id}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise CelesTrakHTTPError(
            f"CelesTrak returned HTTP {response.status_code} for NORAD ID {norad_cat_id}."
        )

    try:
        data = response.json()
    except Exception as exc:
        raise CelesTrakMalformedError(
            f"CelesTrak response for NORAD ID {norad_cat_id} is not valid JSON."
        ) from exc

    if not isinstance(data, list):
        raise CelesTrakMalformedError(
            f"CelesTrak response is not a JSON array (got {type(data).__name__}). "
            "Expected FORMAT=JSON array of OMM records."
        )

    record = _validate_and_parse(data, norad_cat_id)
    _cache_set(record)
    return record


def check_leo(record: OrbitalRecord) -> None:
    """
    Raise CelesTrakNonLEOError if the record is not in LEO.

    Called explicitly by the router so the check is visible in tests and
    not buried inside fetch_orbital_record.
    """
    if not record.is_leo:
        raise CelesTrakNonLEOError(
            f"Object '{record.object_name}' (NORAD {record.norad_cat_id}) "
            f"has mean motion {record.mean_motion_rev_per_day:.4f} rev/day, "
            f"below the LEO screening threshold of "
            f"{_LEO_MIN_MEAN_MOTION_REV_PER_DAY} rev/day. "
            "CollisionGuard AI supports LEO objects only."
        )
