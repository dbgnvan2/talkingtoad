"""
Tests for api/crawler/sitemap.py

All external HTTP calls are mocked — no real network requests.
"""

import gzip
import pytest
import httpx
import respx

from api.crawler.sitemap import fetch_sitemap, fetch_sitemap_recursive


BASE_URL = "https://example.com/"
SITEMAP_URL = "https://example.com/sitemap.xml"


def _urlset(urls: list[str]) -> str:
    locs = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{locs}\n</urlset>'


def _sitemapindex(child_urls: list[str]) -> str:
    sitemaps = "\n".join(f"  <sitemap><loc>{u}</loc></sitemap>" for u in child_urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sitemaps}\n</sitemapindex>'


class TestFetchSitemapStandard:
    @pytest.mark.asyncio
    async def test_standard_sitemap_parsed(self):
        xml = _urlset(["https://example.com/page1", "https://example.com/page2"])
        with respx.mock:
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(200, text=xml))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(BASE_URL, client)

        assert result.found is True
        assert "https://example.com/page1" in result.urls
        assert "https://example.com/page2" in result.urls

    @pytest.mark.asyncio
    async def test_sitemap_url_override_used(self):
        custom_url = "https://example.com/custom-sitemap.xml"
        xml = _urlset(["https://example.com/custom"])
        with respx.mock:
            respx.get(custom_url).mock(return_value=httpx.Response(200, text=xml))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(
                    BASE_URL, client, sitemap_url_override=custom_url
                )

        assert result.found is True
        assert result.source_url == custom_url
        assert "https://example.com/custom" in result.urls

    @pytest.mark.asyncio
    async def test_robots_sitemap_urls_used_as_fallback(self):
        robots_sitemap = "https://example.com/news-sitemap.xml"
        xml = _urlset(["https://example.com/news/1"])
        with respx.mock:
            # /sitemap.xml returns 404, robots sitemap succeeds
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(robots_sitemap).mock(return_value=httpx.Response(200, text=xml))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(
                    BASE_URL, client, robots_sitemap_urls=[robots_sitemap]
                )

        assert result.found is True
        assert "https://example.com/news/1" in result.urls


class TestFetchSitemapGzip:
    @pytest.mark.asyncio
    async def test_gzip_sitemap_decompressed(self):
        xml = _urlset(["https://example.com/gz-page"])
        gz_content = gzip.compress(xml.encode("utf-8"))
        with respx.mock:
            respx.get(SITEMAP_URL).mock(
                return_value=httpx.Response(
                    200,
                    content=gz_content,
                    headers={"content-encoding": "gzip"},
                )
            )
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(BASE_URL, client)

        assert result.found is True
        assert "https://example.com/gz-page" in result.urls

    @pytest.mark.asyncio
    async def test_gzip_detected_without_header(self):
        """Gzip magic bytes are enough — no Content-Encoding header required."""
        xml = _urlset(["https://example.com/gz-page-no-header"])
        gz_content = gzip.compress(xml.encode("utf-8"))
        with respx.mock:
            # No content-encoding header
            respx.get(SITEMAP_URL).mock(
                return_value=httpx.Response(200, content=gz_content)
            )
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(BASE_URL, client)

        assert result.found is True
        assert "https://example.com/gz-page-no-header" in result.urls


class TestFetchSitemapIndex:
    @pytest.mark.asyncio
    async def test_sitemap_index_children_fetched(self):
        child1 = "https://example.com/sitemap-pages.xml"
        child2 = "https://example.com/sitemap-posts.xml"
        index_xml = _sitemapindex([child1, child2])
        child1_xml = _urlset(["https://example.com/about"])
        child2_xml = _urlset(["https://example.com/blog/post-1"])

        with respx.mock:
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(200, text=index_xml))
            respx.get(child1).mock(return_value=httpx.Response(200, text=child1_xml))
            respx.get(child2).mock(return_value=httpx.Response(200, text=child2_xml))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap_recursive(BASE_URL, client)

        assert result.found is True
        assert "https://example.com/about" in result.urls
        assert "https://example.com/blog/post-1" in result.urls

    @pytest.mark.asyncio
    async def test_sitemap_index_partial_child_failure_ok(self):
        """A failing child sitemap doesn't kill the whole result."""
        child1 = "https://example.com/sitemap-ok.xml"
        child2 = "https://example.com/sitemap-broken.xml"
        index_xml = _sitemapindex([child1, child2])
        child1_xml = _urlset(["https://example.com/ok-page"])

        with respx.mock:
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(200, text=index_xml))
            respx.get(child1).mock(return_value=httpx.Response(200, text=child1_xml))
            respx.get(child2).mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap_recursive(BASE_URL, client)

        assert result.found is True
        assert "https://example.com/ok-page" in result.urls


class TestFetchSitemapMissing:
    @pytest.mark.asyncio
    async def test_sitemap_missing_issue_emitted(self):
        with respx.mock:
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(BASE_URL, client)

        assert result.found is False
        assert result.urls == []
        assert result.missing_issue is not None
        assert result.missing_issue["code"] == "SITEMAP_MISSING"
        assert result.missing_issue["severity"] == "info"

    @pytest.mark.asyncio
    async def test_network_error_emits_missing_issue(self):
        with respx.mock:
            respx.get(SITEMAP_URL).mock(side_effect=httpx.ConnectError("refused"))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(BASE_URL, client)

        assert result.found is False
        assert result.missing_issue["code"] == "SITEMAP_MISSING"

    @pytest.mark.asyncio
    async def test_all_candidates_fail_emits_missing(self):
        robots_sitemap = "https://example.com/news-sitemap.xml"
        with respx.mock:
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(robots_sitemap).mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap(
                    BASE_URL, client, robots_sitemap_urls=[robots_sitemap]
                )

        assert result.found is False
        assert result.missing_issue["code"] == "SITEMAP_MISSING"
