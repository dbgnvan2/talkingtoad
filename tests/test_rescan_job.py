"""Rescan a past scan from the home page — POST /api/crawl/{job_id}/rescan.

Purpose: re-run a scan with the settings it was ORIGINALLY run with, so the
         re-run is comparable to the scan it is meant to be compared against.
Spec:    docs/pending/2026-09-01_rescan-from-home.md
Tests:   this file

The test that matters most is `test_rescan_of_single_page_job_does_not_launch_a
_full_crawl`. `/scan-page` stored default CrawlSettings until 2026-09-01, so a
one-page audit read back as `single_page=False`. A rescan that believed it would
crawl up to 500 pages of a nonprofit's site from a button on a row that says
"1 page" — and return a perfectly well-formed 202 while doing it. Asserting on
the response body cannot see that, so it is asserted on the launch.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.models.job import ContentScope, CrawlJob, CrawlSettings
from api.routers.crawl import _is_single_page_job

BASE = "https://example.com"


async def _finished_job(store, **kw) -> CrawlJob:
    """A completed crawl job, as the home page's Recent list would show it."""
    job = CrawlJob(target_url=kw.pop("target_url", BASE), status="complete",
                   pages_crawled=kw.pop("pages_crawled", 12), **kw)
    await store.create_job(job)
    return job


@pytest.fixture
def no_crawl():
    """Stop the background crawl from actually running, and record the launch.

    Patches the background entry point, so a call reaching it is a real launch
    of a real crawl — which is exactly what the single-page test must prove did
    NOT happen.
    """
    with patch("api.routers.crawl._run_crawl_background") as m:
        yield m


# ── R1 — settings are reused, the source job is untouched ─────────────────


