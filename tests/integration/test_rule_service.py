"""Integration tests for RuleService — uses the in-memory SQLite DB."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.services.rule_service import RuleService
from bilancio.storage.models import User


def _now() -> datetime:
    return datetime.now(UTC)


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, display_name="Test", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_rule(db: AsyncSession) -> None:
    user = await _make_user(db, "create@example.com")
    svc = RuleService(db)

    rule = await svc.create(
        user_id=user.id,
        pattern="Esselunga",
        pattern_type="contains",
        category="Groceries",
        priority=10,
    )

    assert rule.id is not None
    assert rule.pattern == "Esselunga"
    assert rule.category == "Groceries"
    assert rule.enabled is True


async def test_create_rule_writes_audit_log(db: AsyncSession) -> None:
    from sqlalchemy import select

    from bilancio.storage.models import AuditLog

    user = await _make_user(db, "audit_create@example.com")
    svc = RuleService(db)
    await svc.create(
        user_id=user.id, pattern="X", pattern_type="contains", category="Y"
    )

    logs = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user.id)))
        .scalars()
        .all()
    )
    assert any(
        log.action == "create" and log.entity_type == "categorization_rule"
        for log in logs
    )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def test_list_returns_only_user_rules(db: AsyncSession) -> None:
    user_a = await _make_user(db, "list_a@example.com")
    user_b = await _make_user(db, "list_b@example.com")
    svc = RuleService(db)

    await svc.create(
        user_id=user_a.id, pattern="A", pattern_type="contains", category="Cat"
    )
    await svc.create(
        user_id=user_b.id, pattern="B", pattern_type="contains", category="Cat"
    )

    rules_a = await svc.list_rules(user_id=user_a.id)
    assert all(r.user_id == user_a.id for r in rules_a)
    assert len(rules_a) == 1


async def test_list_returns_rules_sorted_by_priority_desc(db: AsyncSession) -> None:
    user = await _make_user(db, "sort@example.com")
    svc = RuleService(db)

    await svc.create(
        user_id=user.id,
        pattern="Low",
        pattern_type="contains",
        category="C",
        priority=1,
    )
    await svc.create(
        user_id=user.id,
        pattern="High",
        pattern_type="contains",
        category="C",
        priority=50,
    )
    await svc.create(
        user_id=user.id,
        pattern="Mid",
        pattern_type="contains",
        category="C",
        priority=10,
    )

    rules = await svc.list_rules(user_id=user.id)
    priorities = [r.priority for r in rules]
    assert priorities == sorted(priorities, reverse=True)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_update_rule(db: AsyncSession) -> None:
    user = await _make_user(db, "update@example.com")
    svc = RuleService(db)
    rule = await svc.create(
        user_id=user.id, pattern="Old", pattern_type="contains", category="OldCat"
    )

    updated = await svc.update(rule_id=rule.id, user_id=user.id, category="NewCat")
    assert updated.category == "NewCat"


async def test_update_rule_writes_audit_log(db: AsyncSession) -> None:
    from sqlalchemy import select

    from bilancio.storage.models import AuditLog

    user = await _make_user(db, "audit_update@example.com")
    svc = RuleService(db)
    rule = await svc.create(
        user_id=user.id, pattern="X", pattern_type="contains", category="Y"
    )
    await svc.update(rule_id=rule.id, user_id=user.id, category="Z")

    logs = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user.id)))
        .scalars()
        .all()
    )
    assert any(
        log.action == "update" and log.entity_type == "categorization_rule"
        for log in logs
    )


async def test_update_rule_not_owned_raises(db: AsyncSession) -> None:
    user_a = await _make_user(db, "own_a@example.com")
    user_b = await _make_user(db, "own_b@example.com")
    svc = RuleService(db)
    rule = await svc.create(
        user_id=user_a.id, pattern="X", pattern_type="contains", category="Y"
    )

    with pytest.raises(ValueError, match="not found"):
        await svc.update(rule_id=rule.id, user_id=user_b.id, category="Z")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_rule(db: AsyncSession) -> None:
    user = await _make_user(db, "delete@example.com")
    svc = RuleService(db)
    rule = await svc.create(
        user_id=user.id, pattern="X", pattern_type="contains", category="Y"
    )

    await svc.delete(rule_id=rule.id, user_id=user.id)
    rules = await svc.list_rules(user_id=user.id)
    assert all(r.id != rule.id for r in rules)


async def test_delete_rule_writes_audit_log(db: AsyncSession) -> None:
    from sqlalchemy import select

    from bilancio.storage.models import AuditLog

    user = await _make_user(db, "audit_delete@example.com")
    svc = RuleService(db)
    rule = await svc.create(
        user_id=user.id, pattern="X", pattern_type="contains", category="Y"
    )
    await svc.delete(rule_id=rule.id, user_id=user.id)

    logs = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user.id)))
        .scalars()
        .all()
    )
    assert any(
        log.action == "delete" and log.entity_type == "categorization_rule"
        for log in logs
    )


async def test_delete_rule_not_owned_raises(db: AsyncSession) -> None:
    user_a = await _make_user(db, "del_a@example.com")
    user_b = await _make_user(db, "del_b@example.com")
    svc = RuleService(db)
    rule = await svc.create(
        user_id=user_a.id, pattern="X", pattern_type="contains", category="Y"
    )

    with pytest.raises(ValueError, match="not found"):
        await svc.delete(rule_id=rule.id, user_id=user_b.id)


# ---------------------------------------------------------------------------
# YAML export / import round-trip
# ---------------------------------------------------------------------------


async def test_yaml_export_contains_rules(db: AsyncSession) -> None:
    user = await _make_user(db, "yaml_export@example.com")
    svc = RuleService(db)
    await svc.create(
        user_id=user.id,
        pattern="Esselunga",
        pattern_type="contains",
        category="Groceries",
        priority=10,
    )
    await svc.create(
        user_id=user.id,
        pattern="ILIAD",
        pattern_type="exact",
        category="Utilities",
        priority=20,
    )

    yaml_text = await svc.export_yaml(user_id=user.id)
    assert "Esselunga" in yaml_text
    assert "Groceries" in yaml_text
    assert "ILIAD" in yaml_text


async def test_yaml_import_creates_rules(db: AsyncSession) -> None:
    user = await _make_user(db, "yaml_import@example.com")
    svc = RuleService(db)

    yaml_text = """
