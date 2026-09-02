"""Info tiers — API contract (every field the frontend reads, asserted here first).

Spec:    docs/pending/2026-09-01_info-tiers.md §9
Tests:   this file. Unit + scoring: tests/test_info_tiers.py

The test that matters most is ``test_summary_score_follows_info_detail`` next
to ``test_summary_stored_counts_unchanged``: the score MUST move with the
level (the owner's decision) while the stored counts MUST NOT — the pair is
what keeps a higher score from passing as a cleaner site (P31).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage

BASE = "https://example.com"
PAGE = f"{BASE}/p"

# (code, category, severity, impact) — one row per tier plus a warning.
_ROWS = [
    ("H1_MISSING", "heading", "warning", 4),
    ("IMG_ALT_MISSING", "image", "info", 3),        # high / Key
    ("META_DESC_MISSING", "metadata", "info", 2),   # medium / Notable
    ("TITLE_TOO_SHORT", "metadata", "info", 1),     # low
    ("REDIRECT_TRAILING_SLASH", "redirect", "info", 0),  # low
]


async def _job(store, job_id="j1", info_detail="all", *, url=PAGE, started_at=None):
    job = CrawlJob(job_id=job_id, target_url=BASE, status="complete", pages_crawled=1,
                   settings=CrawlSettings(info_detail=info_detail),
                   started_at=started_at or datetime.now(timezone.utc))
    await store.create_job(job)
    await store.save_pages([CrawledPage(job_id=job_id, url=url, status_code=200, title="t",
                                        crawled_at=datetime.now(timezone.utc))])
    await store.save_issues([
        Issue(job_id=job_id, page_url=url, category=cat, severity=sev, issue_code=code,
              description=code, recommendation="fix", impact=imp)
        for code, cat, sev, imp in _ROWS
    ])
    return job


# ── POST /start, GET /{job_id}, rescan ────────────────────────────────────


class TestSettingTravelsWithTheJob:
    async def test_start_accepts_info_detail(self, api_client, auth_headers, test_store):
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/start", headers=auth_headers,
                                      json={"target_url": BASE, "settings": {"info_detail": "notable"}})
        assert r.status_code == 202, r.text
        job = await test_store.get_job(r.json()["job_id"])
        assert job.settings.info_detail == "notable"

    async def test_start_rejects_bad_info_detail(self, api_client, auth_headers):
        r = await api_client.post("/api/crawl/start", headers=auth_headers,
                                  json={"target_url": BASE, "settings": {"info_detail": "some"}})
        assert r.status_code == 422

    async def test_default_is_all(self):
        assert CrawlSettings().info_detail == "all"
        assert CrawlSettings.model_validate({}).info_detail == "all"  # legacy settings blob

    async def test_job_echoes_info_detail(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="key")
        r = await api_client.get("/api/crawl/j1", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["settings"]["info_detail"] == "key"

    async def test_rescan_inherits_info_detail(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="notable")
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/j1/rescan", headers=auth_headers)
        assert r.status_code == 202, r.text
        new = await test_store.get_job(r.json()["job_id"])
        assert new.settings.info_detail == "notable"


# ── GET /summary (via /results) ───────────────────────────────────────────


class TestSummary:
    async def _summary(self, api_client, auth_headers, job_id):
        r = await api_client.get(f"/api/crawl/{job_id}/results", headers=auth_headers)
        assert r.status_code == 200, r.text
        return r.json()["summary"]

    async def test_summary_score_follows_info_detail(self, api_client, auth_headers, test_store):
        """The owner's decision: the level moves the score. Monotone in tightness."""
        scores = {}
        for n, level in enumerate(("all", "notable", "key", "none")):
            await _job(test_store, job_id=f"j{n}", info_detail=level)
            scores[level] = (await self._summary(api_client, auth_headers, f"j{n}"))["health_score"]
        # deductions: all=10, notable=9, key=7, none=4 (the warning stays)
        assert scores == {"all": 90, "notable": 91, "key": 93, "none": 96}, scores

    async def test_summary_stored_counts_unchanged(self, api_client, auth_headers, test_store):
        """by_severity is what was FOUND; the level changes what is COUNTED."""
        await _job(test_store, job_id="j1", info_detail="all")
        await _job(test_store, job_id="j2", info_detail="none")
        s1 = await self._summary(api_client, auth_headers, "j1")
        s2 = await self._summary(api_client, auth_headers, "j2")
        assert s1["by_severity"] == s2["by_severity"] == {"critical": 0, "warning": 1, "info": 4}
        assert s1["total_issues"] == s2["total_issues"] == 5

    async def test_summary_reports_the_tier_breakdown(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="key")
        s = await self._summary(api_client, auth_headers, "j1")
        assert s["info_detail"] == "key"
        assert s["info_by_tier"] == {"high": 1, "medium": 1, "low": 2}
        assert s["info_scored"] == 1
        assert s["info_excluded"] == 3
        assert s["info_scored"] + s["info_excluded"] == s["by_severity"]["info"]

    async def test_agent_health_follows_the_same_level(self, test_store):
        """Both scores move under one rule so they cannot disagree about what counts."""
        for n, level in enumerate(("all", "none")):
            jid = f"a{n}"
            job = CrawlJob(job_id=jid, target_url=BASE, status="complete", pages_crawled=1,
                           settings=CrawlSettings(info_detail=level))
            await test_store.create_job(job)
            await test_store.save_pages([CrawledPage(job_id=jid, url=PAGE, status_code=200,
                                                     crawled_at=datetime.now(timezone.utc))])
            await test_store.save_issues([Issue(
                job_id=jid, page_url=PAGE, category="ai_readiness", severity="info",
                issue_code="FAQ_SCHEMA_MISSING", description="", recommendation="", impact=2)])
        assert (await test_store.get_summary("a0"))["agent_health_score"] == 98
        assert (await test_store.get_summary("a1"))["agent_health_score"] == 100


