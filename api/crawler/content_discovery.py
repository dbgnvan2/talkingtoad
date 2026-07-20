"""
Content-type discovery and scan-scope resolution.

Purpose: Discover what content types (Pages, Posts, Custom Post Types) and post
         Categories a site exposes, and resolve a user's content-type selection
         into an authoritative allowlist of URLs the crawler may visit.
Spec:    docs/pending/2026-07-20_scan-content-type-scoping.md
Tests:   tests/test_content_discovery.py, tests/test_discover_scope_integration.py

Design note — why an allowlist, not a per-URL guess:
    A URL string cannot reliably distinguish a Page from a Post (WordPress
    permalinks are configurable, so "/about/" and "/our-recap/" are structurally
    identical). Scope must therefore be an explicit URL set built from an
    authoritative source — the WordPress REST API (Tier 1) or per-type child
    sitemaps (Tier 2) — never a pattern match applied while crawling.

Discovery degrades cleanly and needs no credentials (all reads are public):
    Tier 1 "rest"    — /wp-json/ responds → enumerate /wp/v2/types + /categories.
    Tier 2 "sitemap" — no REST but a typed <sitemapindex> exists → classify by
                       child-sitemap filename. Category-by-post scoping is NOT
                       available in this tier (category sitemaps list archive
                       pages, not member posts), so category_scope_supported=False.
    Tier 3 "none"    — neither → only a full-site crawl is possible.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from api.crawler.fetcher import _MAX_RETRIES, _RETRY_BACKOFF_S
from api.crawler.normaliser import is_same_domain, normalise_url
from api.crawler.sitemap import fetch_sitemap_recursive

logger = logging.getLogger(__name__)

_REST_TIMEOUT = 6.0
# Cap pagination of a single REST collection so a huge site can't stall
# discovery. 50 pages × 100 per page = 5,000 URLs per type; announced when hit.
_MAX_REST_PAGES = 50
_REST_PER_PAGE = 100

# Built-in WordPress post types that are not editorial content. Everything else
# reported as public+viewable by /wp/v2/types is treated as a scannable type.
_NON_CONTENT_TYPE_SLUGS: frozenset[str] = frozenset(
    {
        "attachment",
        "nav_menu_item",
        "wp_block",
        "wp_template",
        "wp_template_part",
        "wp_navigation",
        "wp_global_styles",
        "wp_font_family",
        "wp_font_face",
        "custom_css",
        "customize_changeset",
        "oembed_cache",
        "user_request",
        "wp_area",
    }
)

# Stable display order: Pages first, Posts second, then CPTs alphabetically.
_TYPE_SORT_PRIORITY: dict[str, int] = {"page": 0, "post": 1}


def _base_origin(target_url: str) -> str:
    """Return ``scheme://netloc`` for *target_url* (no trailing slash)."""
    p = httpx.URL(target_url)
    return f"{p.scheme}://{p.host}" + (f":{p.port}" if p.port else "")


