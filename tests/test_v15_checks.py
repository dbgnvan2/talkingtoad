"""
Tests for v1.5 extension checks (spec nonprofit-crawler-spec-v1.5-extensions.md).

Covers:
  §E1 Security: HTTP_PAGE, MIXED_CONTENT, MISSING_HSTS, UNSAFE_CROSS_ORIGIN_LINK
  §E2 URL structure: URL_UPPERCASE, URL_HAS_SPACES, URL_HAS_UNDERSCORES, URL_TOO_LONG
  §E3 Pagination: PAGINATION_LINKS_PRESENT
  §E4 Meta refresh: META_REFRESH_REDIRECT
  §E5 Thin content: THIN_CONTENT
  §E6 AMP: AMPHTML_BROKEN (check_amphtml_links helper)
  §E7 Crawl depth: HIGH_CRAWL_DEPTH
  Parser: word_count, pagination_next/prev, amphtml_url, meta_refresh_url,
          mixed_content_count, unsafe_cross_origin_count, has_hsts
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bs4 import BeautifulSoup

from api.crawler.parser import (
    ParsedPage,
    ParsedLink,
    _count_words,
    _extract_link_rel,
    _extract_meta_refresh_url,
    _count_mixed_content,
    _count_unsafe_cross_origin,
    _check_hsts,
)
from api.crawler.issue_checker import (
    Issue,
    check_page,
    check_url_structure,
    check_amphtml_links,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _page(
    url: str = "https://example.com/page",
    *,
    title: str | None = "A Good Enough Page Title",
    meta_description: str | None = "A good meta description that is long enough to pass the minimum length check here.",
    og_title: str | None = "OG Title",
    og_description: str | None = "OG Description",
    canonical_url: str | None = None,
    h1_tags: list[str] | None = None,
    headings_outline: list[dict] | None = None,
    is_indexable: bool = True,
    robots_directive: str | None = None,
    links: list[ParsedLink] | None = None,
    has_favicon: bool | None = None,
    word_count: int | None = 500,
    crawl_depth: int | None = 1,
    pagination_next: str | None = None,
    pagination_prev: str | None = None,
    amphtml_url: str | None = None,
    meta_refresh_url: str | None = None,
    mixed_content_count: int = 0,
    unsafe_cross_origin_count: int = 0,
    has_hsts: bool | None = True,
) -> ParsedPage:
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=1000,
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
        has_viewport_meta=True,
        schema_types=[],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=word_count,
        crawl_depth=crawl_depth,
        pagination_next=pagination_next,
        pagination_prev=pagination_prev,
        amphtml_url=amphtml_url,
        meta_refresh_url=meta_refresh_url,
        mixed_content_count=mixed_content_count,
        unsafe_cross_origin_count=unsafe_cross_origin_count,
        has_hsts=has_hsts,
    )


def _codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


# ---------------------------------------------------------------------------
# §E1 Security checks
# ---------------------------------------------------------------------------

class TestHttpPage:
    def test_http_url_emits_http_page(self):
        page = _page(url="http://example.com/page", has_hsts=None)
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" in codes

    def test_https_url_does_not_emit_http_page(self):
        page = _page(url="https://example.com/page")
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" not in codes

    def test_http_page_skips_https_only_checks(self):
        # MIXED_CONTENT and MISSING_HSTS should NOT appear for an HTTP page
        page = _page(url="http://example.com/page", has_hsts=None, mixed_content_count=3)
        codes = _codes(check_page(page))
        assert "HTTP_PAGE" in codes
        assert "MIXED_CONTENT" not in codes
        assert "MISSING_HSTS" not in codes


class TestMixedContent:
    def test_mixed_content_detected_on_https_page(self):
        page = _page(mixed_content_count=2)
        codes = _codes(check_page(page))
        assert "MIXED_CONTENT" in codes

    def test_no_mixed_content_no_issue(self):
        page = _page(mixed_content_count=0)
        codes = _codes(check_page(page))
        assert "MIXED_CONTENT" not in codes

    def test_mixed_content_extra_has_count(self):
        page = _page(mixed_content_count=3)
        issues = check_page(page)
        mc = next(i for i in issues if i.code == "MIXED_CONTENT")
        assert mc.extra["mixed_count"] == 3


class TestMissingHsts:
    def test_missing_hsts_emits_issue(self):
        page = _page(has_hsts=False)
        codes = _codes(check_page(page))
        assert "MISSING_HSTS" in codes

    def test_present_hsts_no_issue(self):
        page = _page(has_hsts=True)
        codes = _codes(check_page(page))
        assert "MISSING_HSTS" not in codes

    def test_hsts_emitted_once_per_host(self):
        host_set: set[str] = set()
        page1 = _page(url="https://example.com/a", has_hsts=False)
        page2 = _page(url="https://example.com/b", has_hsts=False)
        issues1 = check_page(page1, hsts_checked_hosts=host_set)
        issues2 = check_page(page2, hsts_checked_hosts=host_set)
        codes1 = _codes(issues1)
        codes2 = _codes(issues2)
        assert "MISSING_HSTS" in codes1
        assert "MISSING_HSTS" not in codes2  # same host, already emitted

    def test_hsts_emitted_for_different_hosts(self):
        host_set: set[str] = set()
        page1 = _page(url="https://example.com/page", has_hsts=False)
        page2 = _page(url="https://other.org/page", has_hsts=False)
        issues1 = check_page(page1, hsts_checked_hosts=host_set)
        issues2 = check_page(page2, hsts_checked_hosts=host_set)
        assert "MISSING_HSTS" in _codes(issues1)
        assert "MISSING_HSTS" in _codes(issues2)


class TestUnsafeCrossOriginLink:
    def test_unsafe_links_emit_issue(self):
        page = _page(unsafe_cross_origin_count=2)
        codes = _codes(check_page(page))
        assert "UNSAFE_CROSS_ORIGIN_LINK" in codes

    def test_no_unsafe_links_no_issue(self):
        page = _page(unsafe_cross_origin_count=0)
        codes = _codes(check_page(page))
        assert "UNSAFE_CROSS_ORIGIN_LINK" not in codes

    def test_unsafe_links_extra_has_count(self):
        page = _page(unsafe_cross_origin_count=4)
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "UNSAFE_CROSS_ORIGIN_LINK")
        assert issue.extra["unsafe_link_count"] == 4


# ---------------------------------------------------------------------------
# §E2 URL structure checks
# ---------------------------------------------------------------------------

class TestUrlStructure:
    def test_uppercase_path_emits_url_uppercase(self):
        codes = _codes(check_url_structure("https://example.com/About-Us"))
        assert "URL_UPPERCASE" in codes

    def test_lowercase_path_no_url_uppercase(self):
        codes = _codes(check_url_structure("https://example.com/about-us"))
        assert "URL_UPPERCASE" not in codes

    def test_encoded_space_emits_url_has_spaces(self):
        codes = _codes(check_url_structure("https://example.com/our%20team"))
        assert "URL_HAS_SPACES" in codes

    def test_no_spaces_no_url_has_spaces(self):
        codes = _codes(check_url_structure("https://example.com/our-team"))
        assert "URL_HAS_SPACES" not in codes

    def test_underscore_path_emits_url_has_underscores(self):
        codes = _codes(check_url_structure("https://example.com/our_team"))
        assert "URL_HAS_UNDERSCORES" in codes

    def test_hyphen_path_no_url_has_underscores(self):
        codes = _codes(check_url_structure("https://example.com/our-team"))
        assert "URL_HAS_UNDERSCORES" not in codes

    def test_long_url_emits_url_too_long(self):
        long_url = "https://example.com/" + "a" * 185  # > 200 chars total
        assert len(long_url) > 200
        codes = _codes(check_url_structure(long_url))
        assert "URL_TOO_LONG" in codes

    def test_exact_200_chars_no_url_too_long(self):
        url = "https://example.com/" + "a" * (200 - len("https://example.com/"))
        assert len(url) == 200
        codes = _codes(check_url_structure(url))
        assert "URL_TOO_LONG" not in codes

    def test_clean_url_no_issues(self):
        codes = _codes(check_url_structure("https://example.com/about-us"))
        assert codes == []


# ---------------------------------------------------------------------------
# §E3 Pagination links
# ---------------------------------------------------------------------------

class TestPaginationLinks:
    def test_pagination_next_emits_issue(self):
        page = _page(pagination_next="/blog/page/2")
        codes = _codes(check_page(page))
        assert "PAGINATION_LINKS_PRESENT" in codes

    def test_pagination_prev_emits_issue(self):
        page = _page(pagination_prev="/blog/page/1")
        codes = _codes(check_page(page))
        assert "PAGINATION_LINKS_PRESENT" in codes

    def test_no_pagination_no_issue(self):
        page = _page(pagination_next=None, pagination_prev=None)
        codes = _codes(check_page(page))
        assert "PAGINATION_LINKS_PRESENT" not in codes

    def test_pagination_extra_has_hrefs(self):
        page = _page(pagination_next="/blog/2", pagination_prev="/blog/1")
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "PAGINATION_LINKS_PRESENT")
        assert issue.extra["next"] == "/blog/2"
        assert issue.extra["prev"] == "/blog/1"


# ---------------------------------------------------------------------------
# §E4 Meta refresh redirect
# ---------------------------------------------------------------------------

class TestMetaRefreshRedirect:
    def test_meta_refresh_with_url_emits_issue(self):
        page = _page(meta_refresh_url="/new-page")
        codes = _codes(check_page(page))
        assert "META_REFRESH_REDIRECT" in codes

    def test_no_meta_refresh_no_issue(self):
        page = _page(meta_refresh_url=None)
        codes = _codes(check_page(page))
        assert "META_REFRESH_REDIRECT" not in codes


# ---------------------------------------------------------------------------
# §E5 Thin content
# ---------------------------------------------------------------------------

class TestThinContent:
    def test_low_word_count_emits_thin_content(self):
        page = _page(word_count=50)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" in codes

    def test_exactly_300_words_no_thin_content(self):
        page = _page(word_count=300)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_zero_word_count_no_thin_content(self):
        # Zero = likely parsing failure, suppress
        page = _page(word_count=0)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_noindex_page_no_thin_content(self):
        page = _page(word_count=50, is_indexable=False)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_none_word_count_no_thin_content(self):
        page = _page(word_count=None)
        codes = _codes(check_page(page))
        assert "THIN_CONTENT" not in codes

    def test_thin_content_extra_has_word_count(self):
        page = _page(word_count=42)
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "THIN_CONTENT")
        assert issue.extra["word_count"] == 42


# ---------------------------------------------------------------------------
# §E6 AMP broken link
# ---------------------------------------------------------------------------

class TestAmpBroken:
    def test_amp_broken_404_emits_issue(self):
        page = _page(amphtml_url="https://example.com/amp/page")
        issues = check_amphtml_links([page], {"https://example.com/amp/page": 404})
        codes = _codes(issues)
        assert "AMPHTML_BROKEN" in codes

    def test_amp_ok_no_issue(self):
        page = _page(amphtml_url="https://example.com/amp/page")
        issues = check_amphtml_links([page], {"https://example.com/amp/page": 200})
        assert _codes(issues) == []

    def test_no_amphtml_url_no_issue(self):
        page = _page(amphtml_url=None)
        issues = check_amphtml_links([page], {})
        assert _codes(issues) == []

    def test_amp_extra_has_url_and_status(self):
        page = _page(amphtml_url="https://example.com/amp/page")
        issues = check_amphtml_links([page], {"https://example.com/amp/page": 404})
        issue = issues[0]
        assert issue.extra["amphtml_url"] == "https://example.com/amp/page"
        assert issue.extra["amp_status"] == 404


# ---------------------------------------------------------------------------
# §E7 Crawl depth
# ---------------------------------------------------------------------------

class TestCrawlDepth:
    def test_depth_5_emits_high_crawl_depth(self):
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

    def test_high_depth_extra_has_depth(self):
        page = _page(crawl_depth=7)
        issues = check_page(page)
        issue = next(i for i in issues if i.code == "HIGH_CRAWL_DEPTH")
        assert issue.extra["crawl_depth"] == 7


# ---------------------------------------------------------------------------
# Parser helpers: word count
# ---------------------------------------------------------------------------

class TestWordCount:
    def test_counts_body_words(self):
        soup = _soup("<html><body><p>Hello world foo bar</p></body></html>")
        assert _count_words(soup) == 4

    def test_excludes_nav_and_footer(self):
        soup = _soup("""
            <html><body>
              <nav>Home About Contact</nav>
              <p>Main content here</p>
              <footer>Footer stuff</footer>
            </body></html>
        """)
        count = _count_words(soup)
        assert count == 3  # only "Main content here"

    def test_excludes_script_and_style(self):
        soup = _soup("""
            <html><body>
              <script>var x = 1; function foo() {}</script>
              <style>.cls { color: red; }</style>
              <p>Real content</p>
            </body></html>
        """)
        assert _count_words(soup) == 2  # "Real content"

    def test_no_body_returns_zero(self):
        soup = _soup("<html><head></head></html>")
        assert _count_words(soup) == 0


# ---------------------------------------------------------------------------
# Parser helpers: pagination and AMP links
# ---------------------------------------------------------------------------

class TestExtractLinkRel:
    def test_extracts_next_link(self):
        soup = _soup('<html><head><link rel="next" href="/page/2"></head></html>')
        assert _extract_link_rel(soup, "next") == "/page/2"

    def test_extracts_prev_link(self):
        soup = _soup('<html><head><link rel="prev" href="/page/1"></head></html>')
        assert _extract_link_rel(soup, "prev") == "/page/1"

    def test_extracts_amphtml_link(self):
        soup = _soup('<html><head><link rel="amphtml" href="/amp/page"></head></html>')
        assert _extract_link_rel(soup, "amphtml") == "/amp/page"

    def test_missing_link_returns_none(self):
        soup = _soup("<html><head></head></html>")
        assert _extract_link_rel(soup, "next") is None


# ---------------------------------------------------------------------------
# Parser helpers: meta refresh
# ---------------------------------------------------------------------------

class TestExtractMetaRefreshUrl:
    def test_extracts_redirect_url(self):
        soup = _soup('<html><head><meta http-equiv="refresh" content="0; url=/new-page"></head></html>')
        assert _extract_meta_refresh_url(soup) == "/new-page"

    def test_page_reload_returns_none(self):
        soup = _soup('<html><head><meta http-equiv="refresh" content="30"></head></html>')
        assert _extract_meta_refresh_url(soup) is None

    def test_no_meta_refresh_returns_none(self):
        soup = _soup("<html><head></head></html>")
        assert _extract_meta_refresh_url(soup) is None

    def test_case_insensitive_url_key(self):
        soup = _soup('<html><head><meta http-equiv="refresh" content="0; URL=/target"></head></html>')
        assert _extract_meta_refresh_url(soup) == "/target"


# ---------------------------------------------------------------------------
# Parser helpers: mixed content
# ---------------------------------------------------------------------------

class TestCountMixedContent:
    def test_http_img_on_https_page_counted(self):
        soup = _soup('<html><body><img src="http://cdn.example.com/img.png"></body></html>')
        assert _count_mixed_content(soup, "https://example.com/page") == 1

    def test_https_img_not_counted(self):
        soup = _soup('<html><body><img src="https://cdn.example.com/img.png"></body></html>')
        assert _count_mixed_content(soup, "https://example.com/page") == 0

    def test_http_page_returns_zero(self):
        soup = _soup('<html><body><img src="http://cdn.example.com/img.png"></body></html>')
        assert _count_mixed_content(soup, "http://example.com/page") == 0

    def test_multiple_mixed_resources_counted(self):
        soup = _soup("""
            <html><body>
              <img src="http://cdn.example.com/a.png">
              <script src="http://cdn.example.com/b.js"></script>
            </body></html>
        """)
        assert _count_mixed_content(soup, "https://example.com/page") == 2


# ---------------------------------------------------------------------------
# Parser helpers: unsafe cross-origin links
# ---------------------------------------------------------------------------

class TestCountUnsafeCrossOrigin:
    def test_blank_external_without_noopener_counted(self):
        soup = _soup('<html><body><a href="https://other.com" target="_blank">Link</a></body></html>')
        assert _count_unsafe_cross_origin(soup, "https://example.com/page") == 1

    def test_blank_with_noopener_not_counted(self):
        soup = _soup('<html><body><a href="https://other.com" target="_blank" rel="noopener">Link</a></body></html>')
        assert _count_unsafe_cross_origin(soup, "https://example.com/page") == 0

    def test_blank_with_noreferrer_not_counted(self):
        soup = _soup('<html><body><a href="https://other.com" target="_blank" rel="noreferrer">Link</a></body></html>')
        assert _count_unsafe_cross_origin(soup, "https://example.com/page") == 0

    def test_internal_blank_link_not_counted(self):
        soup = _soup('<html><body><a href="/about" target="_blank">Link</a></body></html>')
        assert _count_unsafe_cross_origin(soup, "https://example.com/page") == 0

    def test_no_blank_links_returns_zero(self):
        soup = _soup('<html><body><a href="https://other.com">Link</a></body></html>')
        assert _count_unsafe_cross_origin(soup, "https://example.com/page") == 0


# ---------------------------------------------------------------------------
# Parser helpers: HSTS check
# ---------------------------------------------------------------------------

class TestCheckHsts:
    def test_https_with_hsts_header_returns_true(self):
        headers = {"Strict-Transport-Security": "max-age=31536000"}
        assert _check_hsts(headers, "https://example.com/page") is True

    def test_https_without_hsts_header_returns_false(self):
        assert _check_hsts({}, "https://example.com/page") is False

    def test_http_page_returns_none(self):
        headers = {"Strict-Transport-Security": "max-age=31536000"}
        assert _check_hsts(headers, "http://example.com/page") is None
