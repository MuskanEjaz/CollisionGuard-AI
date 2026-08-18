"""Phase 2 tests — propagation engine and /propagate endpoint."""
import math
import pytest
from fastapi.testclient import TestClient

from main import app
from propagation import propagate_scenario, CONJUNCTION_THRESHOLD_KM, _brent
from schemas.scenario import Scenario

client = TestClient(app)


# ── /propagate endpoint ───────────────────────────────────────────────────────

def test_propagate_conjunction_returns_200():
    r = client.post("/scenarios/CONJ-001/propagate")
    assert r.status_code == 200


def test_propagate_safe_returns_200():
    r = client.post("/scenarios/SAFE-001/propagate")
    assert r.status_code == 200


def test_propagate_nonexistent_returns_404():
    r = client.post("/scenarios/FAKE-999/propagate")
    assert r.status_code == 404


def test_propagate_response_fields():
    r = client.post("/scenarios/CONJ-001/propagate")
    body = r.json()
    assert "miss_distance_km" in body
    assert "tca_offset_seconds" in body
    assert "tca_utc" in body
    assert "is_conjunction" in body
    assert "conjunction_threshold_km" in body
    assert body["conjunction_threshold_km"] == CONJUNCTION_THRESHOLD_KM


def test_propagate_miss_distance_positive():
    r = client.post("/scenarios/CONJ-001/propagate")
    assert r.json()["miss_distance_km"] > 0


def test_propagate_tca_offset_in_window():
    """TCA must fall within the 24-hour search window."""
    r = client.post("/scenarios/CONJ-001/propagate")
    offset = r.json()["tca_offset_seconds"]
    assert 0 <= offset <= 86_400


def test_conjunction_scenario_is_conjunction():
    """Synthetic CONJ-001 TLEs are designed to produce a close pass < 1 km."""
    r = client.post("/scenarios/CONJ-001/propagate")
    assert r.json()["is_conjunction"] is True


def test_safe_scenario_is_not_conjunction():
    """Synthetic SAFE-001 TLEs are designed to produce a safe separation."""
    r = client.post("/scenarios/SAFE-001/propagate")
    assert r.json()["is_conjunction"] is False


# ── Propagation unit tests ────────────────────────────────────────────────────

def test_propagate_scenario_returns_result():
    import json, pathlib
    data = json.loads(
        (pathlib.Path(__file__).parent.parent / "data/scenarios/conjunction_scenario.json")
        .read_text()
    )
    scenario = Scenario.model_validate(data)
    result = propagate_scenario(scenario)
    assert result.scenario_id == "CONJ-001"
    assert result.miss_distance_km > 0
    assert not math.isnan(result.miss_distance_km)


def test_brent_finds_minimum():
    """Brent's method should find the minimum of a simple parabola."""
    # f(x) = (x - 3)^2, minimum at x=3
    result = _brent(lambda x: (x - 3.0) ** 2, 0.0, 6.0, 1e-6)
    assert abs(result - 3.0) < 1e-4


def test_teme_to_gcrs_conversion():
    """
    TEME→GCRS via t.M must produce a unit-length rotation (det ≈ 1).
    The matrix must be orthonormal — a non-trivial sanity check.
    """
    import numpy as np
    from skyfield.api import load
    import datetime

    ts = load.timescale()
    t = ts.from_datetime(datetime.datetime(2025, 8, 1, 12, 0, 0,
                                           tzinfo=datetime.timezone.utc))
    M = t.M
    det = np.linalg.det(M)
    assert abs(det - 1.0) < 1e-10, f"t.M determinant should be 1.0, got {det}"

    # Should not be the identity matrix — there IS a real rotation
    identity = np.eye(3)
    assert not np.allclose(M, identity, atol=1e-8), \
        "t.M should not be identity — TEME and GCRS differ by a real rotation"
