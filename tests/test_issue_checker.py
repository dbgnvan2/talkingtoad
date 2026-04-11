"""
Tests for api/crawler/issue_checker.py

Covers all Phase 1 issue code generation, canonical scoping rules,
favicon per-homepage rule, and cross-page duplicate detection.
"""

import pytest
from api.crawler.parser import ParsedPage, ParsedLink
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import (
    Issue,
    check_asset,
    check_page,
    check_cross_page,
    check_url_structure,
    issue_for_status,
    issues_for_redirect,
    make_issue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _page(
    url: str = "https://example.com/page",
    *,
    title: str | None = "A Good Page Title Here",
    meta_description: str | None = "A good meta description that is long enough to pass the minimum check easily.",
    og_title: str | None = "OG Title",
    og_description: str | None = "OG Description",
    canonical_url: str | None = None,
    h1_tags: list[str] | None = None,
    headings_outline: list[dict] | None = None,
    is_indexable: bool = True,
    robots_directive: str | None = None,
    links: list[ParsedLink] | None = None,
    has_favicon: bool | None = None,
    has_viewport_meta: bool = True,
    schema_types: list[str] | None = None,
    external_script_count: int = 0,
    external_stylesheet_count: int = 0,
    status_code: int = 200,
    response_size_bytes: int = 1000,
    # Extended fields
    word_count: int | None = None,
    crawl_depth: int | None = None,
    pagination_next: str | None = None,
    pagination_prev: str | None = None,
    amphtml_url: str | None = None,
    meta_refresh_url: str | None = None,
    mixed_content_count: int = 0,
    unsafe_cross_origin_count: int = 0,
    has_hsts: bool | None = None,
    # v1.5 new fields
    img_missing_alt_count: int = 0,
    image_urls: list | None = None,
    empty_anchor_count: int = 0,
    internal_nofollow_count: int = 0,
    # v1.6 new fields
    lang_attr: str | None = "en",
) -> ParsedPage:
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=status_code,
        response_size_bytes=response_size_bytes,
        title=title,
        meta_description=meta_description,
        og_title=og_title,
        og_description=og_description,
        canonical_url=canonical_url,
        h1_tags=h1_tags if h1_tags is not None else ["Main Heading"],
        headings_outline=headings_outline if headings_outline is not None else [{"level": 1, "text": "Main Heading"}],
        is_indexable=is_indexable,
        robots_directive=robots_directive,
        links=links or [],
        has_favicon=has_favicon,
        has_viewport_meta=has_viewport_meta,
        schema_types=schema_types or [],
        external_script_count=external_script_count,
        external_stylesheet_count=external_stylesheet_count,
        word_count=word_count,
        crawl_depth=crawl_depth,
        pagination_next=pagination_next,
        pagination_prev=pagination_prev,
        amphtml_url=amphtml_url,
        meta_refresh_url=meta_refresh_url,
        mixed_content_count=mixed_content_count,
        unsafe_cross_origin_count=unsafe_cross_origin_count,
        has_hsts=has_hsts,
        img_missing_alt_count=img_missing_alt_count,
        image_urls=image_urls if image_urls is not None else [],
        empty_anchor_count=empty_anchor_count,
        internal_nofollow_count=internal_nofollow_count,
        lang_attr=lang_attr,
    )


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


# ---------------------------------------------------------------------------
# Title checks
# ---------------------------------------------------------------------------

class TestTitleChecks:
    def test_title_missing_emits_critical(self):
        page = _page(title=None)
        codes = _codes(check_page(page))
        assert "TITLE_MISSING" in codes

    def test_title_too_short_emits_warning(self):
        page = _page(title="Short")  # < 30 chars
        codes = _codes(check_page(page))
        assert "TITLE_TOO_SHORT" in codes

    def test_title_too_long_emits_warning(self):
        page = _page(title="A" * 61)  # > 60 chars
        codes = _codes(check_page(page))
        assert "TITLE_TOO_LONG" in codes

    def test_title_good_length_no_issue(self):
        page = _page(title="A" * 40)  # 30–60 chars
        codes = _codes(check_page(page))
        assert "TITLE_MISSING" not in codes
        assert "TITLE_TOO_SHORT" not in codes
        assert "TITLE_TOO_LONG" not in codes

    def test_title_exactly_30_chars_ok(self):
        page = _page(title="A" * 30)
        codes = _codes(check_page(page))
        assert "TITLE_TOO_SHORT" not in codes

    def test_title_exactly_60_chars_ok(self):
        page = _page(title="A" * 60)
        codes = _codes(check_page(page))
        assert "TITLE_TOO_LONG" not in codes


# ---------------------------------------------------------------------------
# Meta description checks
# ---------------------------------------------------------------------------

class TestMetaDescChecks:
    def test_meta_desc_missing_emits_critical(self):
        page = _page(meta_description=None)
        codes = _codes(check_page(page))
        assert "META_DESC_MISSING" in codes

    def test_meta_desc_too_short_emits_warning(self):
        page = _page(meta_description="Too short")  # < 70 chars
        codes = _codes(check_page(page))
        assert "META_DESC_TOO_SHORT" in codes

    def test_meta_desc_too_long_emits_warning(self):
        page = _page(meta_description="A" * 161)  # > 160 chars
        codes = _codes(check_page(page))
        assert "META_DESC_TOO_LONG" in codes

    def test_meta_desc_good_length_no_issue(self):
        page = _page(meta_description="A" * 100)
        codes = _codes(check_page(page))
        assert "META_DESC_MISSING" not in codes
        assert "META_DESC_TOO_SHORT" not in codes
        assert "META_DESC_TOO_LONG" not in codes


# ---------------------------------------------------------------------------
# OG tag checks
# ---------------------------------------------------------------------------

