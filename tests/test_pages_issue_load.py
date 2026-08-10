"""CLN7 (P9) — /pages must not reconstruct every Issue in the job to grade the
paginated slice: the citability load is scoped to the returned page URLs.

Spec: docs/pending/2026-08-08_debt-cleanup-batch.md#CLN7
"""

from __future__ import annotations

from datetime import datetime, timezone

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.routers.crawl import get_pages
from api.services.sqlite_store import SQLiteJobStore


async def test_cln7_1_pages_scopes_issue_load_to_returned_urls():
    async with SQLiteJobStore(db_path=":memory:") as store:
        await store.create_job(CrawlJob(
            job_id="j1", target_url="https://example.com", status="complete"))
        shown = "https://example.com/shown"
        other = "https://example.com/other"
        now = datetime.now(timezone.utc)
        await store.save_pages([
            CrawledPage(job_id="j1", url=shown, status_code=200, crawled_at=now),
            CrawledPage(job_id="j1", url=other, status_code=200, crawled_at=now),
        ])
        await store.save_issues([
            Issue(job_id="j1", page_url=shown, category="ai_readiness", severity="info",
                  issue_code="GEO_SUMMARY_BURIED", description="d", recommendation="r", impact=2),
            Issue(job_id="j1", page_url=other, category="ai_readiness", severity="info",
                  issue_code="GEO_SUMMARY_BURIED", description="d", recommendation="r", impact=2),
        ])

        # /pages must NOT fall back to a full get_all_issues load.
        called_all = {"n": 0}
        orig_all = store.get_all_issues

        async def counting_all(job_id):
            called_all["n"] += 1
            return await orig_all(job_id)

        store.get_all_issues = counting_all

        # capture the URL set the scoped query was asked for
        seen_urls: list[list[str]] = []
        orig_scoped = store.get_issues_for_urls

        async def spy_scoped(job_id, urls):
            seen_urls.append(list(urls))
            return await orig_scoped(job_id, urls)

        store.get_issues_for_urls = spy_scoped

        result = await get_pages("j1", page=1, limit=50, min_severity=None, store=store)

        assert called_all["n"] == 0, "/pages must not load ALL issues for citability grading"
        assert seen_urls, "citability grading must use the scoped issue query"
        # only the returned page URLs are queried (both here, since limit=50 > 2)
        assert set(seen_urls[0]) == {shown, other}
        # grading still worked (issue charges the graded page)
        graded = {p["url"]: p["citability_grade"] for p in result["pages"]}
        assert graded[shown] < 100


async def test_cln7_get_issues_for_urls_is_exact_match():
    """CLN7 guard (sweep residual): get_issues_for_urls matches page_url EXACTLY,
    deliberately consistent with the exact `i.page_url = cp.url` count JOIN in
    get_pages_with_issue_counts. /pages feeds it cp.url, so grade and count can't
    disagree; a trailing-slash variant is a DIFFERENT key (do not make it
    slash-tolerant — that would diverge from the count)."""
    async with SQLiteJobStore(db_path=":memory:") as store:
        await store.create_job(CrawlJob(
            job_id="j1", target_url="https://example.com", status="complete"))
        url = "https://example.com/p"
        await store.save_pages([CrawledPage(
            job_id="j1", url=url, status_code=200, crawled_at=datetime.now(timezone.utc))])
        await store.save_issues([Issue(
            job_id="j1", page_url=url, category="ai_readiness", severity="info",
            issue_code="GEO_SUMMARY_BURIED", description="d", recommendation="r", impact=2)])

        assert len(await store.get_issues_for_urls("j1", [url])) == 1        # exact → match
        assert await store.get_issues_for_urls("j1", [url + "/"]) == []      # slash variant → no match
        assert await store.get_issues_for_urls("j1", []) == []              # empty → no query
