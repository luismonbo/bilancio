"""Integration test fixtures — spin up a fresh SQLite in-memory DB per session."""

import secrets
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _now() -> datetime:
    return datetime.now(UTC)


@pytest_asyncio.fixture(scope="session")
async def engine():  # type: ignore[misc]
    from bilancio.storage.models import Base

    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:  # type: ignore[misc]
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def auth_client(db: AsyncSession) -> AsyncClient:  # type: ignore[misc]
    """HTTP client with DB overridden to the in-memory test session."""
    from bilancio.main import app
    from bilancio.storage.database import get_db

    async def _override_get_db():  # type: ignore[misc]
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed(db: AsyncSession, auth_client: AsyncClient):  # type: ignore[misc]
    """Yields (user, headers) with a live token ready for route tests.

    Creates a unique user + API token per test so emails never collide.
    """
    from bilancio.auth.hashing import generate_token, hash_token
    from bilancio.storage.models import ApiToken, User

    email = f"route_{secrets.token_hex(8)}@example.com"
    user = User(email=email, display_name="Route User", created_at=_now())
    db.add(user)
    await db.flush()

    token = generate_token()
    db.add(
        ApiToken(
            user_id=user.id,
            token_hash=hash_token(token),
            name="test",
            created_at=_now(),
        )
    )
    await db.commit()

    yield user, {"Authorization": f"Bearer {token}"}
