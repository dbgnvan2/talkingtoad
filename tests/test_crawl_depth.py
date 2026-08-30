"""AF4 — link discovery must be able to fill in an unknown crawl depth.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF4
Audit: docs/audit/2026-08-30_full-check-audit.md (F4)

Sitemap URLs are seeded with depth None. The old guard (`if norm not in
depth_map`) refused to overwrite, so on any site with a sitemap every page kept
depth None — 255 of 256 on livingsystems.ca — and HIGH_CRAWL_DEPTH could not
fire in 156 jobs.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
SITEMAP = "https://example.com/sitemap.xml"


def _html(title: str, links: list[str]) -> str:
    a = "".join(f'<a href="{h}">link</a>' for h in links)
    return (f"<!DOCTYPE html><html lang='en'><head><title>{title} Page With A Long Title</title>"
            "<meta name='description' content='A description long enough to pass the checks here.'>"
            f"</head><body><h1>{title}</h1>{a}<p>" + " ".join(["word"] * 60) + "</p></body></html>")


def _chain_sitemap(paths: list[str]) -> str:
    locs = "".join(f"<url><loc>https://example.com/{p}</loc></url>" for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')


def _mock_chain(mock, depth: int):
    """Homepage -> p1 -> p2 -> ... -> pN, with every page also in the sitemap."""
    names = [f"p{i}" for i in range(1, depth + 1)]
    mock.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
    mock.get(SITEMAP).mock(return_value=httpx.Response(
        200, text=_chain_sitemap([""] + names), headers={"content-type": "application/xml"}))
    mock.get(BASE).mock(return_value=httpx.Response(
        200, text=_html("Home", ["/p1"]), headers={"content-type": "text/html"}))
    for i, n in enumerate(names):
        nxt = [f"/p{i+2}"] if i + 1 < len(names) else []
        mock.get(f"https://example.com/{n}").mock(return_value=httpx.Response(
            200, text=_html(n, nxt), headers={"content-type": "text/html"}))
    return names


class TestCrawlDepth:
    @pytest.mark.asyncio
    async def test_af4_sitemap_seeded_page_gets_depth_from_link_discovery(self):
        with respx.mock:
            _mock_chain(respx.mock, 2)
            result = await run_crawl("job-depth", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        depths = {p.url.rstrip("/"): p.crawl_depth for p in result.pages}
        assert depths["https://example.com"] == 0
        assert depths["https://example.com/p1"] == 1, "sitemap seeding pinned this to None"
        assert depths["https://example.com/p2"] == 2

    @pytest.mark.asyncio
    async def test_af4_shallowest_depth_still_wins(self):
        """Adversarial: a known depth must never be overwritten by a deeper one."""
        with respx.mock:
            respx.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
            respx.get(SITEMAP).mock(return_value=httpx.Response(404))
            # home links BOTH /deep (depth 1) and /mid; /mid also links /deep (would be 2)
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=_html("Home", ["/mid", "/deep"]), headers={"content-type": "text/html"}))
            respx.get("https://example.com/mid").mock(return_value=httpx.Response(
                200, text=_html("Mid", ["/deep"]), headers={"content-type": "text/html"}))
            respx.get("https://example.com/deep").mock(return_value=httpx.Response(
                200, text=_html("Deep", []), headers={"content-type": "text/html"}))
            result = await run_crawl("job-depth-2", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        depths = {p.url.rstrip("/"): p.crawl_depth for p in result.pages}
        assert depths["https://example.com/deep"] == 1, "shallowest-wins regressed"

    @pytest.mark.asyncio
    async def test_af4_deep_page_emits_high_crawl_depth(self):
        """The whole point: the check can fire again."""
        with respx.mock:
            _mock_chain(respx.mock, 6)
            result = await run_crawl("job-depth-3", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        assert any(i.code == "HIGH_CRAWL_DEPTH" for i in result.issues), \
            "a 6-deep chain must produce HIGH_CRAWL_DEPTH"
