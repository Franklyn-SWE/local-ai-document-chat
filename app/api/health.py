"""
Purpose:
    Provides lightweight health and readiness endpoints for operators and reviewers.

Place in the system:
    This API module exposes process liveness and basic application readiness
    without performing document retrieval or model inference.
"""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Report that the API process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, object]:
    """Report basic application readiness and configuration presence."""
    settings = get_settings()

    return {
        "status": "ready",
        "configuration": {
            "llm_model_configured": bool(settings.llm_model),
            "llm_url_configured": bool(str(settings.llm_url)),
            "data_dir": settings.data_dir,
        },
    }