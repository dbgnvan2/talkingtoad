"""Issue data structures, catalogue, scoring, confidence labels, and the
``make_issue`` factory — split out of ``api/crawler/issue_checker.py`` in
v2.6 M9.1 (Cycle K).

BASELINE: v2.6 M9.1 / Cycle U (tag ``v2.6-stabilized``).
This module's contents are frozen as the canonical end-of-v2.6 baseline.
Subsequent code or threshold changes should be tracked through a new
pending spec and tied to a fresh release (v2.7 or v3.0). The structural
integrity of this file is enforced by five CI parity invariants — see
``tests/test_class1_invariants.py::TestCatalogueScoringParity`` and
``tests/test_architecture_constraints.py::TestAIReadinessConfidenceLabels``.

Single source of truth for:
    - ``Issue`` dataclass and ``_IssueSpec`` dataclass
    - ``_ISSUE_SCORING`` (impact, effort) by code — 155 codes
    - ``_CATALOGUE`` (every issue spec) — 155 codes
    - ``_AI_READINESS_CONFIDENCE`` (confidence labels) — 71 codes
      (of 155 total; the 84 non-ai_readiness codes carry no confidence label)
    - ``_STOP_WORDS`` and ``_GENERIC_ANCHOR_TEXTS`` (shared helpers)
    - Size-limit constants
    - ``make_issue()`` factory, ``_sig_words()``, ``_titles_mismatch()``

The architecture parity tests, the auto-generator for ``docs/issue-codes.md``,
and every domain checker depend on this being one module.
"""

import re
from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Scoring-model version (R5.6 / external spec §8.4)
# ---------------------------------------------------------------------------
# Single source of truth for the scoring-model version stamped on every saved
# audit (see CrawlJob.scoring_model_version). Bump this whenever the scoring
# model — impact/effort tables, derivation matrix, suppression clusters,
# site-scope rules, or the category cap — changes, so a stored report records
# which model produced it. Read as None on legacy audits saved before the stamp.
SCORING_MODEL_VERSION = "2026-07-06-r5"

# ---------------------------------------------------------------------------
# Generic anchor text patterns (Step 3a)
# ---------------------------------------------------------------------------

_GENERIC_ANCHOR_TEXTS = frozenset({
    "click here", "read more", "learn more", "here", "more", "this",
    "link", "more info", "find out more", "go", "see more", "details",
    "continue reading", "click", "download",
})
# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """A single SEO issue found during a crawl."""

    code: str
    category: str
    severity: str           # critical | warning | info
    description: str
    recommendation: str
    page_url: str | None = None
    extra: dict | None = None   # optional supplementary data (e.g. redirect chain)
    impact: int = 0             # v1.5 impact score (0–10)
    effort: int = 0             # v1.5 effort score (0–5)
    priority_rank: int = 0      # R3: (impact × 10) − (effort × 6)
    quick_win: bool = False     # R3: impact ≥ 4 AND effort ≤ 1 (easy, worthwhile)
    human_description: str = "" # plain-English label for nonprofit staff
    # Expanded help for PDF reports
    what_it_is: str = ""
    impact_desc: str = ""
    how_to_fix: str = ""
    fixability: str = "developer_needed"  # wp_fixable | content_edit | developer_needed
    # v2.3 M0.2 — see Issue Pydantic model and _IssueSpec.confidence_label.
    confidence_label: str | None = None

# ---------------------------------------------------------------------------
# Issue catalogue (spec §7.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _IssueSpec:
    category: str
    severity: str
    description: str
    recommendation: str
    # R5.1 — scoring scope. "page": the finding is charged on the page it was
    # found. "site": the finding is a property of the whole site (TLS/host
    # config) and is charged ONCE site-wide at the worst-affected page — see
    # api/services/job_store_base.py::_site_scope_representatives. Scoring-only;
    # the issue still appears on every page where it was detected.
    scope: Literal["page", "site"] = "page"
    human_description: str = ""   # plain-English label for nonprofit staff
    what_it_is: str = ""
    impact_desc: str = ""
    how_to_fix: str = ""
    fixability: str = "developer_needed"  # wp_fixable | content_edit | developer_needed
    # v2.3 (M0.2) — confidence label per v2.0 AI-readiness spec §2.
    # - Established: vendor-confirmed effect on AI crawling/citation
    # - Reasonable proxy: industry consensus, partial vendor confirmation
    # - Heuristic: industry consensus only, no vendor confirmation
    # - None: not an AI-readiness check (the field doesn't apply)
    # An architecture test enforces that every ai_readiness-category code
    # has a non-None confidence_label.
    confidence_label: str | None = None

# ---------------------------------------------------------------------------
# v1.5 Priority scoring table (impact, effort) per issue code
# ---------------------------------------------------------------------------
# priority_rank = (impact × 10) − (effort × 6)
# Impact 1–10: how badly the issue hurts SEO / UX
# Effort  1–5: how hard it is to fix (1 = trivial, 5 = major dev work)

_ISSUE_SCORING: dict[str, tuple[int, int]] = {
    # code:                       (impact, effort)
    "BROKEN_LINK_404":            (2, 2),
    "BROKEN_LINK_410":            (2, 2),
    "BROKEN_LINK_5XX":            (3, 2),
    "BROKEN_LINK_503":            (1, 3),
    "REDIRECT_LOOP":              (10, 4),
    "REDIRECT_CHAIN":             (2, 3),
    "REDIRECT_301":               (2, 2),
    "REDIRECT_302":               (2, 2),
    "REDIRECT_TRAILING_SLASH":    (0, 1),
    "REDIRECT_CASE_NORMALISE":    (0, 1),
    "TITLE_MISSING":              (6, 1),
    "TITLE_DUPLICATE":            (4, 2),
    "TITLE_TOO_SHORT":            (1, 1),
    "TITLE_TOO_LONG":             (2, 1),
    "META_DESC_MISSING":          (2, 1),
    "META_DESC_DUPLICATE":        (2, 2),
    "META_DESC_TOO_SHORT":        (2, 1),
    "META_DESC_TOO_LONG":         (2, 1),
    "SOCIAL_PREVIEW_METADATA_MISSING": (1, 1),  # §7 merge of OG_* + TWITTER_CARD
    "CANONICAL_MISSING":          (6,  2),
    "CANONICAL_EXTERNAL":         (6, 3),
    "FAVICON_MISSING":            (2, 2),
    "H1_MISSING":                 (4, 1),
    "H1_MULTIPLE":                (2, 2),
    "HEADING_SKIP":               (1, 3),
    "NOINDEX_META":               (10, 1),
    "NOINDEX_HEADER":             (10, 2),
    "ROBOTS_BLOCKED":             (9,  2),
    "NOT_IN_SITEMAP":             (2, 1),
    "SITEMAP_MISSING":            (2, 2),
    "HTTP_PAGE":                  (6, 2),
    "MIXED_CONTENT":              (4, 2),
    "MISSING_HSTS":               (1, 2),
    "UNSAFE_CROSS_ORIGIN_LINK":   (0, 1),
    "URL_TOO_LONG":               (1, 2),
    "URL_UPPERCASE":              (2, 2),
    "URL_HAS_SPACES":             (2, 2),
    "URL_HAS_UNDERSCORES":        (2, 2),
    "THIN_CONTENT":               (4, 3),
    "HIGH_CRAWL_DEPTH":           (4, 3),
    "PAGE_TIMEOUT":               (6,  3),
    "EXTERNAL_LINK_TIMEOUT":      (1, 1),
    "EXTERNAL_LINK_SKIPPED":      (0, 1),
    "META_REFRESH_REDIRECT":      (2, 2),
    "PAGINATION_LINKS_PRESENT":   (0, 2),
    "AMPHTML_BROKEN":             (2, 3),
    "PDF_TOO_LARGE":              (1, 2),
    "IMG_OVERSIZED":              (2, 2),
    "IMG_ALT_MISSING":            (3, 2),
    # v1.9image - New image issue codes
    "IMG_ALT_TOO_SHORT":          (1, 1),
    "IMG_ALT_TOO_LONG":           (1, 1),
    "IMG_ALT_GENERIC":            (2, 1),
    "IMG_ALT_DUP_FILENAME":       (1, 1),
    "IMG_ALT_MISUSED":            (1, 2),
    "IMG_SLOW_LOAD":              (2, 2),
    "IMG_OVERSCALED":             (2, 3),
    "IMG_POOR_COMPRESSION":       (2, 2),
    "IMG_FORMAT_LEGACY":          (2,  2),
    "IMG_NO_SRCSET":              (2,  3),
    "IMG_DUPLICATE_CONTENT":      (1, 2),
    "LOGIN_REDIRECT":             (2,  1),
    "INTERNAL_REDIRECT_301":      (2, 1),
    "ORPHAN_PAGE":                (4, 2),
    "MISSING_VIEWPORT_META":      (6,  1),
    "IMG_BROKEN":                 (4, 2),
    "LINK_EMPTY_ANCHOR":          (2, 2),
    "INTERNAL_NOFOLLOW":          (4, 2),
    "PAGE_SIZE_LARGE":            (2, 3),
    # v1.6 new checks
    "LANG_MISSING":               (2, 1),
    "TITLE_H1_MISMATCH":          (1, 2),
    "HTTPS_REDIRECT_MISSING":     (6, 2),
    "CANONICAL_SELF_MISSING":     (2, 1),
    # v1.7 AI-Readiness Module
    "LLMS_TXT_MISSING":           (1, 1),
    "LLMS_TXT_INVALID":           (1, 2),
    "SEMANTIC_DENSITY_LOW":       (1, 3),
    "DOCUMENT_PROPS_MISSING":     (2, 2),
    "JSON_LD_MISSING":            (4, 2),
    "CONVERSATIONAL_H2_MISSING":  (1, 2),
    "BLOG_SECTIONS_MISSING":      (2, 2),
    # v1.9.2 new checks
    "CONTENT_STALE":              (1, 3),
    # Phase 3 new checks
    "ANCHOR_TEXT_GENERIC":        (2, 2),
    "HEADING_EMPTY":              (1, 1),
    "WWW_CANONICALIZATION":       (4, 2),
    # v2.0 AI-Readiness: AI Bot Access
    "AI_BOT_SEARCH_BLOCKED":      (9, 1),
    "AI_BOT_TRAINING_DISALLOWED": (0,  1),
    "AI_BOT_USER_FETCH_BLOCKED":  (3, 1),
    "AI_BOT_DEPRECATED_DIRECTIVE":(2,  1),
    "AI_BOT_NO_AI_DIRECTIVES":    (1,  1),
    "AI_BOT_BLANKET_DISALLOW":    (9,  1),
    "AI_BOT_TABLE_STALE":         (0,  1),
    # v2.0 AI-Readiness: Schema Typing
    "SCHEMA_TYPE_MISMATCH":       (2, 2),
    "SCHEMA_DEPRECATED_TYPE":     (2,  1),
    "SCHEMA_TYPE_CONFLICT":       (2, 2),
    # M3.1: Schema values not visible on page (Established — Google directive)
    "SCHEMA_VISIBLE_MISMATCH":    (6, 2),
    # M3.2: Content not in textual form (Reasonable proxy)
    "AI_CONTENT_NOT_IN_TEXT":     (4,  2),
    # M3.3: X-Robots-Tag AI-preview controls (Established — literal header facts)
    "AI_PREVIEW_SUPPRESSED":     (4, 1),
    "AI_PREVIEW_BLOCKED_AT_BOT": (4, 1),
    # M3.4: No visual companion for text-heavy content (Reasonable proxy)
    "AI_NO_VISUAL_COMPANION":    (1,  1),
    # M3.5: Main content is a small share of total visible text (Heuristic)
    "AI_MAIN_CONTENT_LOW_RATIO": (2,  1),
    # v2.0 AI-Readiness: Content Extractability
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": (9, 4),
    "CONTENT_THIN":               (4,  3),
    "CONTENT_UNSTRUCTURED":       (3,  2),
    "CONTENT_IMAGE_HEAVY":        (1, 3),
    # v2.0 AI-Readiness: Citation & Attribution
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": (3, 2),
    "CITATIONS_ORPHANED":         (1, 1),
    "CITATIONS_SOURCES_INACCESSIBLE": (1, 3),
    # v2.1 GEO Analyzer: Aggarwal et al. checks (Empirical tier, highest impact)
    "STATISTICS_COUNT_LOW":       (3, 2),
    "EXTERNAL_CITATIONS_LOW":     (3, 2),
    "QUOTATIONS_MISSING":         (3, 2),
    "ORPHAN_CLAIM_TECHNICAL":     (3, 2),
    # v2.1 GEO Analyzer: Mechanistic checks
    "RAW_HTML_JS_DEPENDENT":      (9, 3),
    "JS_RENDERED_CONTENT_DIFFERS":(6,  4),
    "CONTENT_CLOAKING_DETECTED":  (6, 4),
    "UA_CONTENT_DIFFERS":         (6, 3),
    "FIRST_VIEWPORT_NO_ANSWER":   (2, 2),
    "AUTHOR_BYLINE_MISSING":      (4,  2),
    "DATE_PUBLISHED_MISSING":     (2, 1),
    "DATE_MODIFIED_MISSING":      (2,  1),
    "CODE_BLOCK_MISSING_TECHNICAL":(1, 2),
    "COMPARISON_TABLE_MISSING":   (1, 2),
    "CHUNKS_NOT_SELF_CONTAINED":  (2, 4),
    "CENTRAL_CLAIM_BURIED":       (2, 3),
    # Cycle GG: higher impact than its peers — a buried answer under
    # an H2 is a stronger AI-extraction failure mode than the cousin
    # word-position / signal-presence checks. Per continuation-prompt
    # Q5's "stronger penalty" intent (penalty=20 didn't translate to
    # this codebase's (impact, effort) tuple; (7, 3) is the closest).
    "GEO_SUMMARY_BURIED":         (2, 3),
    "LINK_PROFILE_PROMOTIONAL":   (1, 2),
    "STRUCTURED_ELEMENTS_LOW":    (1, 2),
    # v2.1 GEO Analyzer: Conventional checks
    "JSON_LD_INVALID":            (4,  2),
    "FAQ_SCHEMA_MISSING":         (2, 2),
    "FAQ_ANSWERS_NOT_IN_HTML":    (4, 3),
    "PROMOTIONAL_CONTENT_INTERRUPTS": (1, 3),
    "AI_TXT_MISSING":             (1,  1),
    # Tier 1 GEO heuristics (spec §4.3–4.6)
    "QUERY_COVERAGE_WEAK":        (2, 2),
    "SECTION_VAGUE_OPENER":       (1, 2),
    "SECTION_CROSS_REFERENCES":   (1, 2),
    "PARA_TOO_LONG":              (1, 2),
    # M4.1: Visible date stale for page type (Content Freshness)
    "CONTENT_DATE_STALE_VISIBLE": (2, 2),
    # M4.2: Outdated statistic or year reference (Content Freshness)
    "CONTENT_STAT_OUTDATED": (1, 1),
    # M5: AI Citation Ingestion
    "AI_CITED_PAGE": (0, 0),
    "AI_HIGH_VALUE_UNCITED": (2, 2),
    # ── Agent-readiness Phase 1 (WP2–WP5) — task-side checks ────────────────
    "JS_DEPENDENT_NAVIGATION":      (6, 3),
    "NON_SEMANTIC_BUTTON":          (1, 3),
    "LANDMARK_MAIN_MISSING":        (1, 2),
    "LANDMARK_NAV_MISSING":         (1, 2),
    "INTERACTIVE_NO_ACCESSIBLE_NAME": (1, 2),
    "PLACEHOLDER_LINK":             (2, 2),
    "WRONG_PLACEHOLDER_LINK":       (2, 2),
    "SCHEMA_ORG_MISSING":           (4, 2),
    "CONTACT_INFO_NOT_IN_HTML":     (4, 2),
    # ── "Search Everywhere" GEO — brand-entity + body-uniqueness (P1) ────────
    # Born into the R5 model: impact below == derive_impact() from the
    # (confidence, effect_size) tiers in _CALIBRATION (asserted by
    # test_r3_calibration.py). Tiers reviewed 2026-07-22 — no rework outstanding.
    "ENTITY_NAME_INCONSISTENT":     (4, 2),
    "ENTITY_SAMEAS_MISSING":        (2, 1),
    "AUTHOR_IDENTITY_INCONSISTENT": (1, 2),
    "NEAR_DUPLICATE_BODY":          (4, 3),
    "BOILERPLATE_RATIO_HIGH":       (1, 2),
    # E3/E4 — schema completeness + author E-E-A-T (Search Everywhere P2)
    "HOWTO_SCHEMA_INCOMPLETE":      (1, 2),
    "PRODUCT_REVIEW_SCHEMA_MISSING":(2, 2),
    "AUTHOR_CREDENTIALS_MISSING":   (1, 2),
}