class TestOgTagChecks:
    def test_og_title_missing_emits_info(self):
        page = _page(og_title=None)
        issues = check_page(page)
        og_issues = [i for i in issues if i.code == "OG_TITLE_MISSING"]
        assert len(og_issues) == 1
        assert og_issues[0].severity == "info"

    def test_og_desc_missing_emits_info(self):
        page = _page(og_description=None)
        issues = check_page(page)
        og_issues = [i for i in issues if i.code == "OG_DESC_MISSING"]
        assert len(og_issues) == 1
        assert og_issues[0].severity == "info"

    def test_og_present_no_issue(self):
        page = _page(og_title="Title", og_description="Desc")
        codes = _codes(check_page(page))
        assert "OG_TITLE_MISSING" not in codes
        assert "OG_DESC_MISSING" not in codes


# ---------------------------------------------------------------------------
# Canonical tag checks — three scoping conditions
# ---------------------------------------------------------------------------

class TestCanonicalChecks:
    def test_condition1_query_string_no_canonical_emits_warning(self):
        """Condition 1: page has query string and no canonical."""
        page = _page(url="https://example.com/news?page=2", canonical_url=None)
        codes = _codes(check_page(page))
        assert "CANONICAL_MISSING" in codes

    def test_condition1_no_query_string_no_canonical_no_issue(self):
        """Condition 1 not triggered: no query string, no canonical — no issue."""
        page = _page(url="https://example.com/about", canonical_url=None)
        codes = _codes(check_page(page))
        assert "CANONICAL_MISSING" not in codes

    def test_condition2_near_duplicate_emits_canonical_missing(self):
        """Condition 2: near-duplicate (same title + meta_desc), no canonical."""
        page_a = _page(url="https://example.com/a", title="Shared Title", meta_description="A" * 80, canonical_url=None)
        page_b = _page(url="https://example.com/b", title="Shared Title", meta_description="A" * 80, canonical_url=None)
        cross_issues = check_cross_page([page_a, page_b])
        codes = _codes(cross_issues)
        assert "CANONICAL_MISSING" in codes

    def test_condition3_external_canonical_emits_canonical_external(self):
        """Condition 3: canonical points to a different domain."""
        page = _page(
            url="https://example.com/page",
            canonical_url="https://other-domain.com/page",
        )
        codes = _codes(check_page(page))
        assert "CANONICAL_EXTERNAL" in codes

    def test_self_referencing_canonical_no_issue(self):
        page = _page(
            url="https://example.com/page",
            canonical_url="https://example.com/page",
        )
        codes = _codes(check_page(page))
        assert "CANONICAL_MISSING" not in codes
        assert "CANONICAL_EXTERNAL" not in codes

    def test_near_duplicate_with_canonical_no_canonical_missing(self):
        """Near-duplicate pages that have a canonical should not trigger CANONICAL_MISSING."""
        page_a = _page(url="https://example.com/a", title="T", meta_description="A" * 80,
                       canonical_url="https://example.com/a")
        page_b = _page(url="https://example.com/b", title="T", meta_description="A" * 80,
                       canonical_url="https://example.com/a")
        cross_issues = check_cross_page([page_a, page_b])
        canonical_missing = [i for i in cross_issues if i.code == "CANONICAL_MISSING"]
        assert len(canonical_missing) == 0


# ---------------------------------------------------------------------------
# Favicon check
# ---------------------------------------------------------------------------

class TestFaviconCheck:
    def test_favicon_missing_emitted_for_homepage(self):
        page = _page(url="https://example.com/", has_favicon=False)
        codes = _codes(check_page(page))
        assert "FAVICON_MISSING" in codes

    def test_favicon_present_no_issue_for_homepage(self):
        page = _page(url="https://example.com/", has_favicon=True)
        codes = _codes(check_page(page))
        assert "FAVICON_MISSING" not in codes

    def test_favicon_not_checked_for_non_homepage(self):
        """has_favicon is None for non-homepage pages — should never emit FAVICON_MISSING."""
        page = _page(url="https://example.com/about", has_favicon=None)
        codes = _codes(check_page(page))
        assert "FAVICON_MISSING" not in codes

    def test_favicon_emitted_only_once_per_job(self):
        """When favicon_emitted=True, do not emit again."""
        page = _page(url="https://example.com/", has_favicon=False)
        codes = _codes(check_page(page, favicon_emitted=True))
        assert "FAVICON_MISSING" not in codes


# ---------------------------------------------------------------------------
# Heading checks
# ---------------------------------------------------------------------------

class TestHeadingChecks:
    def test_h1_missing_emits_critical(self):
        page = _page(h1_tags=[], headings_outline=[])
        codes = _codes(check_page(page))
        assert "H1_MISSING" in codes

    def test_h1_multiple_emits_warning(self):
        page = _page(
            h1_tags=["First", "Second"],
            headings_outline=[{"level": 1, "text": "First"}, {"level": 1, "text": "Second"}],
        )
        codes = _codes(check_page(page))
        assert "H1_MULTIPLE" in codes

    def test_h1_single_no_issue(self):
        page = _page(h1_tags=["One"], headings_outline=[{"level": 1, "text": "One"}])
        codes = _codes(check_page(page))
        assert "H1_MISSING" not in codes
        assert "H1_MULTIPLE" not in codes

    def test_heading_skip_h1_to_h3_emits_warning(self):
        page = _page(
            h1_tags=["H1"],
            headings_outline=[{"level": 1, "text": "H1"}, {"level": 3, "text": "H3"}],
        )
        codes = _codes(check_page(page))
        assert "HEADING_SKIP" in codes

    def test_heading_skip_h2_to_h4_emits_warning(self):
        page = _page(
            h1_tags=["H1"],
            headings_outline=[
                {"level": 1, "text": "H1"},
                {"level": 2, "text": "H2"},
                {"level": 4, "text": "H4"},
            ],
        )
        codes = _codes(check_page(page))
        assert "HEADING_SKIP" in codes

    def test_heading_no_skip_sequential_ok(self):
        page = _page(
            h1_tags=["H1"],
            headings_outline=[
                {"level": 1, "text": "H1"},
                {"level": 2, "text": "H2"},
                {"level": 3, "text": "H3"},
            ],
        )
        codes = _codes(check_page(page))
        assert "HEADING_SKIP" not in codes

    def test_heading_skip_reported_once_per_page(self):
        """Multiple skips on one page should only emit one HEADING_SKIP."""
        page = _page(
            h1_tags=["H1"],
            headings_outline=[
                {"level": 1, "text": "H1"},
                {"level": 3, "text": "H3"},
                {"level": 5, "text": "H5"},
            ],
        )
        codes = _codes(check_page(page))
        assert codes.count("HEADING_SKIP") == 1


