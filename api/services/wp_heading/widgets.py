"""
Cascade helpers: fix headings in shared WordPress content areas
(widgets, synced patterns, template parts).

Split from wp_heading_fixer.py (M9.4 refactor).
"""

import logging

from api.services.wp_client import WPClient
from api.services.wp_heading.edit import _change_heading_level_in_content

logger = logging.getLogger(__name__)


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
