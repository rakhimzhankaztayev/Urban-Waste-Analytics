"""FastAPI router for AI engine endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Lightweight health check endpoint for the AI engine."""
    return {"status": "ok"}
