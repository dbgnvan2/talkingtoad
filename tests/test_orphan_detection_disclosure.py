"""O2 — a suppressed orphan check must never surface as "no orphans found".

Purpose: prove the reason ORPHAN_PAGE did or did not run travels with the job,
         through the store and out of the API, so no surface has to infer
         "clean" from an empty result set.
Spec:    docs/functional-specification.md §4.4 (ORPHAN_PAGE)
Tests:   this file

ORPHAN_PAGE is an absence-proof: it concludes "nothing links here", which is
only decidable after crawling the whole site (P31). When a partial scan, a
page-budget truncation, or a cancellation narrows the crawl, the check is
skipped — and a skipped check returns zero, which the UI would otherwise render
as a green all-clear. That fabricated pass is strictly worse than the false
positives it replaced, so the status is persisted and asserted here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4
import ast
import json
import inspect as _inspect
import textwrap

import pytest

from api.models.job import CrawlJob


async def _job_with(store, orphan_detection):
    job = CrawlJob(
        job_id=str(uuid4()),
        target_url="https://example.com",
        started_at=datetime.now(timezone.utc),
    )
    await store.create_job(job)
    if orphan_detection is not None:
        await store.update_job(job.job_id, orphan_detection=orphan_detection)
    return job.job_id


class TestStoreRoundTrip:
    async def test_o2_orphan_detection_round_trips_through_the_store(self, store):
        payload = {"status": "skipped_partial_scan",
                   "pages_analysed": 37, "pages_out_of_scope": 235}
        job_id = await _job_with(store, payload)
        job = await store.get_job(job_id)
        assert job.orphan_detection == payload

    async def test_o2_legacy_job_without_the_field_reads_back_none(self, store):
        """Audits crawled before this field existed must not read as "complete"
        — an unknown coverage is not a proven-complete one (P1)."""
        job_id = await _job_with(store, None)
        job = await store.get_job(job_id)
        assert job.orphan_detection is None


class TestSummaryContract:
    async def test_o2_1_summary_reports_the_skip_reason(self, store):
        """The frontend reads summary.orphan_detection to decide whether to
        render the all-clear. If this field disappears, the panel silently
        reports "0 orphans" for a scan that never looked."""
        payload = {"status": "skipped_partial_scan",
                   "pages_analysed": 37, "pages_out_of_scope": 235}
        job_id = await _job_with(store, payload)
        summary = await store.get_summary(job_id)
        assert summary["orphan_detection"] == payload

    async def test_o2_2_summary_reports_complete_coverage(self, store):
        payload = {"status": "complete",
                   "pages_analysed": 272, "pages_out_of_scope": 0}
        job_id = await _job_with(store, payload)
        summary = await store.get_summary(job_id)
        assert summary["orphan_detection"]["status"] == "complete"

    async def test_o2_1_endpoint_the_panel_calls_carries_the_field(self, api_client, test_store):
        """Contract test for the exact endpoint getOrphanedPages() hits —
        frontend code does data.summary.orphan_detection."""
        payload = {"status": "skipped_truncated",
                   "pages_analysed": 500, "pages_out_of_scope": 0}
        job_id = await _job_with(test_store, payload)
        r = await api_client.get(
            f"/api/crawl/{job_id}/results/crawlability?limit=5000",
            headers={"Authorization": "Bearer test-token"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "orphan_detection" in body["summary"], \
            "OrphanedPagesPanel reads summary.orphan_detection to avoid a false all-clear"
        assert body["summary"]["orphan_detection"] == payload


class TestOrphanedMediaSibling:
    """P31 "fix the class": find_orphaned_media is the SAME absence-proof over
    the same crawled-page population — "this media item appears on no crawled
    page". It sits behind the adjacent card in the same Orphaned Content
    section, and every row it emits deep-links into the WordPress editor, so a
    false positive here costs the user a real deletion decision.
    """

    async def test_o3_partial_scan_suppresses_orphaned_media(self, api_client, test_store, tmp_path):
        job_id = await _job_with(test_store, {
            "status": "skipped_partial_scan", "pages_analysed": 37,
            "pages_out_of_scope": 235, "archives_skipped": True,
        })
        # Patch the credential paths so this asserts the gate, not whatever
        # wp-credentials.json happens to sit on the machine running the suite.
        missing = tmp_path / "no-such-credentials.json"
        with patch("api.routers.orphaned_media_router._CREDS_PATH", missing), \
             patch("api.routers.fixes_shared._CREDS_PATH", missing):
            r = await api_client.get(
                f"/api/fixes/orphaned-media/{job_id}",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 0
        assert body["coverage"]["status"] == "skipped_partial_scan"

    async def test_o3_suppression_does_not_require_wordpress(self, api_client, test_store, tmp_path):
        """The gate short-circuits BEFORE the credentials check — otherwise a
        partial scan on a site with no wp-credentials.json returns 400 and the
        panel never learns why there is nothing to show. Credentials are patched
        away so this asserts the ordering rather than the developer's machine."""
        job_id = await _job_with(test_store, {
            "status": "skipped_truncated", "pages_analysed": 500,
            "pages_out_of_scope": 120, "archives_skipped": True,
        })
        missing = tmp_path / "no-such-credentials.json"
        with patch("api.routers.orphaned_media_router._CREDS_PATH", missing), \
             patch("api.routers.fixes_shared._CREDS_PATH", missing):
            r = await api_client.get(
                f"/api/fixes/orphaned-media/{job_id}",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 200, (
            "coverage suppression must not depend on WordPress being configured")
        assert r.json()["coverage"]["status"] == "skipped_truncated"

    async def test_o3_complete_crawl_still_reaches_the_wordpress_checks(self, api_client, test_store, tmp_path):
        """Adversarial: the gate must not become an unconditional short-circuit.
        A complete crawl falls through to the real WordPress preconditions."""
        job_id = await _job_with(test_store, {
            "status": "complete", "pages_analysed": 256,
            "pages_out_of_scope": 0, "archives_skipped": True,
        })
        missing = tmp_path / "no-such-credentials.json"
        with patch("api.routers.orphaned_media_router._CREDS_PATH", missing), \
             patch("api.routers.fixes_shared._CREDS_PATH", missing):
            r = await api_client.get(
                f"/api/fixes/orphaned-media/{job_id}",
                headers={"Authorization": "Bearer test-token"},
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"


class TestExportSurfaces:
    """P25 — the PDF and the workbook are the artifacts a client receives. The
    defect was reported FROM the report, so a fix that only reaches two React
    panels has not reached the surface the user was looking at."""

    def test_o4_note_names_the_reason_when_suppressed(self):
        from api.services.coverage_notes import orphan_coverage_note

        job = SimpleNamespace(orphan_detection={
            "status": "skipped_partial_scan", "pages_analysed": 37,
            "pages_out_of_scope": 235, "archives_skipped": True})
        note = orphan_coverage_note(job)
        assert note is not None
        assert "NOT CHECKED" in note
        assert "partial scan" in note
        assert "37" in note and "235" in note

    def test_o4_silent_when_coverage_was_genuinely_total(self):
        """Adversarial: the note must not become unconditional boilerplate."""
        from api.services.coverage_notes import orphan_coverage_note

        job = SimpleNamespace(orphan_detection={
            "status": "complete", "pages_analysed": 42, "pages_out_of_scope": 0,
            "archives_skipped": False, "pages_links_unread": 0})
        assert orphan_coverage_note(job) is None

    def test_o4_complete_still_discloses_its_own_caveats(self):
        from api.services.coverage_notes import orphan_coverage_note

        job = SimpleNamespace(orphan_detection={
            "status": "complete", "pages_analysed": 256, "pages_out_of_scope": 0,
            "archives_skipped": True, "pages_links_unread": 5})
        note = orphan_coverage_note(job)
        assert note is not None and "NOT CHECKED" not in note
        assert "archive" in note.lower() and "5" in note

    def test_o4_legacy_job_makes_no_claim(self):
        from api.services.coverage_notes import orphan_coverage_note

        assert orphan_coverage_note(SimpleNamespace(orphan_detection=None)) is None

    def test_o4_pdf_caveats_section_carries_the_note(self):
        """Binds the note to the PDF: the generator must actually call it."""
        import inspect
        from api.services import report_generator

        src = inspect.getsource(report_generator)
        tree = ast.parse(src)
        called = {
            n.func.id for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "orphan_coverage_note" in called, (
            "report_generator must call orphan_coverage_note — a suppressed "
            "check otherwise reaches the client as zero orphaned pages")

    def test_o4_excel_summary_carries_the_note(self):
        import inspect
        from api.services import excel_generator

        tree = ast.parse(inspect.getsource(excel_generator))
        called = {
            n.func.id for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "orphan_coverage_note" in called
