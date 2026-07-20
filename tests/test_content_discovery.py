"""
Tests for api/crawler/content_discovery.py and sitemap type-grouping.

All external HTTP calls are mocked with respx — no real network requests.

Spec:  docs/functional-specification.md (Scan content-type scoping)
Covers: child-sitemap classification, three-tier discovery, scope resolution.
"""

import httpx
import pytest
import respx

from api.crawler.content_discovery import discover_scope, resolve_scope_urls
from api.crawler.sitemap import classify_child_sitemap, fetch_sitemap_recursive


TARGET = "https://example.com/"


# ── Child-sitemap filename classification ───────────────────────────────────

class TestClassifyChildSitemap:
    @pytest.mark.parametrize(
        "url,expected",
        [
            # Yoast / Rank Math convention
            ("https://e.com/page-sitemap.xml", "page"),
            ("https://e.com/post-sitemap.xml", "post"),
            ("https://e.com/post-sitemap1.xml", "post"),
            ("https://e.com/event-sitemap.xml", "event"),
            ("https://e.com/category-sitemap.xml", "category"),
            ("https://e.com/post-sitemap.xml.gz", "post"),
            # WordPress core 5.5+ convention
            ("https://e.com/wp-sitemap-posts-page-1.xml", "page"),
            ("https://e.com/wp-sitemap-posts-post-1.xml", "post"),
            ("https://e.com/wp-sitemap-posts-event-2.xml", "event"),
            ("https://e.com/wp-sitemap-taxonomies-category-1.xml", "category"),
            # No recognisable type signal
            ("https://e.com/sitemap.xml", None),
            ("https://e.com/random.xml", None),
        ],
    )
    def test_classification(self, url, expected):
        assert classify_child_sitemap(url) == expected


# ── Sitemap grouping (SitemapResult.grouped) ────────────────────────────────

def _urlset(urls):
    locs = "\n".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'


def _index(children):
    sm = "\n".join(f"<sitemap><loc>{u}</loc></sitemap>" for u in children)
    return f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</sitemapindex>'