# ---------------------------------------------------------------------------
# R3 calibration record (2026-07-03) — triangulated from two independent expert
# reviews (Gemini + Fable) + audit. impact is DERIVED from (confidence x effect)
# via the Model-B matrix, with an Aggarwal "measured" lane and a documented
# override set. test_r3_calibration.py asserts _ISSUE_SCORING matches this.
# Spec: docs/pending/OLD/2026-07-03_r3-FINAL-calibration.md
# ---------------------------------------------------------------------------
_IMPACT_MATRIX: dict[tuple[str, str], int] = {
    ("Heuristic", "none"): 0,
    ("Heuristic", "small"): 1,
    ("Heuristic", "moderate"): 2,
    ("Heuristic", "large"): 3,
    ("Reasonable proxy", "none"): 0,
    ("Reasonable proxy", "small"): 2,
    ("Reasonable proxy", "moderate"): 4,
    ("Reasonable proxy", "large"): 6,
    ("Established", "none"): 0,
    ("Established", "small"): 2,
    ("Established", "moderate"): 6,
    ("Established", "large"): 9,
}
_MEASURED_MATRIX: dict[str, int] = {"none": 0, "small": 2, "moderate": 3, "large": 4}
_PAGE_FATAL_10: frozenset[str] = frozenset({"NOINDEX_HEADER", "NOINDEX_META", "REDIRECT_LOOP"})

# code -> (confidence, effect_size, measured)
_CALIBRATION: dict[str, tuple[str, str, bool]] = {
    "AI_BOT_BLANKET_DISALLOW": ("Established", "large", False),
    "AI_BOT_DEPRECATED_DIRECTIVE": ("Established", "small", False),
    "AI_BOT_NO_AI_DIRECTIVES": ("Heuristic", "small", False),
    "AI_BOT_SEARCH_BLOCKED": ("Established", "large", False),
    "AI_BOT_TABLE_STALE": ("Heuristic", "none", False),
    "AI_BOT_TRAINING_DISALLOWED": ("Established", "none", False),
    "AI_BOT_USER_FETCH_BLOCKED": ("Established", "small", False),
    "AI_CITED_PAGE": ("Established", "none", False),
    "AI_CONTENT_NOT_IN_TEXT": ("Reasonable proxy", "moderate", False),
    "AI_HIGH_VALUE_UNCITED": ("Heuristic", "none", False),
    "AI_MAIN_CONTENT_LOW_RATIO": ("Heuristic", "moderate", False),
    "AI_NO_VISUAL_COMPANION": ("Heuristic", "small", False),
    "AI_PREVIEW_BLOCKED_AT_BOT": ("Established", "moderate", False),
    "AI_PREVIEW_SUPPRESSED": ("Established", "moderate", False),
    "AI_TXT_MISSING": ("Heuristic", "small", False),
    "AMPHTML_BROKEN": ("Reasonable proxy", "small", False),
    "ANCHOR_TEXT_GENERIC": ("Established", "small", False),
    "AUTHOR_BYLINE_MISSING": ("Reasonable proxy", "moderate", False),
    "AUTHOR_IDENTITY_INCONSISTENT": ("Heuristic", "small", False),
    "BLOG_SECTIONS_MISSING": ("Heuristic", "moderate", False),
    "BOILERPLATE_RATIO_HIGH": ("Heuristic", "small", False),
    "BROKEN_LINK_404": ("Established", "small", False),
    "BROKEN_LINK_410": ("Established", "small", False),
    "BROKEN_LINK_503": ("Heuristic", "small", False),
    "BROKEN_LINK_5XX": ("Reasonable proxy", "small", False),
    "CANONICAL_EXTERNAL": ("Established", "moderate", False),
    "CANONICAL_MISSING": ("Established", "moderate", False),
    "CANONICAL_SELF_MISSING": ("Established", "small", False),
    "CENTRAL_CLAIM_BURIED": ("Heuristic", "moderate", False),
    "CHUNKS_NOT_SELF_CONTAINED": ("Heuristic", "moderate", False),
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": ("Heuristic", "moderate", True),
    "CITATIONS_ORPHANED": ("Heuristic", "small", False),
    "CITATIONS_SOURCES_INACCESSIBLE": ("Heuristic", "small", False),
    "CODE_BLOCK_MISSING_TECHNICAL": ("Heuristic", "small", False),
    "COMPARISON_TABLE_MISSING": ("Heuristic", "small", False),
    "CONTACT_INFO_NOT_IN_HTML": ("Reasonable proxy", "moderate", False),
    "CONTENT_CLOAKING_DETECTED": ("Reasonable proxy", "large", False),
    "CONTENT_DATE_STALE_VISIBLE": ("Reasonable proxy", "small", False),
    "CONTENT_IMAGE_HEAVY": ("Heuristic", "small", False),
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": ("Established", "large", False),
    "CONTENT_STALE": ("Heuristic", "small", False),
    "CONTENT_STAT_OUTDATED": ("Heuristic", "small", False),
    "CONTENT_THIN": ("Reasonable proxy", "moderate", False),
    "CONTENT_UNSTRUCTURED": ("Reasonable proxy", "moderate", False),
    "CONVERSATIONAL_H2_MISSING": ("Heuristic", "small", False),
    "DATE_MODIFIED_MISSING": ("Reasonable proxy", "small", False),
    "DATE_PUBLISHED_MISSING": ("Reasonable proxy", "small", False),
    "DOCUMENT_PROPS_MISSING": ("Established", "small", False),
    "ENTITY_NAME_INCONSISTENT": ("Reasonable proxy", "moderate", False),
    "ENTITY_SAMEAS_MISSING": ("Reasonable proxy", "small", False),
    "EXTERNAL_CITATIONS_LOW": ("Heuristic", "moderate", True),
    "EXTERNAL_LINK_SKIPPED": ("Heuristic", "none", False),
    "EXTERNAL_LINK_TIMEOUT": ("Heuristic", "small", False),
    "FAQ_SCHEMA_MISSING": ("Established", "small", False),
    "FAQ_ANSWERS_NOT_IN_HTML": ("Reasonable proxy", "moderate", False),
    "FAVICON_MISSING": ("Established", "small", False),
    "FIRST_VIEWPORT_NO_ANSWER": ("Heuristic", "moderate", False),
    "GEO_SUMMARY_BURIED": ("Heuristic", "moderate", False),
    "H1_MISSING": ("Reasonable proxy", "moderate", False),
    "H1_MULTIPLE": ("Established", "small", False),
    "HEADING_EMPTY": ("Heuristic", "small", False),
    "HEADING_SKIP": ("Heuristic", "small", False),
    "HIGH_CRAWL_DEPTH": ("Reasonable proxy", "moderate", False),
    "HTTPS_REDIRECT_MISSING": ("Established", "moderate", False),
    "HTTP_PAGE": ("Established", "moderate", False),
    "IMG_ALT_DUP_FILENAME": ("Heuristic", "small", False),
    "IMG_ALT_GENERIC": ("Established", "small", False),
    "IMG_ALT_MISSING": ("Established", "small", False),
    "IMG_ALT_MISUSED": ("Heuristic", "small", False),
    "IMG_ALT_TOO_LONG": ("Heuristic", "small", False),
    "IMG_ALT_TOO_SHORT": ("Heuristic", "small", False),
    "IMG_BROKEN": ("Reasonable proxy", "moderate", False),
    "IMG_DUPLICATE_CONTENT": ("Heuristic", "small", False),
    "IMG_FORMAT_LEGACY": ("Reasonable proxy", "small", False),
    "IMG_NO_SRCSET": ("Reasonable proxy", "small", False),
    "IMG_OVERSCALED": ("Reasonable proxy", "small", False),
    "IMG_OVERSIZED": ("Established", "small", False),
    "IMG_POOR_COMPRESSION": ("Reasonable proxy", "small", False),
    "IMG_SLOW_LOAD": ("Reasonable proxy", "small", False),
    "INTERACTIVE_NO_ACCESSIBLE_NAME": ("Heuristic", "small", False),
    "INTERNAL_NOFOLLOW": ("Reasonable proxy", "moderate", False),
    "INTERNAL_REDIRECT_301": ("Established", "small", False),
    "JSON_LD_INVALID": ("Reasonable proxy", "moderate", False),
    "JSON_LD_MISSING": ("Reasonable proxy", "moderate", False),
    "JS_DEPENDENT_NAVIGATION": ("Established", "moderate", False),
    "JS_RENDERED_CONTENT_DIFFERS": ("Established", "moderate", False),
    "LANDMARK_MAIN_MISSING": ("Heuristic", "small", False),
    "LANDMARK_NAV_MISSING": ("Heuristic", "small", False),
    "LANG_MISSING": ("Established", "small", False),
    "LINK_EMPTY_ANCHOR": ("Reasonable proxy", "small", False),
    "LINK_PROFILE_PROMOTIONAL": ("Heuristic", "small", False),
    "LLMS_TXT_INVALID": ("Heuristic", "small", False),
    "LLMS_TXT_MISSING": ("Heuristic", "small", False),
    "LOGIN_REDIRECT": ("Heuristic", "none", False),
    "META_DESC_DUPLICATE": ("Established", "small", False),
    "META_DESC_MISSING": ("Established", "small", False),
    "META_DESC_TOO_LONG": ("Established", "small", False),
    "META_DESC_TOO_SHORT": ("Established", "small", False),
    "META_REFRESH_REDIRECT": ("Established", "small", False),
    "MISSING_HSTS": ("Heuristic", "small", False),
    "MISSING_VIEWPORT_META": ("Established", "moderate", False),
    "MIXED_CONTENT": ("Reasonable proxy", "moderate", False),
    "NEAR_DUPLICATE_BODY": ("Reasonable proxy", "moderate", False),
    "NOINDEX_HEADER": ("Established", "large", False),
    "NOINDEX_META": ("Established", "large", False),
    "NON_SEMANTIC_BUTTON": ("Heuristic", "small", False),
    "NOT_IN_SITEMAP": ("Established", "small", False),
    "ORPHAN_CLAIM_TECHNICAL": ("Heuristic", "moderate", True),
    "ORPHAN_PAGE": ("Reasonable proxy", "moderate", False),
    "PAGE_SIZE_LARGE": ("Reasonable proxy", "small", False),
    "PAGE_TIMEOUT": ("Reasonable proxy", "large", False),
    "PAGINATION_LINKS_PRESENT": ("Established", "none", False),
    "PARA_TOO_LONG": ("Heuristic", "small", False),
    "PDF_TOO_LARGE": ("Heuristic", "small", False),
    "PLACEHOLDER_LINK": ("Reasonable proxy", "small", False),
    "PROMOTIONAL_CONTENT_INTERRUPTS": ("Heuristic", "small", False),
    "QUERY_COVERAGE_WEAK": ("Heuristic", "moderate", False),
    "QUOTATIONS_MISSING": ("Heuristic", "moderate", True),
    "RAW_HTML_JS_DEPENDENT": ("Established", "large", False),
    "REDIRECT_301": ("Established", "small", False),
    "REDIRECT_302": ("Established", "small", False),
    "REDIRECT_CASE_NORMALISE": ("Established", "none", False),
    "REDIRECT_CHAIN": ("Established", "small", False),
    "REDIRECT_LOOP": ("Established", "large", False),
    "REDIRECT_TRAILING_SLASH": ("Established", "none", False),
    "ROBOTS_BLOCKED": ("Established", "large", False),
    "SCHEMA_DEPRECATED_TYPE": ("Established", "small", False),
    "SCHEMA_ORG_MISSING": ("Reasonable proxy", "moderate", False),
    "SCHEMA_TYPE_CONFLICT": ("Reasonable proxy", "small", False),
    "SCHEMA_TYPE_MISMATCH": ("Reasonable proxy", "small", False),
    "SCHEMA_VISIBLE_MISMATCH": ("Established", "moderate", False),
    "SECTION_CROSS_REFERENCES": ("Heuristic", "small", False),
    "SECTION_VAGUE_OPENER": ("Heuristic", "small", False),
    "SEMANTIC_DENSITY_LOW": ("Heuristic", "small", False),
    "SITEMAP_MISSING": ("Established", "small", False),
    "STATISTICS_COUNT_LOW": ("Heuristic", "moderate", True),
    "STRUCTURED_ELEMENTS_LOW": ("Heuristic", "small", False),
    "THIN_CONTENT": ("Reasonable proxy", "moderate", False),
    "TITLE_DUPLICATE": ("Reasonable proxy", "moderate", False),
    "TITLE_H1_MISMATCH": ("Heuristic", "small", False),
    "TITLE_MISSING": ("Established", "moderate", False),
    "TITLE_TOO_LONG": ("Established", "small", False),
    "TITLE_TOO_SHORT": ("Heuristic", "small", False),
    "SOCIAL_PREVIEW_METADATA_MISSING": ("Heuristic", "small", False),
    "UA_CONTENT_DIFFERS": ("Reasonable proxy", "large", False),
    "UNSAFE_CROSS_ORIGIN_LINK": ("Established", "none", False),
    "URL_HAS_SPACES": ("Established", "small", False),
    "URL_HAS_UNDERSCORES": ("Established", "small", False),
    "URL_TOO_LONG": ("Heuristic", "small", False),
    "URL_UPPERCASE": ("Reasonable proxy", "small", False),
    "WRONG_PLACEHOLDER_LINK": ("Reasonable proxy", "small", False),
    "WWW_CANONICALIZATION": ("Reasonable proxy", "moderate", False),
    # E3/E4 — schema completeness + author E-E-A-T (Search Everywhere P2)
    "HOWTO_SCHEMA_INCOMPLETE": ("Heuristic", "small", False),
    "PRODUCT_REVIEW_SCHEMA_MISSING": ("Reasonable proxy", "small", False),
    "AUTHOR_CREDENTIALS_MISSING": ("Heuristic", "small", False),
}

