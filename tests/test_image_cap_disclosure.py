"""E1.4 — the per-job image cap must announce what it drops.

Purpose: prove `images_seen_total` counts every distinct image URL found, that
         `images_collected` is what survived the cap, and that a report built on
         a partial sample says so instead of implying full coverage.
Spec:    docs/pending/2026-08-29_E1-lazy-loaded-image-extraction.md#E1.4
Tests:   this file

Post-E1 the cap actually bites on real sites — before E1 the parser saw so few
images on a lazy-loaded site that 150 was never reached. A silent cap plus a
"97%" health score is the exact shape of P9.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE_URL = "https://example.com/"
ROBOTS_URL = "https://example.com/robots.txt"
SITEMAP_URL = "https://example.com/sitemap.xml"
_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"


def _page_with_images(n: int, *, lazy: bool = True, start: int = 0) -> str:
    """A page carrying *n* distinct images, in Smush lazy-load form by default."""
    if lazy:
        tags = "".join(
            f'<img src="data:image/gif;base64,R0lGOD" '
            f'data-src="/img/pic{i}.jpg" alt="Picture {i}">'
            for i in range(start, start + n)
        )
    else:
        tags = "".join(
            f'<img src="/img/pic{i}.jpg" alt="Picture {i}">'
            for i in range(start, start + n)
        )
    return (
        "<!DOCTYPE html><html><head>"
        "<title>Image Page With A Good Long Title Here</title>"
        '<meta name="description" content="A description long enough to pass the checks here.">'
        f"</head><body><h1>Images</h1>{tags}</body></html>"
    )


def _mock(mock: respx.MockRouter, html: str) -> None:
    mock.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
    mock.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
    mock.get(BASE_URL).mock(
        return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
    )
    # Image HEADs — the analyser fetches headers only during a scan.
    mock.head(url__regex=r"https://example\.com/img/pic\d+\.jpg").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "image/jpeg", "content-length": "40000"}
        )
    )
    mock.get(url__regex=r"https://example\.com/img/pic\d+\.jpg").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "image/jpeg", "content-length": "40000"}
        )
    )


class TestCapDisclosure:
    @pytest.mark.asyncio
    async def test_e1_4a_summary_reports_seen_and_collected(self):
        """Under the cap, seen == collected and both are populated."""
        with respx.mock:
            _mock(respx.mock, _page_with_images(5))
            result = await run_crawl(
                "job-cap-1", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1)
            )
        assert result.images_seen_total == 5
        assert result.images_collected <= result.images_seen_total
        assert result.images_seen_total >= result.images_collected

    @pytest.mark.asyncio
    async def test_e1_4a_lazy_images_are_counted_at_all(self):
        """The E1 regression guard at engine level: pre-E1 this was 0."""
        with respx.mock:
            _mock(respx.mock, _page_with_images(5, lazy=True))
            result = await run_crawl(
                "job-cap-lazy", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1)
            )
        assert result.images_seen_total == 5, (
            "every image on this page is a data: placeholder with data-src"
        )

    @pytest.mark.asyncio
    async def test_e1_4b_cap_announced_at_real_scale(self, monkeypatch):
        """Real-scale (P9): with 400 images and a cap of 150, the numbers must
        disagree and both must be reported — a silent 150 reads as 'all of them'."""
        monkeypatch.setenv("TT_IMAGE_URL_CAP_PER_JOB", "150")
        with respx.mock:
            _mock(respx.mock, _page_with_images(400))
            result = await run_crawl(
                "job-cap-2", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1)
            )
        assert result.images_seen_total == 400
        assert result.images_collected <= 150
        assert result.images_seen_total > result.images_collected

    @pytest.mark.asyncio
    async def test_e1_4b_cap_is_configurable(self, monkeypatch):
        """Rule 8: the cap is config, not a magic constant."""
        monkeypatch.setenv("TT_IMAGE_URL_CAP_PER_JOB", "7")
        with respx.mock:
            _mock(respx.mock, _page_with_images(30))
            result = await run_crawl(
                "job-cap-3", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1)
            )
        assert result.images_seen_total == 30
        assert result.images_collected <= 7

    @pytest.mark.asyncio
    async def test_e1_4b_duplicate_urls_counted_once(self):
        """`seen` counts DISTINCT URLs — a logo repeated on every page is one
        image, not one per page, or the disclosure would be nonsense."""
        html = _page_with_images(3) + _page_with_images(3)  # same three URLs twice
        with respx.mock:
            _mock(respx.mock, html)
            result = await run_crawl(
                "job-cap-4", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1)
            )
        assert result.images_seen_total == 3

    @pytest.mark.asyncio
    async def test_e1_4a_no_images_reports_zero_not_none(self):
        """A page with no images reports 0/0 — distinguishable from 'not recorded'."""
        html = (
            "<!DOCTYPE html><html><head><title>No Images Here At All Page</title>"
            '<meta name="description" content="A description long enough to pass the checks.">'
            "</head><body><h1>Text only</h1></body></html>"
        )
        with respx.mock:
            _mock(respx.mock, html)
            result = await run_crawl(
                "job-cap-5", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=1)
            )
        assert result.images_seen_total == 0
        assert result.images_collected == 0
