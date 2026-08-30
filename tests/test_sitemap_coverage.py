"""AF10 — say how much of the sitemap was actually fetched.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF10
Audit: docs/audit/2026-08-30_full-check-audit.md

The sitemap is the site's own declaration of what exists. Nothing compared it
against what the crawl fetched, so a declared URL skipped by the WordPress
archive rule, an admin path, robots, or the query-variant cap simply vanished
from the report — the same shape as the orphan defect: the sitemap declares N,
we crawl N-k, and nobody is told which k or why (P31).
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
SITEMAP = "https://example.com/sitemap.xml"

_PAGE = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Good Long Title</title>"
         "<meta name='description' content='A description long enough to pass the checks here.'>"
         "</head><body><h1>H</h1><p>" + " ".join(["word"] * 80) + "</p></body></html>")


def _sitemap(paths):
    locs = "".join(f"<url><loc>https://example.com/{p}</loc></url>" for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')


def _mock(mock, paths, robots="User-agent: *\nDisallow:\n"):
    mock.get(ROBOTS).mock(return_value=httpx.Response(200, text=robots))
    mock.get(SITEMAP).mock(return_value=httpx.Response(
        200, text=_sitemap(paths), headers={"content-type": "application/xml"}))
    for p in paths:
        mock.get(f"https://example.com/{p}").mock(return_value=httpx.Response(
            200, text=_PAGE, headers={"content-type": "text/html"}))
    mock.get(BASE).mock(return_value=httpx.Response(
        200, text=_PAGE, headers={"content-type": "text/html"}))


class TestSitemapCoverage:
    @pytest.mark.asyncio
    async def test_af10_full_coverage_reports_nothing_missing(self):
        with respx.mock:
            _mock(respx.mock, ["", "a", "b"])
            result = await run_crawl("sc-1", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        cov = result.sitemap_coverage
        assert cov["declared"] == 3
        assert cov["not_crawled"] == 0
        assert cov["reasons"] == {}

    @pytest.mark.asyncio
    async def test_af10_wordpress_archive_skip_is_named(self):
        """A declared URL dropped by skip_wp_archives must be reported, with the
        reason — not silently absent."""
        with respx.mock:
            _mock(respx.mock, ["", "a", "category/news"])
            result = await run_crawl("sc-2", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        cov = result.sitemap_coverage
        assert cov["not_crawled"] == 1
        assert list(cov["reasons"].values()) == ["wordpress_archive"]

    @pytest.mark.asyncio
    async def test_af10_robots_blocked_declared_url_is_named(self):
        with respx.mock:
            _mock(respx.mock, ["", "a", "private/x"],
                  robots="User-agent: *\nDisallow: /private/\n")
            result = await run_crawl("sc-3", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        cov = result.sitemap_coverage
        assert cov["not_crawled"] == 1
        assert "robots" in list(cov["reasons"].values())[0]

    @pytest.mark.asyncio
    async def test_af10_no_sitemap_reports_zero_declared(self):
        """Adversarial: a site without a sitemap must not look like a shortfall."""
        with respx.mock:
            respx.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
            respx.get(SITEMAP).mock(return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=_PAGE, headers={"content-type": "text/html"}))
            result = await run_crawl("sc-4", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        cov = result.sitemap_coverage
        assert cov["declared"] == 0 and cov["not_crawled"] == 0


class TestExportSurfaces:
    """AF10 must reach the artifacts a client actually receives (P25)."""

    @staticmethod
    def _job(cov):
        from types import SimpleNamespace
        return SimpleNamespace(sitemap_coverage=cov)

    def test_af10_note_names_the_shortfall_and_the_reason(self):
        from api.services.coverage_notes import sitemap_coverage_note

        note = sitemap_coverage_note(self._job({
            "declared": 140, "crawled": 132, "not_crawled": 8,
            "reasons": {"a": "wordpress_archive", "b": "robots_blocked"}}))
        assert note and "132 of 140" in note and "8 were not" in note
        assert "WordPress archive" in note and "robots.txt" in note

    def test_af10_full_coverage_says_nothing(self):
        """Adversarial: the note must not become unconditional boilerplate."""
        from api.services.coverage_notes import sitemap_coverage_note

        assert sitemap_coverage_note(self._job(
            {"declared": 140, "crawled": 140, "not_crawled": 0, "reasons": {}})) is None

    def test_af10_legacy_job_makes_no_claim(self):
        from api.services.coverage_notes import sitemap_coverage_note

        assert sitemap_coverage_note(self._job(None)) is None

    def test_af10_pdf_and_excel_call_the_note(self):
        """Parsed from the AST, not grepped: a bare substring would also match a
        comment mentioning it (P19 corollary)."""
        import ast
        import inspect
        import textwrap

        from api.services import excel_generator, report_generator

        for mod in (report_generator, excel_generator):
            tree = ast.parse(textwrap.dedent(inspect.getsource(mod)))
            called = {n.func.id for n in ast.walk(tree)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            assert "sitemap_coverage_note" in called, f"{mod.__name__} does not call it"
