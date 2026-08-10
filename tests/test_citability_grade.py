"""E5 — per-page GEO/citability grade (rollup of ai_readiness issues).

Search Everywhere P3. A dedicated 0–100 lens on AI-extractability, derived from
already-emitted ai_readiness issues (no new detection).
"""

from api.services.job_store_base import compute_citability_grade, compute_page_health


def test_e5_1_only_ai_readiness_counts():
    """A metadata/security issue must not move the citability grade — only
    ai_readiness issues do."""
    rows = [
        ("META_DESC_MISSING", 6, "metadata"),
        ("GEO_SUMMARY_BURIED", 2, "ai_readiness"),
    ]
    assert compute_citability_grade(rows) == 100 - 2
    # overall health, by contrast, counts both.
    assert compute_page_health(rows) < 100 - 2


def test_e5_1_monotonic():
    """More ai_readiness issues ⇒ a not-higher grade (monotonicity, P7)."""
    base = [("GEO_SUMMARY_BURIED", 2, "ai_readiness")]
    worse = base + [("CONTENT_THIN", 4, "ai_readiness")]
    assert compute_citability_grade(worse) <= compute_citability_grade(base)
    assert compute_citability_grade(worse) == 100 - (2 + 4)


def test_e5_no_ai_issues_is_100():
    assert compute_citability_grade([("HTTP_PAGE", 6, "security")]) == 100
    assert compute_citability_grade([]) == 100


def test_e5_suppression_not_double_counted():
    """A suppressed child (its cluster parent is present) must not deduct from
    the grade — the rollup reuses the same suppression the health score uses."""
    # RAW_HTML_JS_DEPENDENT suppresses SEMANTIC_DENSITY_LOW (§6.1). With both
    # present, only the parent should count.
    rows = [
        ("RAW_HTML_JS_DEPENDENT", 4, "ai_readiness"),
        ("SEMANTIC_DENSITY_LOW", 1, "ai_readiness"),
    ]
    parent_only = [("RAW_HTML_JS_DEPENDENT", 4, "ai_readiness")]
    assert compute_citability_grade(rows) == compute_citability_grade(parent_only)


def test_e5_floors_at_zero():
    rows = [(f"CODE{i}", 20, "ai_readiness") for i in range(10)]
    assert compute_citability_grade(rows) == 0


# ── CLN5: the ROUTER must drop user-suppressed codes before grading ──────────
# The grade function only applies R4 *cluster* suppression; job-level *user*
# suppression is filtered at the /pages and /page-priority call sites so the
# citability column (and per-page health) reconcile with site health.

async def test_cln5_1_citability_grade_honours_suppressed_codes():
    """CLN5.1 (P8 dirty-state): suppressing an ai_readiness code raises the page's
    citability grade on /page-priority, matching what site health already does."""
    from datetime import datetime, timezone

    from api.models.issue import Issue
    from api.models.job import CrawlJob
    from api.models.page import CrawledPage
    from api.routers.crawl import get_page_priority
    from api.services.sqlite_store import SQLiteJobStore

    async with SQLiteJobStore(db_path=":memory:") as store:
        await store.create_job(CrawlJob(job_id="j1", target_url="https://example.com", status="complete"))
        url = "https://example.com/p"
        await store.save_pages([CrawledPage(
            job_id="j1", url=url, status_code=200, crawled_at=datetime.now(timezone.utc))])
        await store.save_issues([Issue(
            job_id="j1", page_url=url, category="ai_readiness", severity="info",
            issue_code="GEO_SUMMARY_BURIED", description="d", recommendation="r", impact=2)])

        before = await get_page_priority("j1", store=store)
        g_before = before["pages"][0]["citability_grade"]
        assert g_before < 100, "the ai_readiness issue should charge the grade before suppression"

        await store.add_suppressed_code("GEO_SUMMARY_BURIED")

        after = await get_page_priority("j1", store=store)
        g_after = after["pages"][0]["citability_grade"]
        assert g_after == 100, "suppressed code must no longer charge the citability grade"
        assert g_after > g_before
