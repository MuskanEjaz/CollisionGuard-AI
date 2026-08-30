# Phase 7 backend tests -- cache, analysis, approval, execution, incident report
#
# All tests are fast -- propagation and Granite are mocked where needed.
# Does NOT run the real 1000-trial Monte Carlo or live Granite smoke test.
from __future__ import annotations
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from analysis_cache import flush_all, set_cached, get_cached, invalidate, cache_stats
from schemas.analysis import FullAnalysisResponse, RiskClassification, DataQualityNote
from schemas.maneuver import ManeuverCandidate, ManeuverDirection, EvaluationResponse
from schemas.granite import GraniteAdvisoryResponse, GraniteRankedCandidate

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_prop(miss_km: float = 0.029):
    from datetime import datetime, timezone
    return MagicMock(
        miss_distance_km=miss_km,
        tca_offset_seconds=7102.0,
        tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        is_conjunction=miss_km < 1.0,
        visualization_samples=[],  # falsy, so skip visualization block
        visualization_tca=None,    # falsy, so skip visualization block
        visualization_frame="TEME",
        visualization_units="km",
        relative_velocity_km_s=0.1,
        relative_velocity_vector_km_s=[0.1, 0.0, 0.0],
        relative_velocity_frame="TEME",
        relative_velocity_basis="estimated",
    )


def _mock_candidate(cid: str, is_safe: bool = True,
                    post_miss: float = 13.5) -> ManeuverCandidate:
    return ManeuverCandidate(
        candidate_id=cid,
        label=f"Candidate {cid}",
        direction=ManeuverDirection.PROGRADE,
        delta_v_ms=0.5,
        is_safe=is_safe,
        safety_rejection_reason=None if is_safe else "over budget",
        fuel_cost_kg=0.104,
        post_maneuver_miss_distance_km=post_miss if is_safe else None,
        baseline_score=0.99 if is_safe else 0.0,
    )


def _mock_advisory(source: str = "deterministic_fallback") -> GraniteAdvisoryResponse:
    return GraniteAdvisoryResponse(
        scenario_id="CONJ-001",
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
        source=source,
        model_id="ibm/test-model",
        validation_warnings=[],
        granite_note="ADVISORY ONLY",
    )


def _mock_full_analysis(scenario_id: str = "CONJ-001",
                        miss_km: float = 0.029,
                        advisory_source: str = "deterministic_fallback") -> FullAnalysisResponse:
    candidates = [_mock_candidate("MAN-001"), _mock_candidate("MAN-002")]
    return FullAnalysisResponse(
        scenario_id=scenario_id,
        cached=False,
        analysis_timestamp=datetime.now(tz=timezone.utc),
        nominal_miss_distance_km=miss_km,
        tca_offset_seconds=7102.0,
        tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        is_conjunction=miss_km < 1.0,
        conjunction_threshold_km=1.0,
        risk=RiskClassification(level="CONJUNCTION", label="Conjunction Alert",
                                color_hint="red"),
        data_quality=[DataQualityNote(field="TLE source", note="Synthetic")],
        orbit_element_age_note="Epoch: synthetic",
        candidates=candidates,
        safe_count=2,
        total_count=2,
        evaluation_note="SIMPLIFIED FOR PROTOTYPE",
        advisory=_mock_advisory(advisory_source),
    )


# ---------------------------------------------------------------------------
# Cache unit tests
# ---------------------------------------------------------------------------

def setup_function():
    flush_all()


def test_cache_miss_on_empty():
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    result, hit = get_cached("CONJ-001", scenario)
    assert result is None
    assert hit is False


def test_cache_hit_after_set():
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    analysis = _mock_full_analysis()
    set_cached("CONJ-001", scenario, analysis)
    result, hit = get_cached("CONJ-001", scenario)
    assert hit is True
    assert result.scenario_id == "CONJ-001"


def test_cache_ttl_expiry():
    import json, pathlib, time
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis(), ttl_seconds=0.01)
    time.sleep(0.05)
    result, hit = get_cached("CONJ-001", scenario)
    assert hit is False


def test_cache_invalidate_by_scenario():
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())
    n = invalidate("CONJ-001")
    assert n >= 1
    _, hit = get_cached("CONJ-001", scenario)
    assert hit is False


