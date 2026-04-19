from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from bilancio.auth.dependencies import get_current_user
from bilancio.storage.models import User

router = APIRouter(prefix="/me", tags=["users"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    created_at: datetime


@router.get("", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user