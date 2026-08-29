"""Turn an issue's `extra` payload into report-readable evidence lines.

Purpose: make a finding fixable. Naming the page is not enough — "6 unsafe
         external links on this page" tells the operator to go and re-audit the
         page by hand, which is most of the work the tool was supposed to save.
Spec:    docs/pending/2026-08-29_EV-issue-evidence.md
Tests:   tests/test_issue_evidence.py

Two separate faults produced the same symptom, and both are fixed together (P5):

1. Three checks captured a COUNT and no evidence at all —
   `UNSAFE_CROSS_ORIGIN_LINK`, `MIXED_CONTENT`, `INTERNAL_NOFOLLOW`. Their
   siblings (`IMG_ALT_MISSING`, `LINK_EMPTY_ANCHOR`) had always returned an
   evidence list; these three simply never did. Fixed in the parser.
2. Most codes DO carry good evidence — `ANCHOR_TEXT_GENERIC` has the anchor text
   and href, `SEMANTIC_DENSITY_LOW` has a written diagnosis, `H1_MULTIPLE` has
   the actual headings — and **the report never rendered any of it**. All that
   detail existed in the database and was invisible in the artifact the client
   receives (P25).

This module is the fix for (2), and it is deliberately generic: a per-code
formatter table would need 167 entries and would silently omit the next code
somebody adds. Instead it recognises the ~15 recurring *shapes* that `extra`
actually uses (enumerated from a real 2,137-issue job), and a guard test asserts
that every high-volume code yields evidence or is explicitly recorded as one
whose page URL is the whole story.

Unknown keys are skipped rather than dumped. Raw JSON in a client report is
worse than nothing.
"""

from __future__ import annotations

import os

# How many evidence rows to render per issue. The true total is always stated
# alongside when it is larger (rule 6) — a truncated list must never read as
# complete.
EVIDENCE_ROW_CAP = int(os.getenv("TT_EVIDENCE_ROW_CAP", "10"))

# Keys that are pure measurements. The description already states them; repeating
# "count: 6" under a finding that says "6 links" is noise, not evidence.
_NOISE_KEYS = frozenset({
    "count", "occurrences", "ratio", "ratio_pct", "word_count", "length",
    "score", "size_kb", "limit_kb", "citation_count", "quotations_found",
    "question_count", "skip_at", "unsafe_link_count", "internal_nofollow_count",
    "mixed_count", "active_count", "passive_count", "has_active",
    "missing_alt_count", "empty_anchor_count", "groups_total", "fields_total",
    "occurrence_urls_total", "affected_targets_total", "unsafe_links_total",
    "mixed_content_items_total", "nofollow_links_total", "missing_fields_total",
    "unresolved", "is_lazy_loaded", "faq_heading", "page_type", "year",
    "total_occurrences", "empty_anchor_hrefs",
})

# Prose keys: a sentence already written for a human. Rendered verbatim.
_PROSE_KEYS = ("diagnosis", "caveat", "reason", "sentence")

# Excerpt keys: a chunk of page text. Rendered quoted and truncated.
_EXCERPT_KEYS = ("first_200_words", "meta_description", "title", "h1", "author")

# Scalar keys worth naming (a URL, a path, a host) — short, identifying values.
# `source_url` is deliberately absent: it is the legacy back-compat field that
# duplicates `occurrence_urls[0]`, and printing both reads as two findings.
_SCALAR_KEYS = ("from", "to", "path", "host", "target_url",
                "redirect_to", "opens", "closes")

# Labels for the keys a human actually reads. Without these, `occurrence_urls`
# renders as "Occurrence urls", which is the field name leaking into a client
# report rather than a sentence anybody would write.
_KEY_LABELS = {
    "occurrence_urls": "Linked from",
    "affected_targets": "Broken destinations",
    "unsafe_links": "Unsafe links",
    "mixed_content_items": "Insecure resources",
    "nofollow_links": "Internal nofollow links",
    "examples": "Examples",
    "mismatched_fields": "Schema values not on the page",
    "missing_fields": "Missing fields",
    "fields": "Fields",
    "h2_headings": "Headings on this page",
    "outline": "Heading outline",
    "empty_levels": "Empty heading levels",
    "missing_tags": "Missing tags",
    "duplicate_urls": "Also on",
    "groups": "Duplicate link groups",
    "img_missing_alt_srcs": "Images without alt text",
    "empty_anchors": "Links with no accessible name",
    "variants": "Name variants found",
    "issues": "Detected problems",
    "anchor_texts": "Anchor text used",
}

_MAX_LINE = 160


def _clip(text: str, limit: int = _MAX_LINE) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _label(key: str) -> str:
    if key in _KEY_LABELS:
        return _KEY_LABELS[key]
    return key.replace("_", " ").strip().capitalize()