# ── GET /results, /results/{category} ─────────────────────────────────────


class TestResultsLists:
    async def test_results_has_info_tier_and_filtered_report(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="notable")
        r = await api_client.get("/api/crawl/j1/results", headers=auth_headers)
        body = r.json()
        codes = {i["issue_code"] for i in body["issues"]}
        assert codes == {"H1_MISSING", "IMG_ALT_MISSING", "META_DESC_MISSING"}
        for i in body["issues"]:
            assert "info_tier" in i and "scored" in i
            assert i["scored"] is True
        tiers = {i["issue_code"]: i["info_tier"] for i in body["issues"]}
        assert tiers == {"H1_MISSING": None, "IMG_ALT_MISSING": "high", "META_DESC_MISSING": "medium"}
        assert body["info_filtered"] == {"hidden": 2, "by_tier": {"low": 2}, "info_detail": "notable"}
        assert body["pagination"]["total_issues"] == 3, "the pager must count the served list"

    async def test_hidden_plus_shown_equals_stored_total(self, api_client, auth_headers, test_store):
        """P31: a filter that loses a row fails here."""
        for n, level in enumerate(("all", "notable", "key", "none")):
            await _job(test_store, job_id=f"j{n}", info_detail=level)
            body = (await api_client.get(f"/api/crawl/j{n}/results", headers=auth_headers)).json()
            assert (len(body["issues"]) + body["info_filtered"]["hidden"]
                    + body["filtered"]["hidden"]) == len(_ROWS), level

    async def test_at_all_nothing_changes(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="all")
        body = (await api_client.get("/api/crawl/j1/results", headers=auth_headers)).json()
        assert len(body["issues"]) == 5
        assert body["info_filtered"]["hidden"] == 0
        assert all(i["scored"] for i in body["issues"])

    async def test_reveal_shows_excluded_rows_as_unscored(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="key")
        body = (await api_client.get("/api/crawl/j1/results?info_detail=all",
                                     headers=auth_headers)).json()
        assert len(body["issues"]) == 5
        scored = {i["issue_code"]: i["scored"] for i in body["issues"]}
        assert scored["IMG_ALT_MISSING"] is True and scored["H1_MISSING"] is True
        assert scored["META_DESC_MISSING"] is False and scored["TITLE_TOO_SHORT"] is False
        assert body["info_filtered"]["hidden"] == 0
        # The score is a property of the SCAN: revealing does not move it.
        assert body["summary"]["health_score"] == 93

    async def test_reveal_cannot_tighten(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="all")
        body = (await api_client.get("/api/crawl/j1/results?info_detail=key",
                                     headers=auth_headers)).json()
        assert len(body["issues"]) == 5 and body["info_filtered"]["info_detail"] == "all"
        assert body["summary"]["health_score"] == 90

    async def test_category_results_reveal_only(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="notable")
        r = await api_client.get("/api/crawl/j1/results/metadata", headers=auth_headers)
        body = r.json()
        assert [i["issue_code"] for i in body["issues"]] == ["META_DESC_MISSING"]
        assert body["info_filtered"] == {"hidden": 1, "by_tier": {"low": 1}, "info_detail": "notable"}
        r = await api_client.get("/api/crawl/j1/results/metadata?info_detail=all", headers=auth_headers)
        body = r.json()
        assert {i["issue_code"]: i["scored"] for i in body["issues"]} == {
            "META_DESC_MISSING": True, "TITLE_TOO_SHORT": False}

    async def test_severity_info_view_is_filtered_too(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="key")
        body = (await api_client.get("/api/crawl/j1/results?severity=info",
                                     headers=auth_headers)).json()
        assert [i["issue_code"] for i in body["issues"]] == ["IMG_ALT_MISSING"]
        assert body["info_filtered"]["hidden"] == 3


# ── GET /pages/issues, /pages ─────────────────────────────────────────────


