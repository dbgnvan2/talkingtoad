"""§2 — per-target occurrence counting (broken links / redirects).

Spec: talkingtoad-scoring-change-spec.md#2 and #10.
Broken-link / redirect codes collapse to ONE row per (page, code) with an
occurrence multiplier min(1+0.25(n-1), 2.0) baked into impact, instead of the
old unbounded impact × number-of-links.
"""

import pytest

from api.crawler.checkers.registry import make_issue, _ISSUE_SCORING
from api.crawler.checkers.links import (
    occurrence_multiplier,
    collapse_per_target_occurrences,
    PER_TARGET_CODES,
)
from api.services.job_store_base import compute_page_health


def _broken(page, target, code="BROKEN_LINK_404"):
    iss = make_issue(code, page)
    iss.extra = {"target_url": target}
    return iss


@pytest.mark.parametrize("n,expected_mult", [(1, 1.0), (2, 1.25), (5, 2.0), (20, 2.0)])
def test_occurrence_multiplier_curve(n, expected_mult):
    assert occurrence_multiplier(n) == expected_mult


@pytest.mark.parametrize("n", [1, 2, 5, 20])
def test_collapse_bakes_multiplier_into_impact(n):
    """Spec §10: 1/2/5/20 broken 404s on one page → impact × {1.0,1.25,2.0,2.0}."""
    page = "https://x.org/p"
    base = _ISSUE_SCORING["BROKEN_LINK_404"][0]
    issues = [_broken(page, f"https://ext/{i}") for i in range(n)]
    out = collapse_per_target_occurrences(issues)
    rows = [i for i in out if i.code == "BROKEN_LINK_404"]
    assert len(rows) == 1, "collapsed to one row per (page, code)"
    row = rows[0]
    assert row.extra["occurrences"] == n
    assert len(row.extra["occurrence_urls"]) == n
    assert row.impact == round(base * occurrence_multiplier(n))


def test_distinct_codes_and_pages_not_merged():
    issues = [
        _broken("https://x.org/a", "https://ext/1", "BROKEN_LINK_404"),
        _broken("https://x.org/a", "https://ext/2", "BROKEN_LINK_404"),
        _broken("https://x.org/a", "https://ext/3", "BROKEN_LINK_410"),  # diff code
        _broken("https://x.org/b", "https://ext/4", "BROKEN_LINK_404"),  # diff page
    ]
    out = collapse_per_target_occurrences(issues)
    keys = sorted((i.page_url, i.code, i.extra["occurrences"]) for i in out)
    assert keys == [
        ("https://x.org/a", "BROKEN_LINK_404", 2),
        ("https://x.org/a", "BROKEN_LINK_410", 1),
        ("https://x.org/b", "BROKEN_LINK_404", 1),
    ]


def test_non_per_target_issues_pass_through_untouched():
    keep = make_issue("TITLE_MISSING", "https://x.org/a")
    out = collapse_per_target_occurrences([keep])
    assert len(out) == 1 and out[0].code == "TITLE_MISSING"
    assert out[0].impact == _ISSUE_SCORING["TITLE_MISSING"][0]  # unchanged


def test_scoring_uses_collapsed_impact_not_unbounded_sum():
    """20 broken 404s: collapsed deduction is impact×2.0 (one row), NOT 20×impact
    capped — the whole point of §2 vs relying only on the category cap."""
    page = "https://x.org/p"
    base = _ISSUE_SCORING["BROKEN_LINK_404"][0]
    collapsed = collapse_per_target_occurrences(
        [_broken(page, f"https://ext/{i}") for i in range(20)]
    )
    rows = [(i.code, i.impact, i.category) for i in collapsed]
    score = compute_page_health(rows)
    assert score == 100 - round(base * 2.0)


def test_f2_malformed_jsonld_still_flags_structured_data(monkeypatch):
    """§7/F2: deleting SCHEMA_MISSING must not drop the 'JSON-LD present but no
    usable @type' case. JSON_LD_MISSING now keys on schema_types, so a page with
    a malformed/typeless ld+json (has_json_ld True, schema_types []) still flags."""
    from api.crawler.issue_checker import check_page
    from tests.test_issue_checker import _page
    p = _page(schema_types=[], is_indexable=True)
    p.has_json_ld = True  # a script exists, but no usable type was extracted
    codes = {i.code for i in check_page(p)}
    assert "JSON_LD_MISSING" in codes


def test_per_target_codes_membership():
    for c in ("BROKEN_LINK_404", "BROKEN_LINK_410", "BROKEN_LINK_503",
              "BROKEN_LINK_5XX", "EXTERNAL_LINK_TIMEOUT", "REDIRECT_301", "REDIRECT_302"):
        assert c in PER_TARGET_CODES
