"""GSC priority upload — /start intake (U1b) + engine frontier seeding (U2).

Spec: docs/pending/2026-08-14_gsc-performance-handoff-plan.md
"""

from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE = "https://example.com"
ROBOTS = f"{BASE}/robots.txt"
SITEMAP = f"{BASE}/sitemap.xml"
ALLOW_ROBOTS = "User-agent: *\nAllow: /"
# Homepage links to NOTHING — so any page that gets crawled beyond it must have
# been seeded, not discovered.
HOME_HTML = "<html><head><title>Home</title></head><body><h1>Home</h1></body></html>"
PAGE_HTML = "<html><head><title>P</title></head><body><h1>P</h1><p>hi</p></body></html>"


def _gsc_file(*paths, host="example.com"):
    return {"generated_for": "talkingtoad", "site": host, "count": len(paths),
            "pages": [{"url": f"https://{host}{p}", "clicks": 5, "impressions": 50,
                       "avg_position": 9.0, "top_queries": ["q"], "inquiries": 1}
                      for p in paths]}


# ── U1b — /start intake ───────────────────────────────────────────────────
class TestStartIntake:
    @pytest.mark.asyncio
    async def test_valid_seed_persisted_and_announced(self, api_client, auth_headers, test_store):
        r = await api_client.post("/api/crawl/start", headers=auth_headers, json={
            "target_url": BASE,
            "gsc_priority": _gsc_file("/", "/counselling/"),
        })
        assert r.status_code == 202
        body = r.json()
        assert any("seeded 2 of 2" in n for n in body.get("scope_notes", []))
        job = await test_store.get_job(body["job_id"])
        assert job.priority_seed is not None
        assert job.priority_seed["used"] == 2

    @pytest.mark.asyncio
    async def test_wrong_site_file_rejected_422(self, api_client, auth_headers):
        r = await api_client.post("/api/crawl/start", headers=auth_headers, json={
            "target_url": BASE,
            "gsc_priority": _gsc_file("/a", "/b", host="othersite.org"),
        })
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_PRIORITY_FILE"

    @pytest.mark.asyncio
    async def test_seed_over_budget_warns_loudly(self, api_client, auth_headers, test_store):
        """Sweep #2 (P9): a seed >= max_pages would silently restrict the crawl —
        /start must warn (D-N1: seed orders, never restricts)."""
        r = await api_client.post("/api/crawl/start", headers=auth_headers, json={
            "target_url": BASE,
            "settings": {"max_pages": 2},
            "gsc_priority": _gsc_file("/a", "/b", "/c"),  # 3 seed pages ≥ budget 2
        })
        assert r.status_code == 202
        assert any("crawl budget" in n for n in r.json().get("scope_notes", []))

    @pytest.mark.asyncio
    async def test_no_seed_is_normal_scan(self, api_client, auth_headers, test_store):
        r = await api_client.post("/api/crawl/start", headers=auth_headers,
                                  json={"target_url": BASE})
        assert r.status_code == 202
        job = await test_store.get_job(r.json()["job_id"])
        assert job.priority_seed is None


# ── U2 — engine frontier seeding ──────────────────────────────────────────
class TestEngineSeeding:
    @pytest.mark.asyncio
    async def test_priority_urls_are_crawled_though_unlinked(self):
        """The homepage links to nothing; a seeded URL still gets crawled — proving
        the seed fronts the frontier (it wouldn't be reached otherwise)."""
        with respx.mock:
            respx.get(ROBOTS).mock(return_value=httpx.Response(200, text=ALLOW_ROBOTS))
            respx.get(SITEMAP).mock(return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=HOME_HTML, headers={"content-type": "text/html"}))
            respx.get(url__regex=rf"{BASE}/seeded/?$").mock(return_value=httpx.Response(
                200, text=PAGE_HTML, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0, max_pages=10,
                                     priority_urls=[f"{BASE}/seeded/"])
            result = await run_crawl("job-seed", BASE, settings)

        crawled = {p.url for p in result.pages}
        # slash-tolerant: normalise_url may drop the trailing slash on the stored url
        assert any(u.rstrip("/").endswith("/seeded") for u in crawled), \
            f"seeded URL should have been crawled; got {crawled}"

    @pytest.mark.asyncio
    async def test_off_domain_seed_is_ignored_not_fatal(self):
        with respx.mock:
            respx.get(ROBOTS).mock(return_value=httpx.Response(200, text=ALLOW_ROBOTS))
            respx.get(SITEMAP).mock(return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=HOME_HTML, headers={"content-type": "text/html"}))

            settings = CrawlSettings(crawl_delay_ms=0, max_pages=10,
                                     priority_urls=["https://evil.example.org/x"])
            result = await run_crawl("job-seed2", BASE, settings)

        # crawl still succeeds; the off-domain seed was skipped, nothing external crawled
        # Slash-tolerant like the sibling above: ND3 (2026-09-02) normalises the
        # bare origin to the root path, so the homepage is stored as `BASE + "/"`.
        assert any(p.url.rstrip("/") == BASE.rstrip("/") for p in result.pages)
        assert not any("evil.example.org" in p.url for p in result.pages)
