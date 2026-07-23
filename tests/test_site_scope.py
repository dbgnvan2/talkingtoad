"""R5.1 — site-scope (external spec §6.3).

TLS/host-config findings are properties of the whole site, not of one page.
A site-scoped code deducts ONCE site-wide (at the worst-affected representative
page), never from other pages — including its page-fatal flooring.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.1
"""

from __future__ import annotations

from api.crawler.checkers.registry import (
    _CATALOGUE,
    _ISSUE_SCORING,
    _SITE_SCOPED_CODES,
    issue_scope,
)
from api.services.job_store_base import compute_impact_health

_NO_SEV = {"critical": 0, "warning": 0, "info": 0}

_SITE_CODES = ["HTTP_PAGE", "HTTPS_REDIRECT_MISSING", "MIXED_CONTENT",
               "MISSING_HSTS", "WWW_CANONICALIZATION",
               # "Search Everywhere" GEO (P1) — site-level findings.
               "ENTITY_NAME_INCONSISTENT", "AUTHOR_IDENTITY_INCONSISTENT",
               "NEAR_DUPLICATE_BODY"]


def _imp(code: str) -> int:
    return _ISSUE_SCORING[code][0]


def _row(code: str) -> tuple[str, int, str]:
    return (code, _imp(code), _CATALOGUE[code].category)


def test_site_codes_declared_site_scope():
    """R5.1.1 — the five TLS/site-config codes are declared scope='site'."""
    for code in _SITE_CODES:
        assert _CATALOGUE[code].scope == "site", code
        assert issue_scope(code) == "site", code
    # And nothing else silently became site-scoped.
    site_scoped = {c for c, s in _CATALOGUE.items() if s.scope == "site"}
    assert site_scoped == set(_SITE_CODES)
    assert site_scoped == set(_SITE_SCOPED_CODES)


def test_page_codes_default_page_scope():
    for code in ("TITLE_MISSING", "H1_MISSING", "NOINDEX_META"):
        assert issue_scope(code) == "page"


def test_site_scope_single_deduction():
    """R5.1.2 / spec §10(e) — a 50-page all-HTTP site deducts HTTP_PAGE exactly
    ONCE site-wide. The representative page is floored; the other 49 are not."""
    pages = [f"https://x/p{i}" for i in range(50)]
    per_page = {p: [_row("HTTP_PAGE")] for p in pages}

    site, n = compute_impact_health(pages, per_page, dict(_NO_SEV))
    assert n == 50

    # Exactly ONE page carries the HTTP_PAGE deduction; the other 49 score 100.
    # HTTP_PAGE is page-fatal, impact 6 → representative page scores 100-6=94.
    rep_score = 100 - _imp("HTTP_PAGE")
    expected = round((rep_score + 100 * 49) / 50)
    assert site == expected

    # Sanity: if HTTP_PAGE were charged per page (the old bug), every page would
    # lose points and the site score would be far lower.
    per_page_score_if_all_charged = round(100 - _imp("HTTP_PAGE"))
    assert site > per_page_score_if_all_charged


def test_site_scope_representative_is_worst_affected():
    """The single deduction lands on the page with the highest impact for that
    code (worst-affected), not an arbitrary page."""
    pages = ["https://x/a", "https://x/b", "https://x/c"]
    # Same code, different impacts per page; 'b' is worst.
    per_page = {
        "https://x/a": [("HTTP_PAGE", 3, "security")],
        "https://x/b": [("HTTP_PAGE", 9, "security")],
        "https://x/c": [("HTTP_PAGE", 3, "security")],
    }
    site, _ = compute_impact_health(pages, per_page, dict(_NO_SEV))
    # Only 'b' is charged, at impact 9 (fatal → floors by 9); a and c score 100.
    expected = round(((100 - 9) + 100 + 100) / 3)
    assert site == expected


def test_page_issues_include_scope():
    """R5.1.3 / API-contract — the per-page issues JSON payload exposes `scope`
    so the frontend can label site-wide findings. A site-scoped code serialises
    as "site"; a normal code as "page"."""
    from api.crawler.issue_checker import make_issue
    from api.routers.crawl import _engine_issue_to_model, _issue_dict

    site_model = _engine_issue_to_model(
        make_issue("HTTP_PAGE", page_url="https://example.com/"), job_id="j"
    )
    page_model = _engine_issue_to_model(
        make_issue("H1_MISSING", page_url="https://example.com/"), job_id="j"
    )
    site_payload = _issue_dict(site_model)
    page_payload = _issue_dict(page_model)

    assert "scope" in site_payload, "_issue_dict omitted scope from the payload"
    assert site_payload["scope"] == "site"
    assert page_payload["scope"] == "page"


def test_site_scope_other_pages_not_floored():
    """A site-scoped fatal code floors ONLY its representative page. Other pages
    with the same code but real page-scoped issues keep their own scores."""
    pages = ["https://x/rep", "https://x/other"]
    per_page = {
        "https://x/rep": [_row("HTTP_PAGE")],
        # 'other' also detects HTTP_PAGE (still visible in list) plus a real
        # page-scoped issue. HTTP_PAGE must NOT floor 'other'.
        "https://x/other": [_row("HTTP_PAGE"), _row("H1_MISSING")],
    }
    site, _ = compute_impact_health(pages, per_page, dict(_NO_SEV))
    # rep charged HTTP_PAGE (fatal, 6). 'other' charged only H1_MISSING.
    rep = 100 - _imp("HTTP_PAGE")
    other = 100 - _imp("H1_MISSING")
    assert site == round((rep + other) / 2)
