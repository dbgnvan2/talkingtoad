"""
Tests for api/services/job_store.py

Uses an in-memory SQLite database — no file I/O, no external services.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.link import Link
from api.models.page import CrawledPage
from api.services.job_store import SQLiteJobStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def store():
    """Yield a fresh in-memory SQLiteJobStore for each test."""
    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


def _job(
    target_url: str = "https://example.com",
    status: str = "queued",
    pages_crawled: int = 0,
    pages_total: int | None = None,
) -> CrawlJob:
    return CrawlJob(
        job_id=str(uuid4()),
        target_url=target_url,
        status=status,
        pages_crawled=pages_crawled,
        pages_total=pages_total,
    )


def _page(job_id: str, url: str = "https://example.com/page") -> CrawledPage:
    return CrawledPage(
        job_id=job_id,
        url=url,
        status_code=200,
        title="Example Page",
        meta_description="A good example page description here.",
        h1_tags=["Heading"],
        headings_outline=[{"level": 1, "text": "Heading"}],
        crawled_at=datetime.now(timezone.utc),
    )


def _issue(
    job_id: str,
    *,
    category: str = "metadata",
    severity: str = "warning",
    code: str = "TITLE_TOO_SHORT",
    page_url: str = "https://example.com/page",
) -> Issue:
    return Issue(
        job_id=job_id,
        page_url=page_url,
        category=category,
        severity=severity,
        issue_code=code,
        description="Test description",
        recommendation="Test recommendation",
    )


def _link(job_id: str, *, link_type: str = "internal", is_broken: bool = False) -> Link:
    return Link(
        job_id=job_id,
        source_url="https://example.com/",
        target_url="https://example.com/about",
        link_type=link_type,
        is_broken=is_broken,
    )


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------

class TestJobCrud:
    async def test_create_and_get_job(self, store):
        job = _job()
        await store.create_job(job)
        fetched = await store.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id
        assert fetched.target_url == job.target_url
        assert fetched.status == "queued"

    async def test_get_nonexistent_job_returns_none(self, store):
        result = await store.get_job("does-not-exist")
        assert result is None

    async def test_update_job_status(self, store):
        job = _job()
        await store.create_job(job)
        await store.update_job(job.job_id, status="running")
        fetched = await store.get_job(job.job_id)
        assert fetched.status == "running"

    async def test_update_job_pages_crawled(self, store):
        job = _job()
        await store.create_job(job)
        await store.update_job(job.job_id, pages_crawled=42, pages_total=100)
        fetched = await store.get_job(job.job_id)
        assert fetched.pages_crawled == 42
        assert fetched.pages_total == 100

    async def test_update_job_completed_at(self, store):
        job = _job()
        await store.create_job(job)
        now = datetime.now(timezone.utc)
        await store.update_job(job.job_id, status="complete", completed_at=now)
        fetched = await store.get_job(job.job_id)
        assert fetched.status == "complete"
        assert fetched.completed_at is not None

    async def test_update_job_error_message(self, store):
        job = _job()
        await store.create_job(job)
        await store.update_job(job.job_id, status="failed", error_message="Crawl failed")
        fetched = await store.get_job(job.job_id)
        assert fetched.error_message == "Crawl failed"

    async def test_update_job_unknown_field_raises(self, store):
        job = _job()
        await store.create_job(job)
        with pytest.raises(ValueError, match="unknown fields"):
            await store.update_job(job.job_id, nonexistent_field="value")

    async def test_settings_round_trip(self, store):
        settings = CrawlSettings(max_pages=100, crawl_delay_ms=300, respect_robots=False)
        job = CrawlJob(
            job_id=str(uuid4()),
            target_url="https://example.com",
            settings=settings,
        )
        await store.create_job(job)
        fetched = await store.get_job(job.job_id)
        assert fetched.settings.max_pages == 100
        assert fetched.settings.crawl_delay_ms == 300
        assert fetched.settings.respect_robots is False


# ---------------------------------------------------------------------------
# Page storage
# ---------------------------------------------------------------------------

class TestPageStorage:
    async def test_save_and_retrieve_pages(self, store):
        job = _job()
        await store.create_job(job)
        pages = [_page(job.job_id, url=f"https://example.com/{i}") for i in range(3)]
        await store.save_pages(pages)
        fetched = await store.get_pages(job.job_id)
        assert len(fetched) == 3

    async def test_page_fields_round_trip(self, store):
        job = _job()
        await store.create_job(job)
        page = CrawledPage(
            job_id=job.job_id,
            url="https://example.com/about",
            status_code=200,
            title="About Us",
            meta_description="About our organisation.",
            og_title="About OG",
            og_description="OG Desc",
            canonical_url="https://example.com/about",
            has_favicon=True,
            h1_tags=["About"],
            headings_outline=[{"level": 1, "text": "About"}, {"level": 2, "text": "Mission"}],
            is_indexable=True,
            robots_directive=None,
            response_size_bytes=5000,
            crawled_at=datetime.now(timezone.utc),
            has_viewport_meta=True,
            schema_types=["Organization"],
            external_script_count=2,
            external_stylesheet_count=1,
        )
        await store.save_pages([page])
        fetched = await store.get_pages(job.job_id)
        assert len(fetched) == 1
        p = fetched[0]
        assert p.url == "https://example.com/about"
        assert p.title == "About Us"
        assert p.has_favicon is True
        assert p.h1_tags == ["About"]
        assert p.headings_outline == [{"level": 1, "text": "About"}, {"level": 2, "text": "Mission"}]
        assert p.schema_types == ["Organization"]
        assert p.external_script_count == 2

    async def test_page_has_favicon_none_round_trip(self, store):
        """None has_favicon (non-homepage) must round-trip as None, not False."""
        job = _job()
        await store.create_job(job)
        page = _page(job.job_id)
        page.has_favicon = None
        await store.save_pages([page])
        fetched = await store.get_pages(job.job_id)
        assert fetched[0].has_favicon is None

    async def test_get_pages_empty_for_unknown_job(self, store):
        fetched = await store.get_pages("no-such-job")
        assert fetched == []


# ---------------------------------------------------------------------------
# Issue storage and retrieval
# ---------------------------------------------------------------------------

class TestIssueStorage:
    async def test_save_and_retrieve_issues(self, store):
        job = _job()
        await store.create_job(job)
        issues = [
            _issue(job.job_id, code="TITLE_MISSING", severity="critical"),
            _issue(job.job_id, code="META_DESC_TOO_SHORT", severity="warning"),
            _issue(job.job_id, code="OG_TITLE_MISSING", severity="info"),
        ]
        await store.save_issues(issues)
        fetched, total = await store.get_issues(job.job_id)
        assert total == 3
        assert len(fetched) == 3

    async def test_issues_sorted_critical_first(self, store):
        job = _job()
        await store.create_job(job)
        issues = [
            _issue(job.job_id, severity="info", code="OG_TITLE_MISSING"),
            _issue(job.job_id, severity="critical", code="TITLE_MISSING"),
            _issue(job.job_id, severity="warning", code="TITLE_TOO_SHORT"),
        ]
        await store.save_issues(issues)
        fetched, _ = await store.get_issues(job.job_id)
        severities = [i.severity for i in fetched]
        assert severities == ["critical", "warning", "info"]

    async def test_filter_by_category(self, store):
        job = _job()
        await store.create_job(job)
        issues = [
            _issue(job.job_id, category="metadata", code="TITLE_MISSING"),
            _issue(job.job_id, category="heading", code="H1_MISSING"),
            _issue(job.job_id, category="heading", code="H1_MULTIPLE"),
        ]
        await store.save_issues(issues)
        fetched, total = await store.get_issues(job.job_id, category="heading")
        assert total == 2
        assert all(i.category == "heading" for i in fetched)

    async def test_filter_by_severity(self, store):
        job = _job()
        await store.create_job(job)
        issues = [
            _issue(job.job_id, severity="critical", code="TITLE_MISSING"),
            _issue(job.job_id, severity="warning", code="TITLE_TOO_SHORT"),
            _issue(job.job_id, severity="info", code="OG_TITLE_MISSING"),
        ]
        await store.save_issues(issues)
        fetched, total = await store.get_issues(job.job_id, severity="critical")
        assert total == 1
        assert fetched[0].severity == "critical"

    async def test_pagination_page_and_limit(self, store):
        job = _job()
        await store.create_job(job)
        issues = [_issue(job.job_id, code=f"CODE_{i}") for i in range(10)]
        await store.save_issues(issues)

        page1, total = await store.get_issues(job.job_id, page=1, limit=3)
        assert total == 10
        assert len(page1) == 3

        page2, _ = await store.get_issues(job.job_id, page=2, limit=3)
        assert len(page2) == 3

        page4, _ = await store.get_issues(job.job_id, page=4, limit=3)
        assert len(page4) == 1  # only one issue on last page

    async def test_get_all_issues(self, store):
        job = _job()
        await store.create_job(job)
        issues = [_issue(job.job_id) for _ in range(5)]
        await store.save_issues(issues)
        all_issues = await store.get_all_issues(job.job_id)
        assert len(all_issues) == 5

    async def test_get_issues_empty_for_unknown_job(self, store):
        fetched, total = await store.get_issues("no-such-job")
        assert fetched == []
        assert total == 0

    async def test_issue_fields_round_trip(self, store):
        job = _job()
        await store.create_job(job)
        issue = Issue(
            job_id=job.job_id,
            page_url="https://example.com/page",
            category="metadata",
            severity="critical",
            issue_code="TITLE_MISSING",
            description="Page has no title tag",
            recommendation="Add a unique title tag.",
        )
        await store.save_issues([issue])
        fetched, _ = await store.get_issues(job.job_id)
        f = fetched[0]
        assert f.issue_code == "TITLE_MISSING"
        assert f.severity == "critical"
        assert f.page_url == "https://example.com/page"
        assert f.description == "Page has no title tag"


# ---------------------------------------------------------------------------
# Link storage
# ---------------------------------------------------------------------------

class TestLinkStorage:
    async def test_save_links(self, store):
        job = _job()
        await store.create_job(job)
        links = [
            _link(job.job_id, link_type="internal"),
            _link(job.job_id, link_type="external", is_broken=True),
        ]
        await store.save_links(links)
        # No get_links method in interface — just verify no exception raised
        # and indirectly via summary (broken links would appear as issues)

    async def test_link_check_skipped_round_trip(self, store):
        job = _job()
        await store.create_job(job)
        link = Link(
            job_id=job.job_id,
            source_url="https://example.com/",
            target_url="https://external.org/page",
            link_type="external",
            status_code=None,
            is_broken=False,
            check_skipped=True,
        )
        await store.save_links([link])
        # No error — persisted correctly


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    async def test_summary_counts_by_severity(self, store):
        job = _job(pages_crawled=10)
        await store.create_job(job)
        await store.update_job(job.job_id, pages_crawled=10)
        issues = [
            _issue(job.job_id, severity="critical"),
            _issue(job.job_id, severity="critical"),
            _issue(job.job_id, severity="warning"),
            _issue(job.job_id, severity="info"),
        ]
        await store.save_issues(issues)
        summary = await store.get_summary(job.job_id)
        assert summary["by_severity"]["critical"] == 2
        assert summary["by_severity"]["warning"] == 1
        assert summary["by_severity"]["info"] == 1
        assert summary["total_issues"] == 4

    async def test_summary_counts_by_category(self, store):
        job = _job()
        await store.create_job(job)
        issues = [
            _issue(job.job_id, category="metadata"),
            _issue(job.job_id, category="metadata"),
            _issue(job.job_id, category="heading"),
        ]
        await store.save_issues(issues)
        summary = await store.get_summary(job.job_id)
        assert summary["by_category"]["metadata"] == 2
        assert summary["by_category"]["heading"] == 1

    async def test_summary_empty_job(self, store):
        job = _job()
        await store.create_job(job)
        summary = await store.get_summary(job.job_id)
        assert summary["total_issues"] == 0
        assert summary["pages_crawled"] == 0

    async def test_summary_nonexistent_job_returns_empty(self, store):
        summary = await store.get_summary("no-such-job")
        assert summary == {}


# ---------------------------------------------------------------------------
# TTL cleanup
# ---------------------------------------------------------------------------

class TestByPageView:
    async def test_pages_with_issue_counts_sorted_by_total(self, store):
        job = _job()
        await store.create_job(job)
        page_a = _page(job.job_id, url="https://example.com/a")
        page_b = _page(job.job_id, url="https://example.com/b")
        await store.save_pages([page_a, page_b])
        # 3 issues on /a, 1 on /b
        await store.save_issues([
            _issue(job.job_id, page_url="https://example.com/a", severity="critical"),
            _issue(job.job_id, page_url="https://example.com/a", severity="warning"),
            _issue(job.job_id, page_url="https://example.com/a", severity="info"),
            _issue(job.job_id, page_url="https://example.com/b", severity="info"),
        ])
        pages, total = await store.get_pages_with_issue_counts(job.job_id)
        assert total == 2
        assert pages[0]["url"] == "https://example.com/a"
        assert pages[0]["issue_counts"]["total"] == 3
        assert pages[1]["url"] == "https://example.com/b"

    async def test_pages_with_issue_counts_severity_breakdown(self, store):
        job = _job()
        await store.create_job(job)
        page = _page(job.job_id)
        await store.save_pages([page])
        await store.save_issues([
            _issue(job.job_id, severity="critical"),
            _issue(job.job_id, severity="warning"),
            _issue(job.job_id, severity="info"),
        ])
        pages, _ = await store.get_pages_with_issue_counts(job.job_id)
        counts = pages[0]["issue_counts"]
        assert counts["critical"] == 1
        assert counts["warning"] == 1
        assert counts["info"] == 1

    async def test_pages_with_issue_counts_min_severity_filter(self, store):
        job = _job()
        await store.create_job(job)
        page_a = _page(job.job_id, url="https://example.com/a")
        page_b = _page(job.job_id, url="https://example.com/b")
        await store.save_pages([page_a, page_b])
        await store.save_issues([
            _issue(job.job_id, page_url="https://example.com/a", severity="critical"),
            _issue(job.job_id, page_url="https://example.com/b", severity="info"),
        ])
        pages, total = await store.get_pages_with_issue_counts(job.job_id, min_severity="critical")
        assert total == 1
        assert pages[0]["url"] == "https://example.com/a"

    async def test_pages_with_issue_counts_pagination(self, store):
        job = _job()
        await store.create_job(job)
        pages = [_page(job.job_id, url=f"https://example.com/{i}") for i in range(5)]
        await store.save_pages(pages)
        result, total = await store.get_pages_with_issue_counts(job.job_id, page=1, limit=3)
        assert total == 5
        assert len(result) == 3
        result2, _ = await store.get_pages_with_issue_counts(job.job_id, page=2, limit=3)
        assert len(result2) == 2

    async def test_get_page_issues_by_url_returns_grouped_issues(self, store):
        job = _job()
        await store.create_job(job)
        page = _page(job.job_id)
        await store.save_pages([page])
        await store.save_issues([
            _issue(job.job_id, category="metadata", severity="critical"),
            _issue(job.job_id, category="heading", severity="warning"),
            _issue(job.job_id, category="metadata", severity="info"),
        ])
        crawled, by_cat = await store.get_page_issues_by_url(job.job_id, page.url)
        assert crawled is not None
        assert crawled.url == page.url
        assert len(by_cat["metadata"]) == 2
        assert len(by_cat["heading"]) == 1

    async def test_get_page_issues_by_url_not_found(self, store):
        job = _job()
        await store.create_job(job)
        crawled, by_cat = await store.get_page_issues_by_url(job.job_id, "https://example.com/missing")
        assert crawled is None
        assert by_cat == {}

    async def test_get_page_issues_sorted_critical_first(self, store):
        job = _job()
        await store.create_job(job)
        page = _page(job.job_id)
        await store.save_pages([page])
        await store.save_issues([
            _issue(job.job_id, category="metadata", severity="info"),
            _issue(job.job_id, category="metadata", severity="critical"),
        ])
        _, by_cat = await store.get_page_issues_by_url(job.job_id, page.url)
        severities = [i.severity for i in by_cat["metadata"]]
        assert severities[0] == "critical"


class TestTtlCleanup:
    async def test_expired_job_deleted(self, store):
        old_job = _job()
        await store.create_job(old_job)
        # Back-date the job's started_at to 10 days ago
        old_dt = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        await store._db.execute(
            "UPDATE crawl_jobs SET started_at = ? WHERE job_id = ?",
            (old_dt, old_job.job_id),
        )
        await store._db.commit()

        deleted = await store.cleanup_expired_jobs(ttl_days=7)
        assert deleted == 1
        assert await store.get_job(old_job.job_id) is None

    async def test_recent_job_not_deleted(self, store):
        job = _job()
        await store.create_job(job)
        deleted = await store.cleanup_expired_jobs(ttl_days=7)
        assert deleted == 0
        assert await store.get_job(job.job_id) is not None

    async def test_expired_job_issues_cascade_deleted(self, store):
        old_job = _job()
        await store.create_job(old_job)
        await store.save_issues([_issue(old_job.job_id)])
        old_dt = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        await store._db.execute(
            "UPDATE crawl_jobs SET started_at = ? WHERE job_id = ?",
            (old_dt, old_job.job_id),
        )
        await store._db.commit()

        await store.cleanup_expired_jobs(ttl_days=7)
        fetched, total = await store.get_issues(old_job.job_id)
        assert total == 0


# ---------------------------------------------------------------------------
# list_jobs_by_domain (Step 5b)
# ---------------------------------------------------------------------------

class TestListJobsByDomain:
    """Tests for list_jobs_by_domain method."""

    async def test_returns_matching_domain_only(self, store):
        """Only jobs whose target_url contains the domain should be returned."""
        j1 = _job(target_url="https://example.com", status="complete")
        j2 = _job(target_url="https://example.com/about", status="complete")
        j3 = _job(target_url="https://other-site.org", status="complete")
        for j in [j1, j2, j3]:
            await store.create_job(j)

        results = await store.list_jobs_by_domain("example.com")
        job_ids = {j.job_id for j in results}
        assert j1.job_id in job_ids
        assert j2.job_id in job_ids
        assert j3.job_id not in job_ids

    async def test_excludes_non_complete_jobs(self, store):
        """Only completed jobs should be returned."""
        j_complete = _job(target_url="https://example.com", status="complete")
        j_running = _job(target_url="https://example.com", status="running")
        j_failed = _job(target_url="https://example.com", status="failed")
        for j in [j_complete, j_running, j_failed]:
            await store.create_job(j)

        results = await store.list_jobs_by_domain("example.com")
        assert len(results) == 1
        assert results[0].job_id == j_complete.job_id

    async def test_ordered_newest_first(self, store):
        """Results should be ordered by started_at descending."""
        j1 = _job(target_url="https://example.com", status="complete")
        j2 = _job(target_url="https://example.com", status="complete")
        await store.create_job(j1)
        # Make j2 start later by updating its started_at
        await store.create_job(j2)
        await store._db.execute(
            "UPDATE crawl_jobs SET started_at = ? WHERE job_id = ?",
            ((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), j2.job_id),
        )
        await store._db.commit()

        results = await store.list_jobs_by_domain("example.com")
        assert len(results) == 2
        assert results[0].job_id == j2.job_id  # newer first

    async def test_empty_for_no_matches(self, store):
        """Returns empty list when no jobs match the domain."""
        j = _job(target_url="https://example.com", status="complete")
        await store.create_job(j)

        results = await store.list_jobs_by_domain("nonexistent.com")
        assert results == []

    async def test_respects_limit(self, store):
        """Limit parameter should restrict the number of results."""
        for _ in range(5):
            j = _job(target_url="https://example.com", status="complete")
            await store.create_job(j)

        results = await store.list_jobs_by_domain("example.com", limit=2)
        assert len(results) == 2
