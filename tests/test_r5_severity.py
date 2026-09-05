"""R5.5 — severity derived at runtime + registry housekeeping.

``make_issue`` must derive severity from impact via ``severity_from_impact``
rather than copying the stored ``_IssueSpec.severity`` literal, so a drifted
stored literal can never leak a wrong severity into a live issue.

This docstring used to claim "a parity test already keeps the stored literals
equal to the derived value". It did not — that test pins the FRONTEND help
entry, and the catalogue's own literal went unchecked for 169 of 170 codes until
the 2026-09-05 sweep added the one at the bottom of this file.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.5
"""

from __future__ import annotations

from dataclasses import replace

import api.crawler.checkers.registry as registry
from api.crawler.checkers.registry import (
    _CATALOGUE,
    _ISSUE_SCORING,
    make_issue,
    severity_from_impact,
)


def test_make_issue_severity_is_derived():
    """Override a code's stored severity to a deliberately WRONG value and
    assert make_issue still returns the impact-derived severity."""
    code = "TITLE_MISSING"
    impact = _ISSUE_SCORING[code][0]
    correct = severity_from_impact(impact)
    wrong = "critical" if correct != "critical" else "info"
    assert wrong != correct  # sanity: we chose a genuinely different value

    original = _CATALOGUE[code]
    _CATALOGUE[code] = replace(original, severity=wrong)
    try:
        issue = make_issue(code, page_url="https://example.com/")
        assert issue.severity == correct, (
            "make_issue copied the stored (wrong) severity literal instead of "
            "deriving it from impact"
        )
        assert issue.severity != wrong
    finally:
        _CATALOGUE[code] = original


def test_make_issue_severity_matches_all_codes():
    """Across the whole catalogue, the runtime severity equals the derived one."""
    for code in _CATALOGUE:
        impact = _ISSUE_SCORING[code][0]
        issue = make_issue(code, page_url="https://x/")
        assert issue.severity == severity_from_impact(impact), code


def test_registry_docstring_count_matches():
    """R5.5.3 — the module docstring's documented code count must equal the live
    catalogue size (the stale "151" is fixed to match len(_CATALOGUE))."""
    doc = registry.__doc__ or ""
    live = len(_CATALOGUE)
    assert str(live) in doc, f"module docstring never states the live count {live}"
    assert "151" not in doc, "stale '151' code count still present in docstring"


def test_priority_effort_comment_not_stale():
    """R5.5.3 — the stale 'effort × 2' comment must read 'effort × 6' (matching
    the live priority formula in make_issue)."""
    import inspect

    src = inspect.getsource(registry)
    assert "effort × 2" not in src, "stale 'effort × 2' comment still present"
    assert "impact × 10" in src and "effort × 6" in src


# ---------------------------------------------------------------------------
# P5.4b — the stored literal itself (2026-09-05 sweep §2)
# ---------------------------------------------------------------------------
# This module's docstring says "a parity test already keeps the stored literals
# equal to the derived value". It did not. `test_issue_help_completeness` pins
# the FRONTEND help entry to the derived severity, and `test_faq_detection` pins
# one code — so of 170 catalogue literals, 169 agreed with the derivation by
# convention alone. Nothing failed if one drifted; `make_issue` derives severity
# at runtime, so a drifted literal is silent rather than wrong, which is exactly
# how it would stay wrong.


def test_every_catalogue_severity_matches_the_derived_value():
    from api.crawler.checkers.registry import derive_impact

    drifted = {
        code: (spec.severity, severity_from_impact(derive_impact(code)))
        for code, spec in _CATALOGUE.items()
        if spec.severity != severity_from_impact(derive_impact(code))
    }
    assert not drifted, (
        f"{len(drifted)} catalogue severities disagree with the impact they "
        f"derive from (code: stored -> derived): {drifted}"
    )


def test_the_parity_check_would_notice_a_drifted_literal():
    """The adversarial half. The assertion above passes today because all 170
    agree; without this, a refactor that made `derive_impact` return the stored
    literal would leave it green and meaningless (P32 — an oracle taken from the
    code under test)."""
    from api.crawler.checkers.registry import derive_impact

    code = "TITLE_MISSING"
    derived = severity_from_impact(derive_impact(code))
    wrong = "info" if derived != "info" else "critical"
    assert wrong != derived
    drifted = replace(_CATALOGUE[code], severity=wrong)
    assert drifted.severity != severity_from_impact(derive_impact(code)), (
        "a deliberately wrong stored severity still compares equal — the parity "
        "test above is comparing the derivation with itself"
    )
