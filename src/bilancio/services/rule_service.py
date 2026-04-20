"""RuleService — CRUD for categorization rules + YAML import/export.

Every mutation writes a row to audit_log. No route or parser should call
this service's write methods — only ImportService and API routes may do so.
"""

from datetime import UTC, datetime
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import AuditLog, CategorizationRule

_VALID_PATTERN_TYPES = {"contains", "exact", "starts_with", "regex"}


def _now() -> datetime:
    return datetime.now(UTC)


class RuleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_rules(self, user_id: int) -> list[CategorizationRule]:
        """Return all rules for user sorted by priority descending."""
        result = await self._db.execute(
            select(CategorizationRule)
            .where(CategorizationRule.user_id == user_id)
            .order_by(CategorizationRule.priority.desc())
        )
        return list(result.scalars().all())

    async def get(self, rule_id: int, user_id: int) -> CategorizationRule:
        """Return a single rule. Raises ValueError if not found or not owned."""
        result = await self._db.execute(
            select(CategorizationRule)
            .where(CategorizationRule.id == rule_id)
            .where(CategorizationRule.user_id == user_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise ValueError(f"Rule {rule_id} not found")
        return rule

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: int,
        pattern: str,
        pattern_type: str,
        category: str,
        subcategory: str | None = None,
        priority: int = 0,
        enabled: bool = True,
        created_by: str = "user",
    ) -> CategorizationRule:
        _validate_pattern_type(pattern_type)
        rule = CategorizationRule(
            user_id=user_id,
            pattern=pattern,
            pattern_type=pattern_type,
            category=category,
            subcategory=subcategory,
            priority=priority,
            enabled=enabled,
            created_at=_now(),
            created_by=created_by,
        )
        self._db.add(rule)
        await self._db.flush()  # populate rule.id before audit log

        self._db.add(
            AuditLog(
                timestamp=_now(),
                actor_user_id=user_id,
                action="create",
                entity_type="categorization_rule",
                entity_id=rule.id,
                before_state=None,
                after_state=_rule_snapshot(rule),
            )
        )
        await self._db.commit()
        await self._db.refresh(rule)
        return rule

    async def update(
        self,
        *,
        rule_id: int,
        user_id: int,
        pattern: str | None = None,
        pattern_type: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> CategorizationRule:
        rule = await self.get(rule_id, user_id)
        before = _rule_snapshot(rule)

        if pattern_type is not None:
            _validate_pattern_type(pattern_type)
            rule.pattern_type = pattern_type
        if pattern is not None:
            rule.pattern = pattern
        if category is not None:
            rule.category = category
        if subcategory is not None:
            rule.subcategory = subcategory
        if priority is not None:
            rule.priority = priority
        if enabled is not None:
            rule.enabled = enabled

        self._db.add(
            AuditLog(
                timestamp=_now(),
                actor_user_id=user_id,
                action="update",
                entity_type="categorization_rule",
                entity_id=rule.id,
                before_state=before,
                after_state=_rule_snapshot(rule),
            )
        )
        await self._db.commit()
        await self._db.refresh(rule)
        return rule

    async def delete(self, *, rule_id: int, user_id: int) -> None:
        rule = await self.get(rule_id, user_id)
        before = _rule_snapshot(rule)

        self._db.add(
            AuditLog(
                timestamp=_now(),
                actor_user_id=user_id,
                action="delete",
                entity_type="categorization_rule",
                entity_id=rule.id,
                before_state=before,
                after_state=None,
            )
        )
        await self._db.delete(rule)
        await self._db.commit()

    # ------------------------------------------------------------------
    # YAML import / export
    # ------------------------------------------------------------------

    async def export_yaml(self, user_id: int) -> str:
        """Serialize all user rules to a YAML string."""
        rules = await self.list_rules(user_id)
        payload = {
            "rules": [
                {
                    "pattern": r.pattern,
                    "pattern_type": r.pattern_type,
                    "category": r.category,
                    **({"subcategory": r.subcategory} if r.subcategory else {}),
                    "priority": r.priority,
                    "enabled": r.enabled,
                }
                for r in rules
            ]
        }
        return yaml.dump(payload, allow_unicode=True, sort_keys=False)

    async def import_yaml(self, user_id: int, yaml_text: str) -> int:
        """Create rules from a YAML string. Returns the number of rules created.

        Raises ValueError for any rule with an invalid pattern_type.
        """
        data = yaml.safe_load(yaml_text)
        raw_rules: list[dict[str, Any]] = data.get("rules", [])

        # Validate all before writing any
        for entry in raw_rules:
            pt = entry.get("pattern_type", "")
            _validate_pattern_type(pt)

        count = 0
        for entry in raw_rules:
            await self.create(
                user_id=user_id,
                pattern=entry["pattern"],
                pattern_type=entry["pattern_type"],
                category=entry["category"],
                subcategory=entry.get("subcategory"),
                priority=int(entry.get("priority", 0)),
                enabled=bool(entry.get("enabled", True)),
                created_by="import",
            )
            count += 1

        return count


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _validate_pattern_type(pattern_type: str) -> None:
    if pattern_type not in _VALID_PATTERN_TYPES:
        raise ValueError(
            f"Invalid pattern_type {pattern_type!r}. "
            f"Must be one of: {sorted(_VALID_PATTERN_TYPES)}"
        )


def _rule_snapshot(rule: CategorizationRule) -> dict[str, Any]:
    return {
        "pattern": rule.pattern,
        "pattern_type": rule.pattern_type,
        "category": rule.category,
        "subcategory": rule.subcategory,
        "priority": rule.priority,
        "enabled": rule.enabled,
    }
