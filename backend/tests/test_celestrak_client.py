"""
Unit tests for celestrak_client.py.

All HTTP calls are mocked via unittest.mock.patch.
No live network requests are made.
No expensive analysis pipeline is executed.

Budget compliance: no imports of forbidden modules, no live calls,
no propagation. Expected duration: well under 5 seconds.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import celestrak_client as ct
from celestrak_client import (
    OrbitalRecord,
    CelesTrakTimeoutError,
    CelesTrakHTTPError,
    CelesTrakEmptyError,
    CelesTrakMalformedError,
    CelesTrakIDMismatchError,
    CelesTrakNonLEOError,
    fetch_orbital_record,
    check_leo,
    flush_cache,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

# Minimal valid CelesTrak OMM JSON record for NORAD 25544
_VALID_OMM = {
    "NORAD_CAT_ID": "25544",
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "CLASSIFICATION_TYPE": "U",
    "EPHEMERIS_TYPE": "0",
    "ELEMENT_SET_NO": "999",
    "REV_AT_EPOCH": "12345",
    "EPOCH": "2025-08-01T12:00:00.000000",
    "MEAN_MOTION": "15.49000000",      # > 11.25 → LEO
    "ECCENTRICITY": "0.0001500",
    "INCLINATION": "51.64",
    "RA_OF_ASC_NODE": "208.51",
    "ARG_OF_PERICENTER": "90.00",
    "MEAN_ANOMALY": "270.00",
    "MEAN_MOTION_DOT": "0.00000100",
    "MEAN_MOTION_DDOT": "0.00000000e+0",
    "BSTAR": "0.00010000",
}

# OMM for a GEO object (mean motion ~1.0 rev/day — not LEO)
_GEO_OMM = {**_VALID_OMM, "NORAD_CAT_ID": "33591", "MEAN_MOTION": "1.00270000"}


def _make_mock_response(status_code: int, json_data) -> MagicMock:
    """Return a mock httpx.Response-like object."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


