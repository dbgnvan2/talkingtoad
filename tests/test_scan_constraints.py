"""The four architecture constraints that sat as `pass`-only placeholders for a year.

Spec:  docs/pending/2026-09-02_phase3-happy-path.md#R3.5
Tests: this file

Each was a real rule of the 3-level design (Scan = HTML + HEAD; Fetch = WP API
and downloads, user-triggered; AI = user-triggered) with a green placeholder
where the test should have been. The placeholders were deleted 2026-09-02;
these are the tests.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

import api.crawler.engine as engine
from api.crawler.engine import CrawlSettings, run_crawl

BASE_URL = "https://example.com/"
ROBOTS_URL = "https://example.com/robots.txt"
SITEMAP_URL = "https://example.com/sitemap.xml"
_ALLOW_ALL = "User-agent: *\nAllow: /\n"


def _page(n_images: int) -> str:
    tags = "".join(f'<img src="/img/pic{i}.jpg" alt="Picture {i}">' for i in range(n_images))
    return ("<!DOCTYPE html><html><head><title>Image Page With A Good Long Title Here</title>"
            '<meta name="description" content="A description long enough to pass the checks here.">'
            f"</head><body><h1>Images</h1><p>{'word ' * 60}</p>{tags}</body></html>")


def _site(mock: respx.MockRouter, html: str, *, llms_status: int = 404, llms_body: str = ""):
    mock.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL))
    mock.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
    mock.get("https://example.com/llms.txt").mock(return_value=httpx.Response(llms_status, text=llms_body))
    mock.get("https://example.com/llms-full.txt").mock(return_value=httpx.Response(404))
    mock.get(BASE_URL).mock(return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"}))
    heads = mock.head(url__regex=r"https://example\.com/img/pic\d+\.jpg").mock(
        return_value=httpx.Response(200, headers={"content-type": "image/jpeg", "content-length": "40000"}))
    gets = mock.get(url__regex=r"https://example\.com/img/pic\d+\.jpg").mock(
        return_value=httpx.Response(200, headers={"content-type": "image/jpeg", "content-length": "40000"},
                                    content=b"\xff\xd8" + b"0" * 100))
    return heads, gets


class TestImageScanIsHeadFirstAndBounded:
    @pytest.mark.asyncio
    async def test_every_image_is_headed_before_any_is_downloaded(self):
        with respx.mock:
            heads, gets = _site(respx.mock, _page(4))
            await run_crawl("job-head", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1))
            # Read the call log INSIDE the block: leaving it resets respx.
            calls = [(c.request.method, str(c.request.url)) for c in respx.calls if "/img/" in str(c.request.url)]
        assert heads.call_count == 4, "the scan must HEAD every image for size and type"
        assert len(calls) >= 4, calls
        assert all(m == "HEAD" for m, _ in calls[:4]), f"HEADs come first; the bounded body pass follows: {calls}"

    @pytest.mark.asyncio
    async def test_with_the_dimension_cap_at_zero_no_image_body_is_fetched(self, monkeypatch):
        """The body pass is a bounded extra, not the scan: cap it and only HEADs remain."""
        monkeypatch.setattr(engine, "_IMAGE_DIMENSION_MAX_COUNT", 0)
        with respx.mock:
            heads, gets = _site(respx.mock, _page(3))
            await run_crawl("job-cap0", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1))
        assert heads.call_count == 3
        assert gets.call_count == 0, "with the cap at 0 the scan must not GET a single image"


class TestScanNeverTriggersLevelTwo:
    @pytest.mark.asyncio
    async def test_no_image_processing_or_wp_client_during_a_scan(self):
        """Level 2 (optimise / WP) is user-triggered. A scan must not reach it."""
        with respx.mock, \
                patch("api.services.wp_image_fixer.optimize_existing_image", new_callable=AsyncMock) as opt, \
                patch("api.services.wp_image_fixer.update_image_metadata", new_callable=AsyncMock) as meta:
            _site(respx.mock, _page(2))
            # Any WordPress REST or XML-RPC request during a scan is the regression.
            wp = respx.mock.route(url__regex=r".*/(wp-json|xmlrpc\.php).*").mock(return_value=httpx.Response(200, json={}))
            await run_crawl("job-l2", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1))
        assert wp.call_count == 0, "a scan reached the WordPress API"
        opt.assert_not_called()
        meta.assert_not_called()


class TestGeoRefusesWithoutConfiguration:
    async def test_geo_faq_names_configuration_and_makes_no_ai_call(self, api_client, auth_headers):
        with patch("api.services.geo_faq.generate_faq_block", new_callable=AsyncMock, create=True) as gen:
            r = await api_client.post("/api/ai/geo-faq", headers=auth_headers,
                                      json={"domain": "unconfigured.org", "page_url": "https://unconfigured.org/x",
                                            "page_content": "some text"})
        assert r.status_code == 422, r.text
        assert "configur" in r.text.lower()
        gen.assert_not_called()

    async def test_entity_schema_names_configuration(self, api_client, auth_headers):
        r = await api_client.post("/api/geo/entity-schema", headers=auth_headers,
                                  json={"domain": "unconfigured.org"})
        assert r.status_code == 422, r.text
        assert "configur" in r.text.lower()


class TestLlmsTxtMissingEndToEnd:
    @pytest.mark.asyncio
    async def test_missing_file_emits_the_code_once_at_the_start_url(self):
        with respx.mock:
            _site(respx.mock, _page(0), llms_status=404)
            res = await run_crawl("job-llms", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1))
        hits = [i for i in res.issues if i.code == "LLMS_TXT_MISSING"]
        assert len(hits) == 1
        assert hits[0].page_url.rstrip("/") == BASE_URL.rstrip("/")
        assert hits[0].extra["expected_url"] == "https://example.com/llms.txt"
        assert hits[0].extra["status_code"] == 404

    @pytest.mark.asyncio
    async def test_a_valid_file_does_not_emit_it(self):
        with respx.mock:
            _site(respx.mock, _page(0), llms_status=200, llms_body="# Example Org\n\n> A charity.\n\n## Docs\n- [About](https://example.com/about)\n")
            res = await run_crawl("job-llms-ok", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1))
        assert not [i for i in res.issues if i.code in ("LLMS_TXT_MISSING", "LLMS_TXT_INVALID")]
