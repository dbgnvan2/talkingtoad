"""Fields the frontend reads must be asserted in the API response.

Spec:  CLAUDE.md — "CRITICAL: API Contract Tests (Non-Negotiable)". Any endpoint
       called by frontend code must have an integration test asserting every
       field the frontend depends on.
Tests: this file

Two disclosures shipped without one, and both were provably deletable with the
whole suite green:

  health_score_basis   sqlite_store.get_summary -> SummaryPanel.jsx reads
                       `summary?.health_score_basis`. Deleting the payload line
                       left 3425 tests passing; the Health Score silently
                       reverts to a bare number on a partial scan, which is the
                       entire misreading the feature exists to prevent.

  images_measured/     get_image_summary -> ImageAnalysisPanel.jsx. The unit
  images_measurable    test asserted CrawlResult fields, one layer below any
                       surface, so the counters could reach nothing and stay
                       green (P25).

The cross-backend key-set comparison that used to live here is gone with the
Redis store it compared against (2026-08-31, Cycle 3). It earned its keep --
it caught robots_txt/sitemap missing from the Redis summary -- but its value
came entirely from having two implementations to disagree. With one store there
is nothing to compare, and the drift class it policed no longer exists.

What remains asserts the SQLite payload directly: the disclosure fields must be
present and must survive update_job -> get_job, so a counter cannot reach the
summary as a default and read as real (P25/P6).
"""
from __future__ import annotations

import pytest

from api.models.job import CrawlJob
from api.services.sqlite_store import SQLiteJobStore


@pytest.fixture
async def store(tmp_path):
    """Yields, then closes.

    Returning the store without closing it leaves the aiosqlite connection
    thread alive, which keeps the interpreter from exiting: a single-test run
    of this file hung indefinitely. Not using a resource is not releasing it
    (P30) — and an explicit temporary path keeps the suite off the real
    database (P28).
    """
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


class TestSummaryCarriesTheScoreBasis:
    async def test_s1_summary_response_includes_health_score_basis(self, store):
        """SummaryPanel.jsx:33 reads summary.health_score_basis."""
        job = CrawlJob(job_id="j1", target_url="https://example.com/",
                       status="complete")
        await store.create_job(job)
        summary = await store.get_summary("j1")
        assert "health_score_basis" in summary, (
            "SummaryPanel.jsx reads summary.health_score_basis. Without it the "
            "Health Score renders as a bare number for a scan that may have "
            "run one category of thirteen.")
        basis = summary["health_score_basis"]
        for key in ("mode", "categories_scored", "categories_unscored",
                    "comparable"):
            assert key in basis, f"health_score_basis missing {key!r}"

    async def test_s1_basis_survives_a_partial_scan_to_the_response(self, store):
        """The value must be right at the boundary, not merely present."""
        from api.models.job import CrawlSettings
        job = CrawlJob(job_id="j2", target_url="https://example.com/",
                       status="complete",
                       settings=CrawlSettings(enabled_analyses=["link_integrity"]))
        await store.create_job(job)
        basis = (await store.get_summary("j2"))["health_score_basis"]
        assert basis["mode"] == "partial", (
            f"a scan of one analysis group reported mode={basis['mode']!r}")
        assert basis["comparable"] is False, (
            "a partial scan was reported as comparable to a full one")
        assert basis["categories_unscored"], (
            "no category was reported as unscored on a one-group scan")


class TestImageSummaryCarriesTheMeasurementDisclosure:
    async def test_im1_image_summary_includes_counts_with_images_present(self, store):
        """The branch a real crawl takes.

        A job with NO images returns from an early `total_images == 0` guard,
        so a test using one exercises a different branch from production: the
        main return could drop the keys entirely and stay green. This job has
        an image.
        """
        from api.models.image import ImageInfo
        await store.create_job(CrawlJob(job_id="j3",
                                        target_url="https://example.com/"))
        # update_job is the production write path (api/routers/crawl.py) --
        # create_job's INSERT is a fixed column list and silently drops
        # anything not named in it, which is how orphan_detection was lost.
        await store.update_job("j3", status="complete", images_measured=12,
                               images_measurable=30)
        await store.save_images([ImageInfo(
            url="https://example.com/a.png", page_url="https://example.com/",
            job_id="j3", width=800, height=600, file_size_bytes=40_000,
            http_status=200)])
        summary = await store.get_image_summary("j3")
        assert summary["total_images"] > 0, (
            "precondition: this must exercise the WITH-images branch")
        assert summary["images_measured"] == 12
        assert summary["images_measurable"] == 30, (
            "the dimension-pass shortfall does not reach the image summary, so "
            "an image whose pixels were never read renders like a clean one")

    async def test_im1_image_summary_includes_counts_with_no_images(self, store):
        """And the empty branch, which returns early from a separate literal."""
        await store.create_job(CrawlJob(job_id="j3b",
                                        target_url="https://example.com/"))
        await store.update_job("j3b", status="complete", images_measured=0,
                               images_measurable=7)
        summary = await store.get_image_summary("j3b")
        assert summary["total_images"] == 0
        assert summary["images_measurable"] == 7

    async def test_im1_counts_round_trip_through_the_job_store(self, store):
        await store.create_job(CrawlJob(job_id="j4",
                                        target_url="https://example.com/"))
        await store.update_job("j4", images_measured=5, images_measurable=99)
        back = await store.get_job("j4")
        assert back.images_measured == 5 and back.images_measurable == 99, (
            "the counters did not survive update_job -> get_job. A claim that "
            "does not reach the artifact is the orphan_detection bug again (P6)")

