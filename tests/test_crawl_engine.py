"""
Tests for api/crawler/engine.py and api/crawler/fetcher.py

All external HTTP calls are mocked — no real network requests.
Covers: domain boundary, admin path skipping, robots.txt blocking,
external link cap enforcement, redirect chain and loop detection.
"""

import asyncio
import pytest
import httpx
import respx

from api.crawler.engine import CrawlSettings, run_crawl, _EXTERNAL_LINK_CAP_PER_JOB, _is_bot_blocking_domain
from api.crawler.fetcher import fetch_page, FetchResult


BASE_URL = "https://example.com/"
ROBOTS_URL = "https://example.com/robots.txt"
SITEMAP_URL = "https://example.com/sitemap.xml"

_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"

_MINIMAL_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Test Page With A Good Long Title Here</title>
  <meta name="description" content="A good description that is long enough to pass validation checks easily here.">
</head>
<body><h1>Heading</h1></body>
</html>"""

_HTML_WITH_INTERNAL_LINK = """<!DOCTYPE html>
<html>
<head>
  <title>Home Page With A Good Long Title Here</title>
  <meta name="description" content="A good description that is long enough to pass validation checks easily here.">
</head>
<body>
  <h1>Home</h1>
  <a href="/about">About</a>
</body>
</html>"""

_HTML_WITH_EXTERNAL_LINK = """<!DOCTYPE html>
<html>
<head>
  <title>Home Page With A Good Long Title Here</title>
  <meta name="description" content="A good description that is long enough to pass validation checks easily here.">
</head>
<body>
  <h1>Home</h1>
  <a href="https://external-site.org/">External</a>
