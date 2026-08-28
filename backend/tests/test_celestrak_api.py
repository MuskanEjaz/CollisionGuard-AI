"""
API endpoint tests for POST /scenarios/live (routers/celestrak.py).

Strategy:
  - Mock fetch_orbital_record so no live network request is made.
  - Mock _run_analysis so no propagation, evaluation, or advisory is triggered.
  - Test only the router logic: validation, error handling, and response shape.

Budget compliance: mocked HTTP, mocked analysis pipeline, no live calls,
no forbidden module imports. Expected duration: well under 10 seconds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from celestrak_client import (
    OrbitalRecord,
    CelesTrakTimeoutError,
    CelesTrakHTTPError,
    CelesTrakEmptyError,
    CelesTrakNonLEOError,
    flush_cache,
)

client = TestClient(app)

# ── Shared fixtures ───────────────────────────────────────────────────────────

_NOW = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

def _make_leo_record(norad_id: int, name: str) -> OrbitalRecord:
    """Return a synthetic LEO OrbitalRecord for use in mocks."""
    return OrbitalRecord(
        norad_cat_id=norad_id,
        object_name=name,
        cospar_id=f"1998-{norad_id:03d}A",
        epoch_utc=_NOW,
        mean_motion_rev_per_day=15.49,
        is_leo=True,
        retrieved_at_utc=_NOW,
        raw_omm_fields={
            "NORAD_CAT_ID": str(norad_id),
            "OBJECT_NAME": name,
            "OBJECT_ID": f"1998-{norad_id:03d}A",
            "CLASSIFICATION_TYPE": "U",
            "EPHEMERIS_TYPE": "0",
            "ELEMENT_SET_NO": "999",
            "REV_AT_EPOCH": "12345",
            "EPOCH": "2025-08-01T12:00:00.000000",
            "MEAN_MOTION": "15.49000000",
            "ECCENTRICITY": "0.0001500",
            "INCLINATION": "51.64",
            "RA_OF_ASC_NODE": "208.51",
            "ARG_OF_PERICENTER": "90.00",
            "MEAN_ANOMALY": "270.00",
            "MEAN_MOTION_DOT": "0.00000100",
            "MEAN_MOTION_DDOT": "0.00000000e+0",
            "BSTAR": "0.00010000",
        },
    )


def _make_stub_full_analysis(scenario_id: str):
    """Return a minimal FullAnalysisResponse-like dict for mock injection."""
    from schemas.analysis import (
        FullAnalysisResponse, RiskClassification, DataQualityNote,
    )
    from schemas.granite import GraniteAdvisoryResponse

    return FullAnalysisResponse(
        scenario_id=scenario_id,
        cached=False,
        analysis_timestamp=_NOW,
        nominal_miss_distance_km=0.42,
        tca_offset_seconds=3600.0,
        tca_utc=_NOW,
        is_conjunction=True,
        conjunction_threshold_km=1.0,
        risk=RiskClassification(
            level="CONJUNCTION",
            label="Conjunction Alert -- maneuver review required",
            color_hint="red",
        ),
        data_quality=[
            DataQualityNote(field="TLE source", note="Live CelesTrak public GP elements."),
        ],
        orbit_element_age_note="Epoch: 2025-08-01T12:00:00Z (CelesTrak GP data)",
        candidates=[],
        safe_count=0,
        total_count=0,
        evaluation_note="Stub evaluation note",
        advisory=GraniteAdvisoryResponse(
            scenario_id=scenario_id,
            source="deterministic_fallback",
            model_id="n/a",
            granite_summary="Deterministic fallback: no safe candidates.",
            granite_note="Stub note.",
            ranked_candidates=[],
            validation_warnings=["Stub warning"],
        ),
    )


@pytest.fixture(autouse=True)
def clear_ct_cache():
    flush_cache()
    yield
    flush_cache()


# ── Happy-path tests ──────────────────────────────────────────────────────────

def test_live_endpoint_exists():
    """POST /scenarios/live must not return 404 or 405."""
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot  = _make_leo_record(25544, "ISS (ZARYA)")
        thrt  = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544,
            "threat_catalog_id":    33591,
        })
        assert resp.status_code not in (404, 405)


def test_live_returns_200():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot  = _make_leo_record(25544, "ISS (ZARYA)")
        thrt  = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544,
            "threat_catalog_id":    33591,
        })
        assert resp.status_code == 200


def test_live_response_has_data_source():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert "data_source" in body
        assert "CelesTrak" in body["data_source"]


def test_live_response_live_data_flag_true():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        assert resp.json()["live_data"] is True


def test_live_response_has_covariance_source():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert "covariance_source" in body
        assert "Not provided" in body["covariance_source"]


def test_live_response_has_risk_estimate_basis():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert "risk_estimate_basis" in body
        assert "Screening-level" in body["risk_estimate_basis"]


def test_live_response_has_protected_object_metadata():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert body["protected_object_catalog_id"] == 25544
        assert body["protected_object_name"] == "ISS (ZARYA)"
        assert "protected_element_epoch_utc" in body
        assert "protected_element_age_hours" in body


def test_live_response_has_threat_object_metadata():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert body["threat_object_catalog_id"] == 33591
        assert body["threat_object_name"] == "DEBRIS-33591"
        assert "threat_element_epoch_utc" in body
        assert "threat_element_age_hours" in body


def test_live_response_has_data_limitations():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert "data_limitations" in body
        assert len(body["data_limitations"]) > 20


def test_live_response_has_embedded_analysis():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        body = resp.json()
        assert "analysis" in body
        assert "nominal_miss_distance_km" in body["analysis"]
        assert "risk" in body["analysis"]


def test_live_fetches_both_objects():
    """Verify the router calls fetch_orbital_record twice (once per object)."""
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        assert mock_fetch.call_count == 2


# ── Validation: bad request ───────────────────────────────────────────────────

def test_identical_ids_returns_422():
    resp = client.post("/scenarios/live", json={
        "protected_catalog_id": 25544,
        "threat_catalog_id":    25544,
    })
    assert resp.status_code == 422


def test_zero_protected_id_returns_422():
    resp = client.post("/scenarios/live", json={
        "protected_catalog_id": 0,
        "threat_catalog_id":    33591,
    })
    assert resp.status_code == 422


def test_negative_threat_id_returns_422():
    resp = client.post("/scenarios/live", json={
        "protected_catalog_id": 25544,
        "threat_catalog_id":    -1,
    })
    assert resp.status_code == 422


def test_missing_protected_id_returns_422():
    resp = client.post("/scenarios/live", json={"threat_catalog_id": 33591})
    assert resp.status_code == 422


def test_missing_threat_id_returns_422():
    resp = client.post("/scenarios/live", json={"protected_catalog_id": 25544})
    assert resp.status_code == 422


def test_string_id_returns_422():
    resp = client.post("/scenarios/live", json={
        "protected_catalog_id": "abc",
        "threat_catalog_id":    33591,
    })
    assert resp.status_code == 422


# ── Error propagation from client ────────────────────────────────────────────

def test_timeout_on_protected_returns_504():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch:
        mock_fetch.side_effect = CelesTrakTimeoutError("timed out")
        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        assert resp.status_code == 504


def test_timeout_on_threat_returns_504():
    prot = _make_leo_record(25544, "ISS (ZARYA)")
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch:
        mock_fetch.side_effect = [prot, CelesTrakTimeoutError("timed out")]
        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        assert resp.status_code == 504


def test_not_found_on_protected_returns_404():
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch:
        mock_fetch.side_effect = CelesTrakEmptyError("no records")
        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 99999, "threat_catalog_id": 33591,
        })
        assert resp.status_code == 404


def test_not_found_on_threat_returns_404():
    prot = _make_leo_record(25544, "ISS (ZARYA)")
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch:
        mock_fetch.side_effect = [prot, CelesTrakEmptyError("no records")]
        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 99999,
        })
        assert resp.status_code == 404


def test_non_leo_protected_returns_422():
    non_leo = OrbitalRecord(
        norad_cat_id=11111,
        object_name="GEO-SAT",
        cospar_id="2000-001A",
        epoch_utc=_NOW,
        mean_motion_rev_per_day=1.002,  # GEO, not LEO
        is_leo=False,
        retrieved_at_utc=_NOW,
        raw_omm_fields={},
    )
    thrt = _make_leo_record(33591, "DEBRIS-33591")
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch:
        mock_fetch.side_effect = [non_leo, thrt]
        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 11111, "threat_catalog_id": 33591,
        })
        assert resp.status_code == 422


def test_non_leo_threat_returns_422():
    prot = _make_leo_record(25544, "ISS (ZARYA)")
    non_leo = OrbitalRecord(
        norad_cat_id=22222,
        object_name="GEO-2",
        cospar_id="2001-001A",
        epoch_utc=_NOW,
        mean_motion_rev_per_day=1.002,
        is_leo=False,
        retrieved_at_utc=_NOW,
        raw_omm_fields={},
    )
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch:
        mock_fetch.side_effect = [prot, non_leo]
        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 22222,
        })
        assert resp.status_code == 422


# ── Synthetic scenarios unaffected ───────────────────────────────────────────

def test_synthetic_conjunction_scenario_still_works():
    """Adding the live route must not break existing synthetic scenario listing."""
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    types = {s["scenario_type"] for s in body["scenarios"]}
    assert "conjunction" in types
    assert "safe" in types


def test_live_route_does_not_overwrite_synthetic_scenarios():
    """IDs used by live route must not collide with committed synthetic scenario IDs."""
    with patch("routers.celestrak.fetch_orbital_record") as mock_fetch, \
         patch("routers.celestrak._run_analysis") as mock_analysis:

        prot = _make_leo_record(25544, "ISS (ZARYA)")
        thrt = _make_leo_record(33591, "DEBRIS-33591")
        mock_fetch.side_effect = [prot, thrt]
        mock_analysis.return_value = _make_stub_full_analysis("LIVE-25544-33591")

        resp = client.post("/scenarios/live", json={
            "protected_catalog_id": 25544, "threat_catalog_id": 33591,
        })
        assert resp.status_code == 200

    # Synthetic scenarios must still be intact
    synth = client.get("/scenarios")
    assert synth.status_code == 200
    ids = {s["scenario_id"] for s in synth.json()["scenarios"]}
    assert "LIVE-25544-33591" not in ids
    assert "CONJ-001" in ids or "safe_scenario" in ids or len(ids) == 2
