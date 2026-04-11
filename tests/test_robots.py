"""
Tests for api/crawler/robots.py

All external HTTP calls are mocked — no real network requests.
"""

import pytest
import httpx
import respx

from api.crawler.robots import fetch_robots, RobotsData, CRAWLER_AGENT


ROBOTS_URL = "https://example.com/robots.txt"
BASE_URL = "https://example.com/"


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


class TestFetchRobots:
    @pytest.mark.asyncio
    async def test_disallow_rule_enforced(self):
        robots_txt = f"User-agent: {CRAWLER_AGENT}\nDisallow: /private/\n"
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.is_allowed("https://example.com/private/page") is False
        assert data.is_allowed("https://example.com/public/page") is True

    @pytest.mark.asyncio
    async def test_wildcard_user_agent_fallback(self):
        robots_txt = "User-agent: *\nDisallow: /secret/\n"
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.is_allowed("https://example.com/secret/page") is False
        assert data.is_allowed("https://example.com/public/page") is True

    @pytest.mark.asyncio
    async def test_crawl_delay_extraction(self):
        robots_txt = f"User-agent: {CRAWLER_AGENT}\nCrawl-delay: 2\nDisallow:\n"
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.crawl_delay == 2.0

    @pytest.mark.asyncio
    async def test_crawl_delay_from_wildcard(self):
        robots_txt = "User-agent: *\nCrawl-delay: 3\nDisallow:\n"
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.crawl_delay == 3.0

    @pytest.mark.asyncio
    async def test_sitemap_directive_extraction(self):
        robots_txt = (
            "User-agent: *\nDisallow:\n"
            "Sitemap: https://example.com/sitemap.xml\n"
            "Sitemap: https://example.com/news-sitemap.xml\n"
        )
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert "https://example.com/sitemap.xml" in data.sitemap_urls
        assert "https://example.com/news-sitemap.xml" in data.sitemap_urls

    @pytest.mark.asyncio
    async def test_missing_robots_txt_allows_all(self):
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.is_allowed("https://example.com/any/path") is True
        assert data.crawl_delay is None
        assert data.sitemap_urls == []

    @pytest.mark.asyncio
    async def test_network_error_allows_all(self):
        with respx.mock:
            respx.get(ROBOTS_URL).mock(side_effect=httpx.ConnectError("refused"))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.is_allowed("https://example.com/anything") is True

    @pytest.mark.asyncio
    async def test_specific_agent_overrides_wildcard_crawl_delay(self):
        robots_txt = (
            "User-agent: *\n"
            "Crawl-delay: 5\n"
            "Disallow:\n\n"
            f"User-agent: {CRAWLER_AGENT}\n"
            "Crawl-delay: 1\n"
            "Disallow:\n"
        )
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.crawl_delay == 1.0

    @pytest.mark.asyncio
    async def test_allow_all_when_disallow_empty(self):
        robots_txt = "User-agent: *\nDisallow:\n"
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.is_allowed("https://example.com/any/path") is True

    @pytest.mark.asyncio
    async def test_raw_text_stored(self):
        robots_txt = "User-agent: *\nDisallow: /secret/\n"
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=robots_txt))
            async with httpx.AsyncClient() as client:
                data = await fetch_robots(BASE_URL, client)

        assert data.raw_text is not None
        assert "/secret/" in data.raw_text
