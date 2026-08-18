# Phase 4 tests -- maneuver safety evaluator
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_evaluate_returns_200():
    r = client.post("/scenarios/CONJ-001/evaluate")
    assert r.status_code == 200


def test_evaluate_404_on_unknown():
    r = client.post("/scenarios/FAKE-999/evaluate")
    assert r.status_code == 404


def test_evaluate_response_fields():
    r = client.post("/scenarios/CONJ-001/evaluate")
    body = r.json()
    assert "nominal_miss_distance_km" in body
    assert "candidates" in body
    assert "safe_count" in body
    assert "total_count" in body
    assert "evaluation_note" in body


def test_evaluate_total_count():
    r = client.post("/scenarios/CONJ-001/evaluate")
    body = r.json()
    assert body["total_count"] == 5


def test_evaluate_all_candidates_have_is_safe():
    r = client.post("/scenarios/CONJ-001/evaluate")
    for c in r.json()["candidates"]:
        assert c["is_safe"] is not None


def test_evaluate_safe_candidates_have_score():
    r = client.post("/scenarios/CONJ-001/evaluate")
    for c in r.json()["candidates"]:
        if c["is_safe"]:
            assert c["baseline_score"] is not None
            assert 0.0 <= c["baseline_score"] <= 1.0


def test_evaluate_safe_candidates_have_post_miss():
    r = client.post("/scenarios/CONJ-001/evaluate")
    for c in r.json()["candidates"]:
        if c["is_safe"]:
            assert c["post_maneuver_miss_distance_km"] is not None
            assert c["post_maneuver_miss_distance_km"] > 0


def test_evaluate_safe_candidates_exceed_threshold():
    from maneuver_evaluator import SAFE_MISS_DISTANCE_KM
    r = client.post("/scenarios/CONJ-001/evaluate")
    for c in r.json()["candidates"]:
        if c["is_safe"]:
            assert c["post_maneuver_miss_distance_km"] >= SAFE_MISS_DISTANCE_KM


def test_evaluate_nominal_miss_matches_propagation():
    # The nominal miss distance returned by /evaluate must match /propagate
    r_eval  = client.post("/scenarios/CONJ-001/evaluate").json()
    r_prop  = client.post("/scenarios/CONJ-001/propagate").json()
    assert abs(r_eval["nominal_miss_distance_km"] - r_prop["miss_distance_km"]) < 0.001


def test_evaluate_note_contains_simplified():
    # The evaluation_note must flag simplified areas
    r = client.post("/scenarios/CONJ-001/evaluate")
    assert "SIMPLIFIED" in r.json()["evaluation_note"].upper()


def test_evaluate_conjunction_has_safe_candidates():
    # CONJ-001 should have at least one safe candidate
    r = client.post("/scenarios/CONJ-001/evaluate")
    assert r.json()["safe_count"] >= 1


def test_evaluate_unit_tsiolkovsky():
    from maneuver_evaluator import _tsiolkovsky_fuel
    # For very small delta-v, fuel should be approximately m * dv / Ve
    # Ve = 220 * 9.80665 = 2157.463 m/s
    # fuel ~ 450 * 0.5 / 2157.463 = ~0.1042 kg
    fuel = _tsiolkovsky_fuel(0.5, 450.0)
    assert 0.09 < fuel < 0.12


def test_evaluate_unit_dv_budget():
    # A candidate with delta_v > MAX_DELTA_V_MS must be rejected
    from maneuver_evaluator import evaluate_candidate, MAX_DELTA_V_MS
    from schemas.maneuver import ManeuverCandidate, ManeuverDirection
    import json, pathlib
    from schemas.scenario import Scenario
    data = json.loads((pathlib.Path(__file__).parent.parent /
                       "data/scenarios/conjunction_scenario.json").read_text())
    scenario = Scenario.model_validate(data)
    big_candidate = ManeuverCandidate(
        candidate_id="TEST-BIG",
        label="Over-budget",
        direction=ManeuverDirection.PROGRADE,
        delta_v_ms=MAX_DELTA_V_MS + 1.0,
    )
    result = evaluate_candidate(big_candidate, scenario, 0.03)
    assert result.is_safe is False
    assert "budget" in result.safety_rejection_reason.lower()
