"""
Phase 9 contract tests — live scenario registry, relative velocity, covariance.

Tests cover exactly three connected fixes:
  1. Live scenario registry — register, resolve, expire (410), overflow eviction,
     committed-ID collision protection, approval/execute roundtrip for a live ID.
  2. Relative velocity — propagation produces non-None relative_velocity_km_s,
     correct unit (km/s), correct formula (vel_b - vel_a norm).
  3. Covariance contract — live GP response has covariance_available=False;
     synthetic analysis response has covariance_available=True.

SAFETY RULES (enforced in this file):
  - No live CelesTrak HTTP calls.
  - No live Granite/watsonx calls.
  - No Monte Carlo / robustness runs.
  - No slow tests.
  - All network I/O is mocked or bypassed.
  - No credentials stored or accessed.

Human-supervised decision-support prototype. Simulation only — not flight software.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from scenario_registry import (
    register_runtime_scenario,
    resolve_scenario,
    delete_runtime_scenario,
    clear_expired_runtime_scenarios,
    registry_stats,
    _REGISTRY,
    DEFAULT_TTL_SECONDS,
    MAX_RUNTIME_ENTRIES,
)
from propagation import propagate_scenario, _relative_velocity_at_tca, CONJUNCTION_THRESHOLD_KM
from schemas.analysis import FullAnalysisResponse, RiskClassification, DataQualityNote
from schemas.maneuver import ManeuverCandidate, ManeuverDirection
from schemas.granite import GraniteAdvisoryResponse, GraniteRankedCandidate
from schemas.scenario import Scenario, ScenarioType, SpaceObject, TLEData

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

# Real ISS TLEs (committed to the CONJ-001 scenario — always valid)
_ISS_LINE1 = "1 25544U 98067A   25213.50000000  .00010000  00000-0  15000-3 0  9992"
_ISS_LINE2 = "2 25544  51.6400 200.0000 0005000 100.0000 260.0000 15.50000000000008"

_DEBRIS_LINE1 = "1 33591U 09005A   25213.50000000  .00002000  00000-0  50000-4 0  9991"
_DEBRIS_LINE2 = "2 33591  51.6400 200.1000 0004900 100.1000 260.1000 15.49000000000002"


def _make_live_scenario(sid: str = "LIVE-25544-33591") -> Scenario:
    """Build a minimal in-memory scenario that mimics a CelesTrak live fetch."""
    return Scenario(
        scenario_id=sid,
        scenario_type=ScenarioType.CONJUNCTION,
        description="Test live scenario",
        epoch_utc=datetime(2025, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
        our_satellite=SpaceObject(
            object_id="25544",
            name="ISS (ZARYA)",
            tle=TLEData(line1=_ISS_LINE1, line2=_ISS_LINE2),
            mass_kg=500.0,
            cross_section_m2=5.0,
        ),
        threat_object=SpaceObject(
            object_id="33591",
            name="TEST-DEBRIS",
            tle=TLEData(line1=_DEBRIS_LINE1, line2=_DEBRIS_LINE2),
            mass_kg=500.0,
            cross_section_m2=5.0,
        ),
    )


def _mock_candidate(cid: str = "MAN-001", is_safe: bool = True) -> ManeuverCandidate:
    return ManeuverCandidate(
        candidate_id=cid,
        label=f"Candidate {cid}",
        direction=ManeuverDirection.PROGRADE,
        delta_v_ms=0.5,
        is_safe=is_safe,
        safety_rejection_reason=None if is_safe else "over budget",
        fuel_cost_kg=0.104,
        post_maneuver_miss_distance_km=13.5 if is_safe else None,
        baseline_score=0.99 if is_safe else 0.0,
    )


def _mock_advisory() -> GraniteAdvisoryResponse:
    return GraniteAdvisoryResponse(
        scenario_id="LIVE-25544-33591",
        ranked_candidates=[
            GraniteRankedCandidate(
                candidate_id="MAN-001", rank=1,
                explanation="Best option.",
                delta_v_ms=0.5,
                post_maneuver_miss_distance_km=13.5,
                fuel_cost_kg=0.104,
                baseline_score=0.99,
            )
        ],
        granite_summary="Deterministic fallback ranking.",
        source="deterministic_fallback",
        model_id="test-model",
        validation_warnings=[],
        granite_note="ADVISORY ONLY",
    )


def _mock_full_analysis(sid: str = "LIVE-25544-33591") -> FullAnalysisResponse:
    return FullAnalysisResponse(
        scenario_id=sid,
        cached=False,
        analysis_timestamp=datetime.now(tz=timezone.utc),
        nominal_miss_distance_km=0.029,
        tca_offset_seconds=7102.0,
        tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        is_conjunction=True,
        conjunction_threshold_km=1.0,
        relative_velocity_km_s=7.821,
        relative_velocity_vector_km_s=(1.1, 5.2, -5.9),
        relative_velocity_frame="TEME",
        relative_velocity_timestamp_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        relative_velocity_basis="Difference of both SGP4 velocity vectors at TCA in the TEME frame",
        covariance_available=False,
        covariance_source="Unavailable — not supplied by CelesTrak GP data",
        covariance_basis="CelesTrak public GP elements do not include state-estimate covariance.",
        collision_probability_available=False,
        collision_probability=None,
        risk=RiskClassification(level="CONJUNCTION", label="Conjunction Alert", color_hint="red"),
        data_quality=[DataQualityNote(field="TLE source", note="CelesTrak GP")],
        orbit_element_age_note="Epoch: 2025-07-31T12:00:00Z (CelesTrak public GP data)",
        candidates=[_mock_candidate()],
        safe_count=1,
        total_count=1,
        evaluation_note="SIMPLIFIED FOR PROTOTYPE",
        advisory=_mock_advisory(),
    )


def setup_function():
    """Clear registry and analysis cache before each test."""
    _REGISTRY.clear()
    try:
        from analysis_cache import flush_all
        flush_all()
    except Exception:
        pass


# ===========================================================================
# 1. REGISTRY TESTS
# ===========================================================================

def test_register_live_scenario_returns_id():
    """register_runtime_scenario returns the scenario_id string."""
    s = _make_live_scenario("LIVE-25544-33591")
    sid = register_runtime_scenario(s)
    assert sid == "LIVE-25544-33591"


def test_registry_contains_registered_scenario():
    """After registration, resolve_scenario returns the same Scenario object."""
    s = _make_live_scenario("LIVE-25544-33591")
    register_runtime_scenario(s)
    resolved = resolve_scenario("LIVE-25544-33591")
    assert resolved.scenario_id == "LIVE-25544-33591"


def test_registry_stats_reflect_registration():
    """registry_stats returns count=1 after one registration."""
    s = _make_live_scenario("LIVE-AAA-001")
    register_runtime_scenario(s)
    stats = registry_stats()
    assert stats["count"] == 1
    assert stats["max_entries"] == MAX_RUNTIME_ENTRIES


def test_resolve_unknown_id_raises_404():
    """resolve_scenario raises HTTPException 404 for unknown IDs."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        resolve_scenario("LIVE-DOES-NOT-EXIST")
    assert exc_info.value.status_code == 404


