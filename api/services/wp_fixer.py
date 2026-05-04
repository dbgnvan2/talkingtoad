"""
WordPress fix generation and application engine (v2.0).

Detects active SEO plugins, resolves page URLs to WP post IDs,
generates fix proposals from crawl issues, and applies approved
fixes via the WordPress REST API.

This module now delegates to specialized submodules:
- wp_shared: shared constants and data structures
- wp_title_fixer: title trimming and management
- wp_heading_fixer: heading analysis and manipulation
- wp_image_fixer: image metadata and optimization
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from api.services.wp_client import WPClient
from api.services.job_store import SQLiteJobStore, RedisJobStore

# Import shared constants and utilities
from api.services.wp_shared import (
    _FixSpec,
    _FIELD_SPECS,
    PREDEFINED_FIX_VALUES,
    _CODE_TO_FIELD,
    get_fixable_codes,
)

# Import title fixer functions
from api.services.wp_title_fixer import (
    trim_title,
    get_site_name,
    bulk_trim_titles,
    trim_title_one,
)

# Import heading fixer functions
from api.services.wp_heading_fixer import (
    analyze_heading_sources,
    change_heading_level,
    change_heading_text,
)

# Import image fixer functions
from api.services.wp_image_fixer import (
    find_attachment_by_url,
    get_attachment_info,
    update_image_metadata,
    optimize_existing_image,
    optimize_local_image,
    preview_optimization,
)

logger = logging.getLogger(__name__)


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
    except (RuntimeError, ValueError, KeyError) as exc:
        logger.debug(f"Fallback search API failed for {page_url}: {exc}")

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
        return_exceptions=True,
    )

    fixes: list[dict] = []
    skipped: list[str] = []
    for item, (page_url, _field) in zip(results, work_items):
        if isinstance(item, Exception):
            logger.warning(f"Failed to process {page_url}", exc_info=item)
            if page_url not in skipped:
                skipped.append(page_url)
        elif item is None:
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


# ─────────────────────────────────────────────────────────────────────────
# Re-exports for backward compatibility
# ─────────────────────────────────────────────────────────────────────────

__all__ = [
    # Shared
    "_FixSpec",
    "_FIELD_SPECS",
    "PREDEFINED_FIX_VALUES",
    "_CODE_TO_FIELD",
    "get_fixable_codes",
    # Plugin detection
    "detect_seo_plugin",
    # Post resolution
    "find_orphaned_media",
    "find_post_by_url",
    # Values
    "get_current_value",
    # Fix generation
    "_auto_propose",
    "generate_fixes",
    # Fix application
    "apply_fix",
    "replace_link_in_post",
    "_indexable_meta_value",
    # Title fixer (re-exported)
    "trim_title",
    "get_site_name",
    "bulk_trim_titles",
    "trim_title_one",
    # Heading fixer (re-exported)
    "analyze_heading_sources",
    "change_heading_level",
    "change_heading_text",
    # Image fixer (re-exported)
    "find_attachment_by_url",
    "get_attachment_info",
    "update_image_metadata",
    "optimize_existing_image",
    "optimize_local_image",
    "preview_optimization",
]
