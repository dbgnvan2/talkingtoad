"""C1/C2 — a scan with analyses switched off must say so.

Spec:  docs/pending/2026-08-30_analysis-coverage-disclosure.md
Audit: docs/audit/2026-08-30_full-check-audit.md

Two full crawls of livingsystems.ca, 49 minutes apart, same page budget:

    d1394998  enabled_analyses=['link_integrity']    1 warning   355 info
    a87e2d61  enabled_analyses=None (all)          118 warnings 2088 info

Nothing regressed — the first scan simply never looked at eight categories. But
no surface said so, and a scan with categories off renders exactly like a
thorough scan of a healthy site (P31: an absent finding read as a passing one).
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import respx

from api.crawler.engine import (CrawlSettings, _build_analysis_coverage,
                                run_crawl)
from api.services.coverage_notes import analysis_coverage_note

BASE = "https://example.com/"
_PAGE = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Good Long Title</title>"
         "<meta name='description' content='A description long enough to pass the checks here.'>"
         "</head><body><h1>H</h1><p>" + " ".join(["word"] * 80) + "</p></body></html>")


class TestCoverageRecord:
    def test_c1_1_partial_selection_names_what_did_not_run(self):
        cov = _build_analysis_coverage(CrawlSettings(enabled_analyses=["link_integrity"]))
        assert cov["mode"] == "partial"
        assert cov["groups_enabled"] == ["link_integrity"]
        assert "ai_readiness" in cov["groups_disabled"]
        assert "metadata" in cov["categories_unchecked"]

    def test_c1_2_full_scan_reports_all(self):
        """Adversarial: a normal scan must not look like a partial one."""
        cov = _build_analysis_coverage(CrawlSettings())
        assert cov["mode"] == "all"
        assert cov["groups_disabled"] == []
        assert cov["categories_unchecked"] == []

    def test_c1_3_security_is_always_checked(self):
        """security runs regardless of the toggles, so it can never be listed
        as unchecked."""
        cov = _build_analysis_coverage(CrawlSettings(enabled_analyses=["link_integrity"]))
        assert "security" in cov["categories_checked"]
        assert "security" not in cov["categories_unchecked"]

    def test_c1_3b_checked_and_unchecked_partition_every_category(self):
        """Reconciliation: no category may fall between the two lists."""
        from api.crawler.engine import _ANALYSIS_CATEGORY_MAP, _UNGROUPED_CATEGORIES

        every = set(_UNGROUPED_CATEGORIES)
        for cats in _ANALYSIS_CATEGORY_MAP.values():
            every |= cats
        cov = _build_analysis_coverage(CrawlSettings(enabled_analyses=["image"]))
        assert set(cov["categories_checked"]) | set(cov["categories_unchecked"]) == every
        assert not set(cov["categories_checked"]) & set(cov["categories_unchecked"])

    @pytest.mark.asyncio
    async def test_c1_5_coverage_reaches_the_crawl_result(self):
        with respx.mock:
            respx.get("https://example.com/robots.txt").mock(
                return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
            respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=_PAGE, headers={"content-type": "text/html"}))
            result = await run_crawl("cov", BASE, CrawlSettings(
                crawl_delay_ms=0, max_pages=5, enabled_analyses=["link_integrity"]))
        assert result.analysis_coverage["mode"] == "partial"


class TestExportNote:
    def test_c2_4_partial_scan_names_the_unchecked_categories(self):
        note = analysis_coverage_note(SimpleNamespace(analysis_coverage={
            "mode": "partial", "groups_enabled": ["link_integrity"],
            "groups_disabled": ["seo_essentials"],
            "categories_checked": ["broken_link"], "categories_unchecked": ["metadata", "heading"]}))
        assert note and "PARTIAL" in note and "metadata" in note and "heading" in note

    def test_c2_4b_full_scan_says_nothing(self):
        """Adversarial: the note must not become unconditional boilerplate."""
        assert analysis_coverage_note(SimpleNamespace(analysis_coverage={
            "mode": "all", "categories_unchecked": []})) is None

    def test_c2_4c_legacy_job_makes_no_claim(self):
        assert analysis_coverage_note(SimpleNamespace(analysis_coverage=None)) is None

    def test_c2_4d_pdf_and_excel_call_the_note(self):
        import ast
        import inspect
        import textwrap

        from api.services import excel_generator, report_generator

        for mod in (report_generator, excel_generator):
            tree = ast.parse(textwrap.dedent(inspect.getsource(mod)))
            called = {n.func.id for n in ast.walk(tree)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            assert "analysis_coverage_note" in called, f"{mod.__name__} does not call it"