# ---------------------------------------------------------------------------
# Crawlability checks
# ---------------------------------------------------------------------------

class TestCrawlabilityChecks:
    def test_noindex_meta_emits_warning(self):
        page = _page(is_indexable=False, robots_directive="noindex")
        codes = _codes(check_page(page))
        assert "NOINDEX_META" in codes

    def test_indexable_page_no_noindex_issue(self):
        page = _page(is_indexable=True)
        codes = _codes(check_page(page))
        assert "NOINDEX_META" not in codes
        assert "NOINDEX_HEADER" not in codes


class TestNoindexPageSeoSkip:
    """Noindex pages must not generate SEO issues — those checks are meaningless
    for pages intentionally excluded from search."""

    def test_noindex_page_skips_title_check(self):
        page = _page(is_indexable=False, title=None)
        codes = _codes(check_page(page))
        assert "TITLE_MISSING" not in codes

    def test_noindex_page_skips_meta_desc_check(self):
        page = _page(is_indexable=False, meta_description=None)
        codes = _codes(check_page(page))
        assert "META_DESC_MISSING" not in codes

    def test_noindex_page_skips_og_checks(self):
        page = _page(is_indexable=False, og_title=None, og_description=None)
        codes = _codes(check_page(page))
        assert "OG_TITLE_MISSING" not in codes
        assert "OG_DESC_MISSING" not in codes

    def test_noindex_page_skips_h1_check(self):
        page = _page(is_indexable=False, h1_tags=[], headings_outline=[])
        codes = _codes(check_page(page))
        assert "H1_MISSING" not in codes

    def test_noindex_page_still_emits_noindex_issue(self):
        # The noindex itself should still be flagged
        page = _page(is_indexable=False, robots_directive="noindex")
        codes = _codes(check_page(page))
        assert "NOINDEX_META" in codes

    def test_noindex_page_still_runs_security_checks(self):
        # Security is always checked regardless of noindex
        page = _page(is_indexable=False, url="http://example.com/private")
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" in codes


# ---------------------------------------------------------------------------
# Not-in-sitemap check
# ---------------------------------------------------------------------------

class TestNotInSitemapCheck:
    def test_not_in_sitemap_emits_info(self):
        page = _page(url="https://example.com/about")
        sitemap_urls = {"https://example.com/"}
        codes = _codes(check_page(page, sitemap_urls=sitemap_urls))
        assert "NOT_IN_SITEMAP" in codes

    def test_in_sitemap_no_issue(self):
        page = _page(url="https://example.com/about")
        sitemap_urls = {"https://example.com/about"}
        codes = _codes(check_page(page, sitemap_urls=sitemap_urls))
        assert "NOT_IN_SITEMAP" not in codes

    def test_no_sitemap_no_not_in_sitemap_issue(self):
        page = _page(url="https://example.com/about")
        codes = _codes(check_page(page, sitemap_urls=None))
        assert "NOT_IN_SITEMAP" not in codes

    def test_noindex_page_not_checked_against_sitemap(self):
        page = _page(url="https://example.com/about", is_indexable=False)
        sitemap_urls = {"https://example.com/"}
        codes = _codes(check_page(page, sitemap_urls=sitemap_urls))
        assert "NOT_IN_SITEMAP" not in codes


# ---------------------------------------------------------------------------
# Cross-page duplicate detection
# ---------------------------------------------------------------------------

class TestCrossPageDuplicates:
    def test_duplicate_titles_both_flagged(self):
        pages = [
            _page(url="https://example.com/a", title="Same Title For Both Pages Here"),
            _page(url="https://example.com/b", title="Same Title For Both Pages Here"),
        ]
        issues = check_cross_page(pages)
        affected = {i.page_url for i in issues if i.code == "TITLE_DUPLICATE"}
        assert "https://example.com/a" in affected
        assert "https://example.com/b" in affected

    def test_unique_titles_no_duplicate_issue(self):
        pages = [
            _page(url="https://example.com/a", title="Title A is Unique Here"),
            _page(url="https://example.com/b", title="Title B is Unique Here"),
        ]
        codes = _codes(check_cross_page(pages))
        assert "TITLE_DUPLICATE" not in codes

    def test_duplicate_meta_desc_both_flagged(self):
        desc = "A" * 80
        pages = [
            _page(url="https://example.com/a", meta_description=desc),
            _page(url="https://example.com/b", meta_description=desc),
        ]
        issues = check_cross_page(pages)
        affected = {i.page_url for i in issues if i.code == "META_DESC_DUPLICATE"}
        assert "https://example.com/a" in affected
        assert "https://example.com/b" in affected

    def test_duplicate_pair_emits_title_meta_duplicate_pair(self):
        pages = [
            _page(url="https://example.com/a", title="Same Title Here For Both", meta_description="B" * 80),
            _page(url="https://example.com/b", title="Same Title Here For Both", meta_description="B" * 80),
        ]
        issues = check_cross_page(pages)
        codes = _codes(issues)
        assert "TITLE_META_DUPLICATE_PAIR" in codes

    def test_three_pages_all_flagged_for_duplicate_title(self):
        pages = [
            _page(url=f"https://example.com/{i}", title="Shared Title Is The Same") for i in range(3)
        ]
        issues = check_cross_page(pages)
        dup_urls = {i.page_url for i in issues if i.code == "TITLE_DUPLICATE"}
        assert len(dup_urls) == 3

    def test_single_homepage_no_cross_page_issues(self):
        # The homepage is excluded from orphan detection — a single-page crawl should be clean.
        pages = [_page(url="https://example.com/")]
        issues = check_cross_page(pages, start_url="https://example.com/")
        assert issues == []


