"""
WordPress title and meta trim functionality.

Handles SEO title trimming to remove site name suffixes and manage per-page overrides.
"""

import logging
import re

from api.services.wp_client import WPClient
from api.services.wp_shared import _FIELD_SPECS

logger = logging.getLogger(__name__)

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
    from api.services.wp_fixer import find_post_by_url, apply_fix

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


async def trim_title_one(
    wp: WPClient,
    page_url: str,
    seo_plugin: str | None,
) -> dict:
    """Strip the site-name suffix from the SEO title of a single page.

    Same logic as bulk_trim_titles but for one URL.  Returns a dict with keys:
    success, original_title, trimmed_title, method, error.
    """
    from api.services.wp_fixer import find_post_by_url, apply_fix

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
