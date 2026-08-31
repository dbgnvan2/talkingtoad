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
        """A 404 measures nothing — but KEEPS its status.

        Returning a bare {} made "the image is 404" and "we never fetched it"
        the same stored value (http_status fell back to 0), so IMG_BROKEN could
        not fire even though the crawl had just observed the 404.
        """
        with respx.mock:
            respx.get(f"{BASE}gone.png").mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as c:
                _, meta = await _fetch_image_dimensions(f"{BASE}gone.png", c)
        assert meta["http_status"] == 404, "the observed status was discarded"
        assert "width" not in meta and "content_hash" not in meta, (
            "nothing may be measured from a failed response")

    @pytest.mark.asyncio
    async def test_im1_unreachable_host_measures_nothing_at_all(self):
        """No response at all is distinct from a response that was an error."""
        with respx.mock:
            respx.get(f"{BASE}dead.png").mock(
                side_effect=httpx.ConnectError("refused"))
            async with httpx.AsyncClient() as c:
                _, meta = await _fetch_image_dimensions(f"{BASE}dead.png", c)
        assert meta == {}, "no server answered, so there is nothing to record"

    @pytest.mark.asyncio
    async def test_im1_soft_404_html_is_not_hashed_as_an_image(self):
        """A site serving an HTML error page for a missing image must not have
        it hashed and sized as the image.

        Ten broken <img> tags returning the same error page would otherwise
        hash identically and fabricate IMG_DUPLICATE_CONTENT on nine of them,
        about images that do not exist — and the HTML's length would feed
        IMG_OVERSIZED and IMG_POOR_COMPRESSION.
        """
        with respx.mock:
            respx.get(f"{BASE}missing.png").mock(return_value=httpx.Response(
                200, text="<html><body>Not found</body></html>",
                headers={"content-type": "text/html; charset=utf-8"}))
            async with httpx.AsyncClient() as c:
                _, meta = await _fetch_image_dimensions(f"{BASE}missing.png", c)
        assert "content_hash" not in meta, (
            "an HTML error page was hashed as image content")
        assert "file_size_bytes" not in meta and "width" not in meta
        assert meta["http_status"] == 200

    @pytest.mark.asyncio
    async def test_im1_body_over_the_cap_is_abandoned_mid_stream(self):
        """The byte budget upstream is computed from the HEAD content-length,
        which the remote host supplies. A host can advertise 1 KB and send far
        more, so the only real ceiling is the one enforced while reading."""
        from api.crawler import engine as eng
        big = b"\x00" * 400_000
        with respx.mock, mock.patch.object(eng, "_IMAGE_DIMENSION_MAX_BYTES", 50_000):
            respx.get(f"{BASE}huge.png").mock(return_value=httpx.Response(
                200, content=big,
                headers={"content-type": "image/png", "content-length": "1024"}))
            async with httpx.AsyncClient() as c:
                _, meta = await eng._fetch_image_dimensions(f"{BASE}huge.png", c)
        assert meta.get("oversize_abandoned") is True, (
            "the body was read past the cap despite a truthful cap and a "
            "lying content-length")
        assert "content_hash" not in meta and "width" not in meta

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


