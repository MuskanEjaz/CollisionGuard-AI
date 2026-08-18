"""GET /health endpoint."""
from fastapi import APIRouter
from config import get_settings
from schemas.health import ComponentStatus, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Returns the current health status of the backend.

    Phase 1 reports only the data_layer component.
    Phase 2 will add a propagation component.
    Phase 3 will add a granite component.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        components={
            "data_layer": ComponentStatus(
                status="ok",
                detail="Synthetic scenario files loaded",
            )
        },
    )
