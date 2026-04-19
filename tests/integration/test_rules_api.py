"""Integration tests for /rules API routes."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# GET /rules
# ---------------------------------------------------------------------------


async def test_list_rules_requires_auth(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/rules")).status_code == 401


async def test_list_rules_empty(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    response = await auth_client.get("/rules", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_rules_returns_created(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    await auth_client.post(
        "/rules",
        json={"pattern": "Amazon", "pattern_type": "contains", "category": "Shopping"},
        headers=headers,
    )
    response = await auth_client.get("/rules", headers=headers)
    data = response.json()
    assert len(data) == 1
    assert data[0]["pattern"] == "Amazon"


# ---------------------------------------------------------------------------
# POST /rules
# ---------------------------------------------------------------------------


async def test_create_rule_returns_201(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.post(
        "/rules",
        json={
            "pattern": "ESSELUNGA",
            "pattern_type": "contains",
            "category": "Groceries",
            "subcategory": "Supermarket",
            "priority": 10,
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["pattern"] == "ESSELUNGA"
    assert body["category"] == "Groceries"
    assert body["id"] is not None


async def test_create_rule_invalid_pattern_type_returns_422(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.post(
        "/rules",
        json={"pattern": "X", "pattern_type": "fuzzy", "category": "Y"},
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_rule_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/rules", json={"pattern": "X", "pattern_type": "contains", "category": "Y"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /rules/{id}
# ---------------------------------------------------------------------------


async def test_get_rule(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    created = (
        await auth_client.post(
            "/rules",
            json={"pattern": "X", "pattern_type": "contains", "category": "Y"},
            headers=headers,
        )
    ).json()

    response = await auth_client.get(f"/rules/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_rule_not_found(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    assert (await auth_client.get("/rules/999999", headers=headers)).status_code == 404


# ---------------------------------------------------------------------------
# PATCH /rules/{id}
# ---------------------------------------------------------------------------


async def test_update_rule(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    created = (
        await auth_client.post(
            "/rules",
            json={"pattern": "Old", "pattern_type": "contains", "category": "OldCat"},
            headers=headers,
        )
    ).json()

    response = await auth_client.patch(
        f"/rules/{created['id']}",
        json={"category": "NewCat", "priority": 50},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "NewCat"
    assert body["priority"] == 50


async def test_update_rule_not_found(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    response = await auth_client.patch(
        "/rules/999999", json={"category": "X"}, headers=headers
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /rules/{id}
# ---------------------------------------------------------------------------


async def test_delete_rule(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    created = (
        await auth_client.post(
            "/rules",
            json={"pattern": "X", "pattern_type": "contains", "category": "Y"},
            headers=headers,
        )
    ).json()

    assert (
        await auth_client.delete(f"/rules/{created['id']}", headers=headers)
    ).status_code == 204


async def test_delete_rule_not_found(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    assert (
        await auth_client.delete("/rules/999999", headers=headers)
    ).status_code == 404


# ---------------------------------------------------------------------------
# GET /rules/export  and  POST /rules/import
# ---------------------------------------------------------------------------


async def test_export_rules_returns_yaml(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    await auth_client.post(
        "/rules",
        json={"pattern": "Trenitalia", "pattern_type": "starts_with", "category": "Transport"},
        headers=headers,
    )

    response = await auth_client.get("/rules/export", headers=headers)
    assert response.status_code == 200
    assert "Trenitalia" in response.text
    assert response.headers["content-type"].startswith("text/plain")


async def test_import_rules_creates_rules(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    yaml_body = (
        "rules:\n"
        "  - pattern: Amazon\n"
        "    pattern_type: contains\n"
        "    category: Shopping\n"
        "    priority: 5\n"
        "    enabled: true\n"
    )

    response = await auth_client.post(
        "/rules/import",
        content=yaml_body,
        headers={**headers, "content-type": "text/plain"},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1

    # Rule should now appear in the list
    rules = (await auth_client.get("/rules", headers=headers)).json()
    assert any(r["pattern"] == "Amazon" for r in rules)


async def test_import_rules_invalid_pattern_type_returns_422(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    bad_yaml = (
        "rules:\n"
        "  - pattern: X\n"
        "    pattern_type: fuzzy\n"
        "    category: Y\n"
    )
    response = await auth_client.post(
        "/rules/import",
        content=bad_yaml,
        headers={**headers, "content-type": "text/plain"},
    )
    assert response.status_code == 422