class TestSitemapGrouping:
    @pytest.mark.asyncio
    async def test_sitemap_index_retains_type_grouping(self):
        """A typed <sitemapindex> populates `grouped` per content type; the flat
        `urls` list is unchanged (back-compat for existing callers)."""
        page_urls = ["https://example.com/about", "https://example.com/contact"]
        post_urls = ["https://example.com/our-recap"]
        event_urls = ["https://example.com/event-a"]
        with respx.mock:
            respx.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(200, text=_index([
                    "https://example.com/page-sitemap.xml",
                    "https://example.com/post-sitemap.xml",
                    "https://example.com/event-sitemap.xml",
                ]))
            )
            respx.get("https://example.com/page-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(page_urls)))
            respx.get("https://example.com/post-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(post_urls)))
            respx.get("https://example.com/event-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(event_urls)))
            async with httpx.AsyncClient() as client:
                result = await fetch_sitemap_recursive(TARGET, client)

        assert result.grouped is not None
        assert result.grouped["page"] == page_urls
        assert result.grouped["post"] == post_urls
        assert result.grouped["event"] == event_urls
        # Flat list unchanged: everything still present.
        assert set(result.urls) == set(page_urls + post_urls + event_urls)


# ── REST handler used by the Tier-1 discovery/resolve tests ─────────────────

_TYPES = {
    "post": {"name": "Posts", "rest_base": "posts", "viewable": True},
    "page": {"name": "Pages", "rest_base": "pages", "viewable": True},
    "event": {"name": "Events", "rest_base": "events", "viewable": True},
    "attachment": {"name": "Media", "rest_base": "media", "viewable": True},  # excluded (non-content)
    "wp_block": {"name": "Blocks", "rest_base": "blocks", "viewable": False},  # excluded
}
_COUNTS = {"pages": "14", "posts": "212", "events": "30"}
_CATS = [{"id": 7, "name": "Programs", "count": 41}, {"id": 9, "name": "News", "count": 5}]
_COLLECTIONS = {
    "pages": ["https://example.com/about", "https://example.com/contact"],
    "posts": ["https://example.com/our-recap", "https://example.com/news-1"],
    "events": ["https://example.com/event-a"],
}
_CAT7_POSTS = ["https://example.com/our-recap"]


def _rest_handler(request):
    url = request.url
    path = url.path
    q = dict(url.params)
    if path == "/wp-json/":
        return httpx.Response(200, json={"name": "Example", "routes": {}})
    if path == "/wp-json/wp/v2/types":
        return httpx.Response(200, json=_TYPES)
    if path == "/wp-json/wp/v2/categories":
        page = int(q.get("page", "1"))
        return httpx.Response(200, json=_CATS if page == 1 else [])
    if path.startswith("/wp-json/wp/v2/"):
        base = path.rsplit("/", 1)[-1]
        # Count probe
        if q.get("per_page") == "1":
            return httpx.Response(200, json=[], headers={"X-WP-Total": _COUNTS.get(base, "0")})
        # Collection of links
        if base == "posts" and "categories" in q:
            items = _CAT7_POSTS if q.get("categories") == "7" else []
        else:
            items = _COLLECTIONS.get(base, [])
        page = int(q.get("page", "1"))
        data = [{"link": u} for u in items] if page == 1 else []
        # Small collections fit on page 1 (per_page=100).
        return httpx.Response(200, json=data, headers={"X-WP-TotalPages": "1"})
    return httpx.Response(404)


# ── Tier 1: WordPress REST ──────────────────────────────────────────────────

class TestDiscoverScopeRest:
    @pytest.mark.asyncio
    async def test_rest_returns_types_and_categories(self):
        with respx.mock:
            respx.route(host="example.com").mock(side_effect=_rest_handler)
            async with httpx.AsyncClient() as client:
                result = await discover_scope(TARGET, client)

        assert result["is_wordpress"] is True
        assert result["discovery_tier"] == "rest"
        keys = [t["key"] for t in result["types"]]
        assert keys == ["page", "post", "event"]  # Pages, Posts, then CPTs
        assert "attachment" not in keys and "wp_block" not in keys
        counts = {t["key"]: t["count"] for t in result["types"]}
        assert counts == {"page": 14, "post": 212, "event": 30}
        assert result["category_scope_supported"] is True
        assert any(c["name"] == "Programs" for c in result["categories"])

    @pytest.mark.asyncio
    async def test_resolve_pages_only(self):
        with respx.mock:
            respx.route(host="example.com").mock(side_effect=_rest_handler)
            async with httpx.AsyncClient() as client:
                urls, notes = await resolve_scope_urls(TARGET, ["page"], [], client)
        assert urls == {"https://example.com/about", "https://example.com/contact"}
        # A Post permalink must NOT appear under a Pages-only scope.
        assert "https://example.com/our-recap" not in urls

    @pytest.mark.asyncio
    async def test_resolve_posts_by_category(self):
        with respx.mock:
            respx.route(host="example.com").mock(side_effect=_rest_handler)
            async with httpx.AsyncClient() as client:
                urls, notes = await resolve_scope_urls(TARGET, [], [7], client)
        assert urls == {"https://example.com/our-recap"}

    @pytest.mark.asyncio
    async def test_mid_pagination_failure_is_reported_not_silently_ended(self, monkeypatch):
        """P1/P2/P10: a transient failure on page 2 (which X-WP-TotalPages says
        exists) must be surfaced as truncated=True — NOT treated as the natural
        end of the collection, which would silently under-scope the crawl."""
        # No retry delay in this test.
        monkeypatch.setattr("api.crawler.content_discovery._MAX_RETRIES", 0)

        def handler(request):
            path = request.url.path
            q = dict(request.url.params)
            if path == "/wp-json/":
                return httpx.Response(200, json={"name": "X", "routes": {}})
            if path == "/wp-json/wp/v2/types":
                return httpx.Response(200, json={"post": {"name": "Posts", "rest_base": "posts", "viewable": True}})
            if path == "/wp-json/wp/v2/posts":
                page = int(q.get("page", "1"))
                if page == 1:
                    # Two pages exist; page 1 succeeds with one link.
                    return httpx.Response(
                        200, json=[{"link": "https://example.com/post-1"}],
                        headers={"X-WP-TotalPages": "2"},
                    )
                return httpx.Response(500)  # page 2 fails
            return httpx.Response(404)

        with respx.mock:
            respx.route(host="example.com").mock(side_effect=handler)
            async with httpx.AsyncClient() as client:
                urls, notes = await resolve_scope_urls(TARGET, ["post"], [], client)

        # We keep the page-1 URL but report the resolution as incomplete.
        assert urls == {"https://example.com/post-1"}
        assert any("more items" in n or "limit" in n for n in notes)


# ── Tier 2: typed sitemap (no REST) ─────────────────────────────────────────

class TestDiscoverScopeSitemap:
    @pytest.mark.asyncio
    async def test_sitemap_tier_classifies_types(self):
        with respx.mock:
            respx.get("https://example.com/wp-json/").mock(return_value=httpx.Response(404))
            respx.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(200, text=_index([
                    "https://example.com/page-sitemap.xml",
                    "https://example.com/post-sitemap.xml",
                ]))
            )
            respx.get("https://example.com/page-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(["https://example.com/about"])))
            respx.get("https://example.com/post-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(["https://example.com/our-recap"])))
            async with httpx.AsyncClient() as client:
                result = await discover_scope(TARGET, client)

        assert result["discovery_tier"] == "sitemap"
        assert [t["key"] for t in result["types"]] == ["page", "post"]
        # Category scoping is not available without REST.
        assert result["category_scope_supported"] is False
        assert result["notes"]

    @pytest.mark.asyncio
    async def test_sitemap_tier_resolves_type_urls(self):
        with respx.mock:
            respx.get("https://example.com/wp-json/").mock(return_value=httpx.Response(404))
            respx.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(200, text=_index([
                    "https://example.com/page-sitemap.xml",
                    "https://example.com/post-sitemap.xml",
                ]))
            )
            respx.get("https://example.com/page-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(["https://example.com/about"])))
            respx.get("https://example.com/post-sitemap.xml").mock(
                return_value=httpx.Response(200, text=_urlset(["https://example.com/our-recap"])))
            async with httpx.AsyncClient() as client:
                urls, notes = await resolve_scope_urls(TARGET, ["page"], [], client)
        assert urls == {"https://example.com/about"}


# ── Tier 3: neither REST nor typed sitemap ──────────────────────────────────

class TestSsrfGuardedClient:
    @pytest.mark.asyncio
    async def test_blocks_request_to_private_host(self):
        """A direct request to a loopback/internal host is refused before any
        network call (per-hop SSRF parity with fetch_page)."""
        from api.crawler.fetcher import make_ssrf_guarded_client
        async with make_ssrf_guarded_client() as client:
            with pytest.raises(httpx.RequestError):
                await client.get("http://127.0.0.1/wp-json/")

    @pytest.mark.asyncio
    async def test_blocks_redirect_to_internal_host(self, monkeypatch):
        """A public host that 302-redirects to an internal address must be
        refused on the redirect hop, not followed."""
        from api.crawler import fetcher

        monkeypatch.setattr(fetcher, "is_ssrf_safe", lambda url: "internal" not in url)
        with respx.mock:
            respx.get("https://public.example/wp-json/").mock(
                return_value=httpx.Response(302, headers={"location": "http://internal.local/"})
            )
            async with fetcher.make_ssrf_guarded_client() as client:
                with pytest.raises(httpx.RequestError):
                    await client.get("https://public.example/wp-json/")


class TestDiscoverScopeNone:
    @pytest.mark.asyncio
    async def test_none_tier_offers_full_only(self):
        with respx.mock:
            respx.get("https://example.com/wp-json/").mock(return_value=httpx.Response(404))
            respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
            async with httpx.AsyncClient() as client:
                result = await discover_scope(TARGET, client)
        assert result["discovery_tier"] == "none"
        assert result["types"] == []
        assert result["is_wordpress"] is False
        assert result["notes"]
