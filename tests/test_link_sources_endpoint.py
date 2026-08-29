"""The "Show Source Pages" control on the Broken Links panel.

Purpose: pin the response contract the frontend reads, and the trailing-slash
         tolerance of the lookup behind it.
Spec:    docs/functional-specification.md#415-crawl-fidelity-fixes-and-new-checks
Tests:   this file (+ frontend: CategoryPanelSources.test.jsx)

Two independent faults made the button do nothing on livingsystems.ca:

1. The endpoint returns an envelope ``{target_url, sources, count}`` and the
   frontend assigned the whole object to its `sources` state, so `.length` was
   `undefined` and `.map` threw — the panel expanded onto nothing.
2. `get_links_by_target` matched `target_url` exactly. The UI passes the issue's
   `page_url` (crawler-normalised, no trailing slash) while `links.target_url`
   holds the href as authored, which on WordPress usually carries one.

The second is the same class as the Performance Ledger join key, so both were
fixed together (P5).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.models.job import CrawlJob
from api.models.link import Link

JOB_ID = "job-link-sources"
TARGET = "https://livingsystems.ca/dontation_form"


async def _seed(store, *, stored_target: str) -> None:
    await store.create_job(CrawlJob(
        job_id=JOB_ID, target_url="https://livingsystems.ca",
        status="complete", started_at=datetime.now(timezone.utc),
    ))
    await store.save_links([
        Link(job_id=JOB_ID, source_url=f"https://livingsystems.ca/post-{i}",
             target_url=stored_target, link_text="Donate",
             link_type="internal", status_code=404, is_broken=True)
        for i in range(3)
    ])


class TestLookupToleratesTrailingSlash:
    @pytest.mark.asyncio
    async def test_exact_match_still_works(self, store):
        await _seed(store, stored_target=TARGET)
        assert len(await store.get_links_by_target(JOB_ID, TARGET)) == 3

    @pytest.mark.asyncio
    async def test_stored_with_slash_queried_without(self, store):
        """The real livingsystems.ca case: the href carries a trailing slash,
        the issue's page_url does not."""
        await _seed(store, stored_target=f"{TARGET}/")
        assert len(await store.get_links_by_target(JOB_ID, TARGET)) == 3

    @pytest.mark.asyncio
    async def test_stored_without_slash_queried_with(self, store):
        await _seed(store, stored_target=TARGET)
        assert len(await store.get_links_by_target(JOB_ID, f"{TARGET}/")) == 3

    @pytest.mark.asyncio
    async def test_a_different_target_is_not_matched(self, store):
        """Tolerance must not become a prefix match — /donate must not return
        rows for /donate-now."""
        await _seed(store, stored_target="https://livingsystems.ca/donate-now")
        assert await store.get_links_by_target(JOB_ID, "https://livingsystems.ca/donate") == []

    @pytest.mark.asyncio
    async def test_unknown_target_returns_empty(self, store):
        await _seed(store, stored_target=TARGET)
        assert await store.get_links_by_target(JOB_ID, "https://livingsystems.ca/nope") == []


class TestEndpointContract:
    """The frontend reads `data.sources`. Pin that so the shape cannot drift
    again without a test going red (the original break was exactly this)."""

    @pytest.mark.asyncio
    async def test_response_envelope_shape(self, api_client, auth_headers, test_store):
        await _seed(test_store, stored_target=TARGET)
        resp = await api_client.get(
            "/api/fixes/link-sources",
            params={"job_id": JOB_ID, "target_url": TARGET},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"target_url", "sources", "count"}
        assert isinstance(body["sources"], list), "the frontend calls .map on this"
        assert body["count"] == len(body["sources"]) == 3
        assert {"source_url", "target_url", "link_text", "link_type"} <= set(body["sources"][0])

    @pytest.mark.asyncio
    async def test_endpoint_matches_across_trailing_slash(self, api_client, auth_headers, test_store):
        await _seed(test_store, stored_target=f"{TARGET}/")
        resp = await api_client.get(
            "/api/fixes/link-sources",
            params={"job_id": JOB_ID, "target_url": TARGET},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

    @pytest.mark.asyncio
    async def test_unknown_job_is_404(self, api_client, auth_headers):
        resp = await api_client.get(
            "/api/fixes/link-sources",
            params={"job_id": "no-such-job", "target_url": TARGET},
            headers=auth_headers,
        )
        assert resp.status_code == 404
