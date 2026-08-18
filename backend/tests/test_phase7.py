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
    return MagicMock(
        miss_distance_km=miss_km,
        tca_offset_seconds=7102.0,
        tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        is_conjunction=miss_km < 1.0,
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
    assert "Screening-level" in body["risk_basis_label"]


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