# ---------------------------------------------------------------------------
# Broken link and redirect issue helpers
# ---------------------------------------------------------------------------

class TestIssueForStatus:
    def test_404_returns_broken_link_404(self):
        issue = issue_for_status(404, "https://example.com/gone")
        assert issue is not None
        assert issue.code == "BROKEN_LINK_404"
        assert issue.severity == "critical"

    def test_410_returns_broken_link_410(self):
        issue = issue_for_status(410, "https://example.com/deleted")
        assert issue is not None
        assert issue.code == "BROKEN_LINK_410"

    def test_500_returns_broken_link_5xx(self):
        issue = issue_for_status(500, "https://example.com/error")
        assert issue is not None
        assert issue.code == "BROKEN_LINK_5XX"

    def test_503_returns_broken_link_503_warning(self):
        # 503 now gets its own lower-severity code (CDN bot challenges return 503)
        issue = issue_for_status(503, "https://example.com/error")
        assert issue is not None
        assert issue.code == "BROKEN_LINK_503"
        assert issue.severity == "warning"

    def test_200_returns_none(self):
        assert issue_for_status(200, "https://example.com/ok") is None

    def test_301_returns_none(self):
        assert issue_for_status(301, "https://example.com/redirect") is None

    def test_999_linkedin_anti_bot_returns_none(self):
        # LinkedIn returns 999 for bot requests — must not be flagged as 5xx
        assert issue_for_status(999, "https://www.linkedin.com/company/example") is None

    def test_403_returns_none(self):
        # 403 Forbidden is not a broken link (bot blocking, auth walls, etc.)
        assert issue_for_status(403, "https://example.com/private") is None

    def test_503_returns_broken_link_503_not_5xx(self):
        # 503 gets its own code (warning) because CDNs use it for bot challenges
        issue = issue_for_status(503, "https://example.com/service")
        assert issue is not None
        assert issue.code == "BROKEN_LINK_503"
        assert issue.severity == "warning"

    def test_502_returns_broken_link_5xx(self):
        # 502 is a real server error — stays critical
        issue = issue_for_status(502, "https://example.com/error")
        assert issue is not None
        assert issue.code == "BROKEN_LINK_5XX"
        assert issue.severity == "critical"


class TestIssuesForRedirect:
    def test_301_emits_redirect_301(self):
        issues = issues_for_redirect("https://example.com/old", 301, ["https://example.com/new"],
                                     final_url="https://example.com/new")
        codes = _codes(issues)
        assert "REDIRECT_301" in codes

    def test_302_emits_redirect_302(self):
        issues = issues_for_redirect("https://example.com/temp", 302, ["https://example.com/dest"],
                                     final_url="https://example.com/dest")
        codes = _codes(issues)
        assert "REDIRECT_302" in codes

    def test_chain_emits_redirect_chain(self):
        # A → B → C = 2 intermediate hops = chain
        chain = ["https://example.com/b", "https://example.com/c"]
        issues = issues_for_redirect("https://example.com/a", 301, chain,
                                     final_url="https://example.com/d")
        codes = _codes(issues)
        assert "REDIRECT_CHAIN" in codes

    def test_single_hop_no_chain_issue(self):
        issues = issues_for_redirect("https://example.com/a", 301, ["https://example.com/b"],
                                     final_url="https://example.com/b")
        codes = _codes(issues)
        assert "REDIRECT_CHAIN" not in codes

    def test_trailing_slash_only_emits_trailing_slash_issue(self):
        # /about → /about/ — CMS auto-handles this, not a real REDIRECT_301
        issues = issues_for_redirect(
            "https://example.com/about", 301, ["https://example.com/about/"],
            final_url="https://example.com/about/",
        )
        codes = _codes(issues)
        assert "REDIRECT_TRAILING_SLASH" in codes
        assert "REDIRECT_301" not in codes

    def test_trailing_slash_removal_emits_trailing_slash_issue(self):
        # /about/ → /about — also a trailing-slash normalisation
        issues = issues_for_redirect(
            "https://example.com/about/", 301, ["https://example.com/about"],
            final_url="https://example.com/about",
        )
        codes = _codes(issues)
        assert "REDIRECT_TRAILING_SLASH" in codes
        assert "REDIRECT_301" not in codes

    def test_case_normalise_only_emits_case_issue(self):
        issues = issues_for_redirect(
            "https://example.com/About-Us", 301, ["https://example.com/about-us"],
            final_url="https://example.com/about-us",
        )
        codes = _codes(issues)
        assert "REDIRECT_CASE_NORMALISE" in codes
        assert "REDIRECT_301" not in codes

    def test_real_301_not_misclassified(self):
        # Different path entirely — should still be REDIRECT_301
        issues = issues_for_redirect(
            "https://example.com/old-page", 301, ["https://example.com/new-page"],
            final_url="https://example.com/new-page",
        )
        codes = _codes(issues)
        assert "REDIRECT_301" in codes
        assert "REDIRECT_TRAILING_SLASH" not in codes
        assert "REDIRECT_CASE_NORMALISE" not in codes


# ---------------------------------------------------------------------------
# Extended Phase 1 codes (v1.3 §3.3 additions)
# ---------------------------------------------------------------------------

class TestMetaRefreshRedirect:
    def test_meta_refresh_url_emits_warning(self):
        page = _page(meta_refresh_url="https://example.com/new")
        codes = _codes(check_page(page))
        assert "META_REFRESH_REDIRECT" in codes

    def test_no_meta_refresh_no_issue(self):
        page = _page(meta_refresh_url=None)
        codes = _codes(check_page(page))
        assert "META_REFRESH_REDIRECT" not in codes

    def test_meta_refresh_redirect_is_redirect_category(self):
        page = _page(meta_refresh_url="https://example.com/new")
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "META_REFRESH_REDIRECT")
        assert issue.category == "redirect"


