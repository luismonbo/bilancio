"""Rules engine — matches a merchant string against a list of categorization rules.

Matching logic:
  1. Filter out disabled rules.
  2. Sort remaining rules by priority descending (higher number = higher priority).
  3. Evaluate each rule against the text in order; return the first match.
  4. All string comparisons are case-insensitive.
"""

import re
from dataclasses import dataclass

from bilancio.storage.models import CategorizationRule

_VALID_PATTERN_TYPES = {"contains", "exact", "starts_with", "regex"}


@dataclass
class RuleMatch:
    category: str
    subcategory: str | None
    matched_rule_id: int


def apply_rules(
    text: str,
    rules: list[CategorizationRule],
) -> RuleMatch | None:
    """Apply rules to text (merchant_clean or description_raw).

    Returns the first RuleMatch from the highest-priority matching rule,
    or None if no rule matches.
    """
    if not text or not text.strip():
        return None

    active = sorted(
        (r for r in rules if r.enabled),
        key=lambda r: r.priority,
        reverse=True,
    )

    for rule in active:
        if _matches(text, rule):
            return RuleMatch(
                category=rule.category,
                subcategory=rule.subcategory,
                matched_rule_id=rule.id,
            )

    return None


def _matches(text: str, rule: CategorizationRule) -> bool:
    if rule.pattern_type not in _VALID_PATTERN_TYPES:
        return False

    t = text.casefold()
    p = rule.pattern.casefold()

    if rule.pattern_type == "contains":
        return p in t
    if rule.pattern_type == "exact":
        return t == p
    if rule.pattern_type == "starts_with":
        return t.startswith(p)
    if rule.pattern_type == "regex":
        try:
            return bool(re.search(rule.pattern, text, re.IGNORECASE))
        except re.error:
            return False

    return False  # unreachable but satisfies mypy