async def _get_json(
    client: httpx.AsyncClient, url: str
) -> tuple[object, httpx.Headers] | None:
    """GET *url* and return ``(parsed_json, headers)``, or ``None`` on failure.

    Retries transient conditions (network errors/timeouts and 5xx) with
    exponential backoff, mirroring ``fetch_page``'s policy so discovery's
    external calls are hardened consistently with the crawl path (P5). A
    deterministic non-200 (e.g. 404, 401) or JSON-parse error returns ``None``
    without retry. ``None`` therefore means "no usable JSON after retries" — the
    caller must not assume it means "the collection ended" (P1/P2): pagination
    uses the ``X-WP-TotalPages`` header to tell end-of-data from a failed page.
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = await client.get(url, timeout=_REST_TIMEOUT, follow_redirects=True)
        except httpx.RequestError as exc:
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
                continue
            logger.debug("discovery_fetch_error", extra={"url": url, "error": str(exc)})
            return None
        if r.status_code >= 500 and attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
            continue
        if r.status_code != 200:
            return None
        try:
            return r.json(), r.headers
        except Exception:
            return None
    return None


def _type_label(slug: str, name: str | None) -> str:
    """Human label for a type checkbox."""
    if name:
        return name
    return slug.replace("_", " ").replace("-", " ").title()


def _sort_types(types: list[dict]) -> list[dict]:
    return sorted(
        types,
        key=lambda t: (_TYPE_SORT_PRIORITY.get(t["key"], 2), t["label"].lower()),
    )


# ---------------------------------------------------------------------------
# Tier 1 — WordPress REST
# ---------------------------------------------------------------------------

async def _probe_wp_rest(base: str, client: httpx.AsyncClient) -> bool:
    """Return True if ``GET {base}/wp-json/`` looks like a WP REST root."""
    got = await _get_json(client, f"{base}/wp-json/")
    if not got:
        return False
    data, _ = got
    return isinstance(data, dict) and ("routes" in data or "namespaces" in data or "name" in data)


async def _rest_types(base: str, client: httpx.AsyncClient) -> list[dict]:
    """Enumerate public content post types via ``/wp/v2/types``.

    Returns a list of ``{key, label, rest_base}`` for Pages, Posts, and every
    public+viewable custom post type, excluding built-in non-content types.
    """
    got = await _get_json(client, f"{base}/wp-json/wp/v2/types?context=view")
    if not got:
        return []
    data, _ = got
    if not isinstance(data, dict):
        return []

    out: list[dict] = []
    for slug, info in data.items():
        if slug in _NON_CONTENT_TYPE_SLUGS:
            continue
        if not isinstance(info, dict):
            continue
        # Newer WP exposes "viewable"; when present it must be True. When absent
        # (older WP), fall back to including the type.
        if info.get("viewable") is False:
            continue
        rest_base = info.get("rest_base") or slug
        out.append(
            {
                "key": slug,
                "label": _type_label(slug, info.get("name")),
                "rest_base": rest_base,
            }
        )
    return out


async def _rest_count(base: str, client: httpx.AsyncClient, rest_base: str) -> int | None:
    """Return the total item count for a collection via the ``X-WP-Total`` header."""
    try:
        r = await client.get(
            f"{base}/wp-json/wp/v2/{rest_base}?per_page=1&_fields=id",
            timeout=_REST_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.RequestError:
        return None
    if r.status_code != 200:
        return None
    total = r.headers.get("X-WP-Total")
    try:
        return int(total) if total is not None else None
    except ValueError:
        return None


async def _rest_categories(base: str, client: httpx.AsyncClient) -> list[dict]:
    """List post categories via ``/wp/v2/categories`` (paginated, empties dropped)."""
    cats: list[dict] = []
    for page in range(1, _MAX_REST_PAGES + 1):
        got = await _get_json(
            client,
            f"{base}/wp-json/wp/v2/categories"
            f"?per_page={_REST_PER_PAGE}&page={page}&_fields=id,name,count",
        )
        if not got:
            break
        data, _ = got
        if not isinstance(data, list) or not data:
            break
        for c in data:
            if isinstance(c, dict) and c.get("id") is not None and c.get("count"):
                cats.append({"id": c["id"], "name": c.get("name") or str(c["id"]), "count": c["count"]})
        if len(data) < _REST_PER_PAGE:
            break
    return sorted(cats, key=lambda c: c["name"].lower())


def _collect_links(data: object, urls: list[str]) -> None:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("link"):
                urls.append(item["link"])


async def _rest_collection_urls(
    base: str, client: httpx.AsyncClient, rest_base: str, *, query: str = ""
) -> tuple[list[str], bool]:
    """Return every item ``link`` in a REST collection (paginated).

    Returns ``(urls, truncated)``. *truncated* is True if the result is known to
    be incomplete — either the pagination cap was hit (P9) OR a page that the
    ``X-WP-TotalPages`` header says exists could not be fetched (P1/P2: a
    transient mid-pagination failure must not masquerade as "collection ended").
    Reading the total-page count from page 1 is what lets us tell those apart
    from a normal empty trailing page.
    """
    sep = "&" if query else ""

    def _page_url(page: int) -> str:
        return (
            f"{base}/wp-json/wp/v2/{rest_base}"
            f"?per_page={_REST_PER_PAGE}&page={page}&_fields=link{sep}{query}"
        )

    urls: list[str] = []
    first = await _get_json(client, _page_url(1))
    if not first:
        # Could not fetch even the first page — report incomplete, not "empty".
        return [], True
    data, headers = first
    _collect_links(data, urls)

    try:
        total_pages = int(headers.get("X-WP-TotalPages", "1") or "1")
    except ValueError:
        total_pages = 1

    truncated = total_pages > _MAX_REST_PAGES
    last_page = min(total_pages, _MAX_REST_PAGES)
    for page in range(2, last_page + 1):
        got = await _get_json(client, _page_url(page))
        if not got:
            # A page the server said exists failed after retries → incomplete.
            truncated = True
            break
        _collect_links(got[0], urls)
    return urls, truncated


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def discover_scope(target_url: str, client: httpx.AsyncClient) -> dict:
    """Discover the content types and categories available at *target_url*.

    Returns the payload documented in the spec:
    ``{is_wordpress, discovery_tier, types[], categories[], category_scope_supported, notes}``.
    """
    base = _base_origin(target_url)

    # ── Tier 1: WordPress REST ──────────────────────────────────────────────
    if await _probe_wp_rest(base, client):
        types = await _rest_types(base, client)
        for t in types:
            t["count"] = await _rest_count(base, client, t["rest_base"])
        categories = await _rest_categories(base, client)
        return {
            "is_wordpress": True,
            "discovery_tier": "rest",
            "types": _sort_types(types),
            "categories": categories,
            "category_scope_supported": bool(categories),
            "notes": "",
        }

    # ── Tier 2: typed sitemap index ─────────────────────────────────────────
    sitemap = await fetch_sitemap_recursive(target_url, client)
    if sitemap.found and sitemap.grouped:
        types = []
        for key, urls in sitemap.grouped.items():
            if key in {"category", "post_tag", "author", "tag"}:
                continue  # taxonomy/author archives are not scannable content types
            types.append(
                {
                    "key": key,
                    "label": _type_label(key, None) if key not in ("page", "post")
                    else ("Pages" if key == "page" else "Posts"),
                    "rest_base": None,
                    "count": len(urls),
                }
            )
        if types:
            return {
                "is_wordpress": True,
                "discovery_tier": "sitemap",
                "types": _sort_types(types),
                "categories": [],
                "category_scope_supported": False,
                "notes": (
                    "Content types were read from the site's sitemap. Scoping by "
                    "post category isn't available without the WordPress REST API."
                ),
            }

    # ── Tier 3: nothing to scope on ─────────────────────────────────────────
    return {
        "is_wordpress": False,
        "discovery_tier": "none",
        "types": [],
        "categories": [],
        "category_scope_supported": False,
        "notes": (
            "This site doesn't expose a WordPress REST API or a typed sitemap, so "
            "content-type scoping isn't available — a full-site crawl will run."
        ),
    }


def _normalise_same_domain(urls: list[str], target_url: str) -> set[str]:
    """Normalise *urls* and keep only those on the same domain as *target_url*."""
    out: set[str] = set()
    for u in urls:
        try:
            norm = normalise_url(u)
        except ValueError:
            continue
        if is_same_domain(norm, target_url):
            out.add(norm)
    return out


async def resolve_scope_urls(
    target_url: str,
    type_keys: list[str],
    category_ids: list[int],
    client: httpx.AsyncClient,
) -> tuple[set[str], list[str]]:
    """Resolve a content-type selection into an authoritative allowlist of URLs.

    Returns ``(urls, notes)``. ``urls`` is the normalised, same-domain set the
    crawler is allowed to visit; an empty set means the selection resolved to
    nothing (the caller must treat this as an error, not a full crawl — P2/P6).
    ``notes`` carries human-readable warnings (e.g. pagination truncation).
    """
    base = _base_origin(target_url)
    urls: set[str] = set()
    notes: list[str] = []

    if await _probe_wp_rest(base, client):
        # Map requested type keys → rest_base via a fresh /types read.
        types = {t["key"]: t["rest_base"] for t in await _rest_types(base, client)}
        for key in type_keys:
            rest_base = types.get(key)
            if not rest_base:
                notes.append(f"Content type '{key}' was not found on the site.")
                continue
            collected, truncated = await _rest_collection_urls(base, client, rest_base)
            if truncated:
                notes.append(
                    f"'{key}' resolved to a partial set — either it exceeds the "
                    f"{_MAX_REST_PAGES * _REST_PER_PAGE}-item limit or a page couldn't be "
                    f"fetched; only part of it was scoped."
                )
            urls |= _normalise_same_domain(collected, target_url)
        for cat_id in category_ids:
            collected, truncated = await _rest_collection_urls(
                base, client, "posts", query=f"categories={cat_id}"
            )
            if truncated:
                notes.append(
                    f"Category {cat_id} resolved to a partial set — either it exceeds the "
                    f"{_MAX_REST_PAGES * _REST_PER_PAGE}-post limit or a page couldn't be "
                    f"fetched; only part of it was scoped."
                )
            urls |= _normalise_same_domain(collected, target_url)
        return urls, notes

    # Sitemap tier — type scoping only; category_ids are unsupported here.
    if category_ids:
        notes.append(
            "Category scoping needs the WordPress REST API and was skipped for this site."
        )
    sitemap = await fetch_sitemap_recursive(target_url, client)
    grouped = sitemap.grouped or {}
    for key in type_keys:
        urls |= _normalise_same_domain(grouped.get(key, []), target_url)
    return urls, notes