class TestThinContent:
    def test_under_300_words_emits_warning(self):
        page = _page(word_count=150, is_indexable=True)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" in codes

    def test_exactly_300_words_no_issue(self):
        page = _page(word_count=300, is_indexable=True)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_zero_words_no_issue(self):
        # Zero may be empty/non-HTML — not reported as thin
        page = _page(word_count=0, is_indexable=True)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_noindex_page_not_flagged(self):
        page = _page(word_count=50, is_indexable=False)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_thin_content_is_crawlability_category(self):
        page = _page(word_count=100, is_indexable=True)
        issues = check_page(page)
        issue = next((i for i in issues if i.code == "THIN_CONTENT"), None)
        assert issue is not None
        assert issue.category == "crawlability"


class TestPaginationLinksPresent:
    def test_next_link_emits_info(self):
        page = _page(pagination_next="https://example.com/page/2")
        codes = _codes(check_page(page))
        assert "PAGINATION_LINKS_PRESENT" in codes

    def test_prev_link_emits_info(self):
        page = _page(pagination_prev="https://example.com/page/1")
        codes = _codes(check_page(page))
        assert "PAGINATION_LINKS_PRESENT" in codes

    def test_no_pagination_no_issue(self):
        page = _page(pagination_next=None, pagination_prev=None)
        codes = _codes(check_page(page))
        assert "PAGINATION_LINKS_PRESENT" not in codes

    def test_pagination_links_present_is_crawlability_category(self):
        page = _page(pagination_next="https://example.com/page/2")
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "PAGINATION_LINKS_PRESENT")
        assert issue.category == "crawlability"


class TestAmpHtmlBroken:
    def test_broken_amp_url_emits_warning(self):
        from api.crawler.issue_checker import check_amphtml_links
        pages = [_page(url="https://example.com/", amphtml_url="https://example.com/amp/")]
        statuses = {"https://example.com/amp/": 404}
        issues = check_amphtml_links(pages, statuses)
        assert any(i.code == "AMPHTML_BROKEN" for i in issues)

    def test_working_amp_url_no_issue(self):
        from api.crawler.issue_checker import check_amphtml_links
        pages = [_page(url="https://example.com/", amphtml_url="https://example.com/amp/")]
        statuses = {"https://example.com/amp/": 200}
        issues = check_amphtml_links(pages, statuses)
        assert not any(i.code == "AMPHTML_BROKEN" for i in issues)

    def test_amphtml_broken_is_crawlability_category(self):
        from api.crawler.issue_checker import check_amphtml_links
        pages = [_page(url="https://example.com/", amphtml_url="https://example.com/amp/")]
        statuses = {"https://example.com/amp/": 500}
        issues = check_amphtml_links(pages, statuses)
        issue = next(i for i in issues if i.code == "AMPHTML_BROKEN")
        assert issue.category == "crawlability"


class TestHighCrawlDepth:
    def test_depth_5_emits_warning(self):
        page = _page(crawl_depth=5)
        codes = _codes(check_page(page))
        assert "HIGH_CRAWL_DEPTH" in codes

    def test_depth_4_no_issue(self):
        page = _page(crawl_depth=4)
        codes = _codes(check_page(page))
        assert "HIGH_CRAWL_DEPTH" not in codes

    def test_depth_none_no_issue(self):
        page = _page(crawl_depth=None)
        codes = _codes(check_page(page))
        assert "HIGH_CRAWL_DEPTH" not in codes


class TestPdfTooLarge:
    def test_pdf_over_10mb_emits_warning(self):
        result = FetchResult(
            url="https://example.com/doc.pdf",
            final_url="https://example.com/doc.pdf",
            status_code=200,
            content_type="application/pdf",
            headers={"content-length": str(11 * 1024 * 1024)},  # 11 MB
        )
        issues = check_asset(result)
        assert any(i.code == "PDF_TOO_LARGE" for i in issues)

    def test_pdf_under_10mb_no_issue(self):
        result = FetchResult(
            url="https://example.com/doc.pdf",
            final_url="https://example.com/doc.pdf",
            status_code=200,
            content_type="application/pdf",
            headers={"content-length": str(5 * 1024 * 1024)},  # 5 MB — under 10 MB threshold
        )
        issues = check_asset(result)
        assert not any(i.code == "PDF_TOO_LARGE" for i in issues)

    def test_pdf_exactly_10mb_no_issue(self):
        result = FetchResult(
            url="https://example.com/doc.pdf",
            final_url="https://example.com/doc.pdf",
            status_code=200,
            content_type="application/pdf",
            headers={"content-length": str(10 * 1024 * 1024)},  # exactly 10 MB
        )
        issues = check_asset(result)
        assert not any(i.code == "PDF_TOO_LARGE" for i in issues)