class TestNewlyLiveChecksDoNotMisfire:
    """IM1 woke five checks, not the four the first spec listed.

    IMG_POOR_COMPRESSION was dead alongside the named four because it needs
    width and height. Nothing measured what a 0.5 bytes-per-pixel threshold
    does to a small image, because nobody noticed it had woken up.
    """

    @staticmethod
    def _img(w, h, kb):
        from api.models.image import ImageInfo
        return ImageInfo(url="https://example.com/i.png",
                         page_url="https://example.com/", job_id="j",
                         width=w, height=h, file_size_bytes=int(kb * 1024))

    @pytest.mark.parametrize("w,h,kb", [(16, 16, 1), (32, 32, 2), (64, 64, 4),
                                        (99, 99, 12)])
    def test_im1_small_icons_do_not_report_poor_compression(self, w, h, kb):
        from api.crawler.image_analyzer import DEFAULT_CONFIG, _check_performance
        codes = {i.code for i in _check_performance(
            self._img(w, h, kb), DEFAULT_CONFIG, "j")}
        bpp = (kb * 1024) / (w * h)
        assert "IMG_POOR_COMPRESSION" not in codes, (
            f"a {w}x{h} icon at {kb} KB is {bpp:.1f} bpp and was reported as "
            f"poorly compressed. File overhead dominates below 100x100; the "
            f"ratio says nothing about compression there.")

    def test_im1_a_genuinely_bloated_large_image_still_reports(self):
        """The floor must not disable the check it bounds."""
        from api.crawler.image_analyzer import DEFAULT_CONFIG, _check_performance
        codes = {i.code for i in _check_performance(
            self._img(400, 400, 150), DEFAULT_CONFIG, "j")}
        assert "IMG_POOR_COMPRESSION" in codes, (
            "400x400 at 150 KB is ~0.96 bpp — genuinely bloated, and must "
            "still be caught")

    @pytest.mark.asyncio
    async def test_im1_broken_image_reports_end_to_end_from_a_crawl(self):
        """404 -> ImageInfo.http_status -> IMG_BROKEN, through the engine.

        The first version of this test hand-built ImageInfo(http_status=404)
        and called _check_broken, so it asserted only that _check_broken reads
        its own argument — which was never the bug. Mutating the actual fix
        (dropping http_status from the failed-fetch return) left it green. This
        drives a real crawl whose image 404s.
        """
        page = ("<!DOCTYPE html><html lang='en'><head>"
                "<title>A Page With A Good Long Title</title>"
                "<meta name='description' content='A description long enough "
                "to pass the checks that run here without tripping them.'>"
                "</head><body><h1>H</h1>"
                "<img src='/gone.png' alt='A described photograph'>"
                "<p>" + " ".join(["word"] * 80) + "</p></body></html>")
        with respx.mock:
            respx.get(f"{BASE}robots.txt").mock(return_value=httpx.Response(
                200, text="User-agent: *\nDisallow:\n"))
            respx.get(f"{BASE}sitemap.xml").mock(return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=page, headers={"content-type": "text/html"}))
            respx.head(f"{BASE}gone.png").mock(return_value=httpx.Response(
                200, headers={"content-type": "image/png",
                              "content-length": "5000"}))
            respx.get(f"{BASE}gone.png").mock(return_value=httpx.Response(404))
            result = await run_crawl("brk", BASE,
                                     CrawlSettings(crawl_delay_ms=0, max_pages=3))

        img = next(i for i in result.images if i.url.endswith("gone.png"))
        assert img.http_status == 404, (
            "the crawl observed the 404 and did not record it, so IMG_BROKEN "
            "cannot fire from the scan path")
        assert "IMG_BROKEN" in {i.code for i in result.issues}


class TestDataSourceReflectsWhatWasActuallyDone:
    """data_source was hardcoded "html_only" on every scan row.

    get_image_summary counts images_analyzed as data_source='full_fetch', so
    the panel reported 0 analyzed for a crawl that had downloaded, hashed and
    measured every image. The field claimed less than the code had done.
    """

    @pytest.mark.asyncio
    async def test_im1_a_measured_image_is_recorded_as_fully_fetched(self):
        with respx.mock:
            _mock_site(respx.mock)
            result = await run_crawl("ds1", BASE,
                                     CrawlSettings(crawl_delay_ms=0, max_pages=5))
        big = next(i for i in result.images if i.url.endswith("big.png"))
        assert big.width, "precondition: this image must have been measured"
        assert big.data_source == "full_fetch", (
            f"an image that was downloaded, hashed and measured is recorded as "
            f"{big.data_source!r}, so the summary counts it as not analysed")

    @pytest.mark.asyncio
    async def test_im1_an_unmeasured_image_is_not_claimed_as_fetched(self):
        """The converse: the field must not over-claim either."""
        from api.crawler import engine as eng
        with respx.mock, mock.patch.object(eng, "_IMAGE_DIMENSION_TOTAL_BYTES", 1):
            _mock_site(respx.mock)
            result = await run_crawl("ds2", BASE,
                                     CrawlSettings(crawl_delay_ms=0, max_pages=5))
        assert all(i.data_source != "full_fetch" for i in result.images), (
            "an image the budget never reached is recorded as fully fetched")
