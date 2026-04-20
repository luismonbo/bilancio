"""Integration tests: auth dependency — token validation and /me endpoint."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.hashing import generate_token, hash_token
from bilancio.storage.models import ApiToken, User


def _now() -> datetime:
    return datetime.now(UTC)


async def _make_user_with_token(db: AsyncSession, email: str) -> tuple[User, str]:
    """Helper: insert a user and a valid API token; return (user, raw_token)."""
    user = User(email=email, display_name="Test", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw = generate_token()
    db.add(
        ApiToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            name="test-token",
            created_at=_now(),
        )
    )
    await db.commit()
    return user, raw


async def test_me_requires_bearer_token(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/me")
    assert response.status_code == 401  # no credentials → 401 from HTTPBearer


async def test_me_rejects_invalid_token(auth_client: AsyncClient) -> None:
    response = await auth_client.get(
        "/me", headers={"Authorization": "Bearer bad-token"}
    )
    assert response.status_code == 401


async def test_me_accepts_valid_token(
    auth_client: AsyncClient, db: AsyncSession
) -> None:
    user, raw = await _make_user_with_token(db, "valid@example.com")
    response = await auth_client.get("/me", headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "valid@example.com"
    assert data["id"] == user.id


async def test_me_rejects_revoked_token(
    auth_client: AsyncClient, db: AsyncSession
) -> None:
    user = User(email="revoked@example.com", display_name="Revoked", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw = generate_token()
    token = ApiToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        name="revoked-token",
        created_at=_now(),
        revoked_at=_now(),  # already revoked
    )
    db.add(token)
    await db.commit()

    response = await auth_client.get("/me", headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 401


async def test_me_rejects_disabled_user(
    auth_client: AsyncClient, db: AsyncSession
) -> None:
    user = User(
        email="disabled@example.com",
        display_name="Disabled",
        created_at=_now(),
        disabled_at=_now(),  # user is disabled
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw = generate_token()
    db.add(
        ApiToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            name="t",
            created_at=_now(),
        )
    )
    await db.commit()

    response = await auth_client.get("/me", headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 401