def _make_mock_client(response: MagicMock) -> MagicMock:
    """Return a mock httpx.Client whose .get() returns the given response."""
    mock_client = MagicMock()
    mock_client.get.return_value = response
    return mock_client


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure a clean cache state before and after every test."""
    flush_cache()
    yield
    flush_cache()


# ── fetch_orbital_record: happy path ─────────────────────────────────────────

def test_fetch_returns_orbital_record():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert isinstance(record, OrbitalRecord)


def test_fetch_correct_norad_id():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.norad_cat_id == 25544


def test_fetch_correct_object_name():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.object_name == "ISS (ZARYA)"


def test_fetch_cospar_id():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.cospar_id == "1998-067A"


def test_fetch_epoch_is_utc_aware():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.epoch_utc.tzinfo is not None
    assert record.epoch_utc.tzinfo == timezone.utc


def test_fetch_epoch_value():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.epoch_utc == datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_fetch_mean_motion_stored():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.mean_motion_rev_per_day == pytest.approx(15.49, abs=0.001)


def test_fetch_leo_true_for_leo_object():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.is_leo is True


def test_fetch_leo_false_for_geo_object():
    geo = {**_GEO_OMM}
    resp   = _make_mock_response(200, [geo])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(33591, _http_client=client)
    assert record.is_leo is False


def test_fetch_retrieved_at_is_recent():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    before = datetime.now(tz=timezone.utc)
    record = fetch_orbital_record(25544, _http_client=client)
    after  = datetime.now(tz=timezone.utc)
    assert before <= record.retrieved_at_utc <= after


def test_fetch_raw_omm_fields_preserved():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert "MEAN_MOTION" in record.raw_omm_fields
    assert record.raw_omm_fields["NORAD_CAT_ID"] == "25544"


def test_fetch_calls_correct_url():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    fetch_orbital_record(25544, _http_client=client)
    call_url = client.get.call_args[0][0]
    assert "celestrak.org" in call_url
    assert "CATNR=25544" in call_url
    assert "FORMAT=JSON" in call_url


def test_fetch_sends_user_agent():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    fetch_orbital_record(25544, _http_client=client)
    call_headers = client.get.call_args[1]["headers"]
    assert "User-Agent" in call_headers
    assert "CollisionGuard" in call_headers["User-Agent"]


def test_fetch_uses_https():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    fetch_orbital_record(25544, _http_client=client)
    call_url = client.get.call_args[0][0]
    assert call_url.startswith("https://")


# ── Cache behaviour ───────────────────────────────────────────────────────────

def test_cache_hit_prevents_second_request():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    fetch_orbital_record(25544, _http_client=client)
    # Second call with same ID — client.get should NOT be called again
    fetch_orbital_record(25544, _http_client=client)
    assert client.get.call_count == 1


def test_cache_returns_same_record():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    r1 = fetch_orbital_record(25544, _http_client=client)
    r2 = fetch_orbital_record(25544, _http_client=client)
    assert r1 is r2


def test_flush_cache_clears_all():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    fetch_orbital_record(25544, _http_client=client)
    n = flush_cache()
    assert n == 1


def test_flush_cache_allows_refetch():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    fetch_orbital_record(25544, _http_client=client)
    flush_cache()
    fetch_orbital_record(25544, _http_client=client)
    assert client.get.call_count == 2


# ── Error handling ────────────────────────────────────────────────────────────

def test_raises_value_error_on_zero_id():
    with pytest.raises(ValueError, match="positive integer"):
        fetch_orbital_record(0)


def test_raises_value_error_on_negative_id():
    with pytest.raises(ValueError, match="positive integer"):
        fetch_orbital_record(-1)


def test_raises_http_error_on_404():
    resp   = _make_mock_response(404, {})
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakHTTPError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_http_error_on_500():
    resp   = _make_mock_response(500, {})
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakHTTPError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_empty_error_on_empty_list():
    resp   = _make_mock_response(200, [])
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakEmptyError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_malformed_on_non_list():
    resp   = _make_mock_response(200, {"error": "not a list"})
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakMalformedError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_malformed_on_missing_norad_id():
    omm = {k: v for k, v in _VALID_OMM.items() if k != "NORAD_CAT_ID"}
    resp   = _make_mock_response(200, [omm])
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakMalformedError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_malformed_on_missing_epoch():
    omm = {k: v for k, v in _VALID_OMM.items() if k != "EPOCH"}
    resp   = _make_mock_response(200, [omm])
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakMalformedError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_malformed_on_missing_mean_motion():
    omm = {k: v for k, v in _VALID_OMM.items() if k != "MEAN_MOTION"}
    resp   = _make_mock_response(200, [omm])
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakMalformedError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_id_mismatch():
    # Response says NORAD 99999 but we requested 25544
    omm    = {**_VALID_OMM, "NORAD_CAT_ID": "99999"}
    resp   = _make_mock_response(200, [omm])
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakIDMismatchError):
        fetch_orbital_record(25544, _http_client=client)


def test_raises_timeout_error():
    import httpx
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.TimeoutException("timed out")
    with pytest.raises(CelesTrakTimeoutError):
        fetch_orbital_record(25544, _http_client=mock_client)


def test_raises_malformed_on_bad_json():
    # json() raises an exception
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("not json")
    client = _make_mock_client(mock_response)
    with pytest.raises(CelesTrakMalformedError):
        fetch_orbital_record(25544, _http_client=client)


def test_malformed_epoch_string():
    omm    = {**_VALID_OMM, "EPOCH": "not-a-date"}
    resp   = _make_mock_response(200, [omm])
    client = _make_mock_client(resp)
    with pytest.raises(CelesTrakMalformedError, match="EPOCH"):
        fetch_orbital_record(25544, _http_client=client)


# ── check_leo ─────────────────────────────────────────────────────────────────

def test_check_leo_passes_for_leo():
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    # Should not raise
    check_leo(record)


def test_check_leo_raises_for_geo():
    geo_omm = {**_GEO_OMM}
    resp    = _make_mock_response(200, [geo_omm])
    client  = _make_mock_client(resp)
    record  = fetch_orbital_record(33591, _http_client=client)
    with pytest.raises(CelesTrakNonLEOError):
        check_leo(record)


def test_check_leo_error_contains_mean_motion():
    geo_omm = {**_GEO_OMM}
    resp    = _make_mock_response(200, [geo_omm])
    client  = _make_mock_client(resp)
    record  = fetch_orbital_record(33591, _http_client=client)
    with pytest.raises(CelesTrakNonLEOError, match="mean motion"):
        check_leo(record)


# ── OrbitalRecord fields ──────────────────────────────────────────────────────

def test_orbital_record_raw_fields_are_copy():
    """raw_omm_fields must be a defensive copy — mutating it should not affect cache."""
    resp   = _make_mock_response(200, [_VALID_OMM])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    record.raw_omm_fields["NORAD_CAT_ID"] = "MUTATED"
    # Retrieve from cache — should not have been mutated
    flush_cache()
    # Re-verify original dict is unchanged
    assert _VALID_OMM["NORAD_CAT_ID"] == "25544"


def test_object_name_fallback_when_missing():
    """When OBJECT_NAME is absent, fallback to NORAD-{id}."""
    omm    = {k: v for k, v in _VALID_OMM.items() if k != "OBJECT_NAME"}
    resp   = _make_mock_response(200, [omm])
    client = _make_mock_client(resp)
    record = fetch_orbital_record(25544, _http_client=client)
    assert record.object_name == "NORAD-25544"