def test_cache_stats_reflects_entries():
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())
    stats = cache_stats()
    assert stats["count"] >= 1


def test_cache_no_credential_values():
    # Verify the cache key is a hash, never a credential value
    import json, pathlib
    from schemas.scenario import Scenario
    from analysis_cache import _make_cache_key
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    key = _make_cache_key("CONJ-001", scenario)
    # Key must be a hex digest (16 hex chars), never a URL, API key, etc.
    assert len(key) == 16
    assert all(c in "0123456789abcdef" for c in key)


# ---------------------------------------------------------------------------
# Analysis endpoint tests (mocked)
# ---------------------------------------------------------------------------

def test_analyse_endpoint_returns_200():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001"), _mock_candidate("MAN-002")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    assert r.status_code == 200


def test_analyse_endpoint_404():
    r = client.post("/scenarios/FAKE-999/analyse")
    assert r.status_code == 404


def test_analyse_response_has_required_fields():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    body = r.json()
    for field in ("nominal_miss_distance_km", "tca_offset_seconds", "tca_utc",
                  "is_conjunction", "risk", "candidates", "advisory",
                  "prototype_label", "simulation_label", "risk_basis_label",
                  "cached", "data_quality"):
        assert field in body, f"Missing field: {field}"


def test_analyse_cached_flag_false_on_first_call():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    assert r.json()["cached"] is False


def test_analyse_cached_flag_true_on_second_call():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        client.post("/scenarios/CONJ-001/analyse")
        r2 = client.post("/scenarios/CONJ-001/analyse")
    assert r2.json()["cached"] is True


def test_analyse_cache_invalidation():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        client.post("/scenarios/CONJ-001/analyse")
    r_del = client.delete("/scenarios/CONJ-001/cache")
    assert r_del.status_code == 200
    assert r_del.json()["entries_removed"] >= 1


def test_analyse_disclosure_labels():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    body = r.json()
    assert "Human-supervised" in body["prototype_label"]
    assert "Simulation only" in body["simulation_label"]
    assert "screening-level" in body["risk_basis_label"]


def test_analyse_risk_classification_conjunction():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop(0.029)), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    assert r.json()["risk"]["level"] == "CONJUNCTION"
    assert r.json()["risk"]["color_hint"] == "red"


def test_analyse_risk_classification_safe():
    flush_all()
    with patch("routers.analysis.propagate_scenario",
               return_value=_mock_prop(miss_km=3414.0)), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/SAFE-001/analyse")
    assert r.json()["risk"]["level"] == "SAFE"
    assert r.json()["risk"]["color_hint"] == "green"


def test_analyse_advisory_source_in_response():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory("deterministic_fallback")):
        r = client.post("/scenarios/CONJ-001/analyse")
    body = r.json()
    assert body["advisory"]["source"] == "deterministic_fallback"


# ---------------------------------------------------------------------------
# Approval endpoint tests
# ---------------------------------------------------------------------------

def test_approve_safe_candidate():
    flush_all()
    # Pre-populate cache with a safe candidate
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/approve",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "TEST_OP"})
    assert r.status_code == 200
    body = r.json()
    assert body["safety_gate_passed"] is True
    assert body["execution"]["status"] == "approved"


def test_approve_unsafe_candidate_rejected():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    # Cache an analysis where MAN-001 is marked unsafe
    analysis = _mock_full_analysis()
    for c in analysis.candidates:
        if c.candidate_id == "MAN-001":
            c.is_safe = False
            c.safety_rejection_reason = "over budget"
    set_cached("CONJ-001", scenario, analysis)

    r = client.post("/scenarios/CONJ-001/approve",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "TEST_OP"})
    assert r.status_code == 200
    body = r.json()
    assert body["safety_gate_passed"] is False
    assert body["execution"]["status"] == "rejected"


