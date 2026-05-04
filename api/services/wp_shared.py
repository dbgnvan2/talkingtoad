"""
Shared constants and data structures for WordPress fix engine.

Defines the fix registry, field specifications, and plugin-specific mappings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class _FixSpec:
    """Specification for a fixable field."""
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
