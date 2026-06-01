"""
Heading extraction, normalization, source analysis, and search.

Split from wp_heading_fixer.py (M9.4 refactor).
"""

import html as html_module
import logging
import re
import unicodedata

from api.services.wp_client import WPClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heading extraction and normalization
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


# ---------------------------------------------------------------------------
# Heading source analysis
# ---------------------------------------------------------------------------

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
    from api.services.wp_fixer import find_post_by_url

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
# Heading search (read-only, against store)
# ---------------------------------------------------------------------------

async def find_heading(
    store,
    job_id: str,
    heading_text: str,
    level: int | None = None,
) -> list[dict]:
    """Search a crawl job's pages for headings matching *heading_text*.

    Pure read against the store — no WP API. Returns one entry per match,
    so a page with the same heading at multiple levels yields multiple rows.

    Args:
        store: Job store (SQLite or Redis).
        job_id: The crawl job to search.
        heading_text: Text to match. Comparison is normalized (whitespace
            collapsed, smart quotes/dashes equalised, case-insensitive) via
            the existing _text_matches helper.
        level: If provided (1-6), only match headings at that level.

    Returns:
        List of {page_url, level, text} dicts. Empty list if no matches.
    """
    pages = await store.get_pages(job_id)
    matches: list[dict] = []
    for page in pages:
        for heading in page.headings_outline or []:
            h_text = heading.get("text", "")
            h_level = heading.get("level")
            if level is not None and h_level != level:
                continue
            if _text_matches(h_text, heading_text):
                matches.append({
                    "page_url": page.url,
                    "level": h_level,
                    "text": h_text,
                })
    return matches
