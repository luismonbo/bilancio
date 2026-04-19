"""FastAPI auth dependency — validates Bearer tokens against the DB."""

from datetime import datetime, timezone

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.hashing import verify_token
from bilancio.storage.database import get_db
from bilancio.storage.models import ApiToken, User

logger = structlog.get_logger()
_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the Bearer token and return the authenticated User.

    Raises 401 if the token is invalid, revoked, or belongs to a disabled user.
    """
    raw_token = credentials.credentials
    user = await _lookup_user(raw_token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def _lookup_user(raw_token: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(ApiToken)
        .join(User, ApiToken.user_id == User.id)
        .where(ApiToken.revoked_at.is_(None))
        .where(User.disabled_at.is_(None))
    )
    active_tokens = result.scalars().all()

    for api_token in active_tokens:
        if verify_token(raw_token, api_token.token_hash):
            user_id = api_token.user_id
            api_token.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            return await db.get(User, user_id)

    return None
