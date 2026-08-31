"""IM1 — measure pixel dimensions for the images that warrant it.

Spec:  docs/functional-specification.md (IM1)
Audit: docs/audit/2026-08-30_full-check-audit.md (F5, F15)

HEAD gives size and content-type but never pixel dimensions, so four checks —
IMG_NO_SRCSET, IMG_OVERSCALED, IMG_DUPLICATE_CONTENT, IMG_SLOW_LOAD — had no
data and could not fire in 156 jobs, and every image stored a technical score of
0 (now None). The download helper existed with Pillow extraction and MD5 hashing
and had ZERO callers.

The pass is bounded by a TOTAL byte budget, not by a per-image minimum size.
The minimum-size gate was the first design and it was wrong: measured on
livingsystems.ca, the only two genuinely overscaled images on the site are
30 KB and 9 KB, so a 100 KB gate skipped both and left IMG_OVERSCALED dead on
exactly the cases it exists to catch (P9). Overscaling is a ratio between
intrinsic and display width and has no lower bound in bytes.
"""
from __future__ import annotations

import io
from unittest import mock

import httpx
import pytest
import respx

from api.crawler import engine
from api.crawler.engine import (CrawlSettings, _fetch_image_dimensions,
                                run_crawl)

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
SITEMAP = "https://example.com/sitemap.xml"


def _png(width: int, height: int) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (120, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _pad(data: bytes, min_bytes: int) -> bytes:
    """Pad a real PNG past the measurement threshold without breaking it."""
    return data + b"\x00" * max(0, min_bytes - len(data))


class TestFetchImageDimensions:
    @pytest.mark.asyncio
    async def test_im1_measures_a_real_image(self):
        with respx.mock:
            respx.get(f"{BASE}a.png").mock(return_value=httpx.Response(
                200, content=_png(800, 600), headers={"content-type": "image/png"}))
            async with httpx.AsyncClient() as c:
                url, meta = await _fetch_image_dimensions(f"{BASE}a.png", c)
        assert meta["width"] == 800 and meta["height"] == 600
        assert meta["format"] == "png"
        assert meta["content_hash"] and meta["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_im1_failure_measures_nothing_rather_than_guessing(self):
        """A download error must leave the fields UNMEASURED, never guessed."""
        with respx.mock:
            respx.get(f"{BASE}gone.png").mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as c:
                _, meta = await _fetch_image_dimensions(f"{BASE}gone.png", c)
        assert meta == {}

    @pytest.mark.asyncio
    async def test_im1_undecodable_image_keeps_size_but_no_dimensions(self):
        """An SVG (or anything Pillow cannot decode) yields a partial
        measurement that is honestly partial."""
        with respx.mock:
            respx.get(f"{BASE}a.svg").mock(return_value=httpx.Response(
                200, content=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                headers={"content-type": "image/svg+xml"}))
            async with httpx.AsyncClient() as c:
                _, meta = await _fetch_image_dimensions(f"{BASE}a.svg", c)
        assert meta["file_size_bytes"] > 0 and meta["content_hash"]
        assert "width" not in meta and "height" not in meta


_PAGE = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Good Long Title</title>"
         "<meta name='description' content='A description long enough to pass the checks here.'>"
         "</head><body><h1>H</h1>"
         "<img src='/big.png' alt='A large described photo' width='400'>"
         "<img src='/small.png' alt='A small described photo'>"
         "<p>" + " ".join(["word"] * 80) + "</p></body></html>")


def _mock_site(mock, big=_png(2000, 1500), small=_png(40, 40)):
    big = _pad(big, 300_000)
    mock.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
    mock.get(SITEMAP).mock(return_value=httpx.Response(404))
    mock.get(BASE).mock(return_value=httpx.Response(
        200, text=_PAGE, headers={"content-type": "text/html"}))
    for name, data in (("big.png", big), ("small.png", small)):
        mock.head(f"{BASE}{name}").mock(return_value=httpx.Response(
            200, headers={"content-type": "image/png", "content-length": str(len(data))}))
        mock.get(f"{BASE}{name}").mock(return_value=httpx.Response(
            200, content=data, headers={"content-type": "image/png"}))


class TestCrawlIntegration:
    @pytest.mark.asyncio
    async def test_im1_large_image_is_measured(self):
        with respx.mock:
            _mock_site(respx.mock)
            result = await run_crawl("im1", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=5))
        big = next(i for i in result.images if i.url.endswith("big.png"))
        assert big.width == 2000 and big.height == 1500, "large image was not measured"
        assert big.content_hash, "content hash enables IMG_DUPLICATE_CONTENT"

    @pytest.mark.asyncio
    async def test_im1_small_image_is_measured_too(self):
        """A small image is still measured. This is the regression guard for
        the wrong first design: the two genuinely overscaled images on the
        real site are 30 KB and 9 KB, so a minimum-size gate would leave
        IMG_OVERSCALED dead on precisely the cases it exists to catch."""
        with respx.mock:
            _mock_site(respx.mock)
            result = await run_crawl("im2", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=5))
        small = next(i for i in result.images if i.url.endswith("small.png"))
        assert small.width == 40 and small.height == 40, (
            "a small image must still be measured — size is not a proxy for "
            "whether a dimension check applies")

    @pytest.mark.asyncio
    async def test_im1_total_byte_budget_stops_the_pass(self):
        """The real cost control: the pass stops when the total budget is
        spent, and what it did not reach stays unmeasured, not guessed."""
        with respx.mock, mock.patch.object(engine, "_IMAGE_DIMENSION_TOTAL_BYTES", 1):
            _mock_site(respx.mock)
            result = await run_crawl("im5", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=5))
        assert all(i.width is None for i in result.images), (
            "budget exhausted, yet something was measured")
        assert result.images_measured == 0
        assert result.images_measurable == len(result.images) > 0, (
            "the count of what COULD have been measured must survive, so the "
            "shortfall is disclosable as 'measured N of M'")

    @pytest.mark.asyncio
    async def test_im1_pathological_file_is_skipped_not_budget_eating(self):
        """A single huge file is skipped so it cannot consume the whole
        budget; the rest of the site is still measured."""
        with respx.mock, mock.patch.object(engine, "_IMAGE_DIMENSION_MAX_BYTES", 200_000):
            _mock_site(respx.mock)          # big.png is padded to 300 KB
            result = await run_crawl("im6", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=5))
        big = next(i for i in result.images if i.url.endswith("big.png"))
        small = next(i for i in result.images if i.url.endswith("small.png"))
        assert big.width is None, "a file over the per-image cap must be skipped"
        assert small.width == 40, "the skip must not stop the rest of the pass"

    @pytest.mark.asyncio
    async def test_im1_measurement_counts_are_disclosed(self):
        """measured N of M must be recorded, so no surface can render an
        unmeasured image as a clean one (P31)."""
        with respx.mock:
            _mock_site(respx.mock)
            result = await run_crawl("im7", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=5))
        assert result.images_measurable == 2
        assert result.images_measured == 2

    @pytest.mark.asyncio
    async def test_im1_overscaled_image_now_fires(self):
        """The check this unblocks: 2000px served in a 400px slot."""
        with respx.mock:
            _mock_site(respx.mock)
            result = await run_crawl("im3", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=5))
        codes = {i.code for i in result.issues}
        assert "IMG_OVERSCALED" in codes, f"expected IMG_OVERSCALED, got {sorted(codes)}"
