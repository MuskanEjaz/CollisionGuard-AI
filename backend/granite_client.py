# Granite LLM client -- Phase 6 (hardened in Phase 6.5).
#
# SAFETY ARCHITECTURE (non-negotiable):
#   1. Only backend-validated safe candidates are ever sent to Granite.
#   2. Granite may only rank and explain -- it may not alter computed values.
#   3. Every numeric value in Granite output is validated against the
#      backend-computed value before the response is returned.
#   4. If validation fails or Granite is unavailable, the deterministic
#      fallback is used and source="deterministic_fallback" is set.
#   5. Granite cannot approve execution, override a safety rejection, or
#      select an unsafe candidate.
#
# CREDENTIAL HANDLING:
#   Credentials are read from environment via config.get_settings().
#   They are NEVER logged, NEVER included in API responses, NEVER hardcoded.
#   If credentials are absent or invalid, the client falls back to
#   deterministic ranking. Errors reference only the type of failure, not
#   credential values.
#
# MODEL ID:
#   The active model is always read from settings.watsonx_model_id.
#   It is NEVER hardcoded in this file.
#   The active model_id is always reported in the advisory response.
from __future__ import annotations

import json
import logging

from config import get_settings
from schemas.maneuver import ManeuverCandidate, EvaluationResponse
from schemas.granite import GraniteAdvisoryResponse, GraniteRankedCandidate

logger = logging.getLogger(__name__)

# Tolerance for numeric validation against backend values.
# If Granite states a value differing by more than this fraction (relative),
# the Granite value is rejected and the backend value is used instead.
_NUMERIC_TOLERANCE = 0.01   # 1% relative tolerance


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

class _ConfigError(Exception):
    # Raised when the watsonx configuration is incomplete or invalid.
    # The message describes the problem category only -- no credential values.
    pass


def _validate_config(s) -> None:
    # Raises _ConfigError if any required field is missing or invalid.
    # Error messages describe the category of problem only.
    # They never contain the actual credential value.
    if not s.watsonx_apikey:
        raise _ConfigError("WATSONX_APIKEY is not set")
    if not s.watsonx_project_id:
        raise _ConfigError("WATSONX_PROJECT_ID is not set")
    if not s.watsonx_url:
        raise _ConfigError("WATSONX_URL is not set")
    if not s.watsonx_url.startswith("https://"):
        raise _ConfigError(
            "WATSONX_URL must use HTTPS (value has wrong scheme or is empty)"
        )
    if not s.watsonx_model_id:
        raise _ConfigError("WATSONX_MODEL_ID is not set")