def _row_to_line(row: dict) -> str | None:
    """Render one evidence dict. Handles the shapes `extra` actually uses."""
    if not isinstance(row, dict):
        return _clip(row) if row else None

    # A link: anchor text and destination.
    href = row.get("href") or row.get("url")
    if href:
        bits = []
        text = (row.get("text") or "").strip()
        if text:
            bits.append(f'"{text}"')
        bits.append(str(href))
        tail = []
        if row.get("tag"):
            tail.append(str(row["tag"]))
        if row.get("severity"):
            tail.append(str(row["severity"]))
        if row.get("count"):
            tail.append(f"x{row['count']}")
        line = " -> ".join(bits) if len(bits) > 1 else bits[0]
        return _clip(f"{line}" + (f"  ({', '.join(tail)})" if tail else ""))

    # A schema/entity field with a value (E5, SCHEMA_VISIBLE_MISMATCH).
    field = row.get("field")
    if field:
        node = row.get("node")
        name = f"{node}.{field}" if node else str(field)
        value = row.get("value")
        if value is not None:
            return _clip(f'{name} = "{value}"')
        reason = row.get("reason")
        return _clip(f"{name}" + (f" ({reason})" if reason else ""))

    # A named entity variant (ENTITY_NAME_INCONSISTENT).
    if row.get("name"):
        urls = row.get("urls") or []
        return _clip(f'"{row["name"]}"' + (f" on {len(urls)} page(s)" if urls else ""))

    return None


def evidence_lines(issue_code: str, extra: dict | None) -> tuple[list[str], int]:
    """Return ``(lines, total)`` — readable evidence, and how many rows exist.

    ``total`` exceeds ``len(lines)`` when the list was capped; every caller must
    disclose that rather than presenting the visible rows as the whole set.
    """
    if not extra or not isinstance(extra, dict):
        return [], 0

    lines: list[str] = []
    total = 0

    # 1. Lists of dicts (links, fields, groups, examples) and lists of strings
    #    (headings, outlines, URL lists). Ordered so the most specific run first.
    for key, value in extra.items():
        if key in _NOISE_KEYS or not isinstance(value, list) or not value:
            continue
        rendered = [
            line for line in (_row_to_line(row) for row in value) if line
        ] if isinstance(value[0], dict) else [
            _clip(v) for v in value if isinstance(v, str) and v.strip()
        ]
        if not rendered:
            continue
        declared_total = extra.get(f"{key}_total")
        row_total = int(declared_total) if isinstance(declared_total, int) else len(rendered)
        total += row_total
        head = rendered[:EVIDENCE_ROW_CAP]
        lines.append(f"{_label(key)}:")
        lines.extend(f"  {line}" for line in head)
        if row_total > len(head):
            lines.append(f"  ... and {row_total - len(head)} more "
                         f"(full list in the spreadsheet export)")

    # 2. Prose already written for a human.
    for key in _PROSE_KEYS:
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(_clip(value, 300))
            total += 1

    # 3. Short identifying scalars.
    scalars = [
        f"{_label(k)}: {_clip(extra[k])}"
        for k in _SCALAR_KEYS
        if isinstance(extra.get(k), str) and extra[k].strip()
    ]
    if scalars:
        lines.extend(scalars)
        total += len(scalars)

    # 4. Page-text excerpts, quoted so they read as quotation, not as our prose.
    for key in _EXCERPT_KEYS:
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f'{_label(key)}: "{_clip(value, 220)}"')
            total += 1

    return lines, total


def evidence_for_excel(issue_code: str, extra: dict | None) -> str:
    """The same evidence as one newline-joined cell, uncapped.

    The PDF caps for space and points here; this must therefore actually hold
    the full list, or that promise is false (the F2 lesson from the E-series).
    """
    if not extra or not isinstance(extra, dict):
        return ""
    global EVIDENCE_ROW_CAP
    previous = EVIDENCE_ROW_CAP
    EVIDENCE_ROW_CAP = 10**6
    try:
        lines, _total = evidence_lines(issue_code, extra)
    finally:
        EVIDENCE_ROW_CAP = previous
    return "\n".join(lines)


# Codes whose finding is fully actionable from the page URL alone — the fix is
# "edit this page", and there is no sub-element to point at. Recorded explicitly
# so that a code producing no evidence is a decision, not an oversight.
# Asserted by tests/test_issue_evidence.py::test_ev_every_code_is_actionable.
PAGE_IS_THE_EVIDENCE: frozenset[str] = frozenset({
    "META_DESC_MISSING", "META_DESC_TOO_SHORT", "TITLE_MISSING",
    "TITLE_TOO_SHORT", "TITLE_TOO_LONG", "H1_MISSING",
    # "Thin Content" and "Low Information" are the display labels of these two.
    "CONTENT_THIN", "THIN_CONTENT",
    "CONSENT_MODE_MISSING", "ANALYTICS_TAG_MISSING",
    "LANDMARK_MAIN_MISSING", "LANDMARK_NAV_MISSING",
    "ENTITY_SAMEAS_MISSING", "DATE_MODIFIED_MISSING", "DATE_PUBLISHED_MISSING",
    "NOT_IN_SITEMAP", "ORPHAN_PAGE", "MISSING_VIEWPORT_META", "LANG_MISSING",
    "JSON_LD_MISSING", "SCHEMA_ORG_MISSING", "FAVICON_MISSING",
    "AUTHOR_BYLINE_MISSING", "AUTHOR_CREDENTIALS_MISSING",
    "GEO_SUMMARY_BURIED", "AI_BOT_NO_AI_DIRECTIVES", "AI_TXT_MISSING",
    "LLMS_TXT_MISSING", "SITEMAP_MISSING", "MISSING_HSTS",
})
