"""CLN3 — `_ANALYSIS_CATEGORY_MAP` completeness.

Guards that no issue category is unreachable via analysis toggles: every real
category must be produced either by some named group or by the always-emitted
ungrouped set. Otherwise a partial `enabled_analyses` selection would silently
drop it (P2/P3) with no toggle to turn it back on.

Spec: docs/pending/2026-08-08_debt-cleanup-batch.md#CLN3
"""

from __future__ import annotations

from api.crawler.checkers.registry import _CATALOGUE
from api.crawler.engine import (
    _ANALYSIS_CATEGORY_MAP,
    _UNGROUPED_CATEGORIES,
    _enabled_categories,
)


def _backend_categories() -> set[str]:
    return {spec.category for spec in _CATALOGUE.values()}


def test_cln3_1_map_covers_every_category():
    """The reachable set (every group's categories ∪ the always-emitted ungrouped
    set) must EQUAL the registry category set — nothing unreachable, nothing dead."""
    reachable = set(_UNGROUPED_CATEGORIES)
    for cats in _ANALYSIS_CATEGORY_MAP.values():
        reachable |= cats
    backend = _backend_categories()

    unreachable = backend - reachable
    assert not unreachable, (
        f"categories reachable via NO analysis toggle (silently dropped on a "
        f"partial selection): {sorted(unreachable)}"
    )
    dead = reachable - backend
    assert not dead, (
        f"analysis map/ungrouped references categories no code emits: {sorted(dead)}"
    )


def test_cln3_2_none_selection_runs_all_categories():
    """Regression guard for the default full crawl: no selection ⇒ None (all on)."""
    assert _enabled_categories(None) is None


def test_cln3_2_empty_selection_runs_only_security():
    """Contract (test_crawl_engine::test_no_analyses_enabled_returns_no_issues):
    an empty selection suppresses everything except the always-emitted security."""
    assert _enabled_categories([]) == frozenset({"security"})


def test_cln3_2_partial_selection_adds_security_to_the_group():
    allowed = _enabled_categories(["link_integrity"])
    assert allowed is not None
    assert {"broken_link", "redirect"} <= allowed          # the selected group
    assert "security" in allowed                           # always-emitted
    assert "metadata" not in allowed                       # not selected → excluded


def test_cln3_2_formerly_orphan_categories_are_reachable_via_a_group():
    """The CLN3 fix: image/rendering/semantic_html can now each be enabled by
    selecting a real group (previously reachable only via the all-on path)."""
    assert {"rendering", "semantic_html"} <= _enabled_categories(["ai_readiness"])
    assert "image" in _enabled_categories(["image"])
