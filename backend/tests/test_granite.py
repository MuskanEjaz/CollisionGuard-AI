# Phase 6 + 6.5 tests -- Granite advisory integration
#
# All tests use mocked Granite responses -- no live watsonx credentials needed.
# Tests verify:
#   - Fallback triggers when credentials/config absent or invalid
#   - Only safe candidates are sent to Granite
#   - Physics values always come from backend, never from Granite output
#   - Conflicting Granite values are rejected with a warning
#   - Structurally invalid Granite output falls back to deterministic ranking
#   - Unsafe candidate references in Granite output are skipped
#   - Configurable model ID (never hardcoded)
#   - model_id always reported in advisory response
#   - Credential values never appear in error messages or responses
#   - Invalid URL (non-HTTPS) triggers fallback, not crash
#   - Malformed Granite output handled gracefully
#   - Numeric conflict rejection produces a warning
from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from schemas.maneuver import ManeuverCandidate, ManeuverDirection, EvaluationResponse
from schemas.granite import GraniteAdvisoryResponse
from granite_client import (
    _deterministic_fallback,
    _parse_granite_response,
    _has_valid_config,
    _validate_config,
    _ConfigError,
    get_granite_advisory,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_safe_candidate(cid: str, score: float = 0.9) -> ManeuverCandidate:
    return ManeuverCandidate(
        candidate_id=cid,
        label=f"Candidate {cid}",
        direction=ManeuverDirection.PROGRADE,
        delta_v_ms=0.5,
        is_safe=True,
        fuel_cost_kg=0.104,
        post_maneuver_miss_distance_km=13.5,
        baseline_score=score,
    )


def _make_evaluation(scenario_id: str = "CONJ-001",
                     candidates: list | None = None) -> EvaluationResponse:
    if candidates is None:
        candidates = [
            _make_safe_candidate("MAN-001", 0.99),
            _make_safe_candidate("MAN-002", 0.97),
        ]
    return EvaluationResponse(
        scenario_id=scenario_id,
        nominal_miss_distance_km=0.029,
        candidates=candidates,
        safe_count=sum(1 for c in candidates if c.is_safe),
        total_count=len(candidates),
        evaluation_note="",
    )


# ---------------------------------------------------------------------------
# Unit: configuration validation
# ---------------------------------------------------------------------------

class _MockSettings:
    def __init__(self, **kwargs):
        self.watsonx_apikey    = kwargs.get("watsonx_apikey", "key")
        self.watsonx_project_id = kwargs.get("watsonx_project_id", "proj")
        self.watsonx_url       = kwargs.get("watsonx_url", "https://us-south.ml.cloud.ibm.com")
        self.watsonx_model_id  = kwargs.get("watsonx_model_id", "ibm/granite-3-8b-instruct")


def test_validate_config_passes_with_full_config():
    _validate_config(_MockSettings())   # must not raise


def test_validate_config_fails_missing_apikey():
    with pytest.raises(_ConfigError, match="WATSONX_APIKEY"):
        _validate_config(_MockSettings(watsonx_apikey=""))


def test_validate_config_fails_missing_project_id():
    with pytest.raises(_ConfigError, match="WATSONX_PROJECT_ID"):
        _validate_config(_MockSettings(watsonx_project_id=""))


def test_validate_config_fails_missing_url():
    with pytest.raises(_ConfigError, match="WATSONX_URL"):
        _validate_config(_MockSettings(watsonx_url=""))


def test_validate_config_fails_non_https_url():
    with pytest.raises(_ConfigError, match="HTTPS"):
        _validate_config(_MockSettings(watsonx_url="http://insecure.example.com"))


def test_validate_config_fails_missing_model_id():
    with pytest.raises(_ConfigError, match="WATSONX_MODEL_ID"):
        _validate_config(_MockSettings(watsonx_model_id=""))


def test_config_error_message_contains_no_credential_value():
    # The error message must describe the problem category, not the actual value.
    fake_key = "super_secret_api_key_12345"
    try:
        _validate_config(_MockSettings(watsonx_apikey="", watsonx_project_id=fake_key))
    except _ConfigError as exc:
        assert fake_key not in str(exc), "Credential value leaked into error message"


def test_has_valid_config_false_when_unconfigured():
    with patch("granite_client.get_settings",
               return_value=_MockSettings(watsonx_apikey="",
                                          watsonx_project_id="",
                                          watsonx_url="")):
        valid, reason = _has_valid_config()
    assert valid is False
    assert reason  # must have a non-empty reason


def test_has_valid_config_reason_contains_no_credential_value():
    fake_cred = "my_secret_cred"
    with patch("granite_client.get_settings",
               return_value=_MockSettings(watsonx_apikey=fake_cred,
                                          watsonx_url="http://bad")):
        _, reason = _has_valid_config()
    assert fake_cred not in reason


# ---------------------------------------------------------------------------
# Unit: deterministic fallback
# ---------------------------------------------------------------------------

def test_fallback_returns_advisory():
    safe = [_make_safe_candidate("MAN-001")]
    result = _deterministic_fallback("CONJ-001", safe, "test reason")
    assert isinstance(result, GraniteAdvisoryResponse)
    assert result.source == "deterministic_fallback"


def test_fallback_ranks_by_score():
    c1 = _make_safe_candidate("MAN-001", score=0.6)
    c2 = _make_safe_candidate("MAN-002", score=0.9)
    result = _deterministic_fallback("CONJ-001", [c1, c2], "test")
    top = next(r for r in result.ranked_candidates if r.rank == 1)
    assert top.candidate_id == "MAN-002"


def test_fallback_uses_backend_physics_values():
    c = _make_safe_candidate("MAN-001")
    c.post_maneuver_miss_distance_km = 13.5
    c.fuel_cost_kg = 0.104
    result = _deterministic_fallback("CONJ-001", [c], "test")
    rc = result.ranked_candidates[0]
    assert rc.post_maneuver_miss_distance_km == 13.5
    assert rc.fuel_cost_kg == 0.104


def test_fallback_no_safe_candidates():
    result = _deterministic_fallback("CONJ-001", [], "no safe candidates")
    assert result.source == "deterministic_fallback"
    assert result.ranked_candidates == []


def test_fallback_warning_in_response():
    result = _deterministic_fallback("CONJ-001", [], "test reason")
    assert any("test reason" in w for w in result.validation_warnings)


def test_fallback_granite_note_present():
    result = _deterministic_fallback("CONJ-001", [], "x")
    assert len(result.granite_note) > 0
    assert "human operator" in result.granite_note.lower()


def test_fallback_reports_model_id():
    # model_id must be reported in fallback responses
    result = _deterministic_fallback("CONJ-001", [], "test", model_id="ibm/test-model")
    assert result.model_id == "ibm/test-model"


def test_fallback_model_id_from_settings_when_not_passed():
    with patch("granite_client.get_settings",
               return_value=_MockSettings(watsonx_model_id="ibm/from-settings")):
        result = _deterministic_fallback("CONJ-001", [], "test")
    assert result.model_id == "ibm/from-settings"


# ---------------------------------------------------------------------------
# Unit: _parse_granite_response
# ---------------------------------------------------------------------------

def test_parse_valid_granite_json():
    safe = [_make_safe_candidate("MAN-001"), _make_safe_candidate("MAN-002")]
    raw = json.dumps({
        "ranking": [
            {"candidate_id": "MAN-001", "rank": 1, "explanation": "Best miss."},
            {"candidate_id": "MAN-002", "rank": 2, "explanation": "Good fuel."},
        ],
        "summary": "MAN-001 is recommended.",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe, model_id="ibm/test")
    assert result is not None
    assert result.source == "granite"
    assert len(result.ranked_candidates) == 2
    assert result.ranked_candidates[0].candidate_id == "MAN-001"


def test_parse_model_id_in_response():
    safe = [_make_safe_candidate("MAN-001")]
    raw = json.dumps({
        "ranking": [{"candidate_id": "MAN-001", "rank": 1, "explanation": "Best."}],
        "summary": "summary",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe, model_id="ibm/granite-custom")
    assert result is not None
    assert result.model_id == "ibm/granite-custom"


def test_parse_physics_values_from_backend_not_granite():
    safe = [_make_safe_candidate("MAN-001")]
    safe[0].post_maneuver_miss_distance_km = 13.5
    safe[0].fuel_cost_kg = 0.104
    raw = json.dumps({
        "ranking": [{
            "candidate_id": "MAN-001", "rank": 1, "explanation": "Best.",
            "post_miss": 999.0, "fuel": 999.0,
        }],
        "summary": "MAN-001 is best.",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None
    rc = result.ranked_candidates[0]
    # Backend values must win over Granite's stated values
    assert rc.post_maneuver_miss_distance_km == 13.5
    assert rc.fuel_cost_kg == 0.104


def test_parse_numeric_conflict_produces_warning():
    safe = [_make_safe_candidate("MAN-001")]
    safe[0].post_maneuver_miss_distance_km = 13.5
    raw = json.dumps({
        "ranking": [{
            "candidate_id": "MAN-001", "rank": 1, "explanation": "Best.",
            "post_miss": 9999.0,   # far outside 1% tolerance
        }],
        "summary": "MAN-001.",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None
    assert any("post_miss" in w for w in result.validation_warnings)


def test_parse_rejects_invalid_json():
    safe = [_make_safe_candidate("MAN-001")]
    result = _parse_granite_response("not json at all", "CONJ-001", safe)
    assert result is None


def test_parse_rejects_missing_ranking_key():
    safe = [_make_safe_candidate("MAN-001")]
    raw = json.dumps({"summary": "no ranking key"})
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is None


def test_parse_handles_empty_ranking_list():
    safe = [_make_safe_candidate("MAN-001")]
    raw = json.dumps({"ranking": [], "summary": "empty"})
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None
    # MAN-001 must be appended by backend
    ids = [r.candidate_id for r in result.ranked_candidates]
    assert "MAN-001" in ids
    assert any("omitted" in w.lower() for w in result.validation_warnings)


def test_parse_skips_unsafe_candidate_reference():
    safe = [_make_safe_candidate("MAN-001")]
    raw = json.dumps({
        "ranking": [
            {"candidate_id": "MAN-999-UNSAFE", "rank": 1, "explanation": "Best."},
            {"candidate_id": "MAN-001",         "rank": 2, "explanation": "Second."},
        ],
        "summary": "summary",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None
    ids = [r.candidate_id for r in result.ranked_candidates]
    assert "MAN-999-UNSAFE" not in ids
    assert "MAN-001" in ids
    assert any("MAN-999-UNSAFE" in w for w in result.validation_warnings)


def test_parse_appends_omitted_candidates():
    safe = [_make_safe_candidate("MAN-001"), _make_safe_candidate("MAN-002")]
    raw = json.dumps({
        "ranking": [{"candidate_id": "MAN-001", "rank": 1, "explanation": "Best."}],
        "summary": "Only MAN-001.",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None
    ids = [r.candidate_id for r in result.ranked_candidates]
    assert "MAN-002" in ids
    assert any("omitted" in w.lower() for w in result.validation_warnings)


def test_parse_json_with_preamble():
    safe = [_make_safe_candidate("MAN-001")]
    preamble = "Here is my ranking:\n"
    raw = preamble + json.dumps({
        "ranking": [{"candidate_id": "MAN-001", "rank": 1, "explanation": "Good."}],
        "summary": "MAN-001 is best.",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None


def test_parse_malformed_entry_skipped():
    # An entry with a non-string candidate_id should be skipped gracefully
    safe = [_make_safe_candidate("MAN-001")]
    raw = json.dumps({
        "ranking": [
            {"candidate_id": None, "rank": 1, "explanation": "bad entry"},
            {"candidate_id": "MAN-001", "rank": 2, "explanation": "good entry"},
        ],
        "summary": "summary",
    })
    result = _parse_granite_response(raw, "CONJ-001", safe)
    assert result is not None
    ids = [r.candidate_id for r in result.ranked_candidates]
    assert "MAN-001" in ids


# ---------------------------------------------------------------------------
# Unit: get_granite_advisory -- config gate and error handling
# ---------------------------------------------------------------------------

def test_get_advisory_falls_back_when_no_credentials():
    evaluation = _make_evaluation()
    with patch("granite_client._has_valid_config", return_value=(False, "WATSONX_APIKEY is not set")):
        result = get_granite_advisory(evaluation)
    assert result.source == "deterministic_fallback"
    assert any("WATSONX_APIKEY" in w for w in result.validation_warnings)


def test_get_advisory_falls_back_on_invalid_url():
    evaluation = _make_evaluation()
    with patch("granite_client._has_valid_config",
               return_value=(False, "WATSONX_URL must use HTTPS")):
        result = get_granite_advisory(evaluation)
    assert result.source == "deterministic_fallback"
    assert any("HTTPS" in w for w in result.validation_warnings)


def test_get_advisory_falls_back_on_api_error():
    evaluation = _make_evaluation()
    with patch("granite_client._has_valid_config", return_value=(True, "")), \
         patch("granite_client._call_granite", side_effect=RuntimeError("network error")):
        result = get_granite_advisory(evaluation)
    assert result.source == "deterministic_fallback"
    # Error message must contain the type name, not the raw error message
    # (raw message could contain credential traces in theory)
    assert any("RuntimeError" in w for w in result.validation_warnings)


def test_get_advisory_error_does_not_expose_credentials():
    # Even if the error message from the SDK contains a credential value,
    # the warning stored in the response must only contain the type name.
    evaluation = _make_evaluation()
    fake_cred = "super_secret_key_99999"
    with patch("granite_client._has_valid_config", return_value=(True, "")), \
         patch("granite_client._call_granite",
               side_effect=RuntimeError(f"Auth failed for key={fake_cred}")):
        result = get_granite_advisory(evaluation)
    for w in result.validation_warnings:
        assert fake_cred not in w, f"Credential value leaked into warning: {w!r}"


def test_get_advisory_only_passes_safe_candidates():
    safe_c   = _make_safe_candidate("MAN-001")
    unsafe_c = ManeuverCandidate(
        candidate_id="MAN-UNSAFE",
        label="Unsafe",
        direction=ManeuverDirection.PROGRADE,
        delta_v_ms=99.0,
        is_safe=False,
        safety_rejection_reason="over budget",
    )
    evaluation = _make_evaluation(candidates=[safe_c, unsafe_c])
    captured = {}

    def fake_call(scenario_id, nominal_miss, safe_candidates):
        captured["ids"] = [c.candidate_id for c in safe_candidates]
        return _deterministic_fallback(scenario_id, safe_candidates, "mocked")

    with patch("granite_client._has_valid_config", return_value=(True, "")), \
         patch("granite_client._call_granite", side_effect=fake_call):
        get_granite_advisory(evaluation)

    assert "MAN-UNSAFE" not in captured.get("ids", [])
    assert "MAN-001" in captured.get("ids", [])


def test_get_advisory_with_mocked_granite_response():
    evaluation = _make_evaluation()
    mock_raw = json.dumps({
        "ranking": [
            {"candidate_id": "MAN-001", "rank": 1, "explanation": "Best miss."},
            {"candidate_id": "MAN-002", "rank": 2, "explanation": "Good fuel."},
        ],
        "summary": "MAN-001 is recommended.",
    })

    def fake_call(scenario_id, nominal_miss, safe_candidates):
        return _parse_granite_response(mock_raw, scenario_id, safe_candidates,
                                       model_id="ibm/mock-model")

    with patch("granite_client._has_valid_config", return_value=(True, "")), \
         patch("granite_client._call_granite", side_effect=fake_call):
        result = get_granite_advisory(evaluation)

    assert result.source == "granite"
    assert result.ranked_candidates[0].candidate_id == "MAN-001"
    # Physics values must be backend values
    assert result.ranked_candidates[0].post_maneuver_miss_distance_km == 13.5
    assert result.model_id == "ibm/mock-model"


def test_get_advisory_configurable_model_id():
    # model_id in response must reflect what was configured, not any hardcoded value
    evaluation = _make_evaluation()

    def fake_call(scenario_id, nominal_miss, safe_candidates):
        return _deterministic_fallback(scenario_id, safe_candidates, "mocked",
                                       model_id="ibm/custom-configured-model")

    with patch("granite_client._has_valid_config", return_value=(True, "")), \
         patch("granite_client._call_granite", side_effect=fake_call):
        result = get_granite_advisory(evaluation)

    assert result.model_id == "ibm/custom-configured-model"


def test_get_advisory_model_id_present_in_fallback():
    evaluation = _make_evaluation()
    with patch("granite_client._has_valid_config",
               return_value=(False, "WATSONX_APIKEY is not set")), \
         patch("granite_client.get_settings",
               return_value=_MockSettings(watsonx_model_id="ibm/granite-fallback-test")):
        result = get_granite_advisory(evaluation)
    assert result.model_id == "ibm/granite-fallback-test"


def test_get_advisory_physics_values_never_from_granite():
    evaluation = _make_evaluation()
    # Granite response with wrong physics
    mock_raw = json.dumps({
        "ranking": [
            {"candidate_id": "MAN-001", "rank": 1, "explanation": "Best.",
             "post_miss": 9999.0, "fuel": 9999.0},
            {"candidate_id": "MAN-002", "rank": 2, "explanation": "Good."},
        ],
        "summary": "Recommendation.",
    })

    def fake_call(scenario_id, nominal_miss, safe_candidates):
        return _parse_granite_response(mock_raw, scenario_id, safe_candidates)

    with patch("granite_client._has_valid_config", return_value=(True, "")), \
         patch("granite_client._call_granite", side_effect=fake_call):
        result = get_granite_advisory(evaluation)

    for rc in result.ranked_candidates:
        assert rc.post_maneuver_miss_distance_km == 13.5
        assert rc.fuel_cost_kg == 0.104


# ---------------------------------------------------------------------------
# Endpoint tests (fast -- mock both propagation and Granite)
# ---------------------------------------------------------------------------

def _mock_prop_result():
    from datetime import datetime, timezone
    return MagicMock(
        miss_distance_km=0.029,
        tca_offset_seconds=7102.0,
        tca_utc=datetime(2025, 8, 1, 14, 0, 0, tzinfo=timezone.utc),
        is_conjunction=True,
    )


def test_advise_endpoint_returns_200():
    with patch("routers.granite.propagate_scenario", return_value=_mock_prop_result()), \
         patch("routers.granite.evaluate_all_candidates",
               return_value=_make_evaluation().candidates), \
         patch("granite_client._has_valid_config", return_value=(False, "no creds")):
        r = client.post("/scenarios/CONJ-001/advise")
    assert r.status_code == 200


def test_advise_endpoint_404():
    r = client.post("/scenarios/FAKE-999/advise")
    assert r.status_code == 404


def test_advise_response_has_source():
    with patch("routers.granite.propagate_scenario", return_value=_mock_prop_result()), \
         patch("routers.granite.evaluate_all_candidates",
               return_value=_make_evaluation().candidates), \
         patch("granite_client._has_valid_config", return_value=(False, "no creds")):
        r = client.post("/scenarios/CONJ-001/advise")
    body = r.json()
    assert body["source"] in ("granite", "deterministic_fallback")


def test_advise_response_has_model_id():
    # model_id must always be present in the response
    with patch("routers.granite.propagate_scenario", return_value=_mock_prop_result()), \
         patch("routers.granite.evaluate_all_candidates",
               return_value=_make_evaluation().candidates), \
         patch("granite_client._has_valid_config", return_value=(False, "no creds")):
        r = client.post("/scenarios/CONJ-001/advise")
    body = r.json()
    assert "model_id" in body
    assert body["model_id"]  # must be non-empty


def test_advise_response_granite_note_present():
    with patch("routers.granite.propagate_scenario", return_value=_mock_prop_result()), \
         patch("routers.granite.evaluate_all_candidates",
               return_value=_make_evaluation().candidates), \
         patch("granite_client._has_valid_config", return_value=(False, "no creds")):
        r = client.post("/scenarios/CONJ-001/advise")
    body = r.json()
    assert "granite_note" in body
    assert "human operator" in body["granite_note"].lower()
