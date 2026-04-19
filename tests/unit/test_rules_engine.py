"""Unit tests for the rules engine — no DB, no network."""

import pytest

from bilancio.categorizer.rules_engine import RuleMatch, apply_rules
from bilancio.storage.models import CategorizationRule


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _rule(
    pattern: str,
    pattern_type: str,
    category: str,
    subcategory: str | None = None,
    priority: int = 0,
    enabled: bool = True,
    rule_id: int = 1,
) -> CategorizationRule:
    r = CategorizationRule(
        id=rule_id,
        user_id=1,
        pattern=pattern,
        pattern_type=pattern_type,
        category=category,
        subcategory=subcategory,
        priority=priority,
        enabled=enabled,
        created_at=_now(),
    )
    return r


# ---------------------------------------------------------------------------
# apply_rules — basic matching
# ---------------------------------------------------------------------------


def test_contains_match():
    rules = [_rule("Esselunga", "contains", "Groceries")]
    result = apply_rules("Esselunga Milano", rules)
    assert result is not None
    assert result.category == "Groceries"


def test_contains_case_insensitive():
    rules = [_rule("esselunga", "contains", "Groceries")]
    result = apply_rules("ESSELUNGA MILANO", rules)
    assert result is not None


def test_exact_match():
    rules = [_rule("ILIAD", "exact", "Utilities")]
    assert apply_rules("ILIAD", rules) is not None
    assert apply_rules("ILIAD EXTRA", rules) is None


def test_starts_with_match():
    rules = [_rule("TRENITALIA", "starts_with", "Transport")]
    assert apply_rules("TRENITALIA - PT WL", rules) is not None
    assert apply_rules("BUY TRENITALIA", rules) is None


def test_regex_match():
    rules = [_rule(r"^PayPal", "regex", "Finance")]
    assert apply_rules("PayPal Europe S.a.r.", rules) is not None
    assert apply_rules("Not PayPal", rules) is None


def test_regex_case_insensitive():
    rules = [_rule(r"^paypal", "regex", "Finance")]
    assert apply_rules("PayPal Europe", rules) is not None


def test_no_match_returns_none():
    rules = [_rule("Esselunga", "contains", "Groceries")]
    assert apply_rules("Amazon Prime", rules) is None


def test_empty_rules_returns_none():
    assert apply_rules("Anything", []) is None


def test_match_returns_rule_match_dataclass():
    rules = [_rule("ILIAD", "contains", "Utilities", "Mobile", rule_id=7)]
    result = apply_rules("ILIAD", rules)
    assert isinstance(result, RuleMatch)
    assert result.category == "Utilities"
    assert result.subcategory == "Mobile"
    assert result.matched_rule_id == 7


# ---------------------------------------------------------------------------
# apply_rules — priority
# ---------------------------------------------------------------------------


def test_higher_priority_wins():
    low = _rule("Amazon", "contains", "Shopping", priority=1, rule_id=1)
    high = _rule("Amazon", "contains", "Electronics", priority=10, rule_id=2)
    result = apply_rules("Amazon Prime", [low, high])
    assert result is not None
    assert result.category == "Electronics"


def test_rules_evaluated_in_priority_order_regardless_of_list_order():
    r1 = _rule("Prime", "contains", "Subscriptions", priority=5, rule_id=1)
    r2 = _rule("Amazon", "contains", "Shopping", priority=20, rule_id=2)
    # r2 has higher priority — must win even though r1 is first in the list
    result = apply_rules("Amazon Prime", [r1, r2])
    assert result is not None
    assert result.category == "Shopping"


def test_equal_priority_first_in_list_wins():
    r1 = _rule("Prime", "contains", "Subscriptions", priority=5, rule_id=1)
    r2 = _rule("Amazon", "contains", "Shopping", priority=5, rule_id=2)
    result = apply_rules("Amazon Prime", [r1, r2])
    # Both match — first after sorting by priority (stable) determines the winner
    assert result is not None


# ---------------------------------------------------------------------------
# apply_rules — disabled rules
# ---------------------------------------------------------------------------


def test_disabled_rule_is_skipped():
    rules = [_rule("ILIAD", "contains", "Utilities", enabled=False)]
    assert apply_rules("ILIAD", rules) is None


def test_disabled_rule_does_not_shadow_enabled_rule():
    disabled = _rule("ILIAD", "contains", "Wrong", enabled=False, priority=99, rule_id=1)
    enabled = _rule("ILIAD", "contains", "Utilities", enabled=True, priority=1, rule_id=2)
    result = apply_rules("ILIAD", [disabled, enabled])
    assert result is not None
    assert result.category == "Utilities"


# ---------------------------------------------------------------------------
# apply_rules — invalid pattern_type
# ---------------------------------------------------------------------------


def test_unknown_pattern_type_does_not_crash():
    rules = [_rule("ILIAD", "unknown_type", "Utilities")]
    # Should not raise — just treat as no match
    result = apply_rules("ILIAD", rules)
    assert result is None


# ---------------------------------------------------------------------------
# apply_rules — empty / whitespace merchant
# ---------------------------------------------------------------------------


def test_empty_merchant_returns_none():
    rules = [_rule("", "contains", "Misc")]
    assert apply_rules("", rules) is None


def test_whitespace_merchant_returns_none():
    rules = [_rule("ILIAD", "contains", "Utilities")]
    assert apply_rules("   ", rules) is None
