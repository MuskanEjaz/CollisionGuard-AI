"""Tests for GET /scenarios and GET /scenarios/{scenario_id}."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from schemas.scenario import Scenario, ScenarioType

client = TestClient(app)


# ── List endpoint ─────────────────────────────────────────────────────────────

def test_list_scenarios_returns_200():
    response = client.get("/scenarios")
    assert response.status_code == 200


def test_list_scenarios_count():
    """Exactly 2 synthetic scenarios must be present."""
    response = client.get("/scenarios")
    body = response.json()
    assert body["count"] == 2
    assert len(body["scenarios"]) == 2


def test_scenario_types_present():
    """One conjunction and one safe scenario must be returned."""
    response = client.get("/scenarios")
    types = {s["scenario_type"] for s in response.json()["scenarios"]}
    assert "conjunction" in types
    assert "safe" in types


def test_list_scenarios_schema_valid():
    """Every returned scenario must deserialise through the Scenario schema."""
    response = client.get("/scenarios")
    for raw in response.json()["scenarios"]:
        parsed = Scenario.model_validate(raw)
        assert parsed.scenario_id


# ── Detail endpoint ───────────────────────────────────────────────────────────

def test_get_conjunction_by_id():
    response = client.get("/scenarios/CONJ-001")
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "CONJ-001"
    assert body["scenario_type"] == ScenarioType.CONJUNCTION.value


def test_get_safe_by_id():
    response = client.get("/scenarios/SAFE-001")
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "SAFE-001"
    assert body["scenario_type"] == ScenarioType.SAFE.value


def test_get_nonexistent_scenario_returns_404():
    response = client.get("/scenarios/FAKE-999")
    assert response.status_code == 404


def test_scenario_propagation_fields_are_null():
    """Phase 1: propagation fields must be null (not computed)."""
    for scenario_id in ("CONJ-001", "SAFE-001"):
        response = client.get(f"/scenarios/{scenario_id}")
        body = response.json()
        assert body["predicted_miss_distance_km"] is None
        assert body["time_to_closest_approach_s"] is None


# ── Unit: schema validation ───────────────────────────────────────────────────

def test_invalid_scenario_raises_validation_error():
    """Passing a dict missing required fields must raise pydantic.ValidationError."""
    bad_data = {
        "scenario_id": "BAD-001",
        # scenario_type missing — required field
        "description": "deliberately broken",
        # epoch_utc, our_satellite, threat_object all missing
    }
    with pytest.raises(ValidationError):
        Scenario.model_validate(bad_data)


def test_invalid_tle_length_raises_validation_error():
    """A TLE line that is not 69 characters must be rejected."""
    from schemas.scenario import TLEData

    with pytest.raises(ValidationError):
        TLEData(
            line1="1 TOOSHORT",
            line2="2 99001  51.6400 208.5100 0001500  90.0000 270.0000 15.49000000 00017",
        )


def test_invalid_tle_prefix_raises_validation_error():
    """A TLE line 1 that does not start with '1 ' must be rejected."""
    from schemas.scenario import TLEData

    # Correct length (69) but wrong prefix
    bad_line1 = "X " + "9" * 67
    good_line2 = "2 99001  51.6400 208.5100 0001500  90.0000 270.0000 15.49000000 00017"
    with pytest.raises(ValidationError):
        TLEData(line1=bad_line1, line2=good_line2)


def test_negative_mass_raises_validation_error():
    """SpaceObject with non-positive mass must be rejected."""
    from schemas.scenario import SpaceObject, TLEData

    tle = TLEData(
        line1="1 99001U 25001A   25213.50000000  .00000100  00000-0  10000-4 0  9991",
        line2="2 99001  51.6400 208.5100 0001500  90.0000 270.0000 15.49000000 00017",
    )
    with pytest.raises(ValidationError):
        SpaceObject(
            object_id="BAD_SAT",
            name="Bad Satellite",
            tle=tle,
            mass_kg=-50.0,  # invalid
            cross_section_m2=4.2,
        )
