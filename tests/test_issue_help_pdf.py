"""The PDF prints the explainer's caveat and examples — the client's copy teaches offline.

Spec:  docs/pending/2026-09-02_phase2-education-layer.md#E2.4
Tests: this file
"""
from __future__ import annotations

import inspect
import io
from datetime import datetime, timezone

from pypdf import PdfReader

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.services.issue_help_data import ISSUE_HELP

BASE = "https://example.com"


async def test_pdf_help_box_carries_good_bad_and_caveat(api_client, auth_headers, test_store):
    job = CrawlJob(job_id="j1", target_url=BASE, status="complete", pages_crawled=1,
                   started_at=datetime.now(timezone.utc))
    await test_store.create_job(job)
    await test_store.save_pages([CrawledPage(job_id="j1", url=f"{BASE}/p", status_code=200,
                                             crawled_at=datetime.now(timezone.utc))])
    await test_store.save_issues([Issue(job_id="j1", page_url=f"{BASE}/p", category="metadata",
                                        severity="warning", issue_code="TITLE_MISSING",
                                        description="x", recommendation="y", impact=6)])
    r = await api_client.get("/api/crawl/j1/export/pdf?include_help=true", headers=auth_headers)
    assert r.status_code == 200
    text = " ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(r.content)).pages)
    flat = " ".join(text.split())
    assert "HOW THIS CAN MISLEAD" in flat and "GOOD vs BAD" in flat
    entry = ISSUE_HELP["TITLE_MISSING"]
    probe = " ".join(entry["how_it_can_mislead"].split(".")[1].split())[:25]
    assert probe in flat, f"caveat text did not reach the PDF: {probe!r}"
    good = " ".join(entry["good_vs_bad"]["good"].split())[:25]
    assert good in flat or good.replace("\u2014", "-") in flat, "the good example did not reach the PDF"
    assert "WHY IT MATTERS TO YOU" in flat and entry["mission_impact"][:20] in flat


def _render(**kw) -> str:
    from api.services.report_generator import TalkingToadReport
    pdf = TalkingToadReport()
    pdf.add_page()
    pdf.draw_help_section("what", "impact", "how", **kw)
    out = pdf.output()
    return " ".join(" ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(out)).pages).split())


def test_help_section_skips_empty_blocks():
    """A legacy entry with no good_vs_bad / mislead must not print empty headings."""
    text = _render(good_vs_bad=None, mislead=None, mission=None)
    assert "WHAT IT IS" in text and "HOW TO FIX" in text
    assert "GOOD vs BAD" not in text and "HOW THIS CAN MISLEAD" not in text and "WHY IT MATTERS" not in text


def test_typography_is_transliterated_not_replaced_with_question_marks():
    """508 em dashes in the authored copy used to print as '?' (sweep finding)."""
    from api.services.report_generator import TalkingToadReport
    assert TalkingToadReport().clean_text("before \u2014 after \u2192 next \u2026") == "before - after -> next ..."
    text = _render(mislead="Evidence tier: Heuristic. The server sends \u2014 nothing \u2014 before scripts.")
    assert "?" not in text.split("HOW THIS CAN MISLEAD", 1)[1].split("HOW TO FIX", 1)[0]