def test_approve_scenario_mismatch_rejected():
    r = client.post("/scenarios/CONJ-001/approve",
                    json={"scenario_id": "SAFE-001",   # mismatch
                          "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 422


def test_approve_unknown_scenario_404():
    r = client.post("/scenarios/FAKE-999/approve",
                    json={"scenario_id": "FAKE-999", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Execution endpoint tests (safety gate enforced)
# ---------------------------------------------------------------------------

def test_execute_without_approval_rejected():
    # No prior /approve call -- must be rejected with 403
    import routers.analysis as analysis_mod
    analysis_mod._PENDING_APPROVALS.clear()
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 403


def test_execute_after_approval_succeeds():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    # First approve
    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    # Then execute
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete"
    assert body["simulated"] is True
    assert "SIMULATED" in body["message"]


def test_execute_approval_is_one_use():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    client.post("/scenarios/CONJ-001/execute",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    # Second execution attempt must fail
    r2 = client.post("/scenarios/CONJ-001/execute",
                     json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                           "operator_id": "OP"})
    assert r2.status_code == 403


def test_execute_response_is_simulated():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert body["simulated"] is True
    assert "not flight software" in body["execution_label"].lower()


def test_execute_uses_backend_physics_values():
    # Values in execution response must come from backend candidate, not UI
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    analysis = _mock_full_analysis()
    analysis.candidates[0].post_maneuver_miss_distance_km = 13.5001
    analysis.candidates[0].fuel_cost_kg = 0.1042
    set_cached("CONJ-001", scenario, analysis)

    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert body["post_maneuver_miss_distance_km"] == 13.5001
    assert body["fuel_consumed_kg"] == 0.1042


# ---------------------------------------------------------------------------
# Granite badge / source tests
# ---------------------------------------------------------------------------

def test_fallback_source_label():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory("deterministic_fallback")):
        r = client.post("/scenarios/CONJ-001/analyse")
    assert r.json()["advisory"]["source"] == "deterministic_fallback"


def test_granite_live_source_label():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory("granite")):
        r = client.post("/scenarios/CONJ-001/analyse")
    # "granite" source = live Granite succeeded
    assert r.json()["advisory"]["source"] == "granite"


def test_granite_live_badge_only_when_source_granite():
    # The UI must show "IBM Granite Live" only when source=="granite"
    # This test verifies the API contract the UI relies on
    body_fallback = _mock_advisory("deterministic_fallback").model_dump()
    body_live = _mock_advisory("granite").model_dump()
    assert body_fallback["source"] != "granite"
    assert body_live["source"] == "granite"


# ---------------------------------------------------------------------------
# Incident report tests
# ---------------------------------------------------------------------------

def test_incident_report_200():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/incident-report",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 200


def test_incident_report_is_simulated():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/incident-report",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert body["simulated"] is True
    assert "SIMULATED" in body["report_label"].upper()


def test_incident_report_contains_disclaimer():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/incident-report",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert "SIMULATED" in body["report_text"].upper()


def test_analyse_cache_ttl_expiration_forces_refresh():
    # Verify that expired cache entries are treated as misses and trigger re-computation
    flush_all()
    from unittest.mock import patch
    from analysis_cache import _CACHE, DEFAULT_TTL_SECONDS
    import time

    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()), \
         patch("time.monotonic") as mock_monotonic:
        # Set initial time to 0
        mock_monotonic.return_value = 0.0

        # Step 1: Populate cache (should be a miss)
        r1 = client.post("/scenarios/CONJ-001/analyse")
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["cached"] is False, "First analyse should be a cache miss"
        initial_nominal_miss = body1["nominal_miss_distance_km"]
        assert len(_CACHE) == 1, "Cache should have one entry after first call"

        # Step 2: Verify cache hit before expiration (at t=150s, well within 300s TTL)
        mock_monotonic.return_value = 150.0
        r2 = client.post("/scenarios/CONJ-001/analyse")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["cached"] is True, "Second analyse should be a cache hit (not expired)"
        assert body2["nominal_miss_distance_km"] == initial_nominal_miss, "Cached value should match"

        # Step 3: Simulate TTL expiration (at t=301s, just over 300s TTL)
        mock_monotonic.return_value = DEFAULT_TTL_SECONDS + 1.0
        r3 = client.post("/scenarios/CONJ-001/analyse")
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3["cached"] is False, "Third analyse should be a cache miss (expired)"
        assert len(_CACHE) == 1, "Cache should still have one entry (old replaced by new)"

        # Step 4: Verify fresh data was computed (value may differ due to mock, but we called the function)
        # The key point is that cached=False indicates a fresh computation occurred
        # We can also verify the nominal_miss_distance_km is present (it will be from our mock)
        assert "nominal_miss_distance_km" in body3


def test_analyse_disclosure_labels():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    body = r.json()
    assert "Human-supervised" in body["prototype_label"]
    assert "Simulation only" in body["simulation_label"]
    assert "screening-level" in body["risk_basis_label"]


def test_analyse_risk_classification_conjunction():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop(0.029)), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/CONJ-001/analyse")
    assert r.json()["risk"]["level"] == "CONJUNCTION"
    assert r.json()["risk"]["color_hint"] == "red"