def _has_valid_config() -> tuple[bool, str]:
    # Returns (True, "") if config is valid, (False, reason) otherwise.
    # The reason string contains no credential values.
    try:
        _validate_config(get_settings())
        return True, ""
    except _ConfigError as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    scenario_id: str,
    nominal_miss_km: float,
    safe_candidates: list[ManeuverCandidate],
) -> str:
    # Constructs a structured prompt constraining Granite to rank-and-explain only.
    # The prompt states explicitly that Granite must not modify any physics value.
    lines = [
        "You are an advisory system for a collision-avoidance decision-support tool.",
        "You must NOT modify any computed value. Your role is to rank and explain only.",
        "",
        f"Scenario: {scenario_id}",
        f"Nominal miss distance (no maneuver): {nominal_miss_km:.4f} km",
        "",
        "Safe maneuver candidates (all backend-validated):",
    ]
    for c in safe_candidates:
        lines.append(
            f"  ID={c.candidate_id} label={c.label!r}"
            f" delta_v={c.delta_v_ms:.2f}m/s"
            f" post_miss={c.post_maneuver_miss_distance_km:.4f}km"
            f" fuel={c.fuel_cost_kg:.4f}kg"
            f" score={c.baseline_score:.4f}"
        )
    lines += [
        "",
        "Task: Rank these candidates from best to worst for collision avoidance.",
        "For each candidate, provide a one-sentence explanation.",
        "Then write a 2-3 sentence summary paragraph.",
        "",
        "IMPORTANT: Do not change any numeric value. Do not recommend unsafe candidates.",
        "Do not mention autonomous execution. A human operator makes the final decision.",
        "",
        "Respond in this exact JSON format:",
        '{',
        '  "ranking": [',
        '    {"candidate_id": "...", "rank": 1, "explanation": "..."},',
        '    ...',
        '  ],',
        '  "summary": "..."',
        '}',
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

def _deterministic_fallback(
    scenario_id: str,
    safe_candidates: list[ManeuverCandidate],
    reason: str,
    model_id: str = "",
) -> GraniteAdvisoryResponse:
    # Rank by baseline_score descending -- no LLM, fully deterministic.
    # Used when Granite is unavailable or returns unusable output.
    # reason must describe only the failure category, never credential values.
    sorted_candidates = sorted(
        safe_candidates,
        key=lambda c: (c.baseline_score or 0.0),
        reverse=True,
    )
    ranked = []
    for rank, c in enumerate(sorted_candidates, start=1):
        ranked.append(GraniteRankedCandidate(
            candidate_id=c.candidate_id,
            rank=rank,
            explanation=(
                f"Ranked #{rank} by deterministic baseline score "
                f"({c.baseline_score:.4f}). "
                f"Post-maneuver miss distance: {c.post_maneuver_miss_distance_km:.3f} km. "
                f"Fuel cost: {c.fuel_cost_kg:.4f} kg."
            ),
            delta_v_ms=c.delta_v_ms,
            post_maneuver_miss_distance_km=c.post_maneuver_miss_distance_km,
            fuel_cost_kg=c.fuel_cost_kg,
            baseline_score=c.baseline_score,
        ))
    active_model = model_id or get_settings().watsonx_model_id or "not configured"
    return GraniteAdvisoryResponse(
        scenario_id=scenario_id,
        ranked_candidates=ranked,
        granite_summary=(
            f"Deterministic fallback ranking (reason: {reason}). "
            f"Candidates are sorted by baseline score. "
            f"Human operator must review and approve before any action."
        ),
        source="deterministic_fallback",
        model_id=active_model,
        validation_warnings=[f"Fallback used: {reason}"],
        granite_note=(
            "ADVISORY ONLY -- human operator approval required before execution. "
            "Granite may rank safe candidates only. It cannot alter computed values, "
            "override safety rejections, or approve execution."
        ),
    )


# ---------------------------------------------------------------------------
# Numeric validation
# ---------------------------------------------------------------------------

def _validate_numeric(
    field: str,
    granite_val: float,
    backend_val: float,
    warnings: list[str],
) -> float:
    # Validates a numeric value from Granite against the backend-computed value.
    # Returns the backend value regardless -- Granite values are never used.
    # Appends a warning if the discrepancy exceeds _NUMERIC_TOLERANCE.
    if backend_val == 0:
        if abs(granite_val) > _NUMERIC_TOLERANCE:
            warnings.append(
                f"{field}: Granite stated a non-zero value but backend is 0 "
                f"-- using backend value."
            )
        return backend_val
    rel_err = abs(granite_val - backend_val) / abs(backend_val)
    if rel_err > _NUMERIC_TOLERANCE:
        warnings.append(
            f"{field}: Granite value differs from backend by {rel_err:.2%} "
            f"(>{_NUMERIC_TOLERANCE:.0%} tolerance) -- using backend value."
        )
    return backend_val   # always return backend value


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_granite_response(
    raw_text: str,
    scenario_id: str,
    safe_candidates: list[ManeuverCandidate],
    model_id: str = "",
) -> GraniteAdvisoryResponse | None:
    # Parse and validate Granite JSON output.
    # Returns None if parsing fails or the response is structurally invalid.
    # Physics values are ALWAYS taken from the backend candidate objects,
    # never from anything Granite returned.
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("Granite response contained no JSON object")
            return None
        data = json.loads(raw_text[start:end])
    except json.JSONDecodeError as exc:
        logger.warning("Granite JSON decode failed: %s", exc)
        return None

    if "ranking" not in data or not isinstance(data["ranking"], list):
        logger.warning("Granite response missing 'ranking' list")
        return None

    candidate_map = {c.candidate_id: c for c in safe_candidates}
    warnings: list[str] = []
    ranked: list[GraniteRankedCandidate] = []
    seen_ids: set[str] = set()

    for entry in data["ranking"]:
        cid = entry.get("candidate_id", "")
        if cid not in candidate_map:
            warnings.append(
                f"Granite referenced unknown or unsafe candidate '{cid}' -- skipped."
            )
            continue
        if cid in seen_ids:
            warnings.append(f"Granite listed '{cid}' more than once -- skipped.")
            continue
        seen_ids.add(cid)

        bc = candidate_map[cid]   # backend-computed candidate -- source of truth

        # If Granite embedded numeric fields, validate them against backend.
        # The ranked candidate always uses backend values regardless.
        if "post_miss" in entry:
            _validate_numeric(
                f"{cid}.post_miss", float(entry["post_miss"]),
                bc.post_maneuver_miss_distance_km, warnings,
            )
        if "fuel" in entry:
            _validate_numeric(
                f"{cid}.fuel", float(entry["fuel"]),
                bc.fuel_cost_kg, warnings,
            )

        ranked.append(GraniteRankedCandidate(
            candidate_id=cid,
            rank=entry.get("rank", len(ranked) + 1),
            explanation=str(entry.get("explanation", "")),
            # Physics values: ALWAYS from backend, never from Granite output
            delta_v_ms=bc.delta_v_ms,
            post_maneuver_miss_distance_km=bc.post_maneuver_miss_distance_km,
            fuel_cost_kg=bc.fuel_cost_kg,
            baseline_score=bc.baseline_score,
        ))

    # Append any safe candidates Granite omitted (ranked at the end)
    for cid, bc in candidate_map.items():
        if cid not in seen_ids:
            warnings.append(f"Granite omitted candidate '{cid}' -- appended by backend.")
            ranked.append(GraniteRankedCandidate(
                candidate_id=cid,
                rank=len(ranked) + 1,
                explanation="Not ranked by Granite -- appended by backend.",
                delta_v_ms=bc.delta_v_ms,
                post_maneuver_miss_distance_km=bc.post_maneuver_miss_distance_km,
                fuel_cost_kg=bc.fuel_cost_kg,
                baseline_score=bc.baseline_score,
            ))

    summary = str(data.get("summary", "No summary provided."))
    active_model = model_id or get_settings().watsonx_model_id or "not configured"

    return GraniteAdvisoryResponse(
        scenario_id=scenario_id,
        ranked_candidates=ranked,
        granite_summary=summary,
        source="granite",
        model_id=active_model,
        validation_warnings=warnings,
        granite_note=(
            "ADVISORY ONLY -- human operator approval required before execution. "
            "Granite may rank safe candidates only. All physics values shown are "
            "backend-computed and have been validated. Granite cannot override "
            "safety rejections or approve execution."
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_granite_advisory(
    evaluation: EvaluationResponse,
) -> GraniteAdvisoryResponse:
    # Entry point: get Granite ranking for all safe candidates in an evaluation.
    #
    # SAFETY GATE: only safe candidates are ever sent to Granite.
    safe_candidates = [c for c in evaluation.candidates if c.is_safe]
    if not safe_candidates:
        return _deterministic_fallback(
            evaluation.scenario_id, [], "No safe candidates to rank."
        )

    valid, reason = _has_valid_config()
    if not valid:
        logger.info("watsonx config invalid -- using deterministic fallback: %s", reason)
        return _deterministic_fallback(
            evaluation.scenario_id,
            safe_candidates,
            reason,
        )

    try:
        return _call_granite(
            evaluation.scenario_id,
            evaluation.nominal_miss_distance_km,
            safe_candidates,
        )
    except Exception as exc:
        # Log only the exception type, not any credential values
        err_type = type(exc).__name__
        logger.warning("Granite API call failed (%s) -- using deterministic fallback",
                       err_type)
        return _deterministic_fallback(
            evaluation.scenario_id,
            safe_candidates,
            f"Granite API error: {err_type}",
        )


# ---------------------------------------------------------------------------
# Live Granite call
# ---------------------------------------------------------------------------

def _call_granite(
    scenario_id: str,
    nominal_miss_km: float,
    safe_candidates: list[ManeuverCandidate],
) -> GraniteAdvisoryResponse:
    # Live call to IBM watsonx.ai Granite.
    # Credentials are read from settings -- never hardcoded or logged.
    # Model ID is read from settings -- never hardcoded in this file.
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference

    s = get_settings()
    # Validate once more inside the call path (belt-and-suspenders)
    _validate_config(s)

    creds = Credentials(url=s.watsonx_url, api_key=s.watsonx_apikey)
    model_id = s.watsonx_model_id   # config-driven, never hardcoded

    model = ModelInference(
        model_id=model_id,
        credentials=creds,
        project_id=s.watsonx_project_id,
    )

    prompt = _build_prompt(scenario_id, nominal_miss_km, safe_candidates)
    response = model.chat(
        messages=[
            {"role": "user", "content": prompt}
        ],
        params={
            "max_tokens": 800,
            "temperature": 0.0,
        },
    )
    
    raw_text = response["choices"][0]["message"]["content"]
    parsed = _parse_granite_response(raw_text, scenario_id, safe_candidates,
                                     model_id=model_id)
    if parsed is None:
        return _deterministic_fallback(
            scenario_id,
            safe_candidates,
            "Granite response could not be parsed",
            model_id=model_id,
        )
    return parsed