rules:
  - pattern: "Amazon"
    pattern_type: contains
    category: Shopping
    priority: 5
    enabled: true
  - pattern: "^Netflix"
    pattern_type: regex
    category: Entertainment
    subcategory: Streaming
    priority: 10
    enabled: true
"""
    count = await svc.import_yaml(user_id=user.id, yaml_text=yaml_text)
    assert count == 2

    rules = await svc.list_rules(user_id=user.id)
    categories = {r.category for r in rules}
    assert "Shopping" in categories
    assert "Entertainment" in categories


async def test_yaml_round_trip(db: AsyncSession) -> None:
    user = await _make_user(db, "roundtrip@example.com")
    svc = RuleService(db)

    await svc.create(
        user_id=user.id,
        pattern="Trenitalia",
        pattern_type="starts_with",
        category="Transport",
        priority=15,
    )

    exported = await svc.export_yaml(user_id=user.id)

    # Import into a different user to avoid duplicates
    user2 = await _make_user(db, "roundtrip2@example.com")
    svc2 = RuleService(db)
    await svc2.import_yaml(user_id=user2.id, yaml_text=exported)

    rules2 = await svc2.list_rules(user_id=user2.id)
    assert any(r.pattern == "Trenitalia" and r.category == "Transport" for r in rules2)


async def test_yaml_import_invalid_pattern_type_raises(db: AsyncSession) -> None:
    user = await _make_user(db, "yaml_bad@example.com")
    svc = RuleService(db)

    bad_yaml = """
rules:
  - pattern: "X"
    pattern_type: fuzzy
    category: Misc
"""
    with pytest.raises(ValueError, match="pattern_type"):
        await svc.import_yaml(user_id=user.id, yaml_text=bad_yaml)
