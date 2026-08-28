"""
CelesTrak integration schemas — CollisionGuard AI Phase 8.

Two-object request and live-data analysis response schemas.
All metadata fields are truthful:
  - covariance_source: "Not provided by GP data"
  - risk_estimate_basis: "Screening-level estimate based on public orbital elements"
  - live_data: True for live, False for synthetic

Human-supervised decision-support prototype. Simulation only — not flight software.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from typing import Annotated

from schemas.analysis import FullAnalysisResponse


# ── Request ───────────────────────────────────────────────────────────────────

class LiveScenarioRequest(BaseModel):
    """
    Two-object CelesTrak fetch request.

    Both IDs must be positive integers and must differ.
    """
    protected_catalog_id: Annotated[
        int,
        Field(gt=0, description="NORAD catalog number of the protected satellite"),
    ]
    threat_catalog_id: Annotated[
        int,
        Field(gt=0, description="NORAD catalog number of the threat object"),
    ]

    @model_validator(mode="after")
    def ids_must_differ(self) -> "LiveScenarioRequest":
        if self.protected_catalog_id == self.threat_catalog_id:
            raise ValueError(
                "protected_catalog_id and threat_catalog_id must differ. "
                "Cannot assess conjunction between an object and itself."
            )
        return self


# ── Object metadata ───────────────────────────────────────────────────────────

class CelesTrakObjectMeta(BaseModel):
    """Metadata for one fetched object — returned to the frontend."""
    norad_cat_id: int
    object_name: str
    cospar_id: str
    element_epoch_utc: datetime
    element_age_hours: float          # age of elements at fetch time


# ── Live-data analysis response ───────────────────────────────────────────────

class LiveAnalysisResponse(BaseModel):
    """
    Full analysis for a live two-object CelesTrak scenario.

    Wraps FullAnalysisResponse and adds CelesTrak source metadata.
    All provenance fields are mandatory and must be truthful.
    """
    # Embedded full analysis (same structure as synthetic scenarios)
    analysis: FullAnalysisResponse

    # Source metadata
    data_source: str = "CelesTrak GP catalog"
    data_source_type: str = "Public orbital elements"
    source_provider: str = "CelesTrak"
    source_format: str = "OMM/JSON (General Perturbations)"
    source_retrieved_at_utc: datetime

    # Object identity
    protected_object_catalog_id: int
    threat_object_catalog_id: int
    protected_object_name: str
    threat_object_name: str

    # Element epochs
    protected_element_epoch_utc: datetime
    threat_element_epoch_utc: datetime
    protected_element_age_hours: float
    threat_element_age_hours: float

    # Scientific honesty — these are fixed truthful values
    covariance_available: bool = False
    covariance_source: str = "Unavailable — not supplied by CelesTrak GP data"
    covariance_basis: str = "Public GP orbital elements do not include operational conjunction covariance"
    collision_probability_available: bool = False
    collision_probability: float | None = None
    risk_estimate_basis: str = (
        "Screening-level miss-distance assessment based on public GP elements"
    )
    live_data: bool = True
    data_limitations: str = (
        "CelesTrak GP elements are publicly available general-perturbations orbital "
        "data with no state-estimate covariance. Miss distance and risk estimates "
        "are screening-level only. Element age may reduce accuracy. "
        "SGP4 propagation in TEME frame using public GP elements. "
        "Human-supervised decision-support prototype — not flight software."
    )
    prototype_label: str = "Human-supervised decision-support prototype"
    simulation_label: str = "Simulation only — not flight software"