class TestSecurityChecks:
    def test_http_page_emits_critical(self):
        page = _page(url="http://example.com/page")
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" in codes

    def test_https_page_no_http_page_issue(self):
        page = _page(url="https://example.com/page", has_hsts=True)
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" not in codes

    def test_mixed_content_emits_warning(self):
        page = _page(url="https://example.com/page", mixed_content_count=3, has_hsts=True)
        codes = _codes(check_page(page))
        assert "MIXED_CONTENT" in codes

    def test_no_mixed_content_no_issue(self):
        page = _page(url="https://example.com/page", mixed_content_count=0, has_hsts=True)
        codes = _codes(check_page(page))
        assert "MIXED_CONTENT" not in codes

    def test_missing_hsts_emits_info(self):
        page = _page(url="https://example.com/page", has_hsts=False)
        codes = _codes(check_page(page))
        assert "MISSING_HSTS" in codes

    def test_hsts_present_no_issue(self):
        page = _page(url="https://example.com/page", has_hsts=True)
        codes = _codes(check_page(page))
        assert "MISSING_HSTS" not in codes

    def test_missing_hsts_emitted_once_per_host(self):
        # Same host on two pages — should only emit once
        checked: set[str] = set()
        p1 = _page(url="https://example.com/a", has_hsts=False)
        p2 = _page(url="https://example.com/b", has_hsts=False)
        i1 = check_page(p1, hsts_checked_hosts=checked)
        i2 = check_page(p2, hsts_checked_hosts=checked)
        hsts_issues = [i for i in i1 + i2 if i.code == "MISSING_HSTS"]
        assert len(hsts_issues) == 1

    def test_unsafe_cross_origin_link_emits_info(self):
        page = _page(url="https://example.com/page", unsafe_cross_origin_count=2, has_hsts=True)
        codes = _codes(check_page(page))
        assert "UNSAFE_CROSS_ORIGIN_LINK" in codes

    def test_no_unsafe_links_no_issue(self):
        page = _page(url="https://example.com/page", unsafe_cross_origin_count=0, has_hsts=True)
        codes = _codes(check_page(page))
        assert "UNSAFE_CROSS_ORIGIN_LINK" not in codes

    def test_http_page_suppresses_https_only_checks(self):
        # Mixed content and HSTS checks should not fire on HTTP pages
        page = _page(url="http://example.com/page", mixed_content_count=5, has_hsts=False)
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" in codes
        assert "MIXED_CONTENT" not in codes
        assert "MISSING_HSTS" not in codes


class TestUrlStructureChecks:
    def test_url_uppercase_emits_warning(self):
        issues = check_url_structure("https://example.com/About-Us")
        assert any(i.code == "URL_UPPERCASE" for i in issues)

    def test_url_lowercase_no_issue(self):
        issues = check_url_structure("https://example.com/about-us")
        assert not any(i.code == "URL_UPPERCASE" for i in issues)

    def test_url_has_spaces_emits_warning(self):
        issues = check_url_structure("https://example.com/about%20us")
        assert any(i.code == "URL_HAS_SPACES" for i in issues)

    def test_url_no_spaces_no_issue(self):
        issues = check_url_structure("https://example.com/about-us")
        assert not any(i.code == "URL_HAS_SPACES" for i in issues)

    def test_url_has_underscores_emits_info(self):
        issues = check_url_structure("https://example.com/about_us")
        assert any(i.code == "URL_HAS_UNDERSCORES" for i in issues)

    def test_url_hyphens_no_underscore_issue(self):
        issues = check_url_structure("https://example.com/about-us")
        assert not any(i.code == "URL_HAS_UNDERSCORES" for i in issues)

    def test_url_over_200_chars_emits_info(self):
        long_url = "https://example.com/" + "a" * 190  # total > 200
        issues = check_url_structure(long_url)
        assert any(i.code == "URL_TOO_LONG" for i in issues)

    def test_url_exactly_200_chars_no_issue(self):
        url = "https://example.com/" + "a" * (200 - len("https://example.com/"))
        assert len(url) == 200
        issues = check_url_structure(url)
        assert not any(i.code == "URL_TOO_LONG" for i in issues)

    def test_url_under_200_chars_no_issue(self):
        issues = check_url_structure("https://example.com/short-path")
        assert not any(i.code == "URL_TOO_LONG" for i in issues)


# ---------------------------------------------------------------------------
# Bug fix: IMG_ALT_MISSING (was in scoring table but never detected)
# ---------------------------------------------------------------------------

class TestImgAltMissing:
    def test_img_missing_alt_emits_issue(self):
        page = _page(img_missing_alt_count=3)
        codes = _codes(check_page(page))
        assert "IMG_ALT_MISSING" in codes

    def test_img_missing_alt_includes_count_in_extra(self):
        page = _page(img_missing_alt_count=2)
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "IMG_ALT_MISSING")
        assert issue.extra["missing_alt_count"] == 2

    def test_img_all_have_alt_no_issue(self):
        page = _page(img_missing_alt_count=0)
        codes = _codes(check_page(page))
        assert "IMG_ALT_MISSING" not in codes


# ---------------------------------------------------------------------------
# Bug fix: MISSING_VIEWPORT_META (parser had has_viewport_meta but no issue emitted)
# ---------------------------------------------------------------------------

class TestMissingViewportMeta:
    def test_missing_viewport_meta_emits_issue(self):
        page = _page(has_viewport_meta=False)
        codes = _codes(check_page(page))
        assert "MISSING_VIEWPORT_META" in codes

    def test_present_viewport_meta_no_issue(self):
        page = _page(has_viewport_meta=True)
        codes = _codes(check_page(page))
        assert "MISSING_VIEWPORT_META" not in codes


# ---------------------------------------------------------------------------
# Bug fix: SCHEMA_MISSING (parser had schema_types but no issue emitted)
# ---------------------------------------------------------------------------

class TestSchemaMissing:
    def test_no_schema_on_indexable_page_emits_issue(self):
        page = _page(schema_types=[], is_indexable=True)
        codes = _codes(check_page(page))
        assert "SCHEMA_MISSING" in codes

    def test_schema_present_no_issue(self):
        page = _page(schema_types=["Organization"])
        codes = _codes(check_page(page))
        assert "SCHEMA_MISSING" not in codes

    def test_no_schema_on_noindex_page_skipped(self):
        page = _page(schema_types=[], is_indexable=False)
        codes = _codes(check_page(page))
        assert "SCHEMA_MISSING" not in codes


# ---------------------------------------------------------------------------
# New check: LINK_EMPTY_ANCHOR (impact 7)
# ---------------------------------------------------------------------------

class TestLinkEmptyAnchor:
    def test_empty_anchor_emits_issue(self):
        page = _page(empty_anchor_count=1)
        codes = _codes(check_page(page))
        assert "LINK_EMPTY_ANCHOR" in codes

    def test_empty_anchor_includes_count_in_extra(self):
        page = _page(empty_anchor_count=4)
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "LINK_EMPTY_ANCHOR")
        assert issue.extra["empty_anchor_count"] == 4

    def test_no_empty_anchors_no_issue(self):
        page = _page(empty_anchor_count=0)
        codes = _codes(check_page(page))
        assert "LINK_EMPTY_ANCHOR" not in codes