def test_analyse_risk_classification_safe():
    flush_all()
    with patch("routers.analysis.propagate_scenario",
               return_value=_mock_prop(miss_km=3414.0)), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory()):
        r = client.post("/scenarios/SAFE-001/analyse")
    assert r.json()["risk"]["level"] == "SAFE"
    assert r.json()["risk"]["color_hint"] == "green"


def test_analyse_advisory_source_in_response():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory("deterministic_fallback")):
        r = client.post("/scenarios/CONJ-001/analyse")
    body = r.json()
    assert body["advisory"]["source"] == "deterministic_fallback"


# ---------------------------------------------------------------------------
# Approval endpoint tests
# ---------------------------------------------------------------------------

def test_approve_safe_candidate():
    flush_all()
    # Pre-populate cache with a safe candidate
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/approve",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "TEST_OP"})
    assert r.status_code == 200
    body = r.json()
    assert body["safety_gate_passed"] is True
    assert body["execution"]["status"] == "approved"


def test_approve_unsafe_candidate_rejected():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    # Cache an analysis where MAN-001 is marked unsafe
    analysis = _mock_full_analysis()
    for c in analysis.candidates:
        if c.candidate_id == "MAN-001":
            c.is_safe = False
            c.safety_rejection_reason = "over budget"
    set_cached("CONJ-001", scenario, analysis)

    r = client.post("/scenarios/CONJ-001/approve",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "TEST_OP"})
    assert r.status_code == 200
    body = r.json()
    assert body["safety_gate_passed"] is False
    assert body["execution"]["status"] == "rejected"