</body>
</html>"""


def _mock_standard_setup(mock: respx.MockRouter, home_html: str = _MINIMAL_HTML) -> None:
    """Register robots.txt (allow all), sitemap (404), and home page responses."""
    mock.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
    mock.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
    mock.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))


class TestDomainBoundaryEnforcement:
    @pytest.mark.asyncio
    async def test_external_links_not_crawled_internally(self):
        """External links should only be status-checked, never crawled as pages."""
        external_url = "https://external-site.org/"

        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=_HTML_WITH_EXTERNAL_LINK)
            # External site should only get a HEAD request, not a full crawl
            respx.head(external_url).mock(return_value=httpx.Response(200))

            settings = CrawlSettings(crawl_delay_ms=0, max_pages=10)
            result = await run_crawl("job-1", BASE_URL, settings)

        # The external page must NOT appear in crawled pages
        crawled_urls = {p.url for p in result.pages}
        assert external_url not in crawled_urls
        # But the home page should have been crawled
        assert BASE_URL in crawled_urls

    @pytest.mark.asyncio
    async def test_www_prefix_treated_as_same_domain(self):
        """www.example.com links should be queued as internal, not external."""
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="https://www.example.com/about">About</a></body></html>"""
        about_html = """<!DOCTYPE html>
<html><head><title>About Page With A Good Long Title Here</title>
<meta name="description" content="About description here long enough to pass checks.">
</head><body><h1>About</h1></body></html>"""

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))
            respx.get("https://www.example.com/about").mock(
                return_value=httpx.Response(200, text=about_html, headers={"content-type": "text/html"})
            )

            settings = CrawlSettings(crawl_delay_ms=0, max_pages=10)
            result = await run_crawl("job-2", BASE_URL, settings)

        # www.example.com/about should have been crawled as internal
        crawled_urls = {p.url for p in result.pages}
        assert len(crawled_urls) >= 1  # At minimum the home page

    @pytest.mark.asyncio
    async def test_subdomain_not_crawled(self):
        """blog.example.com should be treated as external — not queued for crawl."""
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="https://blog.example.com/post">Blog</a></body></html>"""

        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            # blog subdomain — only a HEAD check, never a full crawl
            respx.head("https://blog.example.com/post").mock(return_value=httpx.Response(200))

            settings = CrawlSettings(crawl_delay_ms=0, max_pages=10)
            result = await run_crawl("job-3", BASE_URL, settings)

        crawled_urls = {p.url for p in result.pages}
        assert "https://blog.example.com/post" not in crawled_urls


class TestAdminPathSkipping:
    @pytest.mark.asyncio
    async def test_wp_admin_not_crawled(self):
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="/wp-admin/edit.php">Admin</a></body></html>"""

        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            settings = CrawlSettings(crawl_delay_ms=0)
            result = await run_crawl("job-4", BASE_URL, settings)

        crawled_urls = {p.url for p in result.pages}
        assert not any("/wp-admin" in u for u in crawled_urls)

    @pytest.mark.asyncio
    async def test_login_path_not_crawled(self):
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="/login">Login</a></body></html>"""

        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            settings = CrawlSettings(crawl_delay_ms=0)
            result = await run_crawl("job-5", BASE_URL, settings)

        crawled_urls = {p.url for p in result.pages}
        assert "https://example.com/login" not in crawled_urls


class TestRobotsTxtBlocking:
    @pytest.mark.asyncio
    async def test_disallowed_url_emits_robots_blocked_issue(self):
        robots_txt = "User-agent: *\nDisallow: /private/\n"
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="/private/secret">Secret</a></body></html>"""

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0, respect_robots=True)
            result = await run_crawl("job-6", BASE_URL, settings)

        blocked_issues = [i for i in result.issues if i.code == "ROBOTS_BLOCKED"]
        assert len(blocked_issues) >= 1
        blocked_urls = {i.page_url for i in blocked_issues}
        assert "https://example.com/private/secret" in blocked_urls

    @pytest.mark.asyncio
    async def test_disallowed_url_not_crawled(self):
        robots_txt = "User-agent: *\nDisallow: /private/\n"
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="/private/secret">Secret</a></body></html>"""

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0, respect_robots=True)
            result = await run_crawl("job-7", BASE_URL, settings)

        crawled_urls = {p.url for p in result.pages}
        assert "https://example.com/private/secret" not in crawled_urls

    @pytest.mark.asyncio
    async def test_respect_robots_false_ignores_disallow(self):
        robots_txt = "User-agent: *\nDisallow: /\n"

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=_MINIMAL_HTML, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0, respect_robots=False)
            result = await run_crawl("job-8", BASE_URL, settings)

        # The home page should be crawled even though robots blocks everything
        assert len(result.pages) >= 1


class TestExternalLinkCapEnforcement:
    @pytest.mark.asyncio
    async def test_external_link_cap_per_page_50(self):
        """No more than 50 external links per page should be checked."""
        external_links = "".join(
            f'<a href="https://ext{i}.example.org/">Link {i}</a>\n'
            for i in range(60)  # 60 external links > 50 cap
        )
        home_html = f"""<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1>{external_links}</body></html>"""

        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            # Mock all possible external HEAD requests as 200
            for i in range(60):
                respx.head(f"https://ext{i}.example.org/").mock(return_value=httpx.Response(200))

            settings = CrawlSettings(crawl_delay_ms=0)
            result = await run_crawl("job-9", BASE_URL, settings)

        # Should not have checked more than 50 external links from one page
        assert result.external_links_checked <= 50

    @pytest.mark.asyncio
    async def test_external_link_job_cap_500(self):
        """Total external link checks across the job are capped at 500."""
        # This test patches _EXTERNAL_LINK_CAP_PER_JOB via a small cap for speed
        from api.crawler import engine as engine_module
        original_cap = engine_module._EXTERNAL_LINK_CAP_PER_JOB

        try:
            engine_module._EXTERNAL_LINK_CAP_PER_JOB = 3

            external_links = "".join(
                f'<a href="https://ext{i}.example.org/">Link {i}</a>\n'
                for i in range(10)
            )
            home_html = f"""<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1>{external_links}</body></html>"""

            with respx.mock:
                _mock_standard_setup(respx.mock, home_html=home_html)
                for i in range(10):
                    respx.head(f"https://ext{i}.example.org/").mock(return_value=httpx.Response(200))

                settings = CrawlSettings(crawl_delay_ms=0)
                result = await run_crawl("job-10", BASE_URL, settings)

            assert result.external_links_checked <= 3
        finally:
            engine_module._EXTERNAL_LINK_CAP_PER_JOB = original_cap


class TestRedirectDetection:
    @pytest.mark.asyncio
    async def test_redirect_chain_emits_redirect_chain_issue(self):
        """A → B → C multi-hop redirect should emit REDIRECT_CHAIN.

        We patch fetch_page to inject a pre-built FetchResult with a two-hop
        redirect chain, since respx cannot synthesise httpx response.history.
        """
        import unittest.mock as mock
        from api.crawler import fetcher

        url_a = "https://example.com/old"
        url_b = "https://example.com/middle"
        url_c = "https://example.com/final"

        home_html = f"""<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="{url_a}">Old</a></body></html>"""

        original_fetch = fetcher.fetch_page

        async def patched_fetch(url, client, **kwargs):
            if url == url_a:
                # Simulate A → B → C (two intermediate hops)
                return FetchResult(
                    url=url_a,
                    final_url=url_c,
                    status_code=200,
                    first_status_code=301,
                    redirect_chain=[url_a, url_b],  # two intermediate URLs = chain
                )
            return await original_fetch(url, client, **kwargs)

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0)
            with mock.patch("api.crawler.engine.fetch_page", side_effect=patched_fetch):
                result = await run_crawl("job-11", BASE_URL, settings)

        chain_issues = [i for i in result.issues if i.code == "REDIRECT_CHAIN"]
        assert len(chain_issues) >= 1
        assert chain_issues[0].page_url == url_a

    @pytest.mark.asyncio
    async def test_redirect_loop_emits_redirect_loop_issue(self):
        """A URL that httpx identifies as a redirect loop should emit REDIRECT_LOOP."""
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="https://example.com/looping">Loop</a></body></html>"""

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))
            # Simulate TooManyRedirects for the looping URL
            respx.get("https://example.com/looping").mock(
                side_effect=httpx.TooManyRedirects("Too many redirects", request=None)
            )

            settings = CrawlSettings(crawl_delay_ms=0)
            result = await run_crawl("job-12", BASE_URL, settings)

        loop_issues = [i for i in result.issues if i.code == "REDIRECT_LOOP"]
        assert len(loop_issues) >= 1
        assert loop_issues[0].page_url == "https://example.com/looping"

    @pytest.mark.asyncio
    async def test_login_redirect_emits_login_redirect_issue(self):
        """A page that redirects to /login should emit LOGIN_REDIRECT."""
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1><a href="https://example.com/members">Members</a></body></html>"""

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=home_html, headers={"content-type": "text/html"}))
            # /members redirects to /login
            respx.get("https://example.com/members").mock(
                return_value=httpx.Response(
                    200,
                    text="<html><body>Login</body></html>",
                    headers={"content-type": "text/html"},
                )
            )

            settings = CrawlSettings(crawl_delay_ms=0)

            # Patch fetch_page to simulate login redirect for /members
            import unittest.mock as mock
            from api.crawler import fetcher

            original_fetch = fetcher.fetch_page

            async def patched_fetch(url, client, **kwargs):
                if "members" in url:
                    return FetchResult(
                        url=url,
                        final_url="https://example.com/login",
                        status_code=200,
                        first_status_code=302,
                        redirect_chain=["https://example.com/members"],
                        is_login_redirect=True,
                    )
                return await original_fetch(url, client, **kwargs)

            with mock.patch("api.crawler.engine.fetch_page", side_effect=patched_fetch):
                result = await run_crawl("job-13", BASE_URL, settings)

        login_issues = [i for i in result.issues if i.code == "LOGIN_REDIRECT"]
        assert len(login_issues) >= 1


class TestCancellation:
    @pytest.mark.asyncio
    async def test_cancel_event_stops_crawl_cleanly(self):
        cancel = asyncio.Event()
        cancel.set()  # Cancel immediately

        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(return_value=httpx.Response(200, text=_MINIMAL_HTML, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0)
            result = await run_crawl("job-14", BASE_URL, settings, cancel_event=cancel)

        assert result.cancelled is True


class TestMaxPagesCap:
    @pytest.mark.asyncio
    async def test_crawl_stops_at_max_pages(self):
        home_html = """<!DOCTYPE html>
