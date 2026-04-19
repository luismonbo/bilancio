from fastapi import APIRouter
from pydantic import BaseModel

from bilancio.config import get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)
