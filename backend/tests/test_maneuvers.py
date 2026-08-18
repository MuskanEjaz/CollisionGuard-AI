# Phase 3 tests -- maneuver candidate endpoint
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_list_maneuvers_returns_200():
    r = client.get("/scenarios/CONJ-001/maneuvers")
    assert r.status_code == 200


def test_list_maneuvers_for_safe_scenario():
    r = client.get("/scenarios/SAFE-001/maneuvers")
    assert r.status_code == 200


def test_list_maneuvers_nonexistent_404():
    r = client.get("/scenarios/FAKE-999/maneuvers")
    assert r.status_code == 404


def test_maneuver_count():
    r = client.get("/scenarios/CONJ-001/maneuvers")
    body = r.json()
    assert body["count"] == 5
    assert len(body["candidates"]) == 5


def test_maneuver_fields_present():
    r = client.get("/scenarios/CONJ-001/maneuvers")
    for c in r.json()["candidates"]:
        assert "candidate_id" in c
        assert "label" in c
        assert "direction" in c
        assert "delta_v_ms" in c


def test_maneuver_directions_valid():
    valid_dirs = {"prograde", "retrograde", "radial_out", "normal"}
    r = client.get("/scenarios/CONJ-001/maneuvers")
    for c in r.json()["candidates"]:
        assert c["direction"] in valid_dirs


def test_maneuver_safety_fields_null_before_evaluation():
    # Phase 3: safety fields not populated until Phase 4 evaluator runs
    r = client.get("/scenarios/CONJ-001/maneuvers")
    for c in r.json()["candidates"]:
        assert c["is_safe"] is None
        assert c["fuel_cost_kg"] is None
        assert c["baseline_score"] is None


def test_maneuver_scenario_id_in_response():
    r = client.get("/scenarios/CONJ-001/maneuvers")
    assert r.json()["scenario_id"] == "CONJ-001"
