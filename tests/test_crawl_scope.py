"""
Tests for content-type scoping in the crawl engine (partial scan).

All external HTTP calls are mocked with respx — no real network requests.

Spec:  docs/functional-specification.md (Scan content-type scoping)
Covers: allowlist-based scoping at seed + link-follow, the adversarial
        lookalike-URL case (P7), full-mode back-compat, and skip counting (P2).
"""

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl
from api.crawler.normaliser import normalise_url


BASE_URL = "https://example.com/"
ROBOTS_URL = "https://example.com/robots.txt"
SITEMAP_URL = "https://example.com/sitemap.xml"
_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"

# A Page and a Post whose permalinks are structurally identical — the whole
# reason scope must be an authoritative URL set, not a URL-pattern guess.
ABOUT = normalise_url("https://example.com/about")       # a Page
RECAP = normalise_url("https://example.com/our-recap")   # a Post (lookalike)


def _page_html(title: str, body: str = "") -> str:
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>{title} — a nice long descriptive title here</title>"
        '<meta name="description" content="A description long enough to pass the validation checks here.">'
        f"</head><body><h1>{title}</h1>{body}</body></html>"
    )


def _urlset(urls):
    locs = "\n".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'


def _register_site(mock):
    """Home links to both /about and /our-recap; sitemap lists both too."""
    mock.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
    mock.get(SITEMAP_URL).mock(return_value=httpx.Response(200, text=_urlset([ABOUT, RECAP])))
    home = _page_html("Home", '<a href="/about">About</a> <a href="/our-recap">Recap</a>')
    mock.get(BASE_URL).mock(return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"}))
    mock.get(ABOUT).mock(return_value=httpx.Response(200, text=_page_html("About"), headers={"content-type": "text/html"}))
    mock.get(RECAP).mock(return_value=httpx.Response(200, text=_page_html("Our Recap"), headers={"content-type": "text/html"}))


class TestContentScopeFilter:
    @pytest.mark.asyncio
    async def test_pages_only_excludes_lookalike_post(self):
        """Adversarial (P7): a Post whose URL is structurally identical to a Page
        must be excluded under a Pages-only scope — proving the filter uses the
        authoritative allowlist, not a URL-pattern guess. Fails if pattern-based
        classification is ever reintroduced."""
        with respx.mock:
            _register_site(respx.mock)
            settings = CrawlSettings(crawl_delay_ms=0, max_pages=50, scope_urls={ABOUT})
            result = await run_crawl("job-scope", BASE_URL, settings)

        crawled = {p.url for p in result.pages}
        assert any("/about" in u for u in crawled)          # the Page was crawled
        assert not any("our-recap" in u for u in crawled)   # the lookalike Post was not
        # The out-of-scope URL is counted, not silently dropped (P2).
        assert result.scope_skipped >= 1

    @pytest.mark.asyncio
    async def test_full_mode_crawls_everything(self):
        """Back-compat guard: scope_urls=None (full mode) queues every URL exactly
        as before — both the Page and the Post are crawled."""
        with respx.mock:
            _register_site(respx.mock)
            settings = CrawlSettings(crawl_delay_ms=0, max_pages=50, scope_urls=None)
            result = await run_crawl("job-full", BASE_URL, settings)

        crawled = {p.url for p in result.pages}
        assert any("/about" in u for u in crawled)
        assert any("our-recap" in u for u in crawled)
        assert result.scope_skipped == 0
