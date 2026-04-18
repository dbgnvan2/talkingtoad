"""
WordPress fix generation and application engine (v2.0).

Detects active SEO plugins, resolves page URLs to WP post IDs,
generates fix proposals from crawl issues, and applies approved
fixes via the WordPress REST API.
"""

from __future__ import annotations

import asyncio
import html as html_module
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from api.services.wp_client import WPClient
from api.services.job_store import SQLiteJobStore, RedisJobStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixable field registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FixSpec:
    field: str                      # internal field identifier
    label: str                      # human label shown in UI
    yoast_key: str | None           # Yoast SEO REST meta key
    rank_math_key: str | None       # Rank Math REST meta key


_FIELD_SPECS: dict[str, _FixSpec] = {
    "seo_title": _FixSpec(
        "seo_title", "SEO Title",
        yoast_key="_yoast_wpseo_title",
        rank_math_key="rank_math_title",
    ),
    "meta_description": _FixSpec(
        "meta_description", "Meta Description",
        yoast_key="_yoast_wpseo_metadesc",
        rank_math_key="rank_math_description",
    ),
    "og_title": _FixSpec(
        "og_title", "Social Share Title",
        yoast_key="_yoast_wpseo_opengraph-title",
        rank_math_key="rank_math_facebook_title",
    ),
    "og_description": _FixSpec(
        "og_description", "Social Share Description",
        yoast_key="_yoast_wpseo_opengraph-description",
        rank_math_key="rank_math_facebook_description",
    ),
    "indexable": _FixSpec(
        "indexable", "Search Engine Indexing",
        yoast_key="_yoast_wpseo_meta-robots-noindex",
        rank_math_key="rank_math_robots",
    ),
    "sitemap_include": _FixSpec(
        "sitemap_include", "Sitemap Inclusion",
        yoast_key="_yoast_wpseo_sitemap-include",
        rank_math_key=None,
    ),
    "schema_article_type": _FixSpec(
        "schema_article_type", "Schema Article Type",
        yoast_key="_yoast_wpseo_schema_article_type",
        rank_math_key="rank_math_rich_snippet",
    ),
}

# Issue codes whose fix value is predetermined — no user input needed.
# The value shown in the Fix panel is pre-filled and read-only.
PREDEFINED_FIX_VALUES: dict[str, str] = {
    "sitemap_include":    "always",
    "schema_article_type": "Article",
}

# Maps issue_code → field name. Multiple codes may map to the same field;
# only one fix record is created per (page_url, field) pair.
_CODE_TO_FIELD: dict[str, str] = {
    "TITLE_MISSING":       "seo_title",
    "TITLE_TOO_SHORT":     "seo_title",
    "TITLE_TOO_LONG":      "seo_title",
    "META_DESC_MISSING":   "meta_description",
    "META_DESC_TOO_SHORT": "meta_description",
    "META_DESC_TOO_LONG":  "meta_description",
    "OG_TITLE_MISSING":    "og_title",
    "OG_DESC_MISSING":     "og_description",
    "NOINDEX_META":        "indexable",
    "NOT_IN_SITEMAP":      "sitemap_include",
    "SCHEMA_MISSING":      "schema_article_type",
}


def get_fixable_codes() -> frozenset[str]:
    """Return all issue codes that can be fixed by the WP automation engine."""
    return frozenset(_CODE_TO_FIELD.keys())


# ---------------------------------------------------------------------------
# Plugin detection
# ---------------------------------------------------------------------------

async def detect_seo_plugin(wp: WPClient) -> str | None:
    """Return the active SEO plugin name: 'yoast', 'rank_math', or None."""
    try:
        r = await wp.get("plugins?status=active&per_page=100&_fields=plugin,name")
        if r.status_code != 200:
            return None
        for plugin in r.json():
            slug = plugin.get("plugin", "").lower()
            if "wordpress-seo" in slug or "yoast" in slug:
                return "yoast"
            if "seo-by-rank-math" in slug or "rank-math" in slug:
                return "rank_math"
    except Exception as exc:
        logger.warning("plugin_detect_failed", extra={"error": str(exc)})
    return None


# ---------------------------------------------------------------------------
# URL → WP post resolution
# ---------------------------------------------------------------------------

async def find_orphaned_media(
    wp: WPClient,
    job_id: str,
    store: SQLiteJobStore | RedisJobStore
) -> list[dict]:
    """Return a list of media items from WordPress not found in the crawl.

    Compares WP Media Library against all image URLs found on crawled pages.
    Handles WordPress size variants (e.g. -600x403.jpg) in both directions:
    - Crawled page has the size variant, WP stores the original
    - WP source_url is the original, crawled page references a variant

    Args:
        wp: Authenticated WordPress client.
        job_id: ID of the crawl job to compare against.
        store: Job store to retrieve crawled pages.
    """
    # 1. Fetch all media from WordPress
    wp_media = await wp.list_media()
    if not wp_media:
        return []

    # 2. Fetch all image URLs found during the crawl
    pages = await store.get_pages(job_id)
    crawled_image_urls: set[str] = set()
    crawled_base_urls: set[str] = set()  # without size suffix
    for p in pages:
        for img_url in (p.image_urls or []):
            u = urlparse(img_url)
            norm = f"{u.scheme}://{u.netloc}{u.path}".rstrip("/")
            crawled_image_urls.add(norm)
            # Also store the base (without size suffix) for variant matching
            base = re.sub(r"-\d+x\d+(\.[a-zA-Z0-9]+)$", r"\1", norm)
            crawled_base_urls.add(base)

    # 3. Identify orphaned media
    orphans = []
    for item in wp_media:
        source_url = item.get("source_url", "")
        if not source_url:
            continue

        u = urlparse(source_url)
        norm_wp = f"{u.scheme}://{u.netloc}{u.path}".rstrip("/")

        # Check: exact match
        if norm_wp in crawled_image_urls:
            continue
        # Check: WP original matches a crawled size variant's base
        wp_base = re.sub(r"-\d+x\d+(\.[a-zA-Z0-9]+)$", r"\1", norm_wp)
        if wp_base in crawled_base_urls or norm_wp in crawled_base_urls:
            continue
        # Check: crawled pages reference a size variant of this WP image
        # (crawled has -600x403.jpg, WP has the original .jpg)
        if any(norm_wp == re.sub(r"-\d+x\d+(\.[a-zA-Z0-9]+)$", r"\1", cu)
               for cu in crawled_image_urls
               if norm_wp.rsplit("/", 1)[0] == cu.rsplit("/", 1)[0]):
            continue

        # Extract file size from media_details if available
        details = item.get("media_details", {})
        file_size = details.get("filesize")
        width = details.get("width")
        height = details.get("height")

        orphans.append({
            "id": item.get("id"),
            "title": item.get("title", {}).get("rendered", "Untitled"),
            "url": source_url,
            "alt_text": item.get("alt_text", ""),
            "post_parent": item.get("post", 0),
            "mime_type": item.get("mime_type", ""),
            "date": item.get("date", ""),
            "file_size_kb": round(file_size / 1024, 1) if file_size else None,
            "dimensions": f"{width}x{height}" if width and height else None,
            "admin_url": f"{wp.site_url.rstrip('/')}/wp-admin/post.php?post={item.get('id')}&action=edit",
        })

    return orphans


async def find_post_by_url(wp: WPClient, page_url: str) -> dict | None:
    """Return {id, type} for the WP post/page matching *page_url*, or None.

    Returns None immediately for relative URLs (e.g. "/" or "/about") — these
    cannot be resolved to a WordPress post without a base domain.
    """
    if not page_url or not page_url.startswith(("http://", "https://")):
        logger.debug("find_post_by_url_skipped_relative", extra={"url": page_url})
        return None
    parsed = urlparse(page_url)
    path = parsed.path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if path else ""

    if not slug:
        # Homepage — try to find it via the front page setting
        slug = "/"

    norm_url = page_url.rstrip("/")

    for post_type, endpoint in [("page", "pages"), ("post", "posts")]:
        try:
            r = await wp.get(
                f"{endpoint}?slug={slug}&per_page=10&_fields=id,link&context=edit"
            )
            if r.status_code != 200:
                continue
            items = r.json()
            # Exact URL match
            for item in items:
                item_link = item.get("link", "").rstrip("/")
                if item_link == norm_url:
                    return {"id": item["id"], "type": post_type}
            # Slug-only match: if exactly one result has the same slug,
            # trust it even if parent path differs (WordPress may use a
            # different permalink structure than the crawled URL).
            if len(items) == 1:
                return {"id": items[0]["id"], "type": post_type}
        except Exception as exc:
            logger.warning("find_post_failed", extra={"url": page_url, "error": str(exc)})

    # Fallback: search API
    try:
        r = await wp.get(
            f"search?search={slug}&type=post&subtype=any&per_page=10&_fields=id,url,subtype"
        )
        if r.status_code == 200:
            for item in r.json():
                if item.get("url", "").rstrip("/") == norm_url:
                    return {"id": item["id"], "type": item.get("subtype", "post")}
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Current value retrieval
# ---------------------------------------------------------------------------

async def get_current_value(
    wp: WPClient,
    post_info: dict,
    field: str,
    seo_plugin: str | None,
) -> str | None:
    """Fetch the current value of *field* for a WP post from the REST API."""
    spec = _FIELD_SPECS.get(field)
    if not spec:
        return None

    meta_key = spec.yoast_key if seo_plugin == "yoast" else spec.rank_math_key
    if not meta_key:
        return None

    post_type = post_info["type"]
    endpoint_base = "pages" if post_type == "page" else "posts"

    try:
        r = await wp.get(
            f"{endpoint_base}/{post_info['id']}?_fields=meta&context=edit"
        )
        if r.status_code == 200:
            meta = r.json().get("meta", {})
            value = meta.get(meta_key)
            if isinstance(value, list):
                # Rank Math robots is stored as a list
                return ",".join(value)
            return str(value) if value else None
    except Exception as exc:
        logger.warning(
            "get_current_value_failed",
            extra={"field": field, "post_id": post_info["id"], "error": str(exc)},
        )
    return None