def test_approve_scenario_mismatch_rejected():
    r = client.post("/scenarios/CONJ-001/approve",
                    json={"scenario_id": "SAFE-001",   # mismatch
                          "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 422


def test_approve_unknown_scenario_404():
    r = client.post("/scenarios/FAKE-999/approve",
                    json={"scenario_id": "FAKE-999", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Execution endpoint tests (safety gate enforced)
# ---------------------------------------------------------------------------

def test_execute_without_approval_rejected():
    # No prior /approve call -- must be rejected with 403
    import routers.analysis as analysis_mod
    analysis_mod._PENDING_APPROVALS.clear()
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 403


def test_execute_after_approval_succeeds():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    # First approve
    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    # Then execute
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete"
    assert body["simulated"] is True
    assert "SIMULATED" in body["message"]


def test_execute_approval_is_one_use():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    client.post("/scenarios/CONJ-001/execute",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    # Second execution attempt must fail
    r2 = client.post("/scenarios/CONJ-001/execute",
                     json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                           "operator_id": "OP"})
    assert r2.status_code == 403


def test_execute_response_is_simulated():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert body["simulated"] is True
    assert "not flight software" in body["execution_label"].lower()


def test_execute_uses_backend_physics_values():
    # Values in execution response must come from backend candidate, not UI
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    analysis = _mock_full_analysis()
    analysis.candidates[0].post_maneuver_miss_distance_km = 13.5001
    analysis.candidates[0].fuel_cost_kg = 0.1042
    set_cached("CONJ-001", scenario, analysis)

    client.post("/scenarios/CONJ-001/approve",
                json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                      "operator_id": "OP"})
    r = client.post("/scenarios/CONJ-001/execute",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert body["post_maneuver_miss_distance_km"] == 13.5001
    assert body["fuel_consumed_kg"] == 0.1042


def test_execute_revalidates_safety_after_approval():
    # Safety gate: approval must NOT be sufficient to execute if candidate becomes unsafe
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario

    # Load the test scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)

    # Mock propagation to return a conjunction (so safety evaluation runs)
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop(0.029)):
        # Step 1: Cache safe analysis results for approval
        with patch("routers.analysis.evaluate_all_candidates",
                   return_value=[_mock_candidate("MAN-001", is_safe=True),
                                 _mock_candidate("MAN-002", is_safe=True)]):
            safe_analysis = _mock_full_analysis(miss_km=0.029)
            set_cached("CONJ-001", scenario, safe_analysis)

            # Step 2: Approve the safe candidate
            r_approve = client.post("/scenarios/CONJ-001/approve",
                                    json={"scenario_id": "CONJ-001",
                                          "candidate_id": "MAN-001",
                                          "operator_id": "TEST_OP"})
            assert r_approve.status_code == 200
            approve_body = r_approve.json()
            assert approve_body["safety_gate_passed"] is True
            assert approve_body["execution"]["status"] == "approved"

            # Step 3: Invalidate cache and create unsafe analysis for execution
            invalidate("CONJ-001")
            with patch("routers.analysis.evaluate_all_candidates"):
                # Get a fresh analysis and make the first candidate unsafe
                unsafe_analysis = _mock_full_analysis(miss_km=0.029)
                # Modify the first candidate to be unsafe
                for c in unsafe_analysis.candidates:
                    if c.candidate_id == "MAN-001":
                        c.is_safe = False
                        c.safety_rejection_reason = "new tracking data shows risk"
                        c.post_maneuver_miss_distance_km = None
                        c.fuel_cost_kg = None
                        c.baseline_score = 0.0
                        break
                set_cached("CONJ-001", scenario, unsafe_analysis)

                # Step 4: Attempt execution with the same approval
                r_execute = client.post("/scenarios/CONJ-001/execute",
                                        json={"scenario_id": "CONJ-001",
                                              "candidate_id": "MAN-001",
                                              "operator_id": "TEST_OP"})

                # Step 5: Verify execution is rejected due to re-validation
                assert r_execute.status_code == 422, f"Expected 422, got {r_execute.status_code}: {r_execute.text}"
                execute_body = r_execute.json()
                assert "detail" in execute_body
                assert "Safety gate: candidate 'MAN-001' is not safe." in execute_body["detail"]

                # Step 6: Verify pending approval was cleared (execution always deletes it before safety check)
                from routers import analysis as analysis_mod
                assert analysis_mod._PENDING_APPROVALS.get("CONJ-001") != "MAN-001", \
                    "Pending approval should have been cleared during execution attempt"


# ---------------------------------------------------------------------------
# Granite badge / source tests
# ---------------------------------------------------------------------------

def test_fallback_source_label():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory("deterministic_fallback")):
        r = client.post("/scenarios/CONJ-001/analyse")
    assert r.json()["advisory"]["source"] == "deterministic_fallback"


def test_granite_live_source_label():
    flush_all()
    with patch("routers.analysis.propagate_scenario", return_value=_mock_prop()), \
         patch("routers.analysis.evaluate_all_candidates",
               return_value=[_mock_candidate("MAN-001")]), \
         patch("routers.analysis.get_granite_advisory",
               return_value=_mock_advisory("granite")):
        r = client.post("/scenarios/CONJ-001/analyse")
    # "granite" source = live Granite succeeded
    assert r.json()["advisory"]["source"] == "granite"


def test_granite_live_badge_only_when_source_granite():
    # The UI must show "IBM Granite Live" only when source=="granite"
    # This test verifies the API contract the UI relies on
    body_fallback = _mock_advisory("deterministic_fallback").model_dump()
    body_live = _mock_advisory("granite").model_dump()
    assert body_fallback["source"] != "granite"
    assert body_live["source"] == "granite"


# ---------------------------------------------------------------------------
# Incident report tests
# ---------------------------------------------------------------------------

def test_incident_report_200():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/incident-report",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    assert r.status_code == 200


def test_incident_report_is_simulated():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/incident-report",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert body["simulated"] is True
    assert "SIMULATED" in body["report_label"].upper()


def test_incident_report_contains_disclaimer():
    flush_all()
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    set_cached("CONJ-001", scenario, _mock_full_analysis())

    r = client.post("/scenarios/CONJ-001/incident-report",
                    json={"scenario_id": "CONJ-001", "candidate_id": "MAN-001",
                          "operator_id": "OP"})
    body = r.json()
    assert "SIMULATED" in body["report_text"].upper()
