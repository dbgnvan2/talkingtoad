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


def test_collapse_groups_by_page_and_code_preserving_urls():
    """§2 (P2): the collapse must group by (page_url, code) — never merge across
    pages or codes — and preserve every offending target URL (no silent drop).
    This is the shared transform both the full crawl and the rescan path run, so
    if attribution ever diverges between them, the grouped rows differ here."""
    issues = [
        _broken("https://x.org/a", "https://ext/1", "BROKEN_LINK_404"),
        _broken("https://x.org/a", "https://ext/2", "BROKEN_LINK_404"),
        _broken("https://x.org/a", "https://ext/3", "BROKEN_LINK_5XX"),
        _broken("https://x.org/b", "https://ext/1", "BROKEN_LINK_404"),
    ]
    out = collapse_per_target_occurrences(issues)
    by_key = {(i.page_url, i.code): i for i in out}
    # Three distinct (page, code) groups — a/404, a/5xx, b/404.
    assert set(by_key) == {
        ("https://x.org/a", "BROKEN_LINK_404"),
        ("https://x.org/a", "BROKEN_LINK_5XX"),
        ("https://x.org/b", "BROKEN_LINK_404"),
    }
    a404 = by_key[("https://x.org/a", "BROKEN_LINK_404")]
    assert set(a404.extra["occurrence_urls"]) == {"https://ext/1", "https://ext/2"}, \
        "offending URLs must be preserved (P2 — no silent drop)"
    assert a404.extra["occurrences"] == 2


# ── §2 dual-path parity: full crawl vs rescan score a multi-broken-link page
# identically (guards against the two emission sites diverging — TODO item). ──
import httpx
import respx
from api.crawler.engine import run_crawl, CrawlSettings
from api.routers.crawl import _fetch_and_check_page
from api.models.job import CrawlJob

_DUAL_HOME = (
    '<!DOCTYPE html><html><head>'
    '<title>Home Page With A Good Long Title Here Now</title>'
    '<meta name="description" content="A good description long enough to pass validation checks easily.">'
    '</head><body><h1>Home</h1>'
    '<a href="https://ext.org/1">1</a><a href="https://ext.org/2">2</a><a href="https://ext.org/3">3</a>'
    '</body></html>'
)


def _dual_mock(m):
    m.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
    m.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    m.get("https://example.com/").mock(
        return_value=httpx.Response(200, text=_DUAL_HOME, headers={"content-type": "text/html"}))
    for i in (1, 2, 3):
        m.head(f"https://ext.org/{i}").mock(return_value=httpx.Response(404))
        m.get(f"https://ext.org/{i}").mock(return_value=httpx.Response(404))


def _home_404_rows(issues, code_attr="code"):
    # Full crawl returns registry Issue dataclasses (.code); the rescan path
    # returns Pydantic models.issue.Issue (.issue_code). Both carry page_url /
    # impact / extra.
    return [i for i in issues
            if getattr(i, code_attr) == "BROKEN_LINK_404" and i.page_url == "https://example.com/"]


@pytest.mark.asyncio
async def test_full_crawl_and_rescan_score_broken_links_identically(store):
    """3 broken external links on one page must collapse to ONE BROKEN_LINK_404
    row with the same occurrence-multiplied impact on BOTH paths."""
    base = _ISSUE_SCORING["BROKEN_LINK_404"][0]
    expected_impact = round(base * occurrence_multiplier(3))  # n=3 -> ×1.5

    with respx.mock:
        _dual_mock(respx.mock)
        crawl_result = await run_crawl("job-dual", "https://example.com/",
                                       CrawlSettings(crawl_delay_ms=0, max_pages=5))
    full = _home_404_rows(crawl_result.issues)

    job = CrawlJob(job_id="rescan-dual", target_url="https://example.com/")
    await store.create_job(job)
    with respx.mock:
        _dual_mock(respx.mock)
        rescan = await _fetch_and_check_page(
            url="https://example.com/", job_id="rescan-dual",
            base_url="https://example.com/", store=store)
    re_rows = _home_404_rows(rescan.issues, code_attr="issue_code")

    assert len(full) == 1, f"full crawl: expected 1 collapsed row, got {len(full)}"
    assert len(re_rows) == 1, f"rescan: expected 1 collapsed row, got {len(re_rows)}"
    assert full[0].extra["occurrences"] == 3 == re_rows[0].extra["occurrences"]
    assert full[0].impact == expected_impact == re_rows[0].impact
