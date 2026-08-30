"""Reconciliation invariants — quantities derived two independent ways must agree.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF9
Audit: docs/audit/2026-08-30_full-check-audit.md (Part 4)

Why this file exists: the 170-code audit enumerated issue CODES and was blind to
every defect that owns no code. The sitemap `<image:loc>` bug (97 image files
seeded into the page set) belonged to no code, so no code-centric method could
reach it — and the audit had the symptom in hand ("93 of 256 pages are image
uploads") and filed it as an explanation instead of chasing it (P33).

A cross-quantity check is what catches defects living *between* the units. These
invariants would have failed on the pre-fix parser.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
SITEMAP = "https://example.com/sitemap.xml"

# A Yoast-shaped sitemap: two real pages, each carrying nested <image:loc>.
YOAST_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url><loc>https://example.com/</loc>
    <image:image><image:loc>https://example.com/img/one.jpg</image:loc></image:image>
    <image:image><image:loc>https://example.com/img/two.jpg</image:loc></image:image>
  </url>
  <url><loc>https://example.com/about</loc>
    <image:image><image:loc>https://example.com/img/three.png</image:loc></image:image>
  </url>
</urlset>"""

_HTML = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Good Long Title</title>"
         "<meta name='description' content='A description long enough to pass the checks here.'>"
         "</head><body><h1>H</h1><a href='/about'>About</a><p>"
         + " ".join(["word"] * 80) + "</p></body></html>")


def _mock(mock):
    mock.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
    mock.get(SITEMAP).mock(return_value=httpx.Response(
        200, text=YOAST_SITEMAP, headers={"content-type": "application/xml"}))
    for u in (BASE, "https://example.com/about"):
        mock.get(u).mock(return_value=httpx.Response(
            200, text=_HTML, headers={"content-type": "text/html"}))
    # If the crawler wrongly treats image URLs as pages, these answer as images.
    for n in ("one.jpg", "two.jpg", "three.png"):
        mock.get(f"https://example.com/img/{n}").mock(return_value=httpx.Response(
            200, content=b"\xff\xd8\xff", headers={"content-type": "image/jpeg"}))
        mock.head(f"https://example.com/img/{n}").mock(return_value=httpx.Response(
            200, headers={"content-type": "image/jpeg", "content-length": "3"}))


_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp")


class TestCrawlReconciliation:
    @pytest.mark.asyncio
    async def test_af9_image_urls_never_enter_the_page_set(self):
        """The invariant that would have caught the sitemap <image:loc> bug."""
        with respx.mock:
            _mock(respx.mock)
            result = await run_crawl("recon-1", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=50))
        images_as_pages = [p.url for p in result.pages if p.url.lower().endswith(_IMAGE_EXTS)]
        assert images_as_pages == [], (
            f"image files were crawled as pages: {images_as_pages}")

    @pytest.mark.asyncio
    async def test_af9_sitemap_count_matches_the_pages_it_declares(self):
        """The reported sitemap size must be the number of PAGES it declares —
        not pages plus every nested image entry (236 vs 139 on livingsystems.ca)."""
        with respx.mock:
            _mock(respx.mock)
            result = await run_crawl("recon-2", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=50))
        assert result.sitemap_url_count == 2, (
            f"sitemap declares 2 pages, reported {result.sitemap_url_count}")

    @pytest.mark.asyncio
    async def test_af9_page_total_reconciles_with_its_parts(self):
        """pages == html + assets + other. A number that does not reconcile is a
        defect until explained — the audit's own missed lead (P33)."""
        with respx.mock:
            _mock(respx.mock)
            result = await run_crawl("recon-3", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=50))
        pages = result.pages
        html = [p for p in pages if p.title is not None or p.meta_description is not None or p.h1_tags]
        assets = [p for p in pages if p.url.lower().endswith(_IMAGE_EXTS + (".pdf",))]
        other = [p for p in pages if p not in html and p not in assets]
        assert len(html) + len(assets) + len(other) == len(pages)
        assert len(assets) == 0, f"no asset should be a page here: {[p.url for p in assets]}"

    @pytest.mark.asyncio
    async def test_af9_every_crawled_page_is_reachable_or_declared(self):
        """A crawled URL must come from the sitemap or from a discovered link —
        never from nowhere."""
        with respx.mock:
            _mock(respx.mock)
            result = await run_crawl("recon-4", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=50))
        declared = {BASE.rstrip("/"), "https://example.com/about"}
        linked = {l.url.rstrip("/") for p in result.pages for l in (p.links or []) if l.is_internal}
        for p in result.pages:
            u = p.url.rstrip("/")
            assert u in declared or u in linked, f"crawled from nowhere: {p.url}"