# ---------------------------------------------------------------------------
# New check: INTERNAL_NOFOLLOW (impact 5)
# ---------------------------------------------------------------------------

class TestInternalNofollow:
    def test_internal_nofollow_emits_issue(self):
        page = _page(internal_nofollow_count=2)
        codes = _codes(check_page(page))
        assert "INTERNAL_NOFOLLOW" in codes

    def test_no_internal_nofollow_no_issue(self):
        page = _page(internal_nofollow_count=0)
        codes = _codes(check_page(page))
        assert "INTERNAL_NOFOLLOW" not in codes


# ---------------------------------------------------------------------------
# New check: PAGE_SIZE_LARGE (impact 5)
# ---------------------------------------------------------------------------

class TestPageSizeLarge:
    def test_page_over_default_threshold_emits_issue(self):
        # Default threshold is 300 KB
        page = _page(response_size_bytes=310 * 1024)
        codes = _codes(check_page(page))
        assert "PAGE_SIZE_LARGE" in codes

    def test_page_exactly_at_default_threshold_no_issue(self):
        page = _page(response_size_bytes=300 * 1024)
        codes = _codes(check_page(page))
        assert "PAGE_SIZE_LARGE" not in codes

    def test_page_under_default_threshold_no_issue(self):
        page = _page(response_size_bytes=150 * 1024)
        codes = _codes(check_page(page))
        assert "PAGE_SIZE_LARGE" not in codes

    def test_custom_threshold_respected(self):
        page = _page(response_size_bytes=200 * 1024)
        # Under default 300 KB threshold — no issue
        assert "PAGE_SIZE_LARGE" not in _codes(check_page(page))
        # Over custom 150 KB threshold — issue emitted
        assert "PAGE_SIZE_LARGE" in _codes(check_page(page, page_size_limit_kb=150))

    def test_page_size_includes_bytes_and_limit_in_extra(self):
        size = 400 * 1024
        page = _page(response_size_bytes=size)
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "PAGE_SIZE_LARGE")
        assert issue.extra["size_bytes"] == size
        assert issue.extra["limit_kb"] == 300


# ---------------------------------------------------------------------------
# Bug fix: ORPHAN_PAGE (links tracked but never cross-referenced)
# ---------------------------------------------------------------------------

class TestOrphanPage:
    def test_page_with_no_inbound_links_is_orphan(self):
        home = _page(url="https://example.com/", links=[
            ParsedLink(url="https://example.com/about", text="About", is_internal=True),
        ])
        about = _page(url="https://example.com/about", links=[])
        hidden = _page(url="https://example.com/hidden", links=[])
        issues = check_cross_page([home, about, hidden], start_url="https://example.com/")
        orphan_urls = [i.page_url for i in issues if i.code == "ORPHAN_PAGE"]
        assert "https://example.com/hidden" in orphan_urls
        assert "https://example.com/about" not in orphan_urls

    def test_homepage_not_flagged_as_orphan(self):
        home = _page(url="https://example.com/", links=[])
        issues = check_cross_page([home], start_url="https://example.com/")
        assert not any(i.code == "ORPHAN_PAGE" for i in issues)

    def test_page_linked_from_another_not_orphan(self):
        home = _page(url="https://example.com/", links=[
            ParsedLink(url="https://example.com/about", text="About", is_internal=True),
        ])
        about = _page(url="https://example.com/about", links=[])
        issues = check_cross_page([home, about], start_url="https://example.com/")
        assert not any(i.code == "ORPHAN_PAGE" and i.page_url == "https://example.com/about"
                       for i in issues)


# ---------------------------------------------------------------------------
# Bug fix: INTERNAL_REDIRECT_301 (was emitting REDIRECT_301 for all 301s)
# ---------------------------------------------------------------------------

class TestInternalRedirect301:
    def test_internal_301_emits_internal_redirect(self):
        issues = issues_for_redirect(
            "https://example.com/old",
            301,
            ["https://example.com/new"],
            final_url="https://example.com/new",
            base_url="https://example.com/",
        )
        codes = _codes(issues)
        assert "INTERNAL_REDIRECT_301" in codes
        assert "REDIRECT_301" not in codes

    def test_external_301_emits_redirect_301(self):
        issues = issues_for_redirect(
            "https://other.com/page",
            301,
            ["https://other.com/final"],
            final_url="https://other.com/final",
            base_url="https://example.com/",
        )
        codes = _codes(issues)
        assert "REDIRECT_301" in codes
        assert "INTERNAL_REDIRECT_301" not in codes

    def test_no_base_url_falls_back_to_redirect_301(self):
        issues = issues_for_redirect(
            "https://example.com/old",
            301,
            ["https://example.com/new"],
            final_url="https://example.com/new",
        )
        codes = _codes(issues)
        assert "REDIRECT_301" in codes
        assert "INTERNAL_REDIRECT_301" not in codes


# ---------------------------------------------------------------------------
# v1.6 new check: LANG_MISSING (impact 6)
# ---------------------------------------------------------------------------

class TestLangMissing:
    def test_no_lang_attr_emits_issue(self):
        page = _page(lang_attr=None)
        codes = _codes(check_page(page))
        assert "LANG_MISSING" in codes

    def test_empty_lang_attr_emits_issue(self):
        page = _page(lang_attr="")
        codes = _codes(check_page(page))
        assert "LANG_MISSING" in codes

    def test_lang_en_no_issue(self):
        page = _page(lang_attr="en")
        codes = _codes(check_page(page))
        assert "LANG_MISSING" not in codes

    def test_lang_fr_no_issue(self):
        page = _page(lang_attr="fr")
        codes = _codes(check_page(page))
        assert "LANG_MISSING" not in codes

    def test_lang_missing_not_emitted_on_noindex_page(self):
        page = _page(lang_attr=None, is_indexable=False)
        codes = _codes(check_page(page))
        assert "LANG_MISSING" not in codes

    def test_lang_missing_is_metadata_category(self):
        page = _page(lang_attr=None)
        issues = check_page(page)
        issue = next((i for i in issues if i.code == "LANG_MISSING"), None)
        assert issue is not None
        assert issue.category == "metadata"
        assert issue.severity == "warning"


