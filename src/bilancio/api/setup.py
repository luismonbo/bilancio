"""Setup API — first-time bootstrap for a new Bilancio installation.

POST /setup creates the first user and returns a one-time plain API token.
Once any user exists the endpoint returns 409 Conflict.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.hashing import generate_token, hash_token
from bilancio.storage.database import get_db
from bilancio.storage.models import ApiToken, User

router = APIRouter(tags=["setup"])


def _now() -> datetime:
    return datetime.now(UTC)


class SetupCreate(BaseModel):
    email: str
    display_name: str


class SetupRead(BaseModel):
    token: str
    email: str
    message: str


@router.post("/setup", response_model=SetupRead, status_code=status.HTTP_201_CREATED)
async def setup(
    payload: SetupCreate,
    db: AsyncSession = Depends(get_db),
) -> SetupRead:
    """Create the first user and issue a plain API token.

    Returns 409 if any user already exists in the database.
    The token is shown once — store it immediately.
    """
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already configured. Authenticate with your existing token.",
        )

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        created_at=_now(),
    )
    db.add(user)
    await db.flush()

    plain_token = generate_token()
    db.add(
        ApiToken(
            user_id=user.id,
            token_hash=hash_token(plain_token),
            name="Setup token",
            created_at=_now(),
        )
    )
    await db.commit()

    return SetupRead(
        token=plain_token,
        email=user.email,
        message="Account created. Save your token — it will not be shown again.",
    )
