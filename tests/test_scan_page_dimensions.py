"""The single-page scan measures images too.

Spec:  docs/functional-specification.md (IM1)#IM1
Tests: this file

IM1 wired the dimension pass into run_crawl only. scan_single_page kept
hardcoding width=None, height=None, file_size_bytes=None, load_time_ms=None,
content_hash=None -- so IMG_OVERSCALED, IMG_NO_SRCSET, IMG_DUPLICATE_CONTENT,
IMG_SLOW_LOAD and IMG_POOR_COMPRESSION were silently dead on that entry point
while working on a full crawl, with nothing saying so. A capability added at
one front end only (P25).
"""
from __future__ import annotations

import io

import httpx
import pytest
import respx
from PIL import Image

from api.models.job import CrawlJob
from api.routers.crawl import scan_single_page
from api.services.sqlite_store import SQLiteJobStore

URL = "https://example.com/page"


def _png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 90, 140)).save(buf, format="PNG")
    return buf.getvalue()


PAGE = ("<!DOCTYPE html><html lang='en'><head>"
        "<title>A Single Page With A Good Long Title</title>"
        "<meta name='description' content='A description long enough to pass "
        "the metadata checks that run on this page without tripping them.'>"
        "</head><body><h1>Heading</h1>"
        "<img src='/hero.png' alt='A described photograph' width='300'>"
        "<p>" + " ".join(["word"] * 120) + "</p></body></html>")


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


async def _scan(store):
    with respx.mock:
        respx.get("https://example.com/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
        respx.get(URL).mock(return_value=httpx.Response(
            200, text=PAGE, headers={"content-type": "text/html"}))
        respx.get("https://example.com/hero.png").mock(return_value=httpx.Response(
            200, content=_png(1200, 800), headers={"content-type": "image/png"}))
        result = await scan_single_page(url=URL, authenticated=False, store=store)
    job_id = result["job_id"] if isinstance(result, dict) else None
    assert job_id, f"scan did not return a job: {result!r}"
    return job_id


class TestSinglePageMeasuresImages:
    async def test_im1_single_page_scan_measures_pixel_dimensions(self, store):
        job_id = await _scan(store)
        images = await store.get_images(job_id)
        hero = next(i for i in images if i.url.endswith("hero.png"))
        assert hero.width == 1200 and hero.height == 800, (
            "the single-page scan did not measure the image, so five image "
            "checks are dead on this entry point while working on a crawl")

    async def test_im1_single_page_scan_records_the_content_hash(self, store):
        job_id = await _scan(store)
        hero = next(i for i in await store.get_images(job_id)
                    if i.url.endswith("hero.png"))
        assert hero.content_hash, "IMG_DUPLICATE_CONTENT needs the hash"
        assert hero.http_status == 200
        assert hero.data_source == "full_fetch"

    async def test_im1_single_page_scan_reports_overscaling(self, store):
        """The check this unblocks: 1200px served into a 300px slot."""
        job_id = await _scan(store)
        codes = {getattr(i, "code", None) or i.issue_code
                 for i in await store.get_all_issues(job_id)}
        assert "IMG_OVERSCALED" in codes, (
            f"IMG_OVERSCALED did not fire on a 1200px image in a 300px slot; "
            f"got {sorted(c for c in codes if c.startswith('IMG_'))}")