# ---------------------------------------------------------------------------
# Fix generation
# ---------------------------------------------------------------------------

def _auto_propose(issue_code: str, current_value: str | None) -> str:
    """Return an automatic proposed value where possible, else empty string."""
    if issue_code == "TITLE_TOO_LONG" and current_value:
        return current_value[:57].rstrip() + "…"
    if issue_code == "META_DESC_TOO_LONG" and current_value:
        return current_value[:157].rstrip() + "…"
    if issue_code == "NOINDEX_META":
        return "index"   # label only — the apply logic uses plugin-specific values
    field = _CODE_TO_FIELD.get(issue_code)
    if field and field in PREDEFINED_FIX_VALUES:
        return PREDEFINED_FIX_VALUES[field]
    return ""


async def generate_fixes(
    wp: WPClient,
    job_id: str,
    issues: list[dict],
    seo_plugin: str | None,
    *,
    concurrency: int = 5,
) -> tuple[list[dict], list[str]]:
    """Generate fix records from a list of issue dicts.

    Resolves WP posts and fetches current values concurrently (up to
    *concurrency* requests in flight at once) to keep latency manageable
    on sites with many fixable issues.

    Returns (fixes, skipped_urls) where skipped_urls are pages whose WP post
    could not be resolved.
    """
    # Deduplicate by (page_url, field) — only one fix per field per page
    seen: set[tuple[str, str]] = set()
    work_items: list[tuple[str, str]] = []  # (page_url, field) pairs to process

    for issue in issues:
        code = issue.get("code", "")
        page_url = issue.get("page_url")
        if not page_url or code not in _CODE_TO_FIELD:
            continue
        field = _CODE_TO_FIELD[code]
        key = (page_url, field)
        if key in seen:
            continue
        seen.add(key)
        work_items.append((page_url, field))

    # Keep a mapping of page_url → issue_code for _auto_propose
    url_to_code: dict[tuple[str, str], str] = {}
    for issue in issues:
        code = issue.get("code", "")
        page_url = issue.get("page_url")
        if page_url and code in _CODE_TO_FIELD:
            key = (page_url, _CODE_TO_FIELD[code])
            url_to_code.setdefault(key, code)

    sem = asyncio.Semaphore(concurrency)

    async def _process(page_url: str, field: str) -> dict | None:
        async with sem:
            post_info = await find_post_by_url(wp, page_url)
            if not post_info:
                return None
            current = await get_current_value(wp, post_info, field, seo_plugin)
            code = url_to_code.get((page_url, field), "")
            spec = _FIELD_SPECS[field]
            return {
                "id": str(uuid4()),
                "job_id": job_id,
                "issue_code": code,
                "page_url": page_url,
                "wp_post_id": post_info["id"],
                "wp_post_type": post_info["type"],
                "field": field,
                "label": spec.label,
                "current_value": current,
                "proposed_value": _auto_propose(code, current),
                "status": "pending",
                "error": None,
                "applied_at": None,
            }

    results = await asyncio.gather(
        *[_process(page_url, field) for page_url, field in work_items],
        return_exceptions=False,
    )

    fixes: list[dict] = []
    skipped: list[str] = []
    for item, (page_url, _field) in zip(results, work_items):
        if item is None:
            if page_url not in skipped:
                skipped.append(page_url)
        else:
            fixes.append(item)

    return fixes, skipped


# ---------------------------------------------------------------------------
# Fix application
# ---------------------------------------------------------------------------