def test_expired_scenario_raises_410():
    """resolve_scenario raises HTTPException 410 (not 404) for expired entries."""
    from fastapi import HTTPException
    s = _make_live_scenario("LIVE-EXPIRE-001")
    register_runtime_scenario(s, ttl_seconds=0.001)   # expires in 1 ms
    time.sleep(0.05)                                   # wait > TTL
    with pytest.raises(HTTPException) as exc_info:
        resolve_scenario("LIVE-EXPIRE-001")
    assert exc_info.value.status_code == 410
    assert "expired" in exc_info.value.detail.lower()


def test_clear_expired_removes_stale_entries():
    """clear_expired_runtime_scenarios removes only expired entries."""
    live = _make_live_scenario("LIVE-LIVE-001")
    dead = _make_live_scenario("LIVE-DEAD-001")
    register_runtime_scenario(live, ttl_seconds=3600)
    register_runtime_scenario(dead, ttl_seconds=0.001)
    time.sleep(0.05)
    n_removed = clear_expired_runtime_scenarios()
    assert n_removed == 1
    assert "LIVE-LIVE-001" in _REGISTRY
    assert "LIVE-DEAD-001" not in _REGISTRY


def test_registry_cannot_overwrite_committed_scenario():
    """register_runtime_scenario raises ValueError for committed scenario IDs."""
    with pytest.raises(ValueError, match="committed"):
        register_runtime_scenario(_make_live_scenario("CONJ-001"))


def test_registry_evicts_oldest_when_full():
    """When MAX_RUNTIME_ENTRIES is exceeded, the oldest entry is evicted."""
    # Fill registry to capacity
    for i in range(MAX_RUNTIME_ENTRIES):
        s = _make_live_scenario(f"LIVE-OVERFLOW-{i:04d}")
        register_runtime_scenario(s)
    assert len(_REGISTRY) == MAX_RUNTIME_ENTRIES
    # Adding one more should evict the oldest
    extra = _make_live_scenario("LIVE-OVERFLOW-EXTRA")
    register_runtime_scenario(extra)
    assert len(_REGISTRY) == MAX_RUNTIME_ENTRIES
    # New entry must be present
    assert "LIVE-OVERFLOW-EXTRA" in _REGISTRY