# ---------------------------------------------------------------------------
# v1.6 new check: TITLE_H1_MISMATCH (impact 6)
# ---------------------------------------------------------------------------

class TestTitleH1Mismatch:
    def test_completely_different_words_emits_issue(self):
        page = _page(
            title="Contact Our Team Today",
            h1_tags=["Donate Now to Help Animals"],
        )
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" in codes

    def test_matching_words_no_issue(self):
        page = _page(
            title="Counselling Services | Living Systems",
            h1_tags=["Counselling Services"],
        )
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" not in codes

    def test_site_name_suffix_stripped_before_compare(self):
        # "About Us | My Charity" vs "About Us" — should match after suffix stripping
        page = _page(
            title="About Us | My Charity",
            h1_tags=["About Us"],
        )
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" not in codes

    def test_partial_word_overlap_no_issue(self):
        page = _page(
            title="Our Counselling Programs",
            h1_tags=["Counselling and Support Services"],
        )
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" not in codes

    def test_no_title_no_mismatch_emitted(self):
        page = _page(title=None, h1_tags=["Some Heading"])
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" not in codes

    def test_no_h1_no_mismatch_emitted(self):
        page = _page(title="Some Title Here", h1_tags=[])
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" not in codes

    def test_mismatch_includes_title_and_h1_in_extra(self):
        page = _page(
            title="Contact Our Team Today",
            h1_tags=["Donate Now to Help Animals"],
        )
        issues = check_page(page)
        issue = next((i for i in issues if i.code == "TITLE_H1_MISMATCH"), None)
        assert issue is not None
        assert "title" in issue.extra
        assert "h1" in issue.extra

    def test_mismatch_not_emitted_on_noindex_page(self):
        page = _page(
            title="Contact Our Team Today",
            h1_tags=["Donate Now to Help Animals"],
            is_indexable=False,
        )
        codes = _codes(check_page(page))
        assert "TITLE_H1_MISMATCH" not in codes


# ---------------------------------------------------------------------------
# v1.6 new check: CANONICAL_SELF_MISSING (impact 5)
# ---------------------------------------------------------------------------

class TestCanonicalSelfMissing:
    def test_indexable_page_with_no_canonical_emits_info(self):
        page = _page(canonical_url=None, is_indexable=True)
        codes = _codes(check_page(page))
        assert "CANONICAL_SELF_MISSING" in codes

    def test_page_with_canonical_no_issue(self):
        page = _page(canonical_url="https://example.com/page", is_indexable=True)
        codes = _codes(check_page(page))
        assert "CANONICAL_SELF_MISSING" not in codes

    def test_noindex_page_not_flagged(self):
        page = _page(canonical_url=None, is_indexable=False)
        codes = _codes(check_page(page))
        assert "CANONICAL_SELF_MISSING" not in codes

    def test_canonical_self_missing_is_info_severity(self):
        page = _page(canonical_url=None, is_indexable=True)
        issues = check_page(page)
        issue = next((i for i in issues if i.code == "CANONICAL_SELF_MISSING"), None)
        assert issue is not None
        assert issue.severity == "info"
        assert issue.category == "metadata"


# ---------------------------------------------------------------------------
# check_asset: IMG_OVERSIZED
# ---------------------------------------------------------------------------

def _image_result(url: str, size_bytes: int, content_type: str = "image/jpeg") -> FetchResult:
    return FetchResult(
        url=url,
        final_url=url,
        status_code=200,
        content_type=content_type,
        headers={"content-length": str(size_bytes)},
    )


class TestImgOversized:
    def test_image_over_200kb_default_emits_warning(self):
        result = _image_result("https://example.com/photo.jpg", 210 * 1024)
        codes = _codes(check_asset(result))
        assert "IMG_OVERSIZED" in codes

    def test_image_exactly_200kb_no_issue(self):
        result = _image_result("https://example.com/photo.jpg", 200 * 1024)
        codes = _codes(check_asset(result))
        assert "IMG_OVERSIZED" not in codes

    def test_image_under_200kb_no_issue(self):
        result = _image_result("https://example.com/photo.jpg", 100 * 1024)
        codes = _codes(check_asset(result))
        assert "IMG_OVERSIZED" not in codes

    def test_custom_threshold_respected(self):
        result = _image_result("https://example.com/photo.jpg", 310 * 1024)
        codes_default = _codes(check_asset(result))
        assert "IMG_OVERSIZED" in codes_default

        result_small = _image_result("https://example.com/photo.jpg", 150 * 1024)
        codes_tight = _codes(check_asset(result_small, img_size_limit_kb=100))
        assert "IMG_OVERSIZED" in codes_tight

        codes_loose = _codes(check_asset(result_small, img_size_limit_kb=200))
        assert "IMG_OVERSIZED" not in codes_loose

    def test_img_oversized_description_includes_threshold(self):
        result = _image_result("https://example.com/photo.jpg", 300 * 1024)
        issues = check_asset(result, img_size_limit_kb=250)
        issue = next((i for i in issues if i.code == "IMG_OVERSIZED"), None)
        assert issue is not None
        assert "250" in issue.description

    def test_pdf_not_flagged_as_img_oversized(self):
        result = FetchResult(
            url="https://example.com/doc.pdf",
            final_url="https://example.com/doc.pdf",
            status_code=200,
            content_type="application/pdf",
            headers={"content-length": str(500 * 1024)},
        )
        codes = _codes(check_asset(result))
        assert "IMG_OVERSIZED" not in codes

    def test_zero_content_length_no_issue(self):
        result = _image_result("https://example.com/photo.jpg", 0)
        codes = _codes(check_asset(result))
        assert "IMG_OVERSIZED" not in codes