# Deliberate deviations from the pure matrix (auditor adjudication of the 21
# inter-reviewer divergences); see spec for rationale per code.
_IMPACT_OVERRIDES: dict[str, int] = {
    "AI_BOT_USER_FETCH_BLOCKED": 3,
    "AI_HIGH_VALUE_UNCITED": 2,
    "AI_PREVIEW_BLOCKED_AT_BOT": 4,
    "AI_PREVIEW_SUPPRESSED": 4,
    "BROKEN_LINK_5XX": 3,
    "CONTENT_UNSTRUCTURED": 3,
    "IMG_ALT_MISSING": 3,
    "LOGIN_REDIRECT": 2,
}

def derive_impact(code: str) -> int:
    """Impact derived from the calibration record: matrix(confidence, effect),
    the Aggarwal measured lane, the page-fatal 10-tier, then any override."""
    if code in _IMPACT_OVERRIDES:
        return _IMPACT_OVERRIDES[code]
    conf, eff, measured = _CALIBRATION[code]
    base = _MEASURED_MATRIX[eff] if measured else _IMPACT_MATRIX[(conf, eff)]
    if code in _PAGE_FATAL_10 and conf == "Established" and eff == "large":
        return 10
    return base


def severity_from_impact(impact: int) -> str:
    """Single source of truth for severity (R3): derived from impact."""
    return "critical" if impact >= 8 else ("warning" if impact >= 4 else "info")


# R5.1 — codes whose finding is a property of the whole site, not one page.
# The scope lives on each ``_IssueSpec`` (below); this frozenset is the
# authoritative declaration and the catalogue entries must agree with it (an
# architecture-style test can cross-check). See job_store_base for how a
# site-scoped code is charged exactly once, site-wide.
_SITE_SCOPED_CODES: frozenset[str] = frozenset({
    "HTTP_PAGE",
    "HTTPS_REDIRECT_MISSING",
    "MIXED_CONTENT",
    "MISSING_HSTS",
    "WWW_CANONICALIZATION",
    # "Search Everywhere" GEO (P1) — findings that are site-level properties.
    "ENTITY_NAME_INCONSISTENT",
    "AUTHOR_IDENTITY_INCONSISTENT",
    "NEAR_DUPLICATE_BODY",
})


def issue_scope(code: str) -> str:
    """Return the scoring scope (``"page"`` | ``"site"``) for a catalogue code.

    Reads the ``scope`` field off the ``_IssueSpec``; unknown codes default to
    ``"page"`` (the safe, per-page default) rather than raising, so callers on a
    scoring hot-path never blow up on a stray code.
    """
    spec = _CATALOGUE.get(code)
    return spec.scope if spec is not None else "page"


