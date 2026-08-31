"""POST /images/fetch checks the redirect hops, not only the URL it was given.

Spec:  CLAUDE.md, Security Defaults — blocked at start AND on every redirect hop.
Tests: this file

fetch_image_details already refuses an internal image_url outright, and says so
in a comment naming AWS metadata as the risk. But it then fetched with a client
that follows redirects and checks nothing, so a public host answering 302 to
169.254.169.254 was followed — the exact pivot the entry check was written to
stop, one hop later. image_url is a request parameter, so this is reachable by
any authenticated caller.

The internal target is mocked to return a real image. Asserting "no dimensions
came back" would pass whether the guard refused the request or the connection
merely failed; the assertion is that the request was never made.
"""
from __future__ import annotations

import io

import httpx
import pytest
import respx
from PIL import Image

from api.models.image import ImageInfo
from api.routers.crawl import fetch_image_details

PUBLIC = "https://example.com/innocent.png"
INTERNAL = "http://169.254.169.254/latest/meta-data/iam/security-credentials/x.png"


def _png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


class _Store:
    """Minimal store: the endpoint needs a job and an image before it fetches."""

    async def get_job(self, job_id):
        return object()

    async def get_image_by_url(self, job_id, url):
        return ImageInfo(url=url, page_url="https://example.com/", job_id=job_id)

    async def update_image(self, *a, **kw):
        return None

    async def save_image(self, *a, **kw):
        return None

    async def save_images(self, *a, **kw):
        return None


class TestFetchImageDetailsHops:
    @pytest.mark.asyncio
    async def test_ssrf_redirect_to_metadata_service_is_not_followed(self):
        with respx.mock:
            respx.get(PUBLIC).mock(return_value=httpx.Response(
                302, headers={"location": INTERNAL}))
            inner = respx.get(INTERNAL).mock(return_value=httpx.Response(
                200, content=_png(64, 64),
                headers={"content-type": "image/png"}))
            await fetch_image_details(
                job_id="j", image_url=PUBLIC, fetch_wp_metadata=False,
                store=_Store())          # type: ignore[arg-type]
        assert not inner.called, (
            "the endpoint followed a redirect to the cloud metadata service. "
            "The is_ssrf_safe check on image_url does not cover redirect hops.")

    @pytest.mark.asyncio
    async def test_ssrf_a_public_image_is_still_measured(self):
        """The guard must not break the endpoint it protects."""
        with respx.mock:
            respx.get(PUBLIC).mock(return_value=httpx.Response(
                200, content=_png(120, 90),
                headers={"content-type": "image/png"}))
            result = await fetch_image_details(
                job_id="j", image_url=PUBLIC, fetch_wp_metadata=False,
                store=_Store())          # type: ignore[arg-type]
        img = result["image"] if isinstance(result, dict) else None
        assert img is not None, f"unexpected response: {result!r}"
        assert img["width"] == 120 and img["height"] == 90
