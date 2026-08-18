# Maneuver candidate generator -- Phase 3.
#
# For Phase 1 prototype scope: exactly 5 hardcoded delta-v candidates
# spanning a range of prograde, retrograde, and normal burns.
# These are realistic candidate magnitudes for a LEO avoidance maneuver.
#
# NOTE -- SIMPLIFIED FOR PROTOTYPE:
#   Candidate delta-v values are hardcoded, not computed from optimal
#   targeting.  In a real system they would be derived from targeting
#   algorithms (e.g., differential correction against TCA geometry).
#   See SIMPLIFIED markers below.
from __future__ import annotations
from schemas.maneuver import ManeuverCandidate, ManeuverDirection

# SIMPLIFIED FOR PROTOTYPE: fixed candidate set, not optimised for geometry.
_BASE_CANDIDATES: list[dict] = [
    {
        "candidate_id": "MAN-001",
        "label": "Small prograde +0.5 m/s",
        "direction": ManeuverDirection.PROGRADE,
        "delta_v_ms": 0.5,
    },
    {
        "candidate_id": "MAN-002",
        "label": "Medium prograde +1.0 m/s",
        "direction": ManeuverDirection.PROGRADE,
        "delta_v_ms": 1.0,
    },
    {
        "candidate_id": "MAN-003",
        "label": "Large prograde +2.0 m/s",
        "direction": ManeuverDirection.PROGRADE,
        "delta_v_ms": 2.0,
    },
    {
        "candidate_id": "MAN-004",
        "label": "Small retrograde -0.5 m/s",
        "direction": ManeuverDirection.RETROGRADE,
        "delta_v_ms": -0.5,
    },
    {
        "candidate_id": "MAN-005",
        "label": "Out-of-plane normal +1.0 m/s",
        "direction": ManeuverDirection.NORMAL,
        "delta_v_ms": 1.0,
    },
]


def get_maneuver_candidates() -> list[ManeuverCandidate]:
    # Return the hardcoded candidate list as validated ManeuverCandidate objects.
    # SIMPLIFIED FOR PROTOTYPE: no scenario-specific targeting.
    return [ManeuverCandidate(**c) for c in _BASE_CANDIDATES]