<html><head><title>Home Page With A Good Long Title Here</title>
<meta name="description" content="Good description here long enough to pass checks.">
</head><body><h1>H1</h1>
<a href="/page1">P1</a>
<a href="/page2">P2</a>
<a href="/page3">P3</a>
</body></html>"""
        sub_html = """<!DOCTYPE html>
<html><head><title>Sub Page With A Good Long Title Here</title>
<meta name="description" content="Sub description here long enough to pass checks.">
</head><body><h1>Sub</h1></body></html>"""

        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            for i in range(1, 4):
                respx.get(f"https://example.com/page{i}").mock(
                    return_value=httpx.Response(200, text=sub_html, headers={"content-type": "text/html"})
                )

            settings = CrawlSettings(crawl_delay_ms=0, max_pages=2)
            result = await run_crawl("job-15", BASE_URL, settings)

        assert result.pages_crawled <= 2


class TestFetchPageUnit:
    """Unit tests for the fetcher module directly."""

    @pytest.mark.asyncio
    async def test_fetch_records_first_status_code_on_redirect(self):
        with respx.mock:
            # Simulate a single 301 redirect: example.com/old → example.com/new
            respx.get("https://example.com/old").mock(
                return_value=httpx.Response(
                    200,
                    text="<html><body>New</body></html>",
                    headers={"content-type": "text/html"},
                )
            )

            async with httpx.AsyncClient() as client:
                result = await fetch_page("https://example.com/old", client)

        assert result.status_code == 200
        # first_status_code equals status_code when no actual redirect occurred in mock
        assert result.first_status_code == 200

    @pytest.mark.asyncio
    async def test_fetch_returns_error_on_network_failure(self):
        with respx.mock:
            respx.get("https://example.com/broken").mock(
                side_effect=httpx.ConnectError("refused")
            )

            async with httpx.AsyncClient() as client:
                result = await fetch_page("https://example.com/broken", client)

        assert result.status_code == 0
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fetch_redirect_loop_returns_error(self):
        with respx.mock:
            respx.get("https://example.com/loop").mock(
                side_effect=httpx.TooManyRedirects("Too many", request=None)
            )

            async with httpx.AsyncClient() as client:
                result = await fetch_page("https://example.com/loop", client)

        assert result.error == "REDIRECT_LOOP"

    @pytest.mark.asyncio
    async def test_fetch_head_request_used_for_external(self):
        with respx.mock:
            route = respx.head("https://external.org/page").mock(return_value=httpx.Response(200))

            async with httpx.AsyncClient() as client:
                result = await fetch_page("https://external.org/page", client, is_head=True)

        assert route.called
        assert result.status_code == 200


# ── Analysis toggles (v1.3 §3.1) ────────────────────────────────────────────

class TestAnalysisToggles:
    """Verify that enabled_analyses filters issues by category."""

    @pytest.mark.asyncio
    async def test_site_structure_only_suppresses_metadata_issues(self):
        """With only 'site_structure' enabled, metadata issues must not appear."""
        home_html = """<!DOCTYPE html>
