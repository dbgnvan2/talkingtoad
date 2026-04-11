"""
WordPress fix generation and application engine (v2.0).

Detects active SEO plugins, resolves page URLs to WP post IDs,
generates fix proposals from crawl issues, and applies approved
fixes via the WordPress REST API.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

from api.services.wp_client import WPClient

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

async def find_post_by_url(wp: WPClient, page_url: str) -> dict | None:
    """Return {id, type} for the WP post/page matching *page_url*, or None."""
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
            for item in r.json():
                item_link = item.get("link", "").rstrip("/")
                if item_link == norm_url:
                    return {"id": item["id"], "type": post_type}
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


def _indexable_meta_value(seo_plugin: str) -> str | list:
    """Return the plugin-specific value that re-enables search indexing."""
    if seo_plugin == "yoast":
        return "0"   # 0 = use site default (index); 1 = noindex; 2 = force index
    if seo_plugin == "rank_math":
        return []    # empty robots array = no directives = index
    return ""
