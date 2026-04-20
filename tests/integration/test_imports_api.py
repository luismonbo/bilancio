"""Integration tests for POST /accounts/{id}/import."""

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "MediobancaPremier_anonimized.xlsx"
)


async def _create_account(auth_client: AsyncClient, headers: dict) -> dict:
    return (
        await auth_client.post(
            "/accounts",
            json={"name": "Premier", "bank": "Mediobanca Premier"},
            headers=headers,
        )
    ).json()


# ---------------------------------------------------------------------------
# POST /accounts/{id}/import
# ---------------------------------------------------------------------------


async def test_import_requires_auth(auth_client: AsyncClient, authed: tuple) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    with open(_FIXTURE, "rb") as f:
        response = await auth_client.post(
            f"/accounts/{account['id']}/import",
            files={"file": ("statement.xlsx", f, "application/octet-stream")},
            # No auth headers
        )
    assert response.status_code == 401


async def test_import_unknown_account_returns_404(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    with open(_FIXTURE, "rb") as f:
        response = await auth_client.post(
            "/accounts/999999/import",
            files={"file": ("statement.xlsx", f, "application/octet-stream")},
            headers=headers,
        )
    assert response.status_code == 404


async def test_import_real_file_creates_transactions(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    """Upload the anonymised Mediobanca fixture and verify transactions are created."""
    user, headers = authed
    account = await _create_account(auth_client, headers)

    with open(_FIXTURE, "rb") as f:
        response = await auth_client.post(
            f"/accounts/{account['id']}/import",
            files={
                "file": (
                    "MediobancaPremier_anonimized.xlsx",
                    f,
                    "application/octet-stream",
                )
            },
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["added"] > 0
    assert body["skipped"] == 0


async def test_import_idempotent(auth_client: AsyncClient, authed: tuple) -> None:
    """Second import of the same file must report all as skipped."""
    user, headers = authed
    account = await _create_account(auth_client, headers)

    for _ in range(2):
        with open(_FIXTURE, "rb") as f:
            response = await auth_client.post(
                f"/accounts/{account['id']}/import",
                files={
                    "file": (
                        "MediobancaPremier_anonimized.xlsx",
                        f,
                        "application/octet-stream",
                    )
                },
                headers=headers,
            )

    body = response.json()
    assert body["added"] == 0
    assert body["skipped"] > 0


async def test_import_unrecognised_file_returns_422(
    auth_client: AsyncClient, authed: tuple, tmp_path: Path
) -> None:
    """A file that no parser recognises should return 422."""
    _, headers = authed
    account = await _create_account(auth_client, headers)

    fake_file = tmp_path / "garbage.xlsx"
    fake_file.write_bytes(b"not a real xlsx file")

    with open(fake_file, "rb") as f:
        response = await auth_client.post(
            f"/accounts/{account['id']}/import",
            files={"file": ("garbage.xlsx", f, "application/octet-stream")},
            headers=headers,
        )
    assert response.status_code == 422