_CATALOGUE: dict[str, _IssueSpec] = {
    # ── Metadata ──────────────────────────────────────────────────────────
    "TITLE_MISSING": _IssueSpec(
        category="metadata", severity="warning",
        description="Page has no <title> tag",
        recommendation="Add a unique title tag between 30–60 characters that clearly describes this page.",
        human_description="Missing Name Tag",
        what_it_is="The title tag is the most important on-page SEO element. It tells search engines and users what the page is about and appears as the clickable headline in search results.",
        impact_desc="Without a title tag, search engines may not index your page correctly, and users won't see a relevant headline in search results, significantly reducing your click-through rate.",
        how_to_fix="Add a <title> tag to the <head> section of your HTML. In WordPress, you can typically set this using your SEO plugin (Yoast, Rank Math) or the page editor.",
        fixability="wp_fixable",
    ),
    "TITLE_DUPLICATE": _IssueSpec(
        category="metadata", severity="warning",
        description="Same title used on multiple pages",
        recommendation="Make each page title unique. Describe what makes this page different from others on your site.",
        human_description="Duplicate Page Name",
        fixability="content_edit",
    ),
    "TITLE_TOO_SHORT": _IssueSpec(
        category="metadata", severity="info",
        description="Title under 30 characters",
        recommendation="Expand the title to 30–60 characters. Include your organisation name and the page topic.",
        human_description="Too-Short Page Name",
        fixability="wp_fixable",
    ),
    "TITLE_TOO_LONG": _IssueSpec(
        category="metadata", severity="info",
        description="Title over 60 characters",
        recommendation="Shorten the title to under 60 characters. Google truncates longer titles in search results.",
        human_description="Too-Long Page Name",
        fixability="wp_fixable",
    ),
    "META_DESC_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="No meta description",
        recommendation="Add a meta description of 70–160 characters summarising what visitors will find on this page.",
        human_description="Missing Summary Snippet",
        what_it_is="A meta description is a brief summary of a page's content that appears under the title in search results. It helps users decide whether to click on your link.",
        impact_desc="While not a direct ranking factor, a missing description forces search engines to pick random text from your page, which often looks unappealing and reduces click-through rates.",
        how_to_fix="Add a <meta name='description'> tag to your page. Use your SEO plugin to write a compelling summary that includes your primary keywords.",
        fixability="wp_fixable",
    ),
    "META_DESC_DUPLICATE": _IssueSpec(
        category="metadata", severity="info",
        description="Same meta description on multiple pages",
        recommendation="Write a unique meta description for this page that reflects its specific content.",
        human_description="Duplicate Summary Snippet",
        fixability="content_edit",
    ),
    "META_DESC_TOO_SHORT": _IssueSpec(
        category="metadata", severity="info",
        description="Meta description under 70 characters",
        recommendation="Expand the description to 70–160 characters to give search engines more context.",
        human_description="Too-Short Summary Snippet",
        fixability="wp_fixable",
    ),
    "META_DESC_TOO_LONG": _IssueSpec(
        category="metadata", severity="info",
        description="Meta description over 160 characters",
        recommendation="Shorten the description to under 160 characters. Longer descriptions are cut off in search results.",
        human_description="Too-Long Summary Snippet",
        fixability="wp_fixable",
    ),
    "SOCIAL_PREVIEW_METADATA_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="One or more social-preview meta tags are missing (og:title, "
                    "og:description, og:image, or twitter:card)",
        recommendation="Add the missing Open Graph / Twitter Card meta tags so shared links "
                       "render a proper title, description, and preview image. A single SEO "
                       "plugin setting usually populates all of them.",
        human_description="Missing Social Preview Metadata",
        what_it_is="Open Graph and Twitter Card tags control the title, description, and image "
                   "shown when your page is shared on social platforms. They are typically all "
                   "set by one plugin/theme option.",
        impact_desc="Shared links look unprofessional — missing image, wrong title, or plain-text "
                    "preview — reducing click-through from social platforms.",
        how_to_fix="Populate og:title, og:description, og:image and twitter:card (via your SEO "
                   "plugin or theme). The finding lists exactly which tags are missing.",
        fixability="content_edit",
    ),
    "CANONICAL_MISSING": _IssueSpec(
        category="metadata", severity="warning",
        description="No canonical tag — page has query strings or is a near-duplicate",
        recommendation="Add a canonical tag pointing to the preferred URL for this page to prevent duplicate content issues.",
        human_description="Ambiguous Preferred URL",
        fixability="developer_needed",
    ),
    "CANONICAL_EXTERNAL": _IssueSpec(
        category="metadata", severity="warning",
        description="Canonical points to a different domain",
        recommendation="Review this canonical tag — it is pointing search engines to a page on a different website.",
        human_description="External Preferred URL",
        fixability="developer_needed",
    ),
    "FAVICON_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="No favicon found (homepage only)",
        recommendation="Add a favicon to your site. This small icon appears in browser tabs and bookmarks and reinforces your brand.",
        human_description="Missing Website Icon",
        fixability="content_edit",
    ),
    # ── Headings ──────────────────────────────────────────────────────────
    "H1_MISSING": _IssueSpec(
        category="heading", severity="warning",
        description="No H1 tag found on page",
        recommendation="Add a single H1 heading that clearly states the main topic of this page.",
        human_description="Missing Main Heading",
        fixability="content_edit",
    ),
    "H1_MULTIPLE": _IssueSpec(
        category="heading", severity="info",
        description="More than one H1 on the page",
        recommendation="Remove extra H1 tags. Each page should have exactly one H1 that introduces the main topic.",
        human_description="Multiple Main Headings",
        fixability="content_edit",
    ),
    "HEADING_SKIP": _IssueSpec(
        category="heading", severity="info",
        description="Heading levels skip (e.g., H1 → H3)",
        recommendation="Fix the heading structure so levels are not skipped. Use H1, then H2, then H3 in order.",
        human_description="Skipped Heading Level",
        fixability="content_edit",
    ),
    "HEADING_EMPTY": _IssueSpec(
        category="heading", severity="info",
        description="One or more heading tags have no text content",
        recommendation="Remove empty heading tags or add descriptive text. Empty headings confuse screen readers and waste heading structure.",
        human_description="Empty Heading",
        fixability="content_edit",
    ),
    # ── Broken links ──────────────────────────────────────────────────────
    "BROKEN_LINK_404": _IssueSpec(
        category="broken_link", severity="info",
        description="Link destination returns 404 Not Found",
        recommendation="Remove or update this link. The page it points to no longer exists.",
        human_description="Dead Link",
        fixability="wp_fixable",
    ),
    "BROKEN_LINK_410": _IssueSpec(
        category="broken_link", severity="info",
        description="Link destination returns 410 Gone",
        recommendation="Remove this link. The destination has been permanently removed.",
        human_description="Removed Link",
        fixability="wp_fixable",
    ),
    "BROKEN_LINK_5XX": _IssueSpec(
        category="broken_link", severity="info",
        description="Link destination returns a server error",
        recommendation="Check whether the linked site is down. If the problem persists, remove or replace the link.",
        human_description="Broken Server Link",
        # A 5xx lives on the DESTINATION server — nothing in WordPress can fix
        # it. The author's action is to remove/replace the link (content edit).
        fixability="content_edit",
    ),
    "BROKEN_LINK_503": _IssueSpec(
        category="broken_link", severity="info",
        description="Link destination returns 503 — may be temporarily down or blocking automated checks",
        recommendation="Visit the link manually to see if it loads for real visitors. "
                       "If the problem persists, the destination site may be down or blocking crawlers.",
        human_description="Temporarily Blocked Link",
        fixability="developer_needed",
    ),
    "EXTERNAL_LINK_SKIPPED": _IssueSpec(
        category="broken_link", severity="info",
        description="Link not verified — social media platforms block automated checks",
        recommendation="Open this link in a browser to confirm it is working correctly.",
        human_description="Unverified Social Link",
        fixability="developer_needed",
    ),
    "EXTERNAL_LINK_TIMEOUT": _IssueSpec(
        category="broken_link", severity="info",
        description="External link did not respond — destination may be slow or unavailable",
        recommendation="Click the link to confirm it works in a browser. If it consistently fails, "
                       "the destination site may be down or the domain may have expired.",
        human_description="Slow External Link",
        fixability="developer_needed",
    ),
    # ── Redirects ─────────────────────────────────────────────────────────
    "REDIRECT_LOOP": _IssueSpec(
        category="redirect", severity="critical",
        description="Redirect loop detected",
        recommendation="Fix the redirect configuration immediately. This page cannot load and is invisible to search engines.",
        human_description="Spinning Page",
        fixability="developer_needed",
    ),
    "REDIRECT_301": _IssueSpec(
        category="redirect", severity="info",
        description="Page returns a permanent redirect",
        recommendation="Update any internal links pointing here to use the final destination URL directly.",
        human_description="Permanent Redirect",
        fixability="developer_needed",
    ),
    "REDIRECT_302": _IssueSpec(
        category="redirect", severity="info",
        description="Page returns a temporary redirect",
        recommendation="Confirm whether this redirect is intentional. If permanent, change it to a 301 redirect.",
        human_description="Temporary Redirect",
        fixability="developer_needed",
    ),
    "REDIRECT_CHAIN": _IssueSpec(
        category="redirect", severity="info",
        description="Page involves a multi-hop redirect chain",
        recommendation="Consolidate the redirect chain to a single direct redirect to the final destination.",
        human_description="Multi-Hop Detour",
        fixability="developer_needed",
    ),
    "REDIRECT_TRAILING_SLASH": _IssueSpec(
        category="redirect", severity="info",
        description="Redirect adds or removes a trailing slash — your CMS handles this automatically",
        recommendation="No urgent action needed. Your CMS corrects this for visitors automatically. "
                       "To eliminate the extra round trip, update internal links to use the canonical URL "
                       "with the trailing slash your server expects.",
        human_description="Auto-Corrected URL (Slash)",
        fixability="developer_needed",
    ),
    "REDIRECT_CASE_NORMALISE": _IssueSpec(
        category="redirect", severity="info",
        description="Redirect normalises URL case — your web server handles this automatically",
        recommendation="No urgent action needed. Your server redirects uppercase URLs to lowercase automatically. "
                       "To eliminate the extra redirect, update internal links to use lowercase-only URLs.",
        human_description="Auto-Corrected URL (Case)",
        fixability="developer_needed",
    ),
    "META_REFRESH_REDIRECT": _IssueSpec(
        category="redirect", severity="info",
        description="Page uses a <meta http-equiv=\"refresh\"> tag to redirect users",
        recommendation="Replace meta refresh redirects with server-side 301 redirects.",
        human_description="HTML Redirect (Outdated)",
        fixability="developer_needed",
    ),
    # ── Crawlability ──────────────────────────────────────────────────────
    "PAGE_TIMEOUT": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page did not respond within the timeout period",
        recommendation="Check the page manually. A persistent timeout may indicate a slow server, "
                       "heavy page weight, or a broken URL. Consider increasing server response speed.",
        human_description="Slow-Loading Page",
        fixability="developer_needed",
    ),
    "LOGIN_REDIRECT": _IssueSpec(
        category="crawlability", severity="info",
        description="Page redirects to a login screen",
        recommendation="This page requires a login to access. The crawler cannot audit it. Review manually if needed.",
        human_description="Login-Protected Page",
        fixability="developer_needed",
    ),
    "ROBOTS_BLOCKED": _IssueSpec(
        category="crawlability", severity="critical",
        description="Page blocked by robots.txt",
        recommendation="Check whether this page should be blocked. If not, update your robots.txt file.",
        human_description="Blocked by Crawl Rules",
        fixability="developer_needed",
    ),
    "NOINDEX_META": _IssueSpec(
        category="crawlability", severity="critical",
        description="Page has a noindex meta tag",
        recommendation="Confirm whether this page should be excluded from search results. Remove the noindex tag if not.",
        human_description="Hidden from Search",
        fixability="wp_fixable",
    ),
    "NOINDEX_HEADER": _IssueSpec(
        category="crawlability", severity="critical",
        description="Page has a noindex HTTP header",
        recommendation="Check your server configuration. This page is being hidden from search engines via an HTTP header.",
        human_description="Hidden from Search (Server)",
        fixability="developer_needed",
    ),
    "NOT_IN_SITEMAP": _IssueSpec(
        category="crawlability", severity="info",
        description="Crawlable page not listed in sitemap",
        recommendation="Add this URL to your XML sitemap so search engines can find it more reliably.",
        human_description="Missing from Sitemap",
        fixability="wp_fixable",
    ),
    "PDF_TOO_LARGE": _IssueSpec(
        category="crawlability", severity="info",
        description="PDF file exceeds 10 MB",
        recommendation="Reduce the PDF file size. Large PDFs are slow to download and may be skipped by crawlers.",
        human_description="Oversized Document",
        fixability="developer_needed",
    ),
    "IMG_OVERSIZED": _IssueSpec(
        category="image", severity="info",
        description="Image file exceeds 200 KB",
        recommendation="Compress this image. Use Squoosh, TinyPNG, or ImageOptim to reduce the file size without visible quality loss.",
        human_description="Oversized Image",
        fixability="content_edit",
    ),
    "PAGINATION_LINKS_PRESENT": _IssueSpec(
        category="crawlability", severity="info",
        description="Page declares rel=\"next\" or rel=\"prev\" pagination link elements",
        recommendation="No action required. Ensure the linked pages are crawlable.",
        human_description="Paginated Content",
        fixability="developer_needed",
    ),
    "THIN_CONTENT": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page has fewer than 300 words of body content",
        recommendation="Expand the page content to at least 300 words to provide more value to users and search engines.",
        human_description="Low Information",
        fixability="content_edit",
    ),
    "AMPHTML_BROKEN": _IssueSpec(
        category="crawlability", severity="info",
        description="Page declares an AMP version via <link rel=\"amphtml\"> but the AMP URL is not reachable",
        recommendation="Fix the AMP URL or remove the amphtml link element if AMP is no longer in use.",
        human_description="Broken Mobile Version",
        fixability="developer_needed",
    ),
    "HIGH_CRAWL_DEPTH": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page is more than 4 clicks from the homepage",
        recommendation="Improve internal linking so this page can be reached in 3 clicks or fewer from the homepage.",
        human_description="Hard-to-Reach Page",
        fixability="developer_needed",
    ),
    "ORPHAN_PAGE": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page has no internal links pointing to it — search engines may not discover it",
        recommendation="Add at least one internal link to this page from a navigation menu, hub page, "
                       "or relevant content page so search engines and visitors can find it.",
        human_description="Disconnected Page",
        # Adding internal links pointing at the page is content work, not dev.
        fixability="content_edit",
    ),
    "CONTENT_STALE": _IssueSpec(
        category="crawlability", severity="info",
        description="Page content has not been modified in over 12 months",
        recommendation="Review and refresh this page's content. Search engines favour recently updated pages, "
                       "and visitors may lose trust in outdated information. Even small updates signal freshness.",
        human_description="Stale Content",
        fixability="content_edit",
    ),
    # ── Sitemap ───────────────────────────────────────────────────────────
    "SITEMAP_MISSING": _IssueSpec(
        category="sitemap", severity="info",
        description="No sitemap found for this domain",
        recommendation="Create an XML sitemap and submit it to Google Search Console. Most CMS platforms can generate one automatically.",
        human_description="No Sitemap",
        fixability="developer_needed",
    ),
    # ── Duplicate content ─────────────────────────────────────────────────
    # ── Security (§E1) ────────────────────────────────────────────────────
    "HTTP_PAGE": _IssueSpec(
        category="security", severity="warning", scope="site",
        description="Page is served over HTTP, not HTTPS",
        recommendation="Migrate to HTTPS and configure a server-side 301 redirect from HTTP to HTTPS.",
        human_description="Unsecured Page",
        fixability="developer_needed",
    ),
    "MIXED_CONTENT": _IssueSpec(
        category="security", severity="warning", scope="site",
        description="HTTPS page loads resources over HTTP",
        recommendation="Update all resource URLs to use HTTPS. Check images, scripts, stylesheets, and iframes.",
        human_description="Partially Unsecured Page",
        fixability="developer_needed",
    ),
    "MISSING_HSTS": _IssueSpec(
        category="security", severity="info", scope="site",
        description="HTTPS page is missing the Strict-Transport-Security header",
        recommendation="Add Strict-Transport-Security: max-age=31536000; includeSubDomains to all HTTPS responses.",
        human_description="Security Header Missing",
        fixability="developer_needed",
    ),
    "UNSAFE_CROSS_ORIGIN_LINK": _IssueSpec(
        category="security", severity="info",
        description="External link opens in a new tab without rel=\"noopener\" or rel=\"noreferrer\"",
        recommendation="Add rel=\"noopener noreferrer\" to all <a target=\"_blank\"> links pointing to external URLs.",
        human_description="Unsafe External Link",
        fixability="developer_needed",
    ),
    "WWW_CANONICALIZATION": _IssueSpec(
        category="security", severity="warning", scope="site",
        description="Both www and non-www versions of the site resolve without redirecting to each other",
        recommendation="Configure a 301 redirect so one version (www or non-www) redirects to the other. This consolidates link equity and avoids duplicate content.",
        human_description="www/non-www Not Consolidated",
        fixability="developer_needed",
    ),
    # ── URL structure (§E2) ───────────────────────────────────────────────
    "URL_UPPERCASE": _IssueSpec(
        category="url_structure", severity="info",
        description="URL path contains uppercase characters",
        recommendation="Use lowercase-only URLs. Most web servers will auto-redirect uppercase URLs to lowercase, "
                       "but this creates an unnecessary extra redirect. Update internal links and page slugs "
                       "to use lowercase only to avoid that redirect entirely.",
        human_description="Mixed-Case Web Address",
        fixability="content_edit",
    ),
    "URL_HAS_SPACES": _IssueSpec(
        category="url_structure", severity="info",
        description="URL contains encoded spaces (%20)",
        recommendation="Replace spaces in URLs with hyphens.",
        human_description="Spaces in Web Address",
        fixability="content_edit",
    ),
    "URL_HAS_UNDERSCORES": _IssueSpec(
        category="url_structure", severity="info",
        description="URL path uses underscores instead of hyphens",
        recommendation="Use hyphens as word separators in URL paths. Google treats underscores as word-joiners.",
        human_description="Underscores in Web Address",
        fixability="content_edit",
    ),
    "URL_TOO_LONG": _IssueSpec(
        category="url_structure", severity="info",
        description="URL exceeds 200 characters",
        recommendation="Shorten the URL slug. Long URLs are harder to share and may be truncated in search results.",
        human_description="Overly Long Web Address",
        fixability="content_edit",
    ),
    # ── v1.5 bug fixes — codes that existed in scoring but had no catalogue entry ──
    "IMG_ALT_MISSING": _IssueSpec(
        category="image", severity="info",
        description="One or more images are missing an alt attribute or have empty/blank alt text",
        recommendation="Add a descriptive alt attribute to every <img> tag. Describe what the image shows "
                       "in plain language, e.g. alt=\"Counsellor speaking with a young person\". "
                       "Every image should have meaningful alt text for accessibility and SEO.",
        human_description="Images Missing Alt Text",
        fixability="wp_fixable",
    ),
    # ── v1.5 new codes ────────────────────────────────────────────────────
    "INTERNAL_REDIRECT_301": _IssueSpec(
        category="redirect", severity="info",
        description="Internal page URL redirects with a 301 — links should point to the final URL",
        recommendation="Update all internal links pointing to this URL to use the final destination directly. "
                       "This eliminates an unnecessary redirect for every visitor.",
        human_description="Internal Redirect Link",
        fixability="developer_needed",
    ),
    "MISSING_VIEWPORT_META": _IssueSpec(
        category="crawlability", severity="warning",
        description="Page is missing the viewport meta tag",
        recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1"> to the <head>. '
                       "Without it, mobile browsers render the page at desktop width and zoom out, making it hard to use.",
        human_description="Not Mobile-Friendly",
        fixability="developer_needed",
    ),
    "IMG_BROKEN": _IssueSpec(
        category="image", severity="warning",
        description="Image src URL returns an error response (4xx/5xx)",
        recommendation="Replace or remove the broken image. Use your CMS media library to re-upload the file "
                       "or update the src URL to point to the correct location.",
        human_description="Broken Image",
        fixability="developer_needed",
    ),
    # ── v1.9image - Enhanced Image Analysis ─────────────────────────────────
    "IMG_ALT_TOO_SHORT": _IssueSpec(
        category="image", severity="info",
        description="Image alt text is too short (under 5 characters)",
        recommendation="Expand the alt text to at least 5 characters. Describe what the image shows, "
                       "not just a single word.",
        human_description="Alt Text Too Short",
        fixability="wp_fixable",
    ),
    "IMG_ALT_TOO_LONG": _IssueSpec(
        category="image", severity="info",
        description="Image alt text is too long (over 125 characters)",
        recommendation="Shorten the alt text to under 125 characters. Be concise while still describing "
                       "the image content. Screen readers may truncate longer alt text.",
        human_description="Alt Text Too Long",
        fixability="wp_fixable",
    ),
    "IMG_ALT_GENERIC": _IssueSpec(
        category="image", severity="info",
        description="Image alt text uses a generic term like 'image', 'photo', or 'picture'",
        recommendation="Replace generic alt text with a specific description of what the image shows. "
                       "Instead of 'photo', describe the scene, people, or objects depicted.",
        human_description="Generic Alt Text",
        fixability="wp_fixable",
    ),
    "IMG_ALT_DUP_FILENAME": _IssueSpec(
        category="image", severity="info",
        description="Image alt text matches the filename",
        recommendation="Write descriptive alt text instead of using the filename. Describe what the "
                       "image shows to help search engines and screen reader users.",
        human_description="Alt Text is Filename",
        fixability="wp_fixable",
    ),
    "IMG_ALT_MISUSED": _IssueSpec(
        category="image", severity="info",
        description="Alt text usage is incorrect for image type (decorative image has alt text)",
        recommendation="Decorative images should have empty alt=\"\" to be skipped by screen readers. "
                       "Only meaningful images should have descriptive alt text.",
        human_description="Alt Text Misused",
        fixability="content_edit",
    ),
    "IMG_SLOW_LOAD": _IssueSpec(
        category="image", severity="info",
        description="Image takes too long to load (over 1 second)",
        recommendation="Optimize the image by compressing it, reducing dimensions, or using a CDN. "
                       "Consider lazy loading for below-the-fold images.",
        human_description="Slow Loading Image",
        fixability="developer_needed",
    ),
    "IMG_OVERSCALED": _IssueSpec(
        category="image", severity="info",
        description="Image intrinsic size is more than 2x its display size (wasted bandwidth)",
        recommendation="Resize the image to match its display dimensions. Use srcset to serve "
                       "appropriately sized images to different devices.",
        human_description="Overscaled Image",
        fixability="content_edit",
    ),
    "IMG_POOR_COMPRESSION": _IssueSpec(
        category="image", severity="info",
        description="Image has poor compression efficiency (high bytes per pixel)",
        recommendation="Re-compress the image using WebP format for better efficiency. "
                       "Use tools like Squoosh or ImageOptim for lossless compression.",
        human_description="Poor Compression",
        fixability="content_edit",
    ),
    "IMG_FORMAT_LEGACY": _IssueSpec(
        category="image", severity="info",
        description="Image uses legacy format (JPEG/PNG/GIF) where WebP would save significant space",
        recommendation="Convert to WebP format for 25-35% smaller file sizes with the same quality. "
                       "Most modern browsers support WebP.",
        human_description="Legacy Image Format",
        fixability="content_edit",
    ),
    "IMG_NO_SRCSET": _IssueSpec(
        category="image", severity="info",
        description="Large image lacks srcset for responsive delivery",
        recommendation="Add a srcset attribute to serve appropriately sized images to mobile devices. "
                       "This improves load times on smaller screens.",
        human_description="Missing Responsive Images",
        fixability="developer_needed",
    ),
    "IMG_DUPLICATE_CONTENT": _IssueSpec(
        category="image", severity="info",
        description="Same image content used under multiple URLs",
        recommendation="Consolidate duplicate images to a single URL. This saves server space "
                       "and improves caching efficiency.",
        human_description="Duplicate Image",
        fixability="developer_needed",
    ),
    "LINK_EMPTY_ANCHOR": _IssueSpec(
        category="metadata", severity="info",
        description="Link has no visible anchor text — screen readers and search engines cannot describe its destination",
        recommendation='Add descriptive text inside the link. If it is an icon-only link, add an aria-label attribute (e.g. aria-label="Donate now").',
        human_description="Empty Link Text",
        fixability="content_edit",
    ),
    "ANCHOR_TEXT_GENERIC": _IssueSpec(
        category="metadata", severity="info",
        description="Links use non-descriptive anchor text like 'click here' or 'read more'",
        recommendation="Replace generic link text with descriptive text that tells the reader (and search engines) where the link goes. Instead of 'click here', write 'view our counselling services'.",
        human_description="Non-Descriptive Link Text",
        fixability="content_edit",
    ),
    "INTERNAL_NOFOLLOW": _IssueSpec(
        category="crawlability", severity="warning",
        description='Internal link carries rel="nofollow", which may prevent search engines from discovering linked pages',
        recommendation='Remove the nofollow attribute from internal links. Reserve rel="nofollow" for links to '
                       "external or user-generated content.",
        human_description="Blocked Internal Link",
        fixability="developer_needed",
    ),
    "PAGE_SIZE_LARGE": _IssueSpec(
        category="crawlability", severity="info",
        description="HTML page response is unusually large — slower to load, especially on mobile connections",
        recommendation="Reduce page weight by removing unused HTML, lazy-loading off-screen content, and deferring "
                       "non-critical scripts. Large pages cost more mobile data and take longer to render.",
        human_description="Overweight Page",
        fixability="developer_needed",
    ),
    # ── v1.6 new codes ────────────────────────────────────────────────────────
    "LANG_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Page is missing the lang attribute on the <html> element",
        recommendation='Add a lang attribute to your <html> tag, e.g. <html lang="en">. '
                       "This tells search engines and screen readers what language your content is in, "
                       "improving accessibility and search accuracy for multilingual queries.",
        human_description="No Language Declared",
        fixability="developer_needed",
    ),
    "TITLE_H1_MISMATCH": _IssueSpec(
        category="metadata", severity="info",
        description="The page title and the H1 heading share no significant words",
        recommendation="Align the page title and H1 heading so they describe the same topic. "
                       "They do not need to be identical, but both should clearly reflect the page's main subject. "
                       "Significant mismatch confuses users who click a search result and then see an unrelated heading.",
        human_description="Title and Heading Disagree",
        fixability="wp_fixable",
    ),
    "HTTPS_REDIRECT_MISSING": _IssueSpec(
        category="security", severity="warning", scope="site",
        description="HTTP version of the site does not redirect to HTTPS",
        recommendation="Configure a server-side 301 redirect from http:// to https:// for all URLs on your domain. "
                       "Without this, visitors who type your address without 'https' will reach an insecure version "
                       "of your site — and search engines treat HTTP and HTTPS as separate, competing URLs.",
        human_description="Insecure URL Not Redirected",
        fixability="developer_needed",
    ),
    "CANONICAL_SELF_MISSING": _IssueSpec(
        category="metadata", severity="info",
        description="Indexable page has no canonical tag — consider adding a self-referencing canonical",
        recommendation='Add <link rel="canonical" href="[this-page-url]"> to the page <head>. '
                       "A self-referencing canonical is a best-practice signal to search engines "
                       "confirming which URL is the preferred version of this page.",
        human_description="No Canonical Tag",
        fixability="developer_needed",
    ),
    # ── AI Readiness ──────────────────────────────────────────────────────
    "LLMS_TXT_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="No llms.txt found at root",
        recommendation="Create an /llms.txt file to help LLMs and AI agents (Gemini, Perplexity) "
                       "accurately crawl and cite your high-value content.",
        human_description="Missing AI Instruction File",
        fixability="content_edit",
    ),
    "LLMS_TXT_INVALID": _IssueSpec(
        category="ai_readiness", severity="info",
        description="/llms.txt format is invalid",
        recommendation="Per llmstxt.org, the only required element is a Markdown '# Title' H1 heading; "
                       "a '>' summary and '## Section' link lists are optional and there is no URL cap. "
                       "Make sure the file is served as Markdown/plain text and isn't returning a normal "
                       "web page (soft 404).",
        human_description="Invalid AI Instruction File",
        fixability="content_edit",
    ),
    "SEMANTIC_DENSITY_LOW": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Text-to-HTML ratio is below 10%",
        recommendation="Clean up excessive code-bloat (styles, scripts, nested divs). "
                       "High code-to-text ratios consume more AI tokens and confuse retrieval engines.",
        human_description="High Code-to-Text Ratio",
        fixability="developer_needed",
    ),
    "DOCUMENT_PROPS_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="PDF is missing internal Title or Subject metadata",
        recommendation="Update PDF document properties to include a clear Title and Subject. "
                       "AIs use these properties for source labels and citations.",
        human_description="Missing Document Info",
        fixability="content_edit",
    ),
    "JSON_LD_MISSING": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="No JSON-LD structured data found on this indexable page",
        recommendation="Add <script type=\"application/ld+json\"> markup. Schema is the "
                       "'knowledge graph' used by AI systems for RAG-based answers.",
        human_description="Missing AI Schema",
        fixability="developer_needed",
    ),
    "CONVERSATIONAL_H2_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="H2 headings do not use conversational interrogatives (How, What, Why)",
        recommendation="Rewrite some H2 headings as questions. LLMs prefer direct question-answer "
                       "pairings for more accurate retrieval and citing.",
        human_description="Non-Conversational Headings",
        fixability="content_edit",
    ),
    "BLOG_SECTIONS_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Blog or article page lacks sufficient heading structure for AI citation anchors",
        recommendation="Add H2/H3 headings to break content into named sections. AI engines use "
                       "headings as citation anchors — a long post with fewer than 3 headings "
                       "cannot be accurately quoted or cited by AI.",
        human_description="No Section Headings for AI Citation",
        fixability="content_edit",
    ),
    # v2.0 AI Bot Access
    "AI_BOT_SEARCH_BLOCKED": _IssueSpec(
        category="ai_readiness", severity="critical",
        description="A major AI search bot is disallowed in robots.txt",
        recommendation="Allow AI search bots in robots.txt. This bot enables ChatGPT, Gemini, "
                       "and other AI engines to include your site in their answers.",
        human_description="AI Search Bot Blocked",
        fixability="developer_needed",
    ),
    "AI_BOT_TRAINING_DISALLOWED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="An AI training bot is disallowed in robots.txt",
        recommendation="This may be intentional. If accidental, allow the bot. "
                       "Blocking training bots does not affect AI search visibility.",
        human_description="AI Training Bot Disallowed",
        fixability="developer_needed",
    ),
    "AI_BOT_USER_FETCH_BLOCKED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="An AI user-fetch bot is disallowed in robots.txt",
        recommendation="Decide deliberately. robots.txt compliance for user-fetch bots is "
                       "vendor-specific: Anthropic's Claude-User honors robots.txt (so this block "
                       "does stop it — a real visibility cost if unintended), while OpenAI's "
                       "ChatGPT-User treats robots.txt as 'may not apply' and Perplexity-User "
                       "ignores it. Remove the block only if you want these assistants to fetch the page.",
        human_description="AI User Bot Blocked",
        fixability="developer_needed",
    ),
    "AI_BOT_DEPRECATED_DIRECTIVE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="robots.txt references a deprecated AI bot user agent",
        recommendation="Remove deprecated directives (anthropic-ai, claude-web) and replace with "
                       "current bot names (ClaudeBot, Claude-SearchBot, Claude-User).",
        human_description="Deprecated AI Bot Name in robots.txt",
        fixability="developer_needed",
    ),
    "AI_BOT_NO_AI_DIRECTIVES": _IssueSpec(
        category="ai_readiness", severity="info",
        description="robots.txt has no explicit directives for known AI bots",
        recommendation="Add explicit AI bot rules to make your intent clear. Example: allow all "
                       "search bots while optionally blocking training bots.",
        human_description="No AI Bot Configuration",
        fixability="developer_needed",
    ),
    "AI_BOT_BLANKET_DISALLOW": _IssueSpec(
        category="ai_readiness", severity="critical",
        description="robots.txt blocks all bots with User-agent: * / Disallow: /",
        recommendation="Update robots.txt to allow at least AI search bots. Remove 'Disallow: /' "
                       "or add specific allow rules for AI crawlers.",
        human_description="All Bots Blocked",
        fixability="developer_needed",
    ),
    "AI_BOT_TABLE_STALE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Internal AI bot reference table has not been reviewed in >12 months",
        recommendation="Review and update the TalkingToad AI bot reference table.",
        human_description="AI Bot Table Needs Review",
        fixability="developer_needed",
    ),
    # v2.0 Schema Typing
    "SCHEMA_TYPE_MISMATCH": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page schema type does not match inferred page type",
        recommendation="Ensure JSON-LD @type matches the page content (Article for blog posts, "
                       "Person for team bios, Service for service pages).",
        human_description="Mismatched Schema Type",
        fixability="content_edit",
    ),
    "SCHEMA_DEPRECATED_TYPE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page uses deprecated schema.org types",
        recommendation="Replace deprecated schema types with modern equivalents from schema.org.",
        human_description="Deprecated Schema Type",
        fixability="content_edit",
    ),
    "SCHEMA_TYPE_CONFLICT": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page declares multiple conflicting schema types",
        recommendation="Use a single coherent @type. For multiple entities use @graph or nesting.",
        human_description="Conflicting Schema Types",
        fixability="content_edit",
    ),
    # M3.1: Schema values not visible on page (Established — direct Google directive)
    "SCHEMA_VISIBLE_MISMATCH": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="A value declared in JSON-LD structured data does not appear in the page's visible text",
        recommendation="The report lists each mismatched field and the exact schema value that "
                       "isn't on the page. For each one, either add that text to the visible page "
                       "content or correct the schema so it matches what visitors see — Google "
                       "requires markup to match the on-page content.",
        human_description="Schema Not in Visible Text",
        fixability="content_edit",
        how_to_fix="For each field listed below, compare the schema value with the page. If the "
                   "value is correct but missing from the page, add it to the visible content "
                   "(heading, paragraph, FAQ, or address block). If the page is correct, update "
                   "the JSON-LD in your SEO plugin so its value matches the visible text.",
    ),
    # M3.2: Content not in textual form (Reasonable proxy — Google "make content textual")
    "AI_CONTENT_NOT_IN_TEXT": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Important content on this page is not in textual form — it is carried by "
                    "images/video or locked inside an embed (iframe/PDF) that AI systems cannot read as text",
        recommendation="Provide the key information as real on-page text. Add a textual summary "
                       "or transcript alongside any image, video, or embedded document so AI systems and screen "
                       "readers can access it.",
        human_description="Content Not Available as Text",
        fixability="content_edit",
    ),
    # M3.3: X-Robots-Tag AI-preview controls (Established — literal header facts)
    "AI_PREVIEW_SUPPRESSED": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="An X-Robots-Tag response header suppresses this page's search/AI preview "
                    "(nosnippet or max-snippet:0)",
        recommendation="If you want this page to be eligible for AI Overviews and citations, "
                       "remove the nosnippet / max-snippet:0 directive from the X-Robots-Tag "
                       "header (often set in server config or an SEO plugin).",
        human_description="AI Preview Suppressed",
        fixability="developer_needed",
    ),
    "AI_PREVIEW_BLOCKED_AT_BOT": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="An X-Robots-Tag directive specifically blocks an AI crawler "
                    "(e.g. GPTBot, Google-Extended) from indexing this page",
        recommendation="This is intentional if you don't want AI engines using this page. "
                       "If you DO want AI citation, remove the AI-bot-specific directive.",
        human_description="AI Bot Blocked",
        fixability="developer_needed",
    ),
    # M3.4: No visual companion for text-heavy content (Reasonable proxy — Google best practice)
    "AI_NO_VISUAL_COMPANION": _IssueSpec(
        category="ai_readiness", severity="info",
        description="A substantial text page (article/service/FAQ) has no images or video to "
                    "support its content",
        recommendation="Add at least one relevant, high-quality image or video. Visuals help "
                       "both readers and AI systems understand and surface your content.",
        human_description="No Supporting Visual",
        fixability="content_edit",
    ),
    # M3.5: Main content is a small share of total visible text (Heuristic)
    "AI_MAIN_CONTENT_LOW_RATIO": _IssueSpec(
        category="ai_readiness", severity="info",
        description="The main content area contains less than 40% of the page's visible text. "
                    "Navigation, sidebar, and footer content dominates, making it harder for "
                    "AI systems and readers to identify the primary content.",
        recommendation="Consider reducing navigation/sidebar/footer content, or expanding the "
                       "main content area. Ensure the main content is at least 40% of the "
                       "page's visible text.",
        human_description="Low Main Content Ratio",
        fixability="content_edit",
    ),
    # v2.0 Content Extractability
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": _IssueSpec(
        category="ai_readiness", severity="critical",
        description="Page has no visible text — only images, video, or interactive media",
        recommendation="Add descriptive text, captions, or transcripts. AI systems cannot extract "
                       "information from images or videos without accompanying text.",
        human_description="No Text Content",
        fixability="content_edit",
    ),
    "CONTENT_THIN": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Page has very little text (under 100 words)",
        recommendation="Expand the page with substantive content. Thin pages provide insufficient "
                       "context for AI systems to generate accurate summaries.",
        human_description="Thin Content",
        fixability="content_edit",
    ),
    "CONTENT_UNSTRUCTURED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has substantial text but no heading structure",
        recommendation="Add H2 and H3 headings to break content into sections. Headings help AI "
                       "systems identify topics and extract structured information.",
        human_description="No Heading Structure",
        fixability="content_edit",
    ),
    "CONTENT_IMAGE_HEAVY": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has significantly more images than text sections",
        recommendation="Add descriptive captions and surrounding text for each image. AI systems "
                       "rely on text context to interpret visual content.",
        human_description="Image-Heavy Layout",
        fixability="content_edit",
    ),
    # v2.0 Citation & Attribution
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has 200+ words but no citations or source attribution",
        recommendation="Add citations to factual claims. Use inline references or a Sources section.",
        human_description="Missing Citations",
        fixability="content_edit",
    ),
    "CITATIONS_ORPHANED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has citations without surrounding context",
        recommendation="Ensure each citation appears within a sentence that explains its relevance.",
        human_description="Citations Without Context",
        fixability="content_edit",
    ),
    "CITATIONS_SOURCES_INACCESSIBLE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page cites sources that are broken or inaccessible",
        recommendation="Replace broken citation links with working alternatives.",
        human_description="Inaccessible Citation Sources",
        fixability="content_edit",
    ),
    # ── v2.1 GEO Analyzer: Aggarwal et al. checks (Empirical) ──────────────
    "STATISTICS_COUNT_LOW": _IssueSpec(
        category="ai_readiness", severity="info",
        description="500+ word page contains no statistics (numbers paired with units, percentages, or dates)",
        recommendation="Add specific data points: percentages, measurements, dates, counts. "
                       "Aggarwal et al. (2023) found statistics measurably increase citation by generative engines.",
        human_description="No Statistics",
        fixability="content_edit",
    ),
    "EXTERNAL_CITATIONS_LOW": _IssueSpec(
        category="ai_readiness", severity="info",
        description="500+ word page has no outbound links to external authoritative sources in body text",
        recommendation="Add links to authoritative external sources (.gov, .edu, research papers, official docs). "
                       "Aggarwal et al. (2023) found citations measurably increase AI engine quotability.",
        human_description="No External Citations",
        fixability="content_edit",
    ),
    "QUOTATIONS_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="500+ word page contains no direct quotations from named sources",
        recommendation="Add quoted statements from named experts or sources. Use <blockquote> for longer quotes. "
                       "Aggarwal et al. (2023) found quotations measurably increase AI citation rates.",
        human_description="No Expert Quotations",
        fixability="content_edit",
    ),
    "ORPHAN_CLAIM_TECHNICAL": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Technical/how-to page has 3+ factual claims not paired with a source link or attribution",
        recommendation="Add a source link or attribution ('according to [source]') next to each specific "
                       "capability claim, number, or procedure step.",
        human_description="Unsourced Technical Claims",
        fixability="content_edit",
    ),
    # ── v2.1 GEO Analyzer: Mechanistic checks ───────────────────────────────
    "RAW_HTML_JS_DEPENDENT": _IssueSpec(
        category="ai_readiness", severity="critical",
        description="Page raw HTML is a JavaScript app shell with near-zero visible text",
        recommendation="Render critical content server-side (SSR) or as static HTML. AI crawlers "
                       "may not execute JavaScript, so JS-gated content is invisible to them.",
        human_description="JS-Only Content (No SSR)",
        fixability="developer_needed",
    ),
    "JS_RENDERED_CONTENT_DIFFERS": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Rendered page contains substantially more content than raw HTML (>20% more tokens)",
        recommendation="Pre-render key content as HTML so AI crawlers can access it without JavaScript. "
                       "Consider server-side rendering or static generation for important pages.",
        human_description="JS-Gated Content",
        fixability="developer_needed",
    ),
    "CONTENT_CLOAKING_DETECTED": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Rendered content appears to shift the page's topic versus raw HTML — possible cloaking",
        recommendation="Ensure raw HTML and rendered content describe the same topic. Serving different "
                       "content to AI crawlers than to users violates search quality guidelines.",
        human_description="Possible Content Cloaking",
        fixability="developer_needed",
    ),
    "UA_CONTENT_DIFFERS": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="AI crawler user agents (GPTBot, ClaudeBot) receive substantially less content than a browser",
        recommendation="Ensure AI crawler requests receive the same content as regular browsers. "
                       "Serving stripped content to AI bots prevents citation and indexing.",
        human_description="AI Bot Content Stripping",
        fixability="developer_needed",
    ),
    "FIRST_VIEWPORT_NO_ANSWER": _IssueSpec(
        category="ai_readiness", severity="info",
        description="First 200 words contain no direct answer signal (definition, TL;DR, summary phrase)",
        recommendation="Lead with a concise definition or summary ('X is...', 'In short...', 'Key takeaway:'). "
                       "AI systems read top-to-bottom; putting the answer in the first 200 words "
                       "maximises the chance it is retrieved and cited.",
        human_description="No Lead Answer",
        fixability="content_edit",
    ),
    "AUTHOR_BYLINE_MISSING": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="Blog or article page has no author byline, rel=author, or JSON-LD author field",
        recommendation="Add an author byline with name and optionally credentials. Include rel='author' "
                       "on the author link and an 'author' field in your JSON-LD BlogPosting schema.",
        human_description="No Author Attribution",
        fixability="content_edit",
    ),
    "DATE_PUBLISHED_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Blog or article page has no publication date in JSON-LD or meta tags",
        recommendation="Add datePublished to your JSON-LD schema and/or <meta property='article:published_time'>.",
        human_description="Missing Publication Date",
        fixability="developer_needed",
    ),
    "DATE_MODIFIED_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Blog or article page has no last-modified date in JSON-LD",
        recommendation="Add dateModified to your JSON-LD schema to signal content freshness to AI systems.",
        human_description="Missing Last-Modified Date",
        fixability="developer_needed",
    ),
    "CODE_BLOCK_MISSING_TECHNICAL": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Technical how-to/guide page with numbered steps has no <pre> or <code> blocks",
        recommendation="Wrap command-line examples, code snippets, and configuration in <code> or <pre> tags. "
                       "This makes them unambiguously extractable by AI systems.",
        human_description="No Code Blocks in Technical Guide",
        fixability="content_edit",
    ),
    "COMPARISON_TABLE_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page contains comparison language ('vs', 'versus', 'compared to') but no table",
        recommendation="Add a structured comparison table. Tables are the most extractable format for "
                       "comparisons — AI systems can read them as structured data.",
        human_description="Comparison Without Table",
        fixability="content_edit",
    ),
    "CHUNKS_NOT_SELF_CONTAINED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="More than half of the page's H2/H3 sections are not understandable in isolation",
        recommendation="Each section should open with a context sentence that restates the subject. "
                       "AI retrieval systems serve individual chunks, not whole pages.",
        human_description="Sections Lack Context",
        fixability="content_edit",
    ),
    "CENTRAL_CLAIM_BURIED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="The page's main claim or answer does not appear in the first 150 words",
        recommendation="State the central point in the opening paragraph. AI systems weight early content "
                       "more heavily when deciding what to extract and cite.",
        human_description="Main Point Buried",
        fixability="content_edit",
    ),
    # Cycle GG (2026-05-30): DOM-depth-based companion to
    # CENTRAL_CLAIM_BURIED. That one is word-position based; this one
    # looks at content-node depth under each <h2> heading. Together
    # they triangulate "the answer is hard to find" from two angles.
    "GEO_SUMMARY_BURIED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="The first paragraph or list does not lead its H2 or H3 section — the core "
                    "answer is pushed below images, media, or preamble",
        recommendation="Reorder each H2/H3 section so the core answer leads in 1–2 sentences, "
                       "with supporting content following. AI retrievers and skimming humans "
                       "both miss answers that aren't immediately under the heading.",
        human_description="Answer Buried Under H2/H3",
        fixability="content_edit",
    ),
    "LINK_PROFILE_PROMOTIONAL": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Over 80% of outbound body-text links point to the same organisation's own domains",
        recommendation="Add external citations to authoritative third-party sources. An all-internal "
                       "link profile signals low authority to AI systems.",
        human_description="All-Internal Link Profile",
        fixability="content_edit",
    ),
    "STRUCTURED_ELEMENTS_LOW": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has very few structured elements (lists, tables, code blocks) relative to content length",
        recommendation="Add bullet lists, numbered lists, or tables to break up prose. Structured elements "
                       "are more reliably extracted by AI chunkers than continuous paragraphs.",
        human_description="Low Structured Element Count",
        fixability="content_edit",
    ),
    # ── v2.1 GEO Analyzer: Conventional checks ──────────────────────────────
    "JSON_LD_INVALID": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="A JSON-LD block is present but missing @type or @context (invalid schema)",
        recommendation="Ensure every JSON-LD block includes both @type and @context fields. "
                       "Malformed schema blocks are ignored by search engines and AI parsers.",
        human_description="Invalid JSON-LD Schema",
        fixability="developer_needed",
    ),
    "FAQ_SCHEMA_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page has an FAQ section but no FAQPage JSON-LD schema",
        recommendation="Add FAQPage schema to your FAQ section so AI systems can extract Q&A pairs directly.",
        human_description="FAQ Without Schema",
        fixability="developer_needed",
    ),
    "FAQ_ANSWERS_NOT_IN_HTML": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="FAQ questions are in the HTML but their answers are not — the answer text "
                    "only appears after a JavaScript click, so AI crawlers (which don't click) can't read it",
        recommendation="Serve FAQ answer text in the page's HTML source, not injected on click. Use a "
                       "native accordion block (or an accordion plugin) that outputs the answer text "
                       "directly to the source, so AI systems and search engines can read every answer.",
        human_description="FAQ Answers Hidden From AI",
        fixability="developer_needed",
        confidence_label="Reasonable proxy",
    ),
    "PROMOTIONAL_CONTENT_INTERRUPTS": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Mid-article sections classified as promotional interrupt the content flow",
        recommendation="Move promotional or sales content to the end or to a sidebar. AI systems may "
                       "de-weight or skip sections they identify as promotional.",
        human_description="Promotional Content in Article",
        fixability="content_edit",
    ),
    "AI_TXT_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="No /ai.txt file found at site root",
        recommendation="Consider creating /ai.txt to declare AI usage policies and content permissions. "
                       "Emerging convention; no confirmed AI engine support yet.",
        human_description="No ai.txt File",
        fixability="developer_needed",
    ),
    # Tier 1 GEO heuristics (spec §4.3–4.6)
    "QUERY_COVERAGE_WEAK": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page H1 topic terms are under-represented in the intro or section headings — "
                    "AI retrieval systems may not associate this page with its target query",
        recommendation="Ensure the language from your H1 (the page's primary topic) appears naturally "
                       "in the first 200 words and in at least one H2 section heading. "
                       "AI systems score pages by query–content similarity; if your topic terms "
                       "don't appear where they look first, the page may be skipped.",
        human_description="Weak Query Coverage",
        fixability="content_edit",
    ),
    "SECTION_VAGUE_OPENER": _IssueSpec(
        category="ai_readiness", severity="info",
        description="One or more H2/H3 sections begin with a vague demonstrative reference "
                    "('This method…', 'It allows…', 'These features…') instead of an explicit subject",
        recommendation="Replace vague openers with explicit nouns: instead of 'This approach improves…' "
                       "write 'RAG retrieval improves…'. Each section must make sense in isolation — "
                       "AI systems extract sections as independent passages and cannot infer context.",
        human_description="Vague Section Openers",
        fixability="content_edit",
    ),
    "SECTION_CROSS_REFERENCES": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Page contains backward-reference phrases ('as mentioned above', 'as discussed earlier') "
                    "that break section independence",
        recommendation="Remove or replace phrases like 'as mentioned above' with the actual information being "
                       "referenced. AI systems cite individual passages in isolation — a passage that refers "
                       "to earlier content cannot be understood or quoted on its own.",
        human_description="Section Back-References",
        fixability="content_edit",
    ),
    "PARA_TOO_LONG": _IssueSpec(
        category="crawlability", severity="info",
        description="One or more paragraphs exceed 150 words, making content harder to scan and extract",
        recommendation="Break long paragraphs into shorter units of 50–100 words each. "
                       "Short paragraphs improve both human readability and AI passage extraction — "
                       "AI systems prefer self-contained, focused chunks.",
        human_description="Overly Long Paragraphs",
        fixability="content_edit",
    ),
    # M4.1: Content Freshness — visible date stale for page type
    "CONTENT_DATE_STALE_VISIBLE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Visible/declared modified date is old enough to read as stale for its page type",
        recommendation="Review the content for accuracy and update the visible date if the information "
                       "is still current. For evergreen content, consider removing the date entirely "
                       "or adding a note that it has been reviewed.",
        human_description="Stale Visible Date",
        fixability="content_edit",
        confidence_label="Reasonable proxy",
    ),
    # M4.2: Content Freshness — outdated statistic or year reference
    "CONTENT_STAT_OUTDATED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Body text references a year that is ≥24 months old without mentioning the current year.",
        recommendation="Update the statistic or reference to the current year, or add context that "
                       "acknowledges the original year while explaining continued relevance.",
        human_description="Outdated Year Reference",
        fixability="content_edit",
        confidence_label="Heuristic",
    ),
    # M5: AI Citation Ingestion
    "AI_CITED_PAGE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="This page has been cited by AI engines in the last 30 days, indicating established AI visibility.",
        recommendation="Maintain content quality and freshness to sustain AI citation status.",
        human_description="AI-Cited Page",
        fixability="content_edit",
        confidence_label="Established",
    ),
    "AI_HIGH_VALUE_UNCITED": _IssueSpec(
        category="ai_readiness", severity="info",
        description="This healthy, content-rich page has zero AI citations despite recent data, suggesting an AI visibility gap.",
        recommendation="Improve content structure, add schema markup, and build backlinks to increase AI discoverability.",
        human_description="High-Value Page Not AI-Cited",
        fixability="content_edit",
        confidence_label="Reasonable proxy",
    ),
    # ── Agent-readiness Phase 1 (WP2–WP5) — task-side checks ────────────────
    # WP2: rendering — navigation absent from server HTML
    "JS_DEPENDENT_NAVIGATION": _IssueSpec(
        category="rendering", severity="warning",
        description="The page's primary navigation links are not present in the server-rendered "
                    "HTML — they appear only after JavaScript runs",
        recommendation="Render your main navigation as real <a href> links in the server HTML "
                       "(server-side rendering or static output). AI crawlers and task-executing "
                       "agents that do not run JavaScript cannot follow JS-only navigation, so "
                       "they may never discover the rest of your site.",
        human_description="Navigation Needs JavaScript",
        what_it_is="A site's navigation menu should be real HTML links that are present the moment "
                   "the page is delivered. When the menu is built entirely by JavaScript in the "
                   "browser, the raw HTML an automated client receives has no links to follow.",
        impact_desc="AI crawlers (GPTBot, ClaudeBot, PerplexityBot) and task agents frequently do "
                    "not execute JavaScript. If your navigation is JS-only, they see a page with no "
                    "way forward and cannot reach your other pages — large parts of your site become "
                    "invisible to them.",
        how_to_fix="Use server-side rendering or static-site generation so the <nav> contains real "
                   "<a href> links in the initial HTML. A <noscript> fallback list of links also helps.",
        fixability="developer_needed",
    ),
    # WP3: semantic_html
    "NON_SEMANTIC_BUTTON": _IssueSpec(
        category="semantic_html", severity="info",
        description="A clickable control is built from a <div> or <span> with no button/link role "
                    "and no accessible name",
        recommendation="Use a real <button> or <a> element for clickable controls, or add "
                       'role="button" plus an accessible name (text, aria-label, or title). '
                       "Agents read the accessibility tree to decide what is operable.",
        human_description="Fake Button (div/span)",
        what_it_is="Buttons and links should be real <button>/<a> elements. A <div> or <span> with "
                   "a click handler looks clickable to a sighted mouse user but is invisible as a "
                   "control to anything reading the page structurally.",
        impact_desc="Task-executing agents and assistive technology identify what they can operate "
                    "from element roles. A <div> with no role is not recognised as a button, so an "
                    "agent cannot click it — the action it triggers becomes unreachable.",
        how_to_fix="Replace the <div>/<span> with a <button> (for actions) or <a href> (for "
                   'navigation). If you must keep the element, add role="button", tabindex="0", '
                   "and an accessible name.",
        fixability="developer_needed",
    ),
    "LANDMARK_MAIN_MISSING": _IssueSpec(
        category="semantic_html", severity="info",
        description="Page has no <main> landmark (or role=\"main\") identifying its primary content",
        recommendation="Wrap the primary content of the page in a <main> element. Landmarks let "
                       "agents and screen readers jump straight to the main content instead of "
                       "guessing where it begins.",
        human_description="No Main Content Landmark",
        what_it_is="The <main> landmark marks the principal content of a page, distinct from the "
                   "header, navigation, sidebar, and footer.",
        impact_desc="Without a <main> landmark, agents and assistive technology must heuristically "
                    "guess which part of the page is the real content, and may extract navigation "
                    "or boilerplate instead of your actual information.",
        how_to_fix="Wrap your primary content in <main>…</main> (one per page). Most themes have a "
                   "content template where this can be added.",
        fixability="developer_needed",
    ),
    "LANDMARK_NAV_MISSING": _IssueSpec(
        category="semantic_html", severity="info",
        description="Page has no <nav> landmark (or role=\"navigation\") identifying its navigation",
        recommendation="Wrap your primary navigation links in a <nav> element so agents and "
                       "assistive technology can recognise and use the site navigation.",
        human_description="No Navigation Landmark",
        what_it_is="The <nav> landmark marks a block of navigation links. It tells structural "
                   "readers 'these links are how you move around the site'.",
        impact_desc="Without a <nav> landmark, an agent cannot reliably distinguish navigation "
                    "from ordinary in-content links, making site traversal less reliable.",
        how_to_fix="Wrap your main menu in <nav>…</nav>. Add aria-label if you have more than one "
                   "navigation region (e.g. 'Primary', 'Footer').",
        fixability="developer_needed",
    ),
    "INTERACTIVE_NO_ACCESSIBLE_NAME": _IssueSpec(
        category="semantic_html", severity="info",
        description="An interactive element (button, link, or form field) has no accessible name — "
                    "no text, aria-label, or title",
        recommendation="Give every interactive element an accessible name: visible text, an "
                       "aria-label, an associated <label> (for fields), or a title attribute. "
                       "Icon-only controls especially need aria-label.",
        human_description="Unlabelled Control",
        what_it_is="An accessible name is the label an agent or screen reader announces for a "
                   "control. A button with only an icon, or an input with no label, has no name.",
        impact_desc="An agent deciding which control performs an action relies on the accessible "
                    "name. An unnamed control is ambiguous or unusable — the agent cannot tell "
                    "what it does and may skip it.",
        how_to_fix="Add visible text, an aria-label (e.g. aria-label=\"Search\"), a <label for> for "
                   "form fields, or a title attribute to each unnamed interactive element.",
        fixability="developer_needed",
    ),
    # WP4: placeholder / dead links
    "PLACEHOLDER_LINK": _IssueSpec(
        category="broken_link", severity="info",
        description="A navigational call-to-action links nowhere — its href is \"#\" or "
                    "\"javascript:void(0)\"",
        recommendation="Point the link at its real destination URL. A prominent call-to-action "
                       "(Donate, Contact, Sign up) whose only href is '#' goes nowhere for an "
                       "agent following links, even if JavaScript makes it work for a mouse user.",
        human_description="Dead Call-to-Action Link",
        what_it_is="A placeholder link is a styled link or button whose href is a stand-in ('#', "
                   "'javascript:void(0)') rather than a real URL. It often 'works' via JavaScript "
                   "for human clicks but resolves to nothing for an automated follower.",
        impact_desc="AI crawlers and task agents follow href values. A key action whose href is a "
                    "placeholder is a dead end — the agent cannot complete the journey (e.g. reach "
                    "your donation or contact page), and the page graph looks broken.",
        how_to_fix="Set the link's href to the actual target page. Reserve '#'/'javascript:void(0)' "
                   "for genuine in-page controls (accordions, tabs) — not for navigation.",
        fixability="developer_needed",
    ),
    "WRONG_PLACEHOLDER_LINK": _IssueSpec(
        category="broken_link", severity="info",
        description="A link points at a placeholder or example domain (example.com, localhost, or "
                    "a stray search-engine URL) instead of a real destination",
        recommendation="Replace the placeholder URL with the correct destination. Links to "
                       "example.com / localhost / a bare google.com are usually template leftovers "
                       "that were never filled in.",
        human_description="Link to Placeholder Domain",
        what_it_is="A link whose destination is an obvious placeholder — example.com, example.org, "
                   "localhost, 127.0.0.1, or a bare search-engine homepage used as filler — rather "
                   "than the page it was meant to point to.",
        impact_desc="An agent following the link lands somewhere meaningless (or unreachable), "
                    "breaking the task or citation trail. These are almost always unfinished "
                    "template content that shipped by mistake.",
        how_to_fix="Edit the link to use the real URL. If the link is a legitimate reference to "
                   "that domain, ignore the flag — the check is conservative and uses link text "
                   "and position to avoid false positives.",
        fixability="content_edit",
    ),
    # WP5: structured data presence (homepage Organization) + contact info
    "SCHEMA_ORG_MISSING": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="The homepage has no Organization (or LocalBusiness) JSON-LD schema identifying "
                    "the organisation",
        recommendation="Add Organization (or LocalBusiness) JSON-LD to your homepage with your "
                       "name, URL, logo, and contact details. This is the primary machine-readable "
                       "identity AI systems use to recognise and cite your organisation.",
        human_description="No Organization Schema",
        what_it_is="Organization schema is the structured-data block that states who you are — "
                   "name, logo, URL, social profiles, contact points. On the homepage it anchors "
                   "your entire site's identity in the knowledge graph.",
        impact_desc="AI systems build an entity profile of your organisation from Organization "
                    "schema. Without it, they must infer your identity from prose, which is less "
                    "reliable and weakens your chance of being correctly named and cited.",
        how_to_fix="Add a <script type=\"application/ld+json\"> Organization block to your homepage "
                   "(TalkingToad's Entity Schema Factory can generate one), or enable Organization "
                   "schema in your SEO plugin.",
        fixability="wp_fixable",
        confidence_label="Reasonable proxy",
    ),
    "CONTACT_INFO_NOT_IN_HTML": _IssueSpec(
        category="ai_readiness", severity="warning",
        description="The homepage's contact details (address, phone, or email) appear only inside "
                    "images or JavaScript, not as real text in the HTML",
        recommendation="Put your address, phone number, and email in the page as real text (not "
                       "baked into an image or injected by JavaScript). Agents and AI systems can "
                       "only extract and surface contact details they can read as text.",
        human_description="Contact Info Not in Text",
        what_it_is="Contact information that exists on the page only as an image (e.g. a phone "
                   "number in a banner graphic) or that is inserted by client-side JavaScript is "
                   "invisible to anything reading the raw HTML.",
        impact_desc="When an AI assistant is asked 'how do I contact this organisation?', it can "
                    "only answer from text it can read. Image- or JS-only contact details are "
                    "missed, so the agent cannot surface your phone, email, or address.",
        how_to_fix="Render contact details as plain HTML text in the footer or a contact block. "
                   "Optionally add ContactPoint / PostalAddress schema to reinforce them.",
        fixability="content_edit",
        confidence_label="Heuristic",
    ),
    # ── "Search Everywhere" GEO — brand-entity + body-uniqueness (P1) ────────
    # Spec: docs/pending/2026-07-22_p1-entity-consistency-near-duplicate.md
    # confidence_label falls back to _AI_READINESS_CONFIDENCE.
    "ENTITY_NAME_INCONSISTENT": _IssueSpec(
        category="ai_readiness", severity="warning", scope="site",
        description="The organisation is named differently in structured data across pages "
                    "(after casing/legal-suffix normalisation), so no single brand entity is asserted",
        recommendation="Pick one canonical Organization name and use it identically in the JSON-LD "
                       "on every page. AI systems attribute and cite content to a consistent named "
                       "entity — mixed names fragment that identity.",
        human_description="Inconsistent Organisation Name",
        what_it_is="Your Organization schema states your name. When different pages state it "
                   "differently, machines can't be sure they describe one organisation.",
        impact_desc="AI systems build one entity profile per name. Split names dilute the brand "
                    "signal that makes you 'the one people search for by name'.",
        how_to_fix="Standardise Organization.name across all pages/templates to a single spelling.",
        fixability="content_edit",
    ),
    "ENTITY_SAMEAS_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="An Organization or Person block in this page's JSON-LD has no sameAs links "
                    "to authoritative profiles (Wikipedia/Wikidata/official socials)",
        recommendation="Add a sameAs array to your Organization/Person schema pointing to your "
                       "Wikipedia/Wikidata entry and official social profiles — the bridge AI "
                       "systems use to resolve you to a knowledge-graph entity.",
        human_description="No sameAs Entity Links",
        what_it_is="sameAs links connect your entity to authoritative references, letting AI "
                   "confidently disambiguate and cite your organisation.",
        impact_desc="Without sameAs, there is no explicit link to the knowledge graph, weakening "
                    "entity resolution and citation confidence.",
        how_to_fix="Add sameAs URLs to the Organization/Person JSON-LD block.",
        fixability="content_edit",
    ),
    "AUTHOR_IDENTITY_INCONSISTENT": _IssueSpec(
        category="ai_readiness", severity="info", scope="site",
        description="The same author name appears under differing author URLs (or one URL under "
                    "differing names) across pages, fragmenting author identity",
        recommendation="Give each author one canonical profile URL and name, used consistently in "
                       "article schema. Consolidated author identity strengthens E-E-A-T signals.",
        human_description="Inconsistent Author Identity",
        what_it_is="Article schema names the author. Conflicting name↔URL pairings make it unclear "
                   "whether pages share one author.",
        impact_desc="Fragmented author identity weakens the expertise/authority signals AI uses to "
                    "trust and attribute content.",
        how_to_fix="Use one canonical author name + profile URL across all articles.",
        fixability="content_edit",
    ),
    "NEAR_DUPLICATE_BODY": _IssueSpec(
        category="ai_readiness", severity="warning", scope="site",
        description="Two or more pages have near-identical lead content after shared site template "
                    "(nav/footer) is removed — commodity content at high risk of AI absorption",
        recommendation="Consolidate the duplicates into one strong page (and canonical or redirect "
                       "the weaker ones), or differentiate each with first-party specifics. "
                       "Near-identical pages compete with themselves and are the easiest for AI "
                       "answers to replace.",
        human_description="Near-Duplicate Page Content",
        what_it_is="A comparison of each page's lead content (first ~1500 words, boilerplate "
                   "stripped) found pages that are near-identical to each other.",
        impact_desc="Generic, repeated content is the most 'absorbable' by AI answers — if many "
                    "pages say the same thing, one paragraph can replace them all.",
        how_to_fix="Merge or meaningfully differentiate the flagged pages.",
        fixability="content_edit",
    ),
    "BOILERPLATE_RATIO_HIGH": _IssueSpec(
        category="ai_readiness", severity="info",
        description="Most of this page's text is site-wide template (repeated on many other pages) "
                    "with little unique content of its own",
        recommendation="Add substantive first-party content unique to this page. A page that is "
                       "mostly shared template offers little for AI to cite and reads as thin.",
        human_description="Mostly Boilerplate",
        what_it_is="The share of this page's text that also appears across many other pages "
                   "(nav, footer, repeated CTAs) is high relative to its unique content.",
        impact_desc="Template-heavy pages have low citability and are prime AI-replacement targets.",
        how_to_fix="Expand the page with original, page-specific substance.",
        fixability="content_edit",
    ),
    # ── E3/E4 — schema completeness + author E-E-A-T (Search Everywhere P2) ──
    "HOWTO_SCHEMA_INCOMPLETE": _IssueSpec(
        category="ai_readiness", severity="info",
        description="This page has HowTo structured data but it declares no steps, so the "
                    "instructions aren't machine-readable",
        recommendation="Add a step list to your HowTo JSON-LD (each step with a name and text). "
                       "Complete HowTo markup lets AI systems extract and reproduce your "
                       "instructions accurately.",
        human_description="Incomplete HowTo Schema",
        what_it_is="HowTo schema describes a step-by-step procedure. Without a step array it "
                   "announces a how-to but gives machines nothing to extract.",
        impact_desc="AI answers and assistants reproduce procedures from structured steps. An "
                    "empty HowTo block wastes the signal.",
        how_to_fix="Populate the HowTo `step` array in your structured data.",
        fixability="developer_needed",
    ),
    "PRODUCT_REVIEW_SCHEMA_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="This page has Product structured data with no review or aggregateRating, so "
                    "no rating signal is exposed to search or AI",
        recommendation="Add review or aggregateRating to your Product JSON-LD when you have genuine "
                       "ratings. Rating markup drives review rich results and gives AI a trust signal.",
        human_description="Product Missing Review Schema",
        what_it_is="Product schema can carry reviews and an aggregate rating. Without them the "
                   "product is described but never rated in machine-readable form.",
        impact_desc="Review stars in search and AI trust signals both come from rating markup; a "
                    "Product block without it leaves that on the table.",
        how_to_fix="Add review / aggregateRating to the Product JSON-LD (only with real ratings).",
        fixability="developer_needed",
    ),
    "AUTHOR_CREDENTIALS_MISSING": _IssueSpec(
        category="ai_readiness", severity="info",
        description="This article names an author in its structured data, but the author entry has "
                    "no credentials — no job title, bio, sameAs, or profile URL",
        recommendation="Enrich the author schema with jobTitle, a short bio (description), and "
                       "sameAs/URL to an author profile. Author expertise is a core E-E-A-T signal.",
        human_description="Author Credentials Missing",
        what_it_is="A bare author name (no title, bio, or profile link) tells AI who wrote the "
                   "page but nothing about why they're credible.",
        impact_desc="Expertise and authority signals help AI and search decide whom to trust and "
                    "cite. A name alone is a weak signal.",
        how_to_fix="Add jobTitle / description / sameAs / url to the author Person in your JSON-LD.",
        fixability="content_edit",
    ),
}
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no",
    "its", "it", "this", "that", "we", "our", "your", "their", "my",
})


