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
# H4 → bold conversion
# ---------------------------------------------------------------------------

def _h4_to_bold_in_content(
    raw_content: str,
    heading_text: str | None = None,
) -> tuple[str, int]:
    """Convert H4 headings to bold paragraphs in *raw_content*.

    If *heading_text* is given (plain text, no HTML tags), only the H4 whose
    stripped inner text matches is converted.  Otherwise all H4s are converted.

    Handles both Gutenberg block syntax and classic-editor HTML.

    Returns (updated_content, number_of_replacements).
    """
    count = 0
    target_plain = html_module.unescape(heading_text).strip() if heading_text is not None else None

    def _matches(inner_html: str) -> bool:
        if target_plain is None:
            return True
        plain = html_module.unescape(re.sub(r"<[^>]+>", "", inner_html)).strip()
        return plain == target_plain

    updated = raw_content

    # ── Gutenberg H4 blocks ───────────────────────────────────────────────
    # <!-- wp:heading {"level":4,...} -->
    # <h4 class="wp-block-heading">TEXT</h4>
    # <!-- /wp:heading -->
    gutenberg_re = re.compile(
        r'<!-- wp:heading \{[^}]*"level"\s*:\s*4[^}]*\} -->'
        r'\s*<h4[^>]*>(.*?)</h4>\s*'
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

    # ── Classic editor H4 tags ────────────────────────────────────────────
    classic_re = re.compile(r'<h4(?:\s[^>]*)?>(.+?)</h4>', re.DOTALL)

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
) -> dict:
    """Convert H4 headings in a WordPress post to bold paragraphs.

    If *heading_text* is provided, only that specific H4 is changed.
    If None, all H4s on the page are converted.

    Returns a dict with keys: success, changed, error.
    """
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

    updated_content, changed = _h4_to_bold_in_content(raw_content, heading_text)

    if changed == 0:
        target = f'H4 "{heading_text}"' if heading_text else "any H4 headings"
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
    # Normalise the target text the same way BeautifulSoup does: strip tags and
    # decode HTML entities so "&amp;" == "&", "&nbsp;" == "\xa0", etc.
    target_plain = html_module.unescape(heading_text).strip()

    def _matches(inner_html: str) -> bool:
        plain = html_module.unescape(re.sub(r"<[^>]+>", "", inner_html)).strip()
        return plain == target_plain

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
        inner = m.group(4)

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

        opening = re.sub(rf'<h{from_level}', f'<h{to_level}', m.group(3), count=1)
        return f'{new_comment}\n{opening}{inner}</h{to_level}>{m.group(5)}'

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

        # Check if the heading text matches the post title (rendered as H1 by the theme,
        # not present in content.raw — it lives in the "title" field instead).
        try:
            r_title = await wp.get(f"{endpoint_base}/{post_id}?_fields=title&context=edit")
            if r_title.status_code == 200:
                import html as _html
                post_title = r_title.json().get("title", {}).get("raw", "")
                if _html.unescape(post_title).strip() == _html.unescape(heading_text).strip():
                    return {
                        "success": False,
                        "changed": 0,
                        "error": (
                            f'"{heading_text}" is the page title — your theme renders it as '
                            f"H{from_level} automatically. Page titles cannot be changed via "
                            "the heading editor. To fix a skipped heading level, make sure "
                            "your content body starts with H2, not H1."
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
                "It may be in a classic (non-block) widget — edit it directly in "
                "WP Admin → Appearance → Widgets."
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

async def find_attachment_by_url(wp: WPClient, image_url: str) -> dict | None:
    """Resolve an image URL to a WordPress media attachment.

    Tries the source_url filter first (exact match), then falls back to a
    filename search.  Returns a dict with keys: id, source_url, alt_text,
    title, caption, admin_url.  Returns None if not found.
    """
    from urllib.parse import urlparse, unquote

    # Try exact source_url match
    try:
        r = await wp.get(
            f"media?source_url={image_url}&_fields=id,source_url,alt_text,title,caption&per_page=1"
        )
        if r.status_code == 200:
            items = r.json()
            if items:
                return _attachment_dict(items[0], wp.site_url)
    except Exception:
        pass

    # Fallback: search by filename slug
    filename = unquote(urlparse(image_url).path.split("/")[-1])
    slug = re.sub(r"\.[^.]+$", "", filename)   # strip extension
    slug = re.sub(r"-\d+x\d+$", "", slug)       # strip WP size suffix e.g. -300x200
    try:
        r = await wp.get(
            f"media?search={slug}&_fields=id,source_url,alt_text,title,caption&per_page=10"
        )
        if r.status_code == 200:
            for item in r.json():
                src = item.get("source_url", "")
                if urlparse(src).path.split("/")[-1] == filename:
                    return _attachment_dict(item, wp.site_url)
                src_slug = re.sub(r"\.[^.]+$", "", src.split("/")[-1])
                src_slug = re.sub(r"-\d+x\d+$", "", src_slug)
                if src_slug == slug:
                    return _attachment_dict(item, wp.site_url)
    except Exception:
        pass

    return None


def _attachment_dict(item: dict, site_url: str) -> dict:
    att_id = item["id"]
    return {
        "id":         att_id,
        "source_url": item.get("source_url", ""),
        "alt_text":   item.get("alt_text", ""),
        "title":      item.get("title", {}).get("rendered", ""),
        "caption":    item.get("caption", {}).get("rendered", ""),
        "admin_url":  f"{site_url.rstrip('/')}/wp-admin/post.php?post={att_id}&action=edit",
    }


async def get_attachment_info(wp: WPClient, image_url: str) -> dict:
    """Return attachment metadata for *image_url*, or an error dict."""
    att = await find_attachment_by_url(wp, image_url)
    if not att:
        return {"success": False, "error": f"No WordPress media attachment found for: {image_url}"}
    return {"success": True, **att}


async def update_image_metadata(
    wp: WPClient,
    image_url: str,
    alt_text: str | None = None,
    title: str | None = None,
    caption: str | None = None,
) -> dict:
    """Update alt text, title, and/or caption for a WordPress media attachment.

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
                "error":    None,
            }
        body = r.json()
        return {"success": False, "error": body.get("message", f"HTTP {r.status_code}")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