class TestPerPage:
    async def test_page_issues_respect_info_detail(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="notable")
        r = await api_client.get(f"/api/crawl/j1/pages/issues?url={PAGE}", headers=auth_headers)
        body = r.json()
        flat = [i for issues in body["by_category"].values() for i in issues]
        assert {i["issue_code"] for i in flat} == {"H1_MISSING", "IMG_ALT_MISSING", "META_DESC_MISSING"}
        assert all("info_tier" in i and i["scored"] for i in flat)
        assert body["total_issues"] == 3
        assert body["info_filtered"]["hidden"] == 2
        assert "redirect" not in body["by_category"], "an emptied category must not linger"

    async def test_page_issues_reveal(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="notable")
        r = await api_client.get(f"/api/crawl/j1/pages/issues?url={PAGE}&info_detail=all",
                                 headers=auth_headers)
        flat = [i for issues in r.json()["by_category"].values() for i in issues]
        assert len(flat) == 5 and sum(1 for i in flat if not i["scored"]) == 2

    async def test_page_grade_follows_info_detail(self, api_client, auth_headers, test_store):
        """By Page's citability column and the page-priority grade use the level."""
        for n, level in enumerate(("all", "none")):
            jid = f"g{n}"
            job = CrawlJob(job_id=jid, target_url=BASE, status="complete", pages_crawled=1,
                           settings=CrawlSettings(info_detail=level))
            await test_store.create_job(job)
            await test_store.save_pages([CrawledPage(job_id=jid, url=PAGE, status_code=200,
                                                     crawled_at=datetime.now(timezone.utc))])
            await test_store.save_issues([Issue(
                job_id=jid, page_url=PAGE, category="ai_readiness", severity="info",
                issue_code="FAQ_SCHEMA_MISSING", description="", recommendation="", impact=2)])
        g_all = (await api_client.get("/api/crawl/g0/pages", headers=auth_headers)).json()
        g_none = (await api_client.get("/api/crawl/g1/pages", headers=auth_headers)).json()
        assert g_all["pages"][0]["citability_grade"] == 98
        assert g_none["pages"][0]["citability_grade"] == 100
        from api.services.page_priority import build_page_priority
        assert (await build_page_priority(test_store, "g0"))[0]["health_score"] == 98
        assert (await build_page_priority(test_store, "g1"))[0]["health_score"] == 100


# ── Exports ───────────────────────────────────────────────────────────────


class TestExports:
    async def test_csv_export_reflects_the_level(self, api_client, auth_headers, test_store):
        await _job(test_store, info_detail="key")
        r = await api_client.get("/api/crawl/j1/export/csv", headers=auth_headers)
        assert r.status_code == 200
        assert "IMG_ALT_MISSING" in r.text and "TITLE_TOO_SHORT" not in r.text

    async def test_excel_export_caveat_when_info_excluded(self, api_client, auth_headers, test_store):
        from openpyxl import load_workbook
        await _job(test_store, info_detail="notable")
        r = await api_client.get("/api/crawl/j1/export/excel", headers=auth_headers)
        assert r.status_code == 200
        wb = load_workbook(io.BytesIO(r.content))
        cells = [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value]
        body = " ".join(c for c in cells if "Scored at info detail" not in c)
        assert "TITLE_TOO_SHORT" not in body, "the workbook lists a finding the scan excluded"
        assert "META_DESC_MISSING" in body
        caveat = [c for c in cells if "Scored at info detail" in c]
        assert caveat and "2 info notices" in caveat[0] and "health score" in caveat[0]

    async def test_pdf_export_caveat_when_info_excluded(self, api_client, auth_headers, test_store):
        from pypdf import PdfReader
        await _job(test_store, info_detail="notable")
        r = await api_client.get("/api/crawl/j1/export/pdf", headers=auth_headers)
        assert r.status_code == 200
        text = " ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(r.content)).pages)
        assert "Scored at info detail" in text.replace("\n", " ")

    async def test_no_caveat_at_all(self, api_client, auth_headers, test_store):
        from openpyxl import load_workbook
        await _job(test_store, info_detail="all")
        r = await api_client.get("/api/crawl/j1/export/excel", headers=auth_headers)
        wb = load_workbook(io.BytesIO(r.content))
        cells = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value)
        assert "Scored at info detail" not in cells


# ── GET /comparison ───────────────────────────────────────────────────────


class TestComparison:
    async def test_compare_flags_info_detail_mismatch(self, api_client, auth_headers, test_store):
        old = datetime(2026, 1, 1, tzinfo=timezone.utc)
        await _job(test_store, job_id="old", info_detail="all", started_at=old)
        await _job(test_store, job_id="new", info_detail="notable")
        body = (await api_client.get("/api/crawl/new/comparison", headers=auth_headers)).json()
        assert body["comparison_available"] is True
        assert body["comparable"] is False
        assert body["reason"] == "info_detail differs (notable vs all)"
        assert body["current"]["info_detail"] == "notable"
        assert body["previous"]["info_detail"] == "all"
        assert body["delta"]["health_score"] == 1  # still returned, struck through by the UI

    async def test_compare_same_level_is_comparable(self, api_client, auth_headers, test_store):
        old = datetime(2026, 1, 1, tzinfo=timezone.utc)
        await _job(test_store, job_id="old", info_detail="key", started_at=old)
        await _job(test_store, job_id="new", info_detail="key")
        body = (await api_client.get("/api/crawl/new/comparison", headers=auth_headers)).json()
        assert body["comparable"] is True and body["reason"] is None
