"""
Heading level changes, text changes, and heading-to-bold conversion.

Split from wp_heading_fixer.py (M9.4 refactor).
"""

import html as html_module
import logging
import re

from api.services.wp_client import WPClient
from api.services.wp_heading.sources import (
    _normalize_text_for_comparison,
    _text_matches,
)

logger = logging.getLogger(__name__)


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
        # Lazy import to avoid circular dependency (widgets imports _change_heading_level_in_content)
        from api.services.wp_heading.widgets import (
            _fix_heading_in_widgets,
            _fix_heading_in_blocks,
            _fix_heading_in_template_parts,
        )
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

    # v2.3 (M0.9 P4): Removed a no-op block here that claimed to "also handle
    # Gutenberg heading blocks" but only contained `pass`. The block compiled
    # a regex, iterated matches, and discarded the results — a silent dead-end
    # masked as defensive code. The main `pattern.sub(...)` above already
    # handles Gutenberg blocks because WordPress stores them as raw HTML
    # inside <!-- wp:heading --> comments, e.g.:
    #
    #     <!-- wp:heading -->
    #     <h2 class="wp-block-heading">Title</h2>
    #     <!-- /wp:heading -->
    #
    # The H tag inside the block comment is raw, not entity-encoded, so the
    # `<h{level}(\s[^>]*)?>(.+?)</h{level}>` regex matches it as-is. Confirmed
    # by tests/test_wp_fixer.py::TestChangeHeadingText::test_gutenberg_block.

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
# Convert heading to bold paragraph
# ---------------------------------------------------------------------------

async def convert_heading_to_bold(
    wp: WPClient,
    page_url: str,
    heading_text: str,
    level: int,
) -> dict:
    """Convert a specific <h{level}>X</h{level}> to <p><strong>X</strong></p>.

    Reuses the same find/replace machinery as change_heading_text — find the
    post, fetch its content, locate the matching heading tag, replace, PATCH.

    Args:
        wp: WPClient for the target site.
        page_url: URL of the page containing the heading.
        heading_text: Text of the heading to convert. Matched fuzzy (after
            normalize: stripped tags, decoded entities, collapsed whitespace).
        level: H level (1-6) the heading currently is at.

    Returns:
        {
          "success": bool,
          "changed": int,
          "location": "post" | None,
          "error": str | None,
        }
    """
    from api.services.wp_fixer import find_post_by_url

    if level not in (1, 2, 3, 4, 5, 6):
        return {"success": False, "changed": 0,
                "error": f"Invalid level: {level} (must be 1-6)"}

    post_info = await find_post_by_url(wp, page_url)
    if not post_info:
        return {"success": False, "changed": 0,
                "error": f"Could not find WordPress post for {page_url}"}

    post_id = post_info["id"]
    post_type = post_info["type"]
    endpoint_base = "pages" if post_type == "page" else "posts"

    try:
        r = await wp.get(f"{endpoint_base}/{post_id}?context=edit")
        if r.status_code != 200:
            return {"success": False, "changed": 0,
                    "error": f"HTTP {r.status_code} fetching post content"}
        content_data = r.json().get("content") or {}
        raw_content = content_data.get("raw", "") or ""
    except Exception as exc:
        return {"success": False, "changed": 0, "error": str(exc)}

    def _normalize_for_compare(text: str) -> str:
        return re.sub(r'\s+', '', html_module.unescape(text)).strip()

    norm_target = _normalize_for_compare(heading_text)

    count = 0

    def _replace(m: re.Match) -> str:
        nonlocal count
        inner = m.group(2)
        plain = _normalize_for_compare(re.sub(r'<[^>]+>', '', inner))
        if plain != norm_target:
            return m.group(0)
        count += 1
        # Preserve the inner HTML if present (e.g. <strong> inside the H),
        # but ensure the OUTER wrapper is <p><strong>...</strong></p>.
        # If inner already contains <strong>, just use the plain text to
        # avoid <strong><strong>X</strong></strong> nesting.
        if '<strong' in inner.lower() or '<b ' in inner.lower() or inner.lower().startswith('<b>'):
            # Strip the existing emphasis tags and use plain text
            inner_text = html_module.escape(
                re.sub(r'<[^>]+>', '', inner).strip()
            )
            return f'<p><strong>{inner_text}</strong></p>'
        # Inner has no bold; wrap as-is
        return f'<p><strong>{inner}</strong></p>'

    pattern = re.compile(
        rf'<h{level}(\s[^>]*)?>(.+?)</h{level}>',
        re.IGNORECASE | re.DOTALL,
    )
    updated_content = pattern.sub(_replace, raw_content)

    if count == 0:
        return {"success": False, "changed": 0,
                "error": f'H{level} "{heading_text}" was not found in the post content.'}

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
