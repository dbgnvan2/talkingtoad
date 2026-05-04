"""
WordPress heading analysis and manipulation.

Analyzes heading sources, changes levels, converts to bold, and manages heading text.
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
    text = re.sub(r'[‐-―−﹘﹣－]', '-', text)
    # Replace various quotes with simple quotes
    text = re.sub(r'[‘’‚‛]', "'", text)
    text = re.sub(r'[“”„‟]', '"', text)
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
# Heading level changes
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
    from api.services.wp_fixer import find_post_by_url

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
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.debug(f"Could not check if heading matches post title: {exc}")

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


# ---------------------------------------------------------------------------
# Heading text changes
# ---------------------------------------------------------------------------

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
    from api.services.wp_fixer import find_post_by_url

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
        return f'<h{level}{attrs}>{html_module.escape(new_text.strip())}</h{level}>'

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
    """Search synced patterns (reusable blocks) for the heading and change it."""
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
    """Search FSE template parts for the heading."""
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