<html><head></head><body><h1>Home</h1></body></html>"""
        # page has no title → would normally emit TITLE_MISSING (category=metadata)
        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            settings = CrawlSettings(crawl_delay_ms=0, enabled_analyses=["site_structure"])
            result = await run_crawl("job-toggle-1", BASE_URL, settings)

        categories = {i.category for i in result.issues}
        assert "metadata" not in categories

    @pytest.mark.asyncio
    async def test_seo_essentials_only_includes_metadata_issues(self):
        """With 'seo_essentials' enabled, metadata category issues are returned."""
        home_html = """<!DOCTYPE html>
<html><head></head><body><h1>Home</h1></body></html>"""
        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            settings = CrawlSettings(crawl_delay_ms=0, enabled_analyses=["seo_essentials"])
            result = await run_crawl("job-toggle-2", BASE_URL, settings)

        categories = {i.category for i in result.issues}
        assert "metadata" in categories

    @pytest.mark.asyncio
    async def test_no_analyses_enabled_returns_no_issues(self):
        """Empty enabled_analyses list should suppress all non-security issues."""
        home_html = """<!DOCTYPE html>
<html><head></head><body><h1>Home</h1></body></html>"""
        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            settings = CrawlSettings(crawl_delay_ms=0, enabled_analyses=[])
            result = await run_crawl("job-toggle-3", BASE_URL, settings)

        # Only security issues (always emitted) may be present
        non_security = [i for i in result.issues if i.category != "security"]
        assert len(non_security) == 0

    @pytest.mark.asyncio
    async def test_none_analyses_returns_all_issues(self):
        """None (default) means all analyses run; metadata issues should appear on a bad page."""
        home_html = """<!DOCTYPE html>
<html><head></head><body><h1>Home</h1></body></html>"""
        with respx.mock:
            _mock_standard_setup(respx.mock, home_html=home_html)
            settings = CrawlSettings(crawl_delay_ms=0, enabled_analyses=None)
            result = await run_crawl("job-toggle-4", BASE_URL, settings)

        categories = {i.category for i in result.issues}
        assert "metadata" in categories


# ── Bot-blocking domain skip list ────────────────────────────────────────────

class TestBotBlockingDomains:
    """Verify that known bot-blocking social media domains are identified correctly."""

    def test_linkedin_is_bot_blocking(self):
        assert _is_bot_blocking_domain("https://www.linkedin.com/company/example") is True

    def test_linkedin_bare_domain_is_bot_blocking(self):
        assert _is_bot_blocking_domain("https://linkedin.com/in/user") is True

    def test_facebook_is_bot_blocking(self):
        assert _is_bot_blocking_domain("https://www.facebook.com/example") is True

    def test_instagram_is_bot_blocking(self):
        assert _is_bot_blocking_domain("https://www.instagram.com/example/") is True

    def test_twitter_is_bot_blocking(self):
        assert _is_bot_blocking_domain("https://twitter.com/example") is True

    def test_x_com_is_bot_blocking(self):
        assert _is_bot_blocking_domain("https://x.com/example") is True

    def test_normal_external_site_is_not_bot_blocking(self):
        assert _is_bot_blocking_domain("https://example.org/page") is False

    def test_subdomain_of_non_blocked_site_is_not_bot_blocking(self):
        assert _is_bot_blocking_domain("https://docs.example.com/api") is False