def _sig_words(text: str) -> set[str]:
    """Return significant (non-stop, length>=2) lowercase words from *text*."""
    return {
        w.lower() for w in re.findall(r"\w+", text)
        if len(w) >= 2 and w.lower() not in _STOP_WORDS
    }

def _titles_mismatch(title: str, h1: str) -> bool:
    """Return True if the page title and the H1 heading share no significant words.

    Strips a common site-name suffix (text after ' | ', ' - ', ' – ', ' · ')
    from the title before comparing so that "About Us | My Charity" and
    "About Us" are treated as matching rather than mismatching.
    The middle dot (·) is included because Yoast uses it as a common separator.
    """
    # Strip site-name suffix — pipe, hyphen, en-dash, em-dash, middle dot
    clean_title = re.split(r"\s[|·\-–—]\s", title)[0].strip()
    title_words = _sig_words(clean_title)
    h1_words = _sig_words(h1)
    if not title_words or not h1_words:
        return False  # too short to compare meaningfully
    return title_words.isdisjoint(h1_words)
# v2.3 M0.2 — Confidence labels for ai_readiness category codes.
# Per v2.0 AI-Readiness spec §2:
#   - "Established": vendor has publicly confirmed effect on AI crawling
#     or citation. Robots.txt directives for declared AI bots fall here.
#   - "Reasonable proxy": industry consensus treats it as influential;
#     partial vendor confirmation. Schema typing, JSON-LD, document props,
#     freshness signals fall here (Google has called all of these out as
#     things they consider).
#   - "Heuristic": industry consensus only, no vendor confirmation.
#     Passage-quality checks, llms.txt, and most extractability
#     micro-checks fall here.
#
# The architecture test in tests/test_architecture_constraints.py enforces
# that every code with category=="ai_readiness" has an entry here.
_AI_READINESS_CONFIDENCE: dict[str, str] = {
    # Regenerated from _CALIBRATION (R3, 2026-07-03). Canonical 3 tiers;
    # the Aggarwal 'measured' lane is tracked separately in _CALIBRATION.
    "AI_BOT_BLANKET_DISALLOW": "Established",
    "AI_BOT_DEPRECATED_DIRECTIVE": "Established",
    "AI_BOT_NO_AI_DIRECTIVES": "Heuristic",
    "AI_BOT_SEARCH_BLOCKED": "Established",
    "AI_BOT_TABLE_STALE": "Heuristic",
    "AI_BOT_TRAINING_DISALLOWED": "Established",
    "AI_BOT_USER_FETCH_BLOCKED": "Established",
    "AI_CITED_PAGE": "Established",
    "AI_CONTENT_NOT_IN_TEXT": "Reasonable proxy",
    "AI_HIGH_VALUE_UNCITED": "Heuristic",
    "AI_MAIN_CONTENT_LOW_RATIO": "Heuristic",
    "AI_NO_VISUAL_COMPANION": "Heuristic",
    "AI_PREVIEW_BLOCKED_AT_BOT": "Established",
    "AI_PREVIEW_SUPPRESSED": "Established",
    "AI_TXT_MISSING": "Heuristic",
    "AUTHOR_BYLINE_MISSING": "Reasonable proxy",
    "AUTHOR_IDENTITY_INCONSISTENT": "Heuristic",
    "BLOG_SECTIONS_MISSING": "Heuristic",
    "BOILERPLATE_RATIO_HIGH": "Heuristic",
    "HOWTO_SCHEMA_INCOMPLETE": "Heuristic",
    "PRODUCT_REVIEW_SCHEMA_MISSING": "Reasonable proxy",
    "AUTHOR_CREDENTIALS_MISSING": "Heuristic",
    "CENTRAL_CLAIM_BURIED": "Heuristic",
    "CHUNKS_NOT_SELF_CONTAINED": "Heuristic",
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": "Heuristic",
    "CITATIONS_ORPHANED": "Heuristic",
    "CITATIONS_SOURCES_INACCESSIBLE": "Heuristic",
    "CODE_BLOCK_MISSING_TECHNICAL": "Heuristic",
    "COMPARISON_TABLE_MISSING": "Heuristic",
    "CONTACT_INFO_NOT_IN_HTML": "Reasonable proxy",
    "CONTENT_CLOAKING_DETECTED": "Reasonable proxy",
    "CONTENT_DATE_STALE_VISIBLE": "Reasonable proxy",
    "CONTENT_IMAGE_HEAVY": "Heuristic",
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": "Established",
    "CONTENT_STAT_OUTDATED": "Heuristic",
    "CONTENT_THIN": "Reasonable proxy",
    "CONTENT_UNSTRUCTURED": "Reasonable proxy",
    "CONVERSATIONAL_H2_MISSING": "Heuristic",
    "DATE_MODIFIED_MISSING": "Reasonable proxy",
    "DATE_PUBLISHED_MISSING": "Reasonable proxy",
    "DOCUMENT_PROPS_MISSING": "Established",
    "ENTITY_NAME_INCONSISTENT": "Reasonable proxy",
    "ENTITY_SAMEAS_MISSING": "Reasonable proxy",
    "EXTERNAL_CITATIONS_LOW": "Heuristic",
    "FAQ_SCHEMA_MISSING": "Established",
    "FAQ_ANSWERS_NOT_IN_HTML": "Reasonable proxy",
    "FIRST_VIEWPORT_NO_ANSWER": "Heuristic",
    "GEO_SUMMARY_BURIED": "Heuristic",
    "JSON_LD_INVALID": "Reasonable proxy",
    "JSON_LD_MISSING": "Reasonable proxy",
    "JS_RENDERED_CONTENT_DIFFERS": "Established",
    "LINK_PROFILE_PROMOTIONAL": "Heuristic",
    "LLMS_TXT_INVALID": "Heuristic",
    "LLMS_TXT_MISSING": "Heuristic",
    "NEAR_DUPLICATE_BODY": "Reasonable proxy",
    "ORPHAN_CLAIM_TECHNICAL": "Heuristic",
    "PROMOTIONAL_CONTENT_INTERRUPTS": "Heuristic",
    "QUERY_COVERAGE_WEAK": "Heuristic",
    "QUOTATIONS_MISSING": "Heuristic",
    "RAW_HTML_JS_DEPENDENT": "Established",
    "SCHEMA_DEPRECATED_TYPE": "Established",
    "SCHEMA_ORG_MISSING": "Reasonable proxy",
    "SCHEMA_TYPE_CONFLICT": "Reasonable proxy",
    "SCHEMA_TYPE_MISMATCH": "Reasonable proxy",
    "SCHEMA_VISIBLE_MISMATCH": "Established",
    "SECTION_CROSS_REFERENCES": "Heuristic",
    "SECTION_VAGUE_OPENER": "Heuristic",
    "SEMANTIC_DENSITY_LOW": "Heuristic",
    "STATISTICS_COUNT_LOW": "Heuristic",
    "STRUCTURED_ELEMENTS_LOW": "Heuristic",
    "UA_CONTENT_DIFFERS": "Reasonable proxy",
}
def make_issue(
    code: str,
    page_url: str | None = None,
    extra: dict | None = None,
    *,
    job_id: str = "",
) -> Issue:
    """Construct an :class:`Issue` from a code in the catalogue.

    Automatically populates *impact*, *effort*, and *priority_rank* from
    :data:`_ISSUE_SCORING`.

    Raises :class:`KeyError` if *code* is not in :data:`_CATALOGUE` — a typo'd
    or unregistered code must fail fast, not silently produce a zero-scored,
    empty-metadata issue that buries itself in every ranking. (The parity tests
    guarantee every catalogue code also has a scoring entry, so the ``.get()``
    fallback below is defensive only and never hit for a real catalogue code.)

    For ai_readiness category codes, also populates *confidence_label* from
    :data:`_AI_READINESS_CONFIDENCE` per the v2.0 spec confidence taxonomy.

    Args:
        code: The issue code from the catalogue.
        page_url: The URL of the page where the issue was found.
        extra: Optional supplementary data.
        job_id: The crawl job ID (used for image analysis module).
    """
    try:
        spec = _CATALOGUE[code]
    except KeyError:
        raise KeyError(
            f"make_issue: unknown issue code {code!r} — not found in _CATALOGUE. "
            f"Register the code in api/crawler/checkers/registry.py "
            f"(_CATALOGUE + _ISSUE_SCORING) before emitting it."
        ) from None
    impact, effort = _ISSUE_SCORING.get(code, (0, 0))
    # R3 priority formula: effort weighted ×6 so it can reorder WITHIN an impact
    # tier (surfacing volunteer "quick wins") but never across two tiers.
    priority_rank = (impact * 10) - (effort * 6)
    quick_win = impact >= 4 and effort <= 1
    # Prefer the spec-attached confidence_label if set (lets individual
    # codes override the lookup); otherwise read from the centralised map.
    confidence_label = spec.confidence_label or _AI_READINESS_CONFIDENCE.get(code)
    # R5.5 — severity is DERIVED from impact at runtime, not copied from the
    # stored _IssueSpec.severity literal. severity_from_impact is the single
    # source of truth (R3); a parity test keeps the stored literals equal to the
    # derived value, so this changes no current output — it only removes the
    # possibility of a drifted literal leaking a wrong severity into a live issue.
    return Issue(
        code=code,
        category=spec.category,
        severity=severity_from_impact(impact),
        description=spec.description,
        recommendation=spec.recommendation,
        page_url=page_url,
        extra=extra,
        impact=impact,
        effort=effort,
        priority_rank=priority_rank,
        quick_win=quick_win,
        human_description=spec.human_description,
        what_it_is=spec.what_it_is,
        impact_desc=spec.impact_desc,
        how_to_fix=spec.how_to_fix,
        fixability=spec.fixability,
        confidence_label=confidence_label,
    )
# ---------------------------------------------------------------------------
# Per-page checks
# ---------------------------------------------------------------------------

_DEFAULT_PAGE_SIZE_LIMIT_KB = 300
_PDF_SIZE_LIMIT   = 10 * 1024 * 1024  # 10 MB
_IMAGE_SIZE_LIMIT_KB = 200  # default, overridable per job
