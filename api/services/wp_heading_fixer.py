"""
wp_heading_fixer.py — FACADE (M9.4 refactor)

All heading-fix logic has been split into api/services/wp_heading/ submodules.
This module re-exports every public name so existing imports remain unchanged.
"""

from api.services.wp_heading.sources import (
    _extract_headings_from_html,
    _normalize_text_for_comparison,
    _text_matches,
    analyze_heading_sources,
    find_heading,
)

from api.services.wp_heading.edit import (
    _change_heading_level_in_content,
    change_heading_level,
    change_heading_text,
    convert_heading_to_bold,
)

from api.services.wp_heading.widgets import (
    _fix_heading_in_widgets,
    _fix_heading_in_blocks,
    _fix_heading_in_template_parts,
)

from api.services.wp_heading.bulk import (
    bulk_replace_heading,
)

__all__ = [
    "_extract_headings_from_html",
    "_normalize_text_for_comparison",
    "_text_matches",
    "analyze_heading_sources",
    "find_heading",
    "_change_heading_level_in_content",
    "change_heading_level",
    "change_heading_text",
    "convert_heading_to_bold",
    "_fix_heading_in_widgets",
    "_fix_heading_in_blocks",
    "_fix_heading_in_template_parts",
    "bulk_replace_heading",
]