class TestSettingsAreReused:
    @pytest.mark.asyncio
    async def test_rescan_creates_new_job_reusing_stored_settings(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        original = CrawlSettings(
            max_pages=42, crawl_delay_ms=900, img_size_limit_kb=333,
            enabled_analyses=["seo_essentials", "site_structure"],
            suppress_h1_strings=["Thinking Systems Blog"],
            suppress_banner_h1=False,
        )
        job = await _finished_job(test_store, settings=original)

        r = await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        assert r.status_code == 202, r.text
        new_id = r.json()["job_id"]
        assert new_id != job.job_id, "a rescan is a NEW job, not an overwrite"

        new = await test_store.get_job(new_id)
        assert new.settings.max_pages == 42
        assert new.settings.crawl_delay_ms == 900
        assert new.settings.img_size_limit_kb == 333
        assert new.settings.enabled_analyses == ["seo_essentials", "site_structure"]
        assert new.settings.suppress_h1_strings == ["Thinking Systems Blog"]
        assert new.settings.suppress_banner_h1 is False
        assert new.target_url == job.target_url

    @pytest.mark.asyncio
    async def test_settings_reach_the_engine_not_just_the_record(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """A faithfully stored setting that never reaches the crawler is not a
        reused setting (P25/P27 — asserting construction, not use)."""
        job = await _finished_job(
            test_store, settings=CrawlSettings(max_pages=7, crawl_delay_ms=1500)
        )
        await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)

        assert no_crawl.called
        engine_settings = no_crawl.call_args.args[2]
        assert engine_settings.max_pages == 7
        assert engine_settings.crawl_delay_ms == 1500

    @pytest.mark.asyncio
    async def test_rescan_does_not_mutate_the_source_job(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """The previous scan is what /comparison measures the new one against."""
        job = await _finished_job(test_store, pages_crawled=31)
        before = (await test_store.get_job(job.job_id)).model_dump()

        await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)

        after = (await test_store.get_job(job.job_id)).model_dump()
        assert after == before

    @pytest.mark.asyncio
    async def test_response_names_the_source_job(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        job = await _finished_job(test_store)
        body = (await api_client.post(
            f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)).json()
        assert body["source_job_id"] == job.job_id


# ── R2 — a single-page scan must rescan as a single page ──────────────────


class TestSinglePageProvenance:
    @pytest.mark.asyncio
    async def test_scan_page_records_single_page_in_its_settings(
        self, api_client, auth_headers, test_store
    ):
        """R2.1 — the job must describe how it actually ran.

        The fetch is short-circuited: this is about what `/scan-page` RECORDS at
        job creation, which is the field a later rescan reads back.
        """
        from fastapi.responses import JSONResponse

        with patch("api.routers.crawl._fetch_and_check_page",
                   return_value=JSONResponse(status_code=502, content={})):
            await api_client.post(
                f"/api/crawl/scan-page?url={BASE}/one-page", headers=auth_headers)

        jobs = await test_store.list_recent_jobs(limit=5)
        scanned = next(j for j in jobs if j.target_url.endswith("/one-page"))
        assert scanned.settings.single_page is True
        assert _is_single_page_job(scanned), "and the rescan router must agree"

    @pytest.mark.asyncio
    async def test_rescan_of_single_page_job_does_not_launch_a_full_crawl(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """THE test. A well-formed 202 is what the wrong answer looks like, so
        this asserts no crawl was launched, not what came back."""
        job = await _finished_job(
            test_store, target_url=f"{BASE}/one-page", pages_crawled=1,
            settings=CrawlSettings(single_page=True),
        )
        with patch("api.routers.crawl.scan_single_page") as scan:
            scan.return_value = {"job_id": "new-single"}
            r = await api_client.post(
                f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)

        assert not no_crawl.called, "a one-page audit must not become a site crawl"
        assert scan.called
        assert r.json()["mode"] == "single_page"
        assert r.json()["job_id"] == "new-single"

    @pytest.mark.asyncio
    async def test_rescan_of_legacy_single_page_job_uses_orphan_marker(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """Every single-page audit already in the user's database predates
        R2.1 and reads back as single_page=False."""
        job = await _finished_job(
            test_store, target_url=f"{BASE}/legacy-page", pages_crawled=1,
            settings=CrawlSettings(single_page=False),
        )
        await test_store.update_job(
            job.job_id,
            orphan_detection={"status": "skipped_single_page", "pages_analysed": 1,
                              "pages_out_of_scope": 0, "archives_skipped": False},
        )
        with patch("api.routers.crawl.scan_single_page") as scan:
            scan.return_value = {"job_id": "new-legacy"}
            r = await api_client.post(
                f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)

        assert not no_crawl.called
        assert r.json()["mode"] == "single_page"

    @pytest.mark.asyncio
    async def test_single_page_rescan_is_unauthenticated(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """Called in-process, an omitted `Query(False)` default arrives as a
        Query OBJECT, which is TRUTHY — the rescan would silently sign in to
        WordPress and audit drafts as though they were live."""
        job = await _finished_job(
            test_store, target_url=f"{BASE}/p", pages_crawled=1,
            settings=CrawlSettings(single_page=True),
        )
        with patch("api.routers.crawl.scan_single_page") as scan:
            scan.return_value = {"job_id": "x"}
            await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)

        assert scan.call_args.kwargs["authenticated"] is False

    @pytest.mark.asyncio
    async def test_a_normal_crawl_job_still_rescans_as_a_crawl(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """The other side of R2: don't turn every site crawl into a page scan."""
        job = await _finished_job(test_store, pages_crawled=48)
        r = await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        assert r.json()["mode"] == "crawl"
        assert no_crawl.called


# ── R1 — failure modes ────────────────────────────────────────────────────


class TestFailureModes:
    @pytest.mark.asyncio
    async def test_rescan_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.post("/api/crawl/no-such-job/rescan", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.parametrize("status", ["queued", "running"])
    @pytest.mark.asyncio
    async def test_rescan_running_job_returns_409(
        self, api_client, auth_headers, test_store, no_crawl, status
    ):
        job = CrawlJob(target_url=BASE, status=status)
        await test_store.create_job(job)
        r = await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CRAWL_IN_PROGRESS"
        assert not no_crawl.called

    @pytest.mark.parametrize("status", ["complete", "failed", "cancelled"])
    @pytest.mark.asyncio
    async def test_finished_jobs_of_any_outcome_can_be_rescanned(
        self, api_client, auth_headers, test_store, no_crawl, status
    ):
        """Re-running a failed scan is the recovery, not an error."""
        job = CrawlJob(target_url=BASE, status=status)
        await test_store.create_job(job)
        r = await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        assert r.status_code == 202

    @pytest.mark.asyncio
    async def test_rescan_revalidates_the_stored_url(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """SSRF safety is a property of NOW. A stored URL is caller-supplied
        input that has been sitting in a database; the host may have been
        re-pointed at a private address since it was accepted."""
        job = await _finished_job(test_store)
        with patch("api.routers.crawl.is_ssrf_safe", return_value=False):
            r = await api_client.post(
                f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "BLOCKED_URL"
        assert not no_crawl.called

    @pytest.mark.asyncio
    async def test_partial_scope_that_now_resolves_empty_returns_422(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """A rescan re-resolves its content-type scope against the live site."""
        job = await _finished_job(test_store, settings=CrawlSettings(
            content_scope=ContentScope(mode="types", type_keys=["event"])))
        with patch("api.routers.crawl.resolve_scope_urls", return_value=(set(), [])):
            r = await api_client.post(
                f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "SCOPE_EMPTY"
        assert not no_crawl.called


# ── R1 — the GSC seed carries over ────────────────────────────────────────


class TestPrioritySeedCarriesOver:
    @pytest.mark.asyncio
    async def test_rescan_carries_the_gsc_priority_seed(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        """So a GSC-seeded scan keeps its crawl ordering without the user
        re-uploading the file they no longer have to hand."""
        seed = {"site": "example.com", "used": 2, "total": 2,
                "held_out_offdomain": 0, "held_out_blank": 0,
                "pages": [{"url": f"{BASE}/a", "clicks": 9},
                          {"url": f"{BASE}/b", "clicks": 4}]}
        job = await _finished_job(test_store)
        await test_store.update_job(job.job_id, priority_seed=seed)

        r = await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        new = await test_store.get_job(r.json()["job_id"])
        assert new.priority_seed == seed
        assert any("seeded 2 of 2" in n for n in r.json().get("scope_notes", []))

    @pytest.mark.asyncio
    async def test_seed_urls_reach_the_engine(
        self, api_client, auth_headers, test_store, no_crawl
    ):
        seed = {"site": "example.com", "used": 1, "total": 1,
                "held_out_offdomain": 0, "held_out_blank": 0,
                "pages": [{"url": f"{BASE}/priority", "clicks": 9}]}
        job = await _finished_job(test_store)
        await test_store.update_job(job.job_id, priority_seed=seed)

        await api_client.post(f"/api/crawl/{job.job_id}/rescan", headers=auth_headers)
        engine_settings = no_crawl.call_args.args[2]
        assert engine_settings.priority_urls == [f"{BASE}/priority"]