async def apply_fix(
    wp: WPClient,
    fix: dict,
    seo_plugin: str | None,
) -> tuple[bool, str | None]:
    """Apply a single approved fix via the WP REST API.

    Returns (success, error_message).
    """
    field = fix.get("field", "")
    spec = _FIELD_SPECS.get(field)
    if not spec:
        return False, f"No fix spec for field '{field}'"

    if not seo_plugin:
        return False, "No supported SEO plugin detected (Yoast or Rank Math required)"

    meta_key = spec.yoast_key if seo_plugin == "yoast" else spec.rank_math_key
    if not meta_key:
        return False, f"No meta key for field '{field}' with plugin '{seo_plugin}'"

    wp_post_id = fix.get("wp_post_id")
    wp_post_type = fix.get("wp_post_type", "page")
    if not wp_post_id:
        return False, "Missing wp_post_id — regenerate fixes"

    endpoint = f"{'pages' if wp_post_type == 'page' else 'posts'}/{wp_post_id}"
    proposed = fix.get("proposed_value", "")

    # Guard: never write an empty string to a text field — it would silently clear live content
    if field != "indexable" and not proposed.strip():
        return False, "Proposed value is empty — edit the fix before applying"

    # Special handling for the indexable field
    if field == "indexable":
        meta_value = _indexable_meta_value(seo_plugin)
    else:
        meta_value = proposed

    try:
        r = await wp.patch(endpoint, json={"meta": {meta_key: meta_value}})
        if r.status_code == 200:
            return True, None
        body = r.json()
        return False, body.get("message", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc:
        return False, str(exc)


async def replace_link_in_post(
    wp: WPClient,
    source_url: str,
    old_url: str,
    new_url: str,
) -> tuple[bool, str | None]:
    """Replace *old_url* with *new_url* in the content of the WP post at *source_url*.

    Works for both classic-editor HTML and Gutenberg block content — the URL
    appears as a plain string in both representations so a text replacement is safe.

    Returns (success, error_message).
    """
    post_info = await find_post_by_url(wp, source_url)
    if not post_info:
        return False, f"Could not resolve a WordPress post for: {source_url}"

    post_type = post_info["type"]
    endpoint_base = "pages" if post_type == "page" else "posts"
    post_id = post_info["id"]

    # Fetch the raw post content
    try:
        r = await wp.get(f"{endpoint_base}/{post_id}?_fields=content&context=edit")
        if r.status_code != 200:
            body = r.json()
            return False, body.get("message", f"HTTP {r.status_code} fetching post content")
        raw_content = r.json().get("content", {}).get("raw", "")
    except Exception as exc:
        return False, f"Error fetching post content: {exc}"

    if old_url not in raw_content:
        return False, f"The URL '{old_url}' was not found in the post content."

    updated_content = raw_content.replace(old_url, new_url)

    try:
        r = await wp.patch(
            f"{endpoint_base}/{post_id}",
            json={"content": updated_content},
        )
        if r.status_code == 200:
            return True, None
        body = r.json()
        return False, body.get("message", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc:
        return False, str(exc)


def _indexable_meta_value(seo_plugin: str) -> str | list:
    """Return the plugin-specific value that re-enables search indexing."""
    if seo_plugin == "yoast":
        return "0"   # 0 = use site default (index); 1 = noindex; 2 = force index
    if seo_plugin == "rank_math":
        return []    # empty robots array = no directives = index
    return ""


# ---------------------------------------------------------------------------
# Bulk title trim
# ---------------------------------------------------------------------------

_YOAST_SEPARATORS = [" | ", " - ", " · ", " — ", " « ", " » ", " • ", " :: "]

# Yoast/Rank Math variable that means "just the post title, no suffix"
_SEO_TITLE_VAR: dict[str, str] = {
    "yoast":     "%%title%%",
    "rank_math": "%title%",
}


def _detect_separator(title: str, site_name: str) -> str | None:
    """Return the separator used between the post title and site name, or None."""
    for sep in _YOAST_SEPARATORS:
        if title.endswith(sep + site_name):
            return sep
    return None


def trim_title(title: str, site_name: str) -> str | None:
    """Strip separator + site name from the end of *title*.

    Returns the trimmed title, or None if the site name is not found at the end.
    """
    sep = _detect_separator(title, site_name)
    if sep is None:
        return None
    trimmed = title[: -(len(sep) + len(site_name))].rstrip()
    return trimmed or None


async def get_site_name(wp: WPClient) -> str | None:
    """Fetch the WordPress site name.

    Tries two sources:
    1. ``GET /wp-json/`` (the WP REST API root) — returns ``name`` without auth.
    2. ``GET /wp/v2/settings`` — requires manage_options; returns ``title``.
    """
    # Source 1: unauthenticated API root (most reliable)
    try:
        assert wp._client is not None
        r = await wp._client.get(f"{wp.site_url}/wp-json/")
        if r.status_code == 200:
            name = r.json().get("name") or None
            if name:
                return name
    except Exception as exc:
        logger.warning("get_site_name_root_failed", extra={"error": str(exc)})

    # Source 2: authenticated settings endpoint
    try:
        r = await wp.get("settings")
        if r.status_code == 200:
            return r.json().get("title") or None
    except Exception as exc:
        logger.warning("get_site_name_settings_failed", extra={"error": str(exc)})

    return None


async def _get_per_page_seo_title(
    wp: WPClient,
    post_id: int,
    post_type: str,
    seo_plugin: str,
) -> str | None:
    """Fetch the current per-page SEO title meta value via the WP REST API.

    Returns the raw meta value (may be an empty string when the global Yoast
    template is in use), or None if the request fails.

    When Yoast has no per-page override, _yoast_wpseo_title is empty string —
    meaning Yoast generates the title from its global template, typically
    ``%%title%% %%sep%% %%sitename%%``.
    """
    spec = _FIELD_SPECS.get("seo_title")
    if not spec:
        return None
    meta_key = spec.yoast_key if seo_plugin == "yoast" else spec.rank_math_key
    if not meta_key:
        return None

    endpoint_base = "pages" if post_type == "page" else "posts"
    try:
        r = await wp.get(f"{endpoint_base}/{post_id}?context=edit&_fields=meta")
        if r.status_code == 200:
            meta = r.json().get("meta") or {}
            return meta.get(meta_key)   # empty string = no override set
    except Exception as exc:
        logger.warning("get_per_page_seo_title_failed", extra={"post_id": post_id, "error": str(exc)})
    return None


async def bulk_trim_titles(
    wp: WPClient,
    pages: list[dict],           # list of {page_url, title} from crawled_pages
    seo_plugin: str | None,
) -> list[dict]:
    """Remove the site-name suffix from SEO titles for all *pages*.

    Strategy (Yoast / Rank Math):
    1. Fetch the per-page SEO title meta for each post.
    2. If it is empty — Yoast is generating the title from its global template
       (``%%title%% %%sep%% %%sitename%%``) — write ``%%title%%`` (or ``%title%%``
       for Rank Math).  This tells the plugin to render just the post title with
       no suffix, and stays correct even if the page is later renamed.
    3. If a custom title is already set but still ends with the site name, strip
       the suffix from that string (same as before).

    Falls back to the string-strip approach when no SEO plugin is detected.

    Returns a list of result dicts with keys:
      url, original_title, trimmed_title, method, success, error
    """
    site_name = await get_site_name(wp)
    # site_name is only needed for the string-strip fallback paths; don't bail out
    # here — pages that can use the %%title%% variable method don't need it.

    results = []
    for page in pages:
        url = page["page_url"]
        raw_title = page.get("title") or ""

        post_info = await find_post_by_url(wp, url)
        if not post_info:
            results.append({
                "url": url,
                "original_title": raw_title,
                "trimmed_title": None,
                "method": None,
                "success": False,
                "error": "Could not find WordPress post for this URL",
            })
            continue

        post_id   = post_info["id"]
        post_type = post_info["type"]

        # ── Decide what value to write ────────────────────────────────────
        title_var  = _SEO_TITLE_VAR.get(seo_plugin or "") if seo_plugin else None
        new_value: str | None = None
        method:    str        = "unknown"

        if seo_plugin and title_var:
            # Fetch the current per-page SEO title meta to determine what Yoast
            # is doing.  An empty string means the global template is active.
            current_meta = await _get_per_page_seo_title(wp, post_id, post_type, seo_plugin)
            if current_meta is not None and current_meta.strip() == "":
                # No per-page override — Yoast is appending %%sep%%%%sitename%%.
                # Write the post-title variable so the plugin renders just the
                # page title without the suffix.
                new_value = title_var
                method = "variable"
            elif current_meta:
                # A custom title is set — strip the site name if it's there.
                if not site_name:
                    results.append({
                        "url": url, "original_title": raw_title, "trimmed_title": None,
                        "method": "skip", "success": False,
                        "error": "Could not determine site name — unable to strip suffix from custom title",
                    })
                    continue
                stripped = trim_title(current_meta, site_name)
                if stripped:
                    new_value = stripped
                    method = "strip_custom"
                else:
                    results.append({
                        "url": url,
                        "original_title": raw_title,
                        "trimmed_title": None,
                        "method": "skip",
                        "success": False,
                        "error": (
                            f"Custom SEO title '{current_meta[:60]}' does not end with "
                            f"site name '{site_name}' — manual review needed"
                        ),
                    })
                    continue
            else:
                # Could not read meta — best-effort: write the title variable.
                # This is almost certainly correct for TITLE_TOO_LONG pages where
                # Yoast is applying the global %%title%% %%sep%% %%sitename%% template.
                logger.warning(
                    "bulk_trim_meta_unreadable_using_variable",
                    extra={"url": url, "seo_plugin": seo_plugin},
                )
                new_value = title_var
                method = "variable_fallback"
        else:
            # No recognised SEO plugin — cannot write a title override
            results.append({
                "url": url,
                "original_title": raw_title,
                "trimmed_title": None,
                "method": "skip",
                "success": False,
                "error": "No supported SEO plugin detected (Yoast or Rank Math required to set title overrides)",
            })
            continue

        # ── Apply the fix ─────────────────────────────────────────────────
        fix_record = {
            "field":        "seo_title",
            "wp_post_id":   post_id,
            "wp_post_type": post_type,
            "proposed_value": new_value,
        }
        ok, err = await apply_fix(wp, fix_record, seo_plugin)
        results.append({
            "url":            url,
            "original_title": raw_title,
            "trimmed_title":  new_value,
            "method":         method,
            "success":        ok,
            "error":          err,
        })

    return results


# ---------------------------------------------------------------------------
# Single-page title trim
# ---------------------------------------------------------------------------

async def trim_title_one(
    wp: WPClient,
    page_url: str,
    seo_plugin: str | None,
) -> dict:
    """Strip the site-name suffix from the SEO title of a single page.

    Same logic as bulk_trim_titles but for one URL.  Returns a dict with keys:
    success, original_title, trimmed_title, method, error.
    """
    site_name = await get_site_name(wp)

    post_info = await find_post_by_url(wp, page_url)
    if not post_info:
        return {"success": False, "error": "Could not find WordPress post for this URL"}

    post_id   = post_info["id"]
    post_type = post_info["type"]

    title_var = _SEO_TITLE_VAR.get(seo_plugin or "") if seo_plugin else None

    if not seo_plugin or not title_var:
        return {
            "success": False,
            "error": "No supported SEO plugin detected (Yoast or Rank Math required)",
        }

    current_meta = await _get_per_page_seo_title(wp, post_id, post_type, seo_plugin)

    if current_meta is not None and current_meta.strip() == "":
        new_value = title_var
        method    = "variable"
    elif current_meta:
        if not site_name:
            return {"success": False, "error": "Could not determine site name"}
        stripped = trim_title(current_meta, site_name)
        if not stripped:
            return {
                "success": False,
                "error": f"Custom title does not end with site name '{site_name}'",
            }
        new_value = stripped
        method    = "strip_custom"
    else:
        # Meta read failed (Yoast may not expose the field via REST for this post type).
        # Best-effort: write %%title%% — this is almost certainly the right fix for
        # TITLE_TOO_LONG caused by the global Yoast template appending the site name.
        logger.warning(
            "trim_title_one_meta_unreadable_using_variable",
            extra={"page_url": page_url, "seo_plugin": seo_plugin},
        )
        new_value = title_var
        method    = "variable_fallback"

    fix_record = {
        "field":          "seo_title",
        "wp_post_id":     post_id,
        "wp_post_type":   post_type,
        "proposed_value": new_value,
    }
    ok, err = await apply_fix(wp, fix_record, seo_plugin)
    return {
        "success":       ok,
        "trimmed_title": new_value if ok else None,
        "method":        method,
        "error":         err,
    }


# ---------------------------------------------------------------------------
# Heading source analysis — identify where each heading lives
# ---------------------------------------------------------------------------

def _extract_headings_from_html(html_content: str) -> list[dict]:
    """Extract all headings (H1-H6) from HTML content.

    Returns list of {"level": int, "text": str} dicts.
    """
    headings = []
    # Match <h1>...</h1> through <h6>...</h6>
    pattern = re.compile(r'<h([1-6])(?:\s[^>]*)?>(.+?)</h\1>', re.DOTALL | re.IGNORECASE)
    for m in pattern.finditer(html_content):
        level = int(m.group(1))
        # Strip HTML tags and decode entities from inner content
        inner = m.group(2)
        text = html_module.unescape(re.sub(r'<[^>]+>', '', inner)).strip()
        if text:
            headings.append({"level": level, "text": text})
    return headings


def _normalize_text_for_comparison(text: str) -> str:
    """Normalize text for fuzzy comparison (handles dashes, quotes, whitespace)."""
    import unicodedata
    # Normalize unicode
    text = unicodedata.normalize('NFKC', text)
    # Replace various dashes with regular hyphen
    text = re.sub(r'[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]', '-', text)
    # Replace various quotes with simple quotes
    text = re.sub(r'[\u2018\u2019\u201A\u201B]', "'", text)
    text = re.sub(r'[\u201C\u201D\u201E\u201F]', '"', text)
    # Remove ALL whitespace for comparison (handles missing/extra spaces)
    text = re.sub(r'\s+', '', text)
    return text.lower()


def _text_matches(text1: str, text2: str) -> bool:
    """Check if two heading texts match (with normalization)."""
    return _normalize_text_for_comparison(text1) == _normalize_text_for_comparison(text2)


async def analyze_heading_sources(
    wp: WPClient,
    page_url: str,
    crawled_headings: list[dict],
) -> dict:
    """Analyze where each heading on a page comes from.

    Takes the headings found by the crawler and identifies their source:
    - post_content: In the main WordPress post/page content
    - widget: In a WordPress widget
    - acf_field: In an Advanced Custom Fields field
    - unknown: Could not locate (likely theme template or plugin)

    Args:
        wp: WordPress client
        page_url: URL of the page
        crawled_headings: List of {"level": int, "text": str} from crawler

    Returns:
        {
            "page_url": str,
            "post_id": int | None,
            "post_type": str | None,
            "headings": [
                {
                    "level": int,
                    "text": str,
                    "source": "post_content" | "widget" | "acf_field" | "unknown",
                    "source_details": {...},  # varies by source type
                    "fixable": bool,
                }
            ],
            "widgets_checked": int,
            "acf_fields_checked": int,
        }
    """
    result = {
        "page_url": page_url,
        "post_id": None,
        "post_type": None,
        "headings": [],
        "widgets_checked": 0,
        "acf_fields_checked": 0,
        "_debug": {
            "post_found": False,
            "raw_content_length": 0,
            "headings_in_post_content": [],
            "crawled_headings_normalized": [],
        },
    }

    # Track which crawled headings we've found sources for
    # Key: (level, normalized_text) -> source info
    found_sources: dict[tuple[int, str], dict] = {}

    # --- 1. Check post content ---
    post_info = await find_post_by_url(wp, page_url)
    if post_info:
        result["_debug"]["post_found"] = True
        result["post_id"] = post_info["id"]
        result["post_type"] = post_info["type"]

        post_id = post_info["id"]
        post_type = post_info["type"]
        endpoint_base = "pages" if post_type == "page" else "posts"

        try:
            r = await wp.get(f"{endpoint_base}/{post_id}?context=edit&_fields=content,acf")
            if r.status_code == 200:
                data = r.json()
                raw_content = data.get("content", {}).get("raw", "")
                result["_debug"]["raw_content_length"] = len(raw_content)

                # Show sample of h-tags in raw content for debugging
                h_tag_samples = []
                for m in re.finditer(r'<h([1-6])[^>]*>(.{0,60})', raw_content, re.IGNORECASE):
                    h_tag_samples.append(f"H{m.group(1)}: {m.group(0)[:80]}...")
                result["_debug"]["h_tags_in_raw_content"] = h_tag_samples[:10]  # first 10

                # Extract headings from post content
                post_headings = _extract_headings_from_html(raw_content)
                result["_debug"]["headings_in_post_content"] = [
                    {"level": h["level"], "text": h["text"][:50], "normalized": _normalize_text_for_comparison(h["text"])[:50]}
                    for h in post_headings
                ]

                for ph in post_headings:
                    key = (ph["level"], _normalize_text_for_comparison(ph["text"]))
                    found_sources[key] = {
                        "source": "post_content",
                        "source_details": {
                            "post_id": post_id,
                            "post_type": post_type,
                        },
                        "fixable": True,
                    }

                # --- 2. Check ACF fields ---
                acf_data = data.get("acf", {})
                if acf_data and isinstance(acf_data, dict):
                    for field_name, field_value in acf_data.items():
                        if isinstance(field_value, str) and '<h' in field_value.lower():
                            result["acf_fields_checked"] += 1
                            acf_headings = _extract_headings_from_html(field_value)
                            for ah in acf_headings:
                                key = (ah["level"], _normalize_text_for_comparison(ah["text"]))
                                if key not in found_sources:
                                    found_sources[key] = {
                                        "source": "acf_field",
                                        "source_details": {
                                            "post_id": post_id,
                                            "field_name": field_name,
                                        },
                                        "fixable": False,  # ACF fields need special handling
                                    }
        except Exception as exc:
            logger.warning("analyze_heading_sources_post_error", extra={
                "page_url": page_url, "error": str(exc)
            })

    # --- 3. Check widgets ---
    try:
        # Get all widget areas (sidebars)
        r = await wp.get("sidebars?context=edit")
        if r.status_code == 200:
            sidebars = r.json()
            for sidebar in sidebars:
                sidebar_id = sidebar.get("id")
                widgets = sidebar.get("widgets", [])

                for widget in widgets:
                    result["widgets_checked"] += 1
                    widget_id = widget.get("id")
                    # Widget content might be in 'rendered' or 'content'
                    rendered = widget.get("rendered", "")

                    if '<h' in rendered.lower():
                        widget_headings = _extract_headings_from_html(rendered)
                        for wh in widget_headings:
                            key = (wh["level"], _normalize_text_for_comparison(wh["text"]))
                            if key not in found_sources:
                                found_sources[key] = {
                                    "source": "widget",
                                    "source_details": {
                                        "widget_id": widget_id,
                                        "sidebar_id": sidebar_id,
                                        "sidebar_name": sidebar.get("name", ""),
                                    },
                                    "fixable": False,  # Widgets need special handling
                                }
    except Exception as exc:
        logger.warning("analyze_heading_sources_widgets_error", extra={
            "page_url": page_url, "error": str(exc)
        })

    # --- 4. Check reusable blocks (wp_block post type) ---
    try:
        r = await wp.get("blocks?per_page=100&context=edit")
        if r.status_code == 200:
            blocks = r.json()
            for block in blocks:
                block_id = block.get("id")
                block_content = block.get("content", {}).get("raw", "")

                if '<h' in block_content.lower():
                    block_headings = _extract_headings_from_html(block_content)
                    for bh in block_headings:
                        key = (bh["level"], _normalize_text_for_comparison(bh["text"]))
                        if key not in found_sources:
                            found_sources[key] = {
                                "source": "reusable_block",
                                "source_details": {
                                    "block_id": block_id,
                                    "block_title": block.get("title", {}).get("raw", ""),
                                },
                                "fixable": True,  # Reusable blocks can be edited via REST API
                            }
    except Exception as exc:
        logger.warning("analyze_heading_sources_blocks_error", extra={
            "page_url": page_url, "error": str(exc)
        })

    # --- Build final heading list ---
    result["_debug"]["crawled_headings_normalized"] = [
        {"level": ch.get("level"), "text": ch.get("text", "")[:50], "normalized": _normalize_text_for_comparison(ch.get("text", ""))[:50]}
        for ch in crawled_headings
    ]

    # Also build a text-only index for fallback matching (when level changed)
    text_only_sources: dict[str, dict] = {}
    for (lvl, norm_text), source_info in found_sources.items():
        if norm_text not in text_only_sources:
            text_only_sources[norm_text] = {**source_info, "found_level": lvl}

    for ch in crawled_headings:
        level = ch.get("level")
        text = ch.get("text", "")
        norm_text = _normalize_text_for_comparison(text)
        key = (level, norm_text)

        if key in found_sources:
            # Exact match (level + text)
            source_info = found_sources[key]
            result["headings"].append({
                "level": level,
                "text": text,
                **source_info,
            })
        elif norm_text in text_only_sources:
            # Text matches but level differs (heading was changed)
            source_info = text_only_sources[norm_text]
            found_level = source_info.get("found_level")
            result["headings"].append({
                "level": level,
                "text": text,
                "source": source_info.get("source"),
                "fixable": source_info.get("fixable", False),
                "source_details": {
                    **source_info.get("source_details", {}),
                    "note": f"Text found as H{found_level} in content (crawled as H{level})",
                },
            })
        else:
            result["headings"].append({
                "level": level,
                "text": text,
                "source": "unknown",
                "source_details": {
                    "note": "Not found in post content, widgets, ACF fields, or reusable blocks. "
                            "May be in theme template, plugin output, or shortcode."
                },
                "fixable": False,
            })

    return result


# ---------------------------------------------------------------------------
# Heading → bold conversion
# ---------------------------------------------------------------------------

def _heading_to_bold_in_content(
    raw_content: str,
    heading_text: str | None = None,
    level: int = 4,
) -> tuple[str, int]:
    """Convert headings of a specific level to bold paragraphs in *raw_content*.

    If *heading_text* is given (plain text, no HTML tags), only the heading whose
    stripped inner text matches is converted.  Otherwise all headings at *level* are converted.

    Handles both Gutenberg block syntax and classic-editor HTML.

    Returns (updated_content, number_of_replacements).
    """
    if not (1 <= level <= 6):
        return raw_content, 0

    count = 0
    target_normalized = _normalize_text_for_comparison(heading_text) if heading_text is not None else None

    def _matches(inner_html: str) -> bool:
        if target_normalized is None:
            return True
        plain = html_module.unescape(re.sub(r"<[^>]+>", "", inner_html)).strip()
        return _normalize_text_for_comparison(plain) == target_normalized

    updated = raw_content

    # ── Gutenberg heading blocks ──────────────────────────────────────────
    # For H2 (default level), match blocks without explicit level OR with "level":2
    # For other levels, require explicit "level":N
    if level == 2:
        # Match either no "level" key (default H2) or explicit "level":2
        gutenberg_re = re.compile(
            r'<!-- wp:heading(?:\s+\{[^}]*\})?\s*-->'
            rf'\s*<h{level}[^>]*>(.*?)</h{level}>\s*'
            r'<!-- /wp:heading -->',
            re.DOTALL,
        )
    else:
        gutenberg_re = re.compile(
            rf'<!-- wp:heading \{{[^}}]*"level"\s*:\s*{level}[^}}]*\}} -->'
            rf'\s*<h{level}[^>]*>(.*?)</h{level}>\s*'
            r'<!-- /wp:heading -->',
            re.DOTALL,
        )

    def _replace_gutenberg(m: re.Match) -> str:
        nonlocal count
        inner = m.group(1)
        if not _matches(inner):
            return m.group(0)
        count += 1
        return (
            f'<!-- wp:paragraph -->\n'
            f'<p><strong>{inner}</strong></p>\n'
            f'<!-- /wp:paragraph -->'
        )

    updated = gutenberg_re.sub(_replace_gutenberg, updated)

    # ── Classic editor heading tags ───────────────────────────────────────
    classic_re = re.compile(rf'<h{level}(?:\s[^>]*)?>(.+?)</h{level}>', re.DOTALL)

    def _replace_classic(m: re.Match) -> str:
        nonlocal count
        inner = m.group(1)
        if not _matches(inner):
            return m.group(0)
        count += 1
        return f'<p><strong>{inner}</strong></p>'

    updated = classic_re.sub(_replace_classic, updated)

    return updated, count


async def convert_heading_to_bold(
    wp: WPClient,
    page_url: str,
    heading_text: str | None = None,
    level: int = 4,
) -> dict:
    """Convert headings of a specific level in a WordPress post to bold paragraphs.

    If *heading_text* is provided, only that specific heading is changed.
    If None, all headings at *level* on the page are converted.

    Returns a dict with keys: success, changed, error.
    """
    if not (1 <= level <= 6):
        return {"success": False, "changed": 0, "error": "Heading level must be between 1 and 6"}

    post_info = await find_post_by_url(wp, page_url)
    if not post_info:
        return {"success": False, "changed": 0, "error": f"Could not find WordPress post for: {page_url}"}

    post_type     = post_info["type"]
    post_id       = post_info["id"]
    endpoint_base = "pages" if post_type == "page" else "posts"

    try:
        r = await wp.get(f"{endpoint_base}/{post_id}?context=edit&_fields=content")
        if r.status_code != 200:
            body = r.json()
            return {"success": False, "changed": 0,
                    "error": body.get("message", f"HTTP {r.status_code} fetching content")}
        raw_content = r.json().get("content", {}).get("raw", "")
    except Exception as exc:
        return {"success": False, "changed": 0, "error": f"Error fetching content: {exc}"}

    updated_content, changed = _heading_to_bold_in_content(raw_content, heading_text, level)

    if changed == 0:
        target = f'H{level} "{heading_text}"' if heading_text else f"any H{level} headings"
        return {"success": False, "changed": 0,
                "error": f"No matching {target} found in post content"}

    try:
        r = await wp.patch(
            f"{endpoint_base}/{post_id}",
            json={"content": updated_content},
        )
        if r.status_code == 200:
            return {"success": True, "changed": changed, "error": None}
        body = r.json()
        return {"success": False, "changed": 0,
                "error": body.get("message", f"HTTP {r.status_code}: {r.text[:120]}")}
    except Exception as exc:
        return {"success": False, "changed": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Change heading level
# ---------------------------------------------------------------------------

def _change_heading_level_in_content(
    raw_content: str,
    heading_text: str,
    from_level: int,
    to_level: int,
) -> tuple[str, int]:
    """Change the level of a specific heading in *raw_content*.

    Matches by plain text content (HTML tags stripped from inner HTML before
    comparing, with HTML entities decoded to match what BeautifulSoup returns).
    Handles both Gutenberg block syntax and classic-editor HTML.

    Returns (updated_content, number_of_replacements).
    """
    count = 0
    # Normalise the target text for whitespace-agnostic comparison
    target_normalized = _normalize_text_for_comparison(heading_text)

    def _matches(inner_html: str) -> bool:
        plain = html_module.unescape(re.sub(r"<[^>]+>", "", inner_html)).strip()
        return _normalize_text_for_comparison(plain) == target_normalized

    updated = raw_content

    # ── Gutenberg heading blocks ──────────────────────────────────────────
    # Use `.*?-->` to capture the block comment so that nested JSON objects
    # (e.g. {"level":1,"style":{"color":"red"}}) don't break the match.
    # The terminator `-->` is unique — JSON attribute values never contain it.
    # This single pattern covers:
    #   A) explicit level:  <!-- wp:heading {"level":N, ...} -->
    #   B) default H2:      <!-- wp:heading --> or <!-- wp:heading {..., no "level"} -->
    gutenberg_re = re.compile(
        r'(<!-- wp:heading.*?-->)'               # open block comment (any attrs, incl. nested JSON)
        rf'(\s*<h{from_level}(?:\s[^>]*)?>)(.*?)(</h{from_level}>)'
        r'(\s*<!-- /wp:heading -->)',
        re.DOTALL,
    )

    def _replace_gutenberg(m: re.Match) -> str:
        nonlocal count
        block_comment = m.group(1)
        inner = m.group(3)  # heading text content

        # Verify this block has the right level:
        #   - explicit "level":from_level in the block attrs, OR
        #   - from_level==2 and no "level" key (H2 is the Gutenberg default)
        has_explicit = bool(re.search(rf'"level"\s*:\s*{from_level}\b', block_comment))
        has_default_h2 = (from_level == 2 and '"level"' not in block_comment)
        if not (has_explicit or has_default_h2):
            return m.group(0)

        if not _matches(inner):
            return m.group(0)

        count += 1

        # Update the block comment level
        if has_explicit:
            new_comment = re.sub(
                rf'"level"\s*:\s*{from_level}',
                f'"level":{to_level}',
                block_comment,
                count=1,
            )
        else:
            # H2 default — inject "level":to_level into the JSON
            if '{' in block_comment:
                new_comment = re.sub(r'(\{)', rf'\1"level":{to_level},', block_comment, count=1)
            else:
                new_comment = block_comment.replace(
                    '<!-- wp:heading -->',
                    f'<!-- wp:heading {{"level":{to_level}}} -->',
                )

        opening = re.sub(rf'<h{from_level}', f'<h{to_level}', m.group(2), count=1)  # group 2 is opening tag
        return f'{new_comment}{opening}{inner}</h{to_level}>{m.group(5)}'

    updated = gutenberg_re.sub(_replace_gutenberg, updated)

    # ── Classic editor heading tags ───────────────────────────────────────
    classic_re = re.compile(
        rf'<h{from_level}((?:\s[^>]*)?)>(.+?)</h{from_level}>',
        re.DOTALL,
    )

    def _replace_classic(m: re.Match) -> str:
        nonlocal count
        attrs = m.group(1)
        inner = m.group(2)
        if not _matches(inner):
            return m.group(0)
        count += 1
        return f'<h{to_level}{attrs}>{inner}</h{to_level}>'

    updated = classic_re.sub(_replace_classic, updated)

    return updated, count


async def change_heading_level(
    wp: WPClient,
    page_url: str,
    heading_text: str,
    from_level: int,
    to_level: int,
) -> dict:
    """Change the level of a specific heading in a WordPress post.

    Finds the heading with matching plain text at *from_level* and changes it
    to *to_level*.  Handles Gutenberg blocks and classic editor HTML.

    Returns a dict with keys: success, changed, error.
    """
    if from_level == to_level:
        return {"success": False, "changed": 0, "error": "from_level and to_level are the same"}
    if not (1 <= from_level <= 6) or not (1 <= to_level <= 6):
        return {"success": False, "changed": 0, "error": "Heading levels must be between 1 and 6"}

    post_info = await find_post_by_url(wp, page_url)
    if not post_info:
        logger.warning(
            "change_heading_level_post_not_found",
            extra={"page_url": page_url, "heading_text": heading_text},
        )
        return {"success": False, "changed": 0,
                "error": f"Could not find WordPress post for: {page_url}"}

    post_type     = post_info["type"]
    post_id       = post_info["id"]
    endpoint_base = "pages" if post_type == "page" else "posts"

    try:
        r = await wp.get(f"{endpoint_base}/{post_id}?context=edit&_fields=content")
        if r.status_code != 200:
            body = r.json()
            return {"success": False, "changed": 0,
                    "error": body.get("message", f"HTTP {r.status_code} fetching content")}
        raw_content = r.json().get("content", {}).get("raw", "")
    except Exception as exc:
        return {"success": False, "changed": 0, "error": f"Error fetching content: {exc}"}

    updated_content, changed = _change_heading_level_in_content(
        raw_content, heading_text, from_level, to_level
    )

    if changed == 0:
        # Post content didn't have it — cascade to widgets, synced patterns, template parts
        for search_fn in (
            _fix_heading_in_widgets,
            _fix_heading_in_blocks,
            _fix_heading_in_template_parts,
        ):
            result = await search_fn(wp, heading_text, from_level, to_level)
            if result is not None:
                return result

        # Check if the heading text matches the post title (themes can render
        # titles at any heading level, not just H1).
        try:
            r_title = await wp.get(f"{endpoint_base}/{post_id}?_fields=title&context=edit")
            if r_title.status_code == 200:
                import html as _html
                post_title = r_title.json().get("title", {}).get("raw", "")
                if _text_matches(post_title, heading_text):
                    return {
                        "success": False,
                        "changed": 0,
                        "error": (
                            f'"{heading_text}" is the page/post title — your theme renders it as '
                            f"H{from_level} automatically. To change the heading level, "
                            "edit the theme template or use custom CSS. To change the text, "
                            "edit the page/post title in WordPress."
                        ),
                    }
        except Exception:
            pass

        return {
            "success": False,
            "changed": 0,
            "error": (
                f'H{from_level} "{heading_text}" was not found in the post content, '
                "block widgets, synced patterns, or theme template parts. "
                "This heading may be generated by your theme from the page title, "
                "a menu, or a template — edit it directly in WordPress admin."
            ),
        }

    try:
        r = await wp.patch(
            f"{endpoint_base}/{post_id}",
            json={"content": updated_content},
        )
        if r.status_code == 200:
            logger.info(
                "change_heading_level_success",
                extra={"page_url": page_url, "heading_text": heading_text,
                       "from": from_level, "to": to_level, "location": "post"},
            )
            return {"success": True, "changed": changed, "location": "post", "error": None}
        body = r.json()
        err_msg = body.get("message", f"HTTP {r.status_code}: {r.text[:200]}")
        logger.warning(
            "change_heading_level_patch_failed",
            extra={"page_url": page_url, "status": r.status_code, "error": err_msg},
        )
        return {"success": False, "changed": 0, "error": err_msg}
    except Exception as exc:
        return {"success": False, "changed": 0, "error": str(exc)}


async def change_heading_text(
    wp: WPClient,
    page_url: str,
    old_text: str,
    new_text: str,
    level: int = 1,
) -> dict:
    """Change the text of a heading in a WordPress post.

    Finds the heading at *level* with *old_text* and replaces the inner text
    with *new_text*.  Handles Gutenberg blocks and classic editor HTML.

    Returns a dict with keys: success, changed, error.
    """
    if not new_text.strip():
        return {"success": False, "changed": 0, "error": "New heading text cannot be empty"}

    post_info = await find_post_by_url(wp, page_url)
    if not post_info:
        return {"success": False, "changed": 0,
                "error": f"Could not find WordPress post for: {page_url}"}

    post_type     = post_info["type"]
    post_id       = post_info["id"]
    endpoint_base = "pages" if post_type == "page" else "posts"

    try:
        r = await wp.get(f"{endpoint_base}/{post_id}?context=edit&_fields=content,title")
        if r.status_code != 200:
            body = r.json()
            return {"success": False, "changed": 0,
                    "error": body.get("message", f"HTTP {r.status_code} fetching content")}
        data = r.json()
        raw_content = data.get("content", {}).get("raw", "")
        post_title = data.get("title", {}).get("raw", "")
    except Exception as exc:
        return {"success": False, "changed": 0, "error": f"Error fetching content: {exc}"}

    # Check if the heading is actually the post title (theme renders it as H1)
    import html as _html
    def _norm(t): return re.sub(r'\s+', ' ', _html.unescape(t)).strip()
    if _norm(post_title) == _norm(old_text):
        # Update the post title field directly
        try:
            r = await wp.patch(
                f"{endpoint_base}/{post_id}",
                json={"title": new_text.strip()},
            )
            if r.status_code == 200:
                return {"success": True, "changed": 1, "location": "post_title", "error": None}
            body = r.json()
            return {"success": False, "changed": 0,
                    "error": body.get("message", f"HTTP {r.status_code}")}
        except Exception as exc:
            return {"success": False, "changed": 0, "error": str(exc)}

    # Replace in post content
    import html as html_module

    def _normalize_for_compare(text: str) -> str:
        """Normalize heading text for fuzzy comparison.

        Handles differences caused by inline HTML tags (<strong>, etc.)
        eating whitespace at tag boundaries, e.g. the crawler sees
        "Reactivity& Relationships" while WP content has
        "<strong>Reactivity</strong> &amp; Relationships".
        Strips ALL whitespace so spacing diffs don't matter.
        """
        return re.sub(r'\s+', '', html_module.unescape(text)).strip()

    norm_old = _normalize_for_compare(old_text)

    count = 0
    def _replace_text(m: re.Match) -> str:
        nonlocal count
        inner = m.group(2)
        plain = _normalize_for_compare(re.sub(r'<[^>]+>', '', inner))
        if plain != norm_old:
            return m.group(0)
        count += 1
        attrs = m.group(1) or ''  # group(1) is None when <h1> has no attributes
        return f'<h{level}{attrs}>{new_text.strip()}</h{level}>'

    pattern = re.compile(
        rf'<h{level}(\s[^>]*)?>(.+?)</h{level}>',
        re.IGNORECASE | re.DOTALL,
    )
    updated_content = pattern.sub(_replace_text, raw_content)

    # Also handle Gutenberg heading blocks
    gb_pattern = re.compile(
        rf'("content"\s*:\s*")<h{level}[^>]*?>.*?</h{level}>(")' ,
        re.IGNORECASE,
    )
    for m in gb_pattern.finditer(raw_content):
        block_html = m.group(0)
        inner_plain = html_module.unescape(re.sub(r'<[^>]+>', '', block_html)).strip()
        if norm_old in inner_plain:
            # Already handled by HTML replacement above
            pass

    if count == 0:
        return {"success": False, "changed": 0,
                "error": f'H{level} "{old_text}" was not found in the post content.'}

    try:
        r = await wp.patch(
            f"{endpoint_base}/{post_id}",
            json={"content": updated_content},
        )
        if r.status_code == 200:
            return {"success": True, "changed": count, "location": "post", "error": None}
        body = r.json()
        return {"success": False, "changed": 0,
                "error": body.get("message", f"HTTP {r.status_code}")}
    except Exception as exc:
        return {"success": False, "changed": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Cascade helpers: fix heading in shared WordPress content areas
# ---------------------------------------------------------------------------

async def _fix_heading_in_widgets(
    wp: WPClient,
    heading_text: str,
    from_level: int,
    to_level: int,
) -> dict | None:
    """Search block widgets for *heading_text* at H*from_level* and change it.

    Returns a success dict on first match, or None if not found / on error.
    Block widgets store Gutenberg markup in ``content.raw``.
    Classic (non-block) widgets are not editable via this route.
    """
    try:
        r = await wp.get("widgets?per_page=100&context=edit")
        if r.status_code != 200:
            return None
        widgets = r.json()
        if not isinstance(widgets, list):
            return None
    except Exception:
        return None

    for widget in widgets:
        raw_content = (widget.get("content") or {}).get("raw", "")
        if not raw_content:
            continue
        updated, changed = _change_heading_level_in_content(raw_content, heading_text, from_level, to_level)
        if changed == 0:
            continue
        widget_id = widget.get("id", "")
        try:
            # Try raw-object format first (block widget); fall back to string
            r2 = await wp.patch(
                f"widgets/{widget_id}",
                json={"content": {"raw": updated}},
            )
            if r2.status_code != 200:
                r2 = await wp.patch(
                    f"widgets/{widget_id}",
                    json={"content": updated},
                )
            if r2.status_code == 200:
                label = widget.get("description") or widget.get("id_base") or str(widget_id)
                return {
                    "success": True,
                    "changed": changed,
                    "location": "widget",
                    "location_label": f"block widget \"{label}\"",
                    "shared": True,
                    "error": None,
                }
        except Exception:
            pass
    return None


async def _fix_heading_in_blocks(
    wp: WPClient,
    heading_text: str,
    from_level: int,
    to_level: int,
) -> dict | None:
    """Search synced patterns (reusable blocks) for the heading and change it.

    Returns a success dict on first match, or None if not found / on error.
    """
    try:
        r = await wp.get("blocks?per_page=100&context=edit")
        if r.status_code != 200:
            return None
        blocks = r.json()
        if not isinstance(blocks, list):
            return None
    except Exception:
        return None

    for block in blocks:
        raw_content = (block.get("content") or {}).get("raw", "")
        if not raw_content:
            continue
        updated, changed = _change_heading_level_in_content(raw_content, heading_text, from_level, to_level)
        if changed == 0:
            continue
        block_id = block.get("id")
        try:
            r2 = await wp.patch(f"blocks/{block_id}", json={"content": updated})
            if r2.status_code == 200:
                title = (block.get("title") or {}).get("rendered", "") or str(block_id)
                return {
                    "success": True,
                    "changed": changed,
                    "location": "block",
                    "location_label": f"synced pattern \"{title}\"",
                    "shared": True,
                    "error": None,
                }
        except Exception:
            pass
    return None


async def _fix_heading_in_template_parts(
    wp: WPClient,
    heading_text: str,
    from_level: int,
    to_level: int,
) -> dict | None:
    """Search FSE template parts (header, footer, sidebar, etc.) for the heading.

    Returns a success dict on first match, or None if not found / on error.
    Only applies to block-based (Full Site Editing) themes.
    """
    try:
        r = await wp.get("template-parts?per_page=100&context=edit")
        if r.status_code != 200:
            return None
        parts = r.json()
        if not isinstance(parts, list):
            return None
    except Exception:
        return None

    for part in parts:
        raw_content = (part.get("content") or {}).get("raw", "")
        if not raw_content:
            continue
        updated, changed = _change_heading_level_in_content(raw_content, heading_text, from_level, to_level)
        if changed == 0:
            continue
        part_id = part.get("id", "")
        try:
            r2 = await wp.patch(
                f"template-parts/{part_id}",
                json={"content": {"raw": updated, "rendered": ""}},
            )
            if r2.status_code == 200:
                title = (part.get("title") or {}).get("rendered", "") or str(part_id)
                return {
                    "success": True,
                    "changed": changed,
                    "location": "template_part",
                    "location_label": f"template part \"{title}\"",
                    "shared": True,
                    "error": None,
                }
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Image metadata helpers
# ---------------------------------------------------------------------------

async def find_attachment_by_url(wp: WPClient, image_url: str, cache_bust: bool = False) -> dict | None:
    """Resolve an image URL to a WordPress media attachment.

    Tries the source_url filter first (exact match), then falls back to a
    filename search.  Returns a dict with keys: id, source_url, alt_text,
    title, caption, admin_url.  Returns None if not found.
    """
    from urllib.parse import urlparse, unquote
    import time

    # Add cache-busting parameter if requested
    cache_param = f"&_nocache={int(time.time() * 1000)}" if cache_bust else ""

    # Extract filename and convert to WordPress slug format
    filename = unquote(urlparse(image_url).path.split("/")[-1])
    # Remove extension first
    name_no_ext = re.sub(r'\.[^.]+$', '', filename).lower()
    # Strip WordPress size suffix (e.g. "-600x403", "-1024x683", "-150x150")
    name_base = re.sub(r'-\d+x\d+$', '', name_no_ext)
    # WordPress slug: special chars become hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name_base).strip('-')

    # Also build a slug from the raw name (with size suffix) as fallback
    slug_with_size = re.sub(r'[^a-z0-9]+', '-', name_no_ext).strip('-')

    print(f"[WP FETCH] Looking for image: {image_url}")
    print(f"[WP FETCH] Filename: {filename}, slug: {slug}")

    # Build the expected source_url (original without size suffix) for matching
    # e.g. dissappointment-600x403.jpg → dissappointment.jpg
    image_path = urlparse(image_url).path
    ext_match = re.search(r'\.[^.]+$', filename)
    ext = ext_match.group(0) if ext_match else ''
    base_url = image_url.replace(filename, name_base + ext) if name_base != name_no_ext else None

    try:
        # Try base slug first (without size suffix), then with size suffix
        slugs_to_try = [slug]
        if slug_with_size != slug:
            slugs_to_try.append(slug_with_size)

        for try_slug in slugs_to_try:
            print(f"[WP FETCH] Querying WordPress by slug={try_slug}")
            r = await wp.get(
                f"media?slug={try_slug}&_fields=id,source_url,alt_text,title,caption,description{cache_param}"
            )

            if r.status_code != 200:
                print(f"[WP FETCH] WordPress API error: {r.status_code}")
                continue

            items = r.json()
            print(f"[WP FETCH] WordPress returned {len(items)} items")

            if not items:
                continue

            # Check each item for URL match
            for item in items:
                wp_data = _attachment_dict(item, wp.site_url)
                wp_url = wp_data.get('source_url', '')
                wp_id = wp_data.get('id')

                print(f"[WP FETCH] Checking item {wp_id}: {wp_url}")

                # Exact match
                if wp_url == image_url:
                    print(f"[WP FETCH] ✓ EXACT MATCH! WP ID: {wp_id}")
                    return wp_data

                # Size-variant match: page uses e.g. img-600x403.jpg,
                # WP source_url is img.jpg (same directory, same base name)
                if base_url and wp_url == base_url:
                    print(f"[WP FETCH] ✓ SIZE-VARIANT MATCH! WP ID: {wp_id}")
                    return wp_data

                # Same directory + base filename match (handles URL encoding diffs)
                wp_path = urlparse(wp_url).path
                wp_dir = wp_path.rsplit('/', 1)[0] if '/' in wp_path else ''
                img_dir = image_path.rsplit('/', 1)[0] if '/' in image_path else ''
                if wp_dir == img_dir:
                    wp_base = re.sub(r'-\d+x\d+(?=\.[^.]+$)', '', wp_path.rsplit('/', 1)[-1])
                    img_base = re.sub(r'-\d+x\d+(?=\.[^.]+$)', '', image_path.rsplit('/', 1)[-1])
                    if wp_base == img_base:
                        print(f"[WP FETCH] ✓ DIRECTORY+BASENAME MATCH! WP ID: {wp_id}")
                        return wp_data

        print(f"[WP FETCH] ✗ No match found for {image_url}")
        return None
    except Exception as e:
        print(f"[WP FETCH] Exception: {e}")
        return None


def _attachment_dict(item: dict, site_url: str) -> dict:
    import re

    def strip_html(text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()

    att_id = item["id"]

    # Get rendered fields and strip HTML
    title_raw = item.get("title", {}).get("rendered", "")
    caption_raw = item.get("caption", {}).get("rendered", "")
    description_raw = item.get("description", {}).get("rendered", "")

    print(f"[WP PARSE] Media ID {att_id}:")
    print(f"  - Title raw: {title_raw[:100] if title_raw else '(empty)'}")
    print(f"  - Caption raw: {caption_raw[:100] if caption_raw else '(empty)'}")
    print(f"  - Description raw: {description_raw[:100] if description_raw else '(empty)'}")

    return {
        "id":          att_id,
        "source_url":  item.get("source_url", ""),
        "alt_text":    item.get("alt_text", ""),
        "title":       strip_html(title_raw),
        "caption":     strip_html(caption_raw),
        "description": strip_html(description_raw),
        "admin_url":   f"{site_url.rstrip('/')}/wp-admin/post.php?post={att_id}&action=edit",
    }


async def get_attachment_info(wp: WPClient, image_url: str, cache_bust: bool = False) -> dict:
    """Return attachment metadata for *image_url*, or an error dict."""
    att = await find_attachment_by_url(wp, image_url, cache_bust=cache_bust)
    if not att:
        return {"success": False, "error": f"No WordPress media attachment found for: {image_url}"}
    return {"success": True, **att}


async def update_image_metadata(
    wp: WPClient,
    image_url: str,
    alt_text: str | None = None,
    title: str | None = None,
    caption: str | None = None,
    description: str | None = None,
) -> dict:
    """Update alt text, title, caption, and/or description for a WordPress media attachment.

    Finds the attachment by URL, then PATCHes only the provided fields.
    Returns a dict with keys: success, id, error.
    """
    att = await find_attachment_by_url(wp, image_url)
    if not att:
        return {"success": False, "error": f"No WordPress media attachment found for: {image_url}"}

    payload: dict = {}
    if alt_text is not None:
        payload["alt_text"] = alt_text
    if title is not None:
        payload["title"] = title
    if caption is not None:
        payload["caption"] = caption
    if description is not None:
        payload["description"] = description

    if not payload:
        return {"success": False, "error": "No fields to update."}

    try:
        r = await wp.patch(f"media/{att['id']}", json=payload)
        if r.status_code == 200:
            updated = r.json()
            return {
                "success":  True,
                "id":       att["id"],
                "alt_text": updated.get("alt_text", ""),
                "title":    updated.get("title", {}).get("rendered", ""),
                "caption":  updated.get("caption", {}).get("rendered", ""),
                "description": updated.get("description", {}).get("rendered", ""),
                "error":    None,
            }
        body = r.json()
        return {"success": False, "error": body.get("message", f"HTTP {r.status_code}")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def optimize_media_item(
    wp: WPClient,
    image_url: str,
    target_width: int | None = None,
    new_filename: str | None = None,
    job_id: str | None = None,
    store: SQLiteJobStore | RedisJobStore | None = None,
) -> dict:
    """Download, optimize (optionally rename), re-upload, and replace an image in WordPress.

    Workflow:
    1. Resolve attachment ID.
    2. Download to temp file.
    3. Run ImageOptimizer (converts to WebP).
    4. If new_filename is provided, rename the optimized file before upload.
    5. Upload optimized version.
    6. Replace URL in all posts using the original.
    7. Delete original attachment.

    Returns {success: bool, old_url, new_url, new_id, replacements}.
    """
    from api.services.image_processor import ImageOptimizer
    import tempfile
    import os
    import httpx

    # 1. Resolve attachment
    att = await find_attachment_by_url(wp, image_url)
    if not att:
        return {"success": False, "error": f"No WP attachment found for: {image_url}"}

    old_att_id = att["id"]
    old_url = att["source_url"]

    # 2. Download to temp
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        filename = os.path.basename(urlparse(old_url).path)
        input_path = tmp_path / filename

        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(old_url)
                res.raise_for_status()
                with open(input_path, "wb") as f:
                    f.write(res.content)
        except Exception as exc:
            return {"success": False, "error": f"Failed to download image: {exc}"}

        # 3. Optimize
        optimizer = ImageOptimizer(archive_path=tmp_path / "archive")
        output_path = optimizer.optimize(input_path, target_width=target_width)
        if not output_path:
            # If optimization failed or was skipped (no gain), we might still want to rename.
            # But currently, we only proceed if optimization happened.
            return {"success": False, "error": "Image optimization skipped (no size gain) or failed."}

        # 4. Handle Rename (if requested)
        if new_filename:
            # Ensure new_filename ends with .webp since optimizer converts it
            if not new_filename.lower().endswith(".webp"):
                new_filename = os.path.splitext(new_filename)[0] + ".webp"
            
            final_upload_path = output_path.with_name(new_filename)
            output_path.rename(final_upload_path)
            output_path = final_upload_path

        # 5. Upload new version
        new_media = await wp.upload_media(
            output_path,
            title=att.get("title"),
            alt_text=att.get("alt_text")
        )
        if not new_media:
            return {"success": False, "error": "Failed to upload optimized image to WordPress."}

        new_url = new_media.get("source_url")
        new_id = new_media.get("id")

        # 6. Replace URLs in content
        # Find exactly which pages use this image
        replaced_count = 0
        target_pages = []
        if job_id and store:
            pages = await store.get_pages(job_id)
            for p in pages:
                # Store the full image URLs in image_urls, so we check for old_url
                if old_url in p.image_urls:
                    target_pages.append(p.url)
        
        if target_pages:
            for p_url in target_pages:
                success, _ = await replace_link_in_post(wp, p_url, old_url, new_url)
                if success:
                    replaced_count += 1
        else:
            # Fallback: simple search in WP API (might be slow)
            pass

        # 7. Delete old attachment
        await wp.delete_media(old_att_id)

        return {
            "success": True,
            "old_url": old_url,
            "new_url": new_url,
            "new_id": new_id,
            "replacements": replaced_count
        }


# ---------------------------------------------------------------------------
# Image Optimization Module v1.9.1 - Two Workflow Functions
# ---------------------------------------------------------------------------

async def optimize_existing_image(
    wp: WPClient,
    image_url: str,
    page_urls: list[str],
    geo_config: "GeoConfig | None" = None,
    target_width: int = 1200,
    apply_gps: bool = True,
    seo_keyword: str | None = None,
    archive_path: Path | None = None,
    generate_geo_metadata: bool = False,
    page_h1: str = "",
    surrounding_text: str = "",
) -> dict:
    """
    Workflow A: Optimize an existing WordPress image.

    Downloads from WP, optimizes, uploads NEW version. Original STAYS in WP.
    User must manually replace the old image on pages.

    Args:
        wp: Authenticated WPClient
        image_url: URL of existing image in WordPress
        page_urls: List of page URLs where image is used (for user reference)
        geo_config: GeoConfig for GPS coordinates and metadata
        target_width: Max width after resize (default 1200)
        apply_gps: Whether to inject GPS EXIF (default True)
        seo_keyword: Keyword for SEO filename (optional)
        archive_path: Path to save original and optimized copies
        generate_geo_metadata: Whether to generate AI alt text, description, caption
        page_h1: H1 heading from the page (for GEO context)
        surrounding_text: Text context around the image (for GEO context)

    Returns:
        {
            success: bool,
            old_url: str (stays in WP),
            new_url: str (new optimized),
            new_media_id: int,
            page_urls: list[str] (where to replace),
            archive_paths: {original: str, optimized: str},
            file_size_kb: float,
            message: str,
            error: str | None,
            geo_metadata: {alt_text, description, caption} | None,
        }
    """
    from api.services.image_processor import ImageOptimizer, generate_seo_filename
    from api.services.exif_injector import inject_gps_coordinates, get_gps_from_geo_config
    from api.services.upload_validator import validate_for_upload
    import tempfile
    import shutil
    import httpx

    result = {
        "success": False,
        "old_url": image_url,
        "new_url": None,
        "new_media_id": None,
        "page_urls": page_urls,
        "archive_paths": {"original": None, "optimized": None},
        "file_size_kb": 0,
        "message": "",
        "error": None,
        "geo_metadata": None,
    }

    # Setup archive directory
    if archive_path:
        archive_path = Path(archive_path)
        (archive_path / "originals").mkdir(parents=True, exist_ok=True)
        (archive_path / "optimized").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Download original
        original_filename = Path(urlparse(image_url).path).name
        input_path = tmp_path / original_filename

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(image_url)
                res.raise_for_status()
                with open(input_path, "wb") as f:
                    f.write(res.content)
        except Exception as exc:
            result["error"] = f"Failed to download image: {exc}"
            return result

        # 2. Archive original
        if archive_path:
            original_archive = archive_path / "originals" / original_filename
            shutil.copy2(input_path, original_archive)
            result["archive_paths"]["original"] = str(original_archive)

        # 3. Optimize (resize + WebP)
        optimizer = ImageOptimizer()
        output_path = optimizer.optimize(
            input_path,
            target_width=target_width,
            delete_original=False,  # Keep original for archiving
        )

        if not output_path:
            result["error"] = "Optimization failed or no size reduction achieved"
            return result

        # 4. Generate SEO filename
        city = geo_config.primary_location if geo_config else ""
        if seo_keyword or city:
            seo_name = generate_seo_filename(
                original_filename,
                keyword=seo_keyword or "",
                city=city,
            )
            final_path = output_path.with_name(seo_name)
            output_path.rename(final_path)
            output_path = final_path

        # 5. Inject GPS EXIF
        if apply_gps and geo_config:
            gps_coords = get_gps_from_geo_config(geo_config)
            if gps_coords:
                try:
                    inject_gps_coordinates(output_path, gps_coords[0], gps_coords[1])
                except Exception as exc:
                    logger.warning(f"GPS injection failed: {exc}")
                    # Continue without GPS

        # 6. Validate before upload
        validation = validate_for_upload(output_path, require_gps=apply_gps)
        if not validation.is_valid:
            result["error"] = f"Validation failed: {', '.join(validation.errors)}"
            return result

        result["file_size_kb"] = validation.file_size_kb

        # 7. Archive optimized
        if archive_path:
            optimized_archive = archive_path / "optimized" / output_path.name
            shutil.copy2(output_path, optimized_archive)
            result["archive_paths"]["optimized"] = str(optimized_archive)

        # 8. Upload to WordPress (NEW file, don't delete old)
        new_media = await wp.upload_media(output_path)
        if not new_media:
            result["error"] = "Failed to upload optimized image to WordPress"
            return result

        result["new_url"] = new_media.get("source_url")
        result["new_media_id"] = new_media.get("id")
        result["success"] = True

        # 9. Generate GEO AI metadata if requested
        if generate_geo_metadata and geo_config and result["new_media_id"]:
            try:
                from api.services.ai_analyzer import analyze_image_with_geo

                # Convert GeoConfig to dict for AI analyzer
                geo_dict = {
                    "org_name": geo_config.org_name if hasattr(geo_config, 'org_name') else geo_config.get("org_name", ""),
                    "primary_location": geo_config.primary_location if hasattr(geo_config, 'primary_location') else geo_config.get("primary_location", ""),
                    "location_pool": geo_config.location_pool if hasattr(geo_config, 'location_pool') else geo_config.get("location_pool", []),
                    "topic_entities": geo_config.topic_entities if hasattr(geo_config, 'topic_entities') else geo_config.get("topic_entities", []),
                }

                geo_result = await analyze_image_with_geo(
                    image_url=result["new_url"],
                    page_h1=page_h1,
                    surrounding_text=surrounding_text,
                    geo_config=geo_dict,
                )

                if geo_result.get("success"):
                    alt_text = geo_result.get("alt_text", "")
                    long_desc = geo_result.get("long_description", "")

                    # Update WordPress media with GEO metadata
                    await wp.update_media_metadata(
                        media_id=result["new_media_id"],
                        alt_text=alt_text,
                        description=long_desc,
                        caption=alt_text[:200] if alt_text else None,  # Caption is shorter version
                    )

                    result["geo_metadata"] = {
                        "alt_text": alt_text,
                        "description": long_desc,
                        "caption": alt_text[:200] if alt_text else "",
                        "entities_used": geo_result.get("entities_used", []),
                    }
                    logger.info("geo_metadata_applied", extra={"media_id": result["new_media_id"]})
                else:
                    logger.warning("geo_metadata_failed", extra={"error": geo_result.get("error")})
            except Exception as exc:
                logger.warning("geo_metadata_error", extra={"error": str(exc)})
                # Don't fail the whole operation if GEO fails

        # Build user message
        if page_urls:
            pages_str = ", ".join(page_urls[:3])
            if len(page_urls) > 3:
                pages_str += f" (+{len(page_urls) - 3} more)"
            result["message"] = f"Optimized image uploaded. Replace on: {pages_str}"
        else:
            result["message"] = "Optimized image uploaded. Link it to your pages manually."

        return result


async def optimize_local_image(
    wp: WPClient,
    local_path: Path,
    geo_config: "GeoConfig | None" = None,
    target_width: int = 1200,
    apply_gps: bool = True,
    seo_keyword: str | None = None,
    archive_path: Path | None = None,
    generate_geo_metadata: bool = False,
) -> dict:
    """
    Workflow B: Optimize a local image and upload to WordPress.

    Takes a local file, optimizes it, uploads to WP. Only 1 file in WP.

    Args:
        wp: Authenticated WPClient
        local_path: Path to local image file
        geo_config: GeoConfig for GPS coordinates
        target_width: Max width after resize (default 1200)
        apply_gps: Whether to inject GPS EXIF (default True)
        seo_keyword: Keyword for SEO filename (optional)
        archive_path: Path to save original and optimized copies
        generate_geo_metadata: Whether to generate AI alt text, description, caption

    Returns:
        {
            success: bool,
            new_url: str,
            new_media_id: int,
            archive_paths: {original: str, optimized: str},
            file_size_kb: float,
            message: str,
            error: str | None,
            geo_metadata: {alt_text, description, caption} | None,
        }
    """
    from api.services.image_processor import ImageOptimizer, generate_seo_filename
    from api.services.exif_injector import inject_gps_coordinates, get_gps_from_geo_config
    from api.services.upload_validator import validate_for_upload
    import tempfile
    import shutil

    local_path = Path(local_path)
    result = {
        "success": False,
        "new_url": None,
        "new_media_id": None,
        "archive_paths": {"original": None, "optimized": None},
        "file_size_kb": 0,
        "message": "",
        "error": None,
        "geo_metadata": None,
    }

    if not local_path.exists():
        result["error"] = f"File not found: {local_path}"
        return result

    # Setup archive directory
    if archive_path:
        archive_path = Path(archive_path)
        (archive_path / "originals").mkdir(parents=True, exist_ok=True)
        (archive_path / "optimized").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Copy to temp for processing
        original_filename = local_path.name
        input_path = tmp_path / original_filename
        shutil.copy2(local_path, input_path)

        # 2. Archive original
        if archive_path:
            original_archive = archive_path / "originals" / original_filename
            shutil.copy2(local_path, original_archive)
            result["archive_paths"]["original"] = str(original_archive)

        # 3. Optimize (resize + WebP)
        optimizer = ImageOptimizer()
        output_path = optimizer.optimize(
            input_path,
            target_width=target_width,
            delete_original=False,
        )

        if not output_path:
            result["error"] = "Optimization failed or no size reduction achieved"
            return result

        # 4. Generate SEO filename
        city = geo_config.primary_location if geo_config else ""
        if seo_keyword or city:
            seo_name = generate_seo_filename(
                original_filename,
                keyword=seo_keyword or "",
                city=city,
            )
            final_path = output_path.with_name(seo_name)
            output_path.rename(final_path)
            output_path = final_path

        # 5. Inject GPS EXIF
        if apply_gps and geo_config:
            gps_coords = get_gps_from_geo_config(geo_config)
            if gps_coords:
                try:
                    inject_gps_coordinates(output_path, gps_coords[0], gps_coords[1])
                except Exception as exc:
                    logger.warning(f"GPS injection failed: {exc}")

        # 6. Validate before upload
        validation = validate_for_upload(output_path, require_gps=apply_gps)
        if not validation.is_valid:
            result["error"] = f"Validation failed: {', '.join(validation.errors)}"
            return result

        result["file_size_kb"] = validation.file_size_kb

        # 7. Archive optimized
        if archive_path:
            optimized_archive = archive_path / "optimized" / output_path.name
            shutil.copy2(output_path, optimized_archive)
            result["archive_paths"]["optimized"] = str(optimized_archive)

        # 8. Upload to WordPress
        new_media = await wp.upload_media(output_path)
        if not new_media:
            result["error"] = "Failed to upload optimized image to WordPress"
            return result

        result["new_url"] = new_media.get("source_url")
        result["new_media_id"] = new_media.get("id")
        result["success"] = True
        result["message"] = "Image optimized and uploaded. Link it to your pages in WordPress."

        # 9. Generate GEO metadata if requested
        if generate_geo_metadata and geo_config and result["new_url"]:
            try:
                from api.services.ai_analyzer import analyze_image_with_geo

                geo_result = await analyze_image_with_geo(
                    image_url=result["new_url"],
                    page_h1="",  # No page context for local uploads
                    surrounding_text=seo_keyword or "",  # Use keyword as context
                    geo_config=geo_config,
                )

                if geo_result and geo_result.get("success"):
                    geo_data = geo_result.get("result", {})
                    alt_text = geo_data.get("alt_text", "")
                    description = geo_data.get("long_description", "")
                    caption = geo_data.get("caption", "")

                    # Update WordPress metadata
                    media_id = result["new_media_id"]
                    if media_id and (alt_text or description or caption):
                        await wp.update_media_metadata(
                            media_id=media_id,
                            alt_text=alt_text or None,
                            description=description or None,
                            caption=caption or None,
                        )

                    result["geo_metadata"] = {
                        "alt_text": alt_text,
                        "description": description,
                        "caption": caption,
                        "entities_used": geo_data.get("entities_used", []),
                    }
                else:
                    logger.warning(
                        "geo_metadata_skipped",
                        extra={"reason": geo_result.get("error", "Unknown")}
                    )
            except Exception as exc:
                logger.warning(f"GEO metadata generation failed: {exc}")

        return result


async def preview_optimization(
    image_url: str | None = None,
    local_path: Path | None = None,
    target_width: int = 1200,
) -> dict:
    """
    Preview optimization results without uploading.

    Args:
        image_url: URL of existing image (for Workflow A)
        local_path: Path to local file (for Workflow B)
        target_width: Target width for resize

    Returns:
        {
            original_size_kb: float,
            estimated_size_kb: float,
            original_dimensions: tuple,
            target_dimensions: tuple,
            savings_percent: float,
        }
    """
    from api.services.upload_validator import estimate_optimized_size
    from pathlib import Path
    from PIL import Image
    import tempfile
    import httpx

    result = {
        "original_size_kb": 0,
        "estimated_size_kb": 0,
        "original_dimensions": None,
        "target_dimensions": None,
        "savings_percent": 0,
    }

    temp_file = None

    try:
        if image_url:
            # Download to temp for analysis
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
                temp_file = Path(f.name)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.get(image_url)
                    res.raise_for_status()
                    f.write(res.content)
            file_path = temp_file
        elif local_path:
            file_path = Path(local_path)
            if not file_path.exists():
                return result
        else:
            return result

        # Get original stats
        result["original_size_kb"] = file_path.stat().st_size / 1024

        with Image.open(file_path) as img:
            width, height = img.size
            result["original_dimensions"] = (width, height)

            # Calculate target dimensions
            if width > target_width:
                scale = target_width / width
                target_height = int(height * scale)
                result["target_dimensions"] = (target_width, target_height)
            else:
                result["target_dimensions"] = (width, height)

        # Estimate optimized size
        result["estimated_size_kb"] = estimate_optimized_size(file_path, target_width)

        # Calculate savings
        if result["original_size_kb"] > 0:
            result["savings_percent"] = round(
                100 - (result["estimated_size_kb"] / result["original_size_kb"] * 100),
                1
            )

    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()

    return result