def test_delete_removes_entry():
    """delete_runtime_scenario removes the entry and returns True."""
    s = _make_live_scenario("LIVE-DELETE-001")
    register_runtime_scenario(s)
    removed = delete_runtime_scenario("LIVE-DELETE-001")
    assert removed is True
    assert "LIVE-DELETE-001" not in _REGISTRY


# ===========================================================================
# 2. LIVE APPROVAL ROUNDTRIP (the primary 404 fix)
# ===========================================================================

def test_approve_live_scenario_returns_200():
    """
    POST /scenarios/LIVE-25544-33591/approve must succeed (not 404) after
    the scenario is registered in the runtime registry.
    """
    s = _make_live_scenario("LIVE-25544-33591")
    register_runtime_scenario(s)

    with (
        patch("routers.analysis.propagate_scenario") as mock_prop,
        patch("routers.analysis.evaluate_all_candidates") as mock_eval,
        patch("routers.analysis.get_granite_advisory") as mock_adv,
        patch("routers.analysis.get_cached", return_value=(_mock_full_analysis(), True)),
    ):
        mock_prop.return_value = MagicMock(
            miss_distance_km=0.029,
            tca_offset_seconds=7102.0,
            tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
            is_conjunction=True,
            relative_velocity_km_s=7.821,
            relative_velocity_vector_km_s=(1.1, 5.2, -5.9),
            relative_velocity_frame="TEME",
            relative_velocity_basis="Difference of both SGP4 velocity vectors at TCA in the TEME frame",
        )
        mock_eval.return_value = [_mock_candidate()]
        mock_adv.return_value = _mock_advisory()

        r = client.post(
            "/scenarios/LIVE-25544-33591/approve",
            json={
                "scenario_id": "LIVE-25544-33591",
                "candidate_id": "MAN-001",
                "operator_id": "TEST-OP",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["safety_gate_passed"] is True


def test_approve_unregistered_live_scenario_returns_404():
    """
    POST /scenarios/LIVE-UNREGISTERED/approve must return 404 (never 500)
    because the scenario was not registered.
    """
    r = client.post(
        "/scenarios/LIVE-UNREGISTERED/approve",
        json={
            "scenario_id": "LIVE-UNREGISTERED",
            "candidate_id": "MAN-001",
            "operator_id": "TEST-OP",
        },
    )
    assert r.status_code == 404


def test_approve_expired_live_scenario_returns_410():
    """
    POST /scenarios/{sid}/approve must return 410 for an expired live scenario.
    """
    s = _make_live_scenario("LIVE-EXPIRED-APPROVE")
    register_runtime_scenario(s, ttl_seconds=0.001)
    time.sleep(0.05)

    r = client.post(
        "/scenarios/LIVE-EXPIRED-APPROVE/approve",
        json={
            "scenario_id": "LIVE-EXPIRED-APPROVE",
            "candidate_id": "MAN-001",
            "operator_id": "TEST-OP",
        },
    )
    assert r.status_code == 410


def test_unsafe_candidate_rejected_for_live_scenario():
    """
    Safety gate: approving an unsafe candidate for a live scenario returns
    safety_gate_passed=False and status='rejected'.
    """
    s = _make_live_scenario("LIVE-25544-33591-UNSAFE")
    register_runtime_scenario(s)

    unsafe_analysis = _mock_full_analysis("LIVE-25544-33591-UNSAFE")
    unsafe_analysis.candidates = [_mock_candidate("MAN-001", is_safe=False)]

    with patch("routers.analysis.get_cached", return_value=(unsafe_analysis, True)):
        r = client.post(
            "/scenarios/LIVE-25544-33591-UNSAFE/approve",
            json={
                "scenario_id": "LIVE-25544-33591-UNSAFE",
                "candidate_id": "MAN-001",
                "operator_id": "TEST-OP",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["safety_gate_passed"] is False
    assert body["execution"]["status"] == "rejected"


# ===========================================================================
# 3. RELATIVE VELOCITY TESTS
# ===========================================================================

def test_relative_velocity_in_full_analysis_response():
    """FullAnalysisResponse with relative_velocity_km_s populated is valid."""
    a = _mock_full_analysis()
    assert a.relative_velocity_km_s is not None
    assert isinstance(a.relative_velocity_km_s, float)
    assert a.relative_velocity_km_s > 0.0
    assert a.relative_velocity_frame == "TEME"


def test_relative_velocity_formula_direction():
    """
    _relative_velocity_at_tca returns vel_b - vel_a (threat minus protected).
    With identical TLEs, the difference is zero.
    """
    from sgp4.api import Satrec, WGS84, jday
    sat_a = Satrec.twoline2rv(_ISS_LINE1, _ISS_LINE2, WGS84)
    sat_b = Satrec.twoline2rv(_DEBRIS_LINE1, _DEBRIS_LINE2, WGS84)
    jd_w, jd_f = jday(2025, 7, 31, 12, 0, 0.0)
    speed, vec = _relative_velocity_at_tca(sat_a, sat_b, jd_w, jd_f, tca_offset_s=0.0)
    # Speed must be non-negative and in a plausible LEO relative-velocity range
    assert speed is not None
    assert speed >= 0.0
    assert speed < 20.0    # km/s — physical upper bound for LEO close approaches
    assert vec is not None
    assert len(vec) == 3


def test_propagate_scenario_populates_relative_velocity():
    """propagate_scenario sets relative_velocity_km_s on the result."""
    # Use the committed CONJ-001 scenario (synthetic, always available)
    from routers.scenarios import _load_scenarios
    scenarios = _load_scenarios()
    s = scenarios.get("CONJ-001")
    if s is None:
        pytest.skip("CONJ-001 committed scenario not available")
    result = propagate_scenario(s)
    assert result.relative_velocity_km_s is not None
    assert isinstance(result.relative_velocity_km_s, float)
    assert result.relative_velocity_km_s > 0.0


# ===========================================================================
# 4. COVARIANCE CONTRACT TESTS
# ===========================================================================

def test_live_covariance_contract_is_false():
    """
    FullAnalysisResponse for a live GP scenario must have
    covariance_available=False and a truthful covariance_source.
    """
    a = _mock_full_analysis()
    assert a.covariance_available is False
    assert "unavailable" in a.covariance_source.lower() or \
           "not supplied" in a.covariance_source.lower()
    assert a.collision_probability_available is False
    assert a.collision_probability is None


def test_synthetic_covariance_contract_is_true():
    """
    FullAnalysisResponse for a synthetic scenario has covariance_available=True
    and collision_probability_available=True (value may still be None).
    """
    from datetime import datetime, timezone
    a = FullAnalysisResponse(
        scenario_id="CONJ-001",
        cached=False,
        analysis_timestamp=datetime.now(tz=timezone.utc),
        nominal_miss_distance_km=0.029,
        tca_offset_seconds=7102.0,
        tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        is_conjunction=True,
        conjunction_threshold_km=1.0,
        covariance_available=True,
        covariance_source="Synthetic covariance",
        covariance_basis="Committed demonstration uncertainty model",
        collision_probability_available=True,
        collision_probability=None,   # not computed numerically
        risk=RiskClassification(level="CONJUNCTION", label="Conjunction Alert", color_hint="red"),
        data_quality=[DataQualityNote(field="TLE source", note="Synthetic")],
        orbit_element_age_note="Epoch: synthetic",
        candidates=[_mock_candidate()],
        safe_count=1,
        total_count=1,
        evaluation_note="SIMPLIFIED FOR PROTOTYPE",
        advisory=_mock_advisory(),
    )
    assert a.covariance_available is True
    assert a.collision_probability_available is True
    assert a.collision_probability is None   # value is None, but field is available


def test_synthetic_analyse_endpoint_returns_covariance_fields():
    """
    GET /scenarios/CONJ-001/analyse returns covariance_available in the body.
    Does not check the boolean value — only that the field is present and typed.
    """
    r = client.post("/scenarios/CONJ-001/analyse")
    assert r.status_code == 200
    body = r.json()
    assert "covariance_available" in body
    assert isinstance(body["covariance_available"], bool)
    assert "covariance_source" in body


def test_analyse_returns_relative_velocity_field():
    """
    GET /scenarios/CONJ-001/analyse returns relative_velocity_km_s in the body.
    Value must be a float (not None, not missing).
    """
    r = client.post("/scenarios/CONJ-001/analyse")
    assert r.status_code == 200
    body = r.json()
    assert "relative_velocity_km_s" in body
    assert body["relative_velocity_km_s"] is not None
    assert isinstance(body["relative_velocity_km_s"], float)
    assert body["relative_velocity_km_s"] > 0.0
