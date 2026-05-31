"""
Issue detection logic for the TalkingToad crawler.

**Facade (v2.6 M9.1 / Cycle K).** This module used to be a 2,567-line
monolith. In Cycle K the data structures, the catalogue, the make_issue
factory, the already-extracted ``_check_*`` helpers, and the standalone
checks (``check_asset``, ``check_url_structure``, ``check_amphtml_links``,
``check_cross_page``, ``issue_for_status``, ``issues_for_redirect``,
``_run_geo_checks`` + all GEO helpers) were moved into
``api/crawler/checkers/``. This file is now a thin orchestrator plus a set
of back-compat re-exports so that every existing caller
(``engine.py``, the routers, the test suite, the docs generator) can keep
``from api.crawler.issue_checker import ...`` unchanged.

See ``docs/pending/2026-05-28_issue-checker-split.md`` for the split spec.

The remaining inline body of ``check_page`` is the per-page orchestration
itself — it sets up shared state (banner-H1 suppression) and emits issues
in a specific interleaved order across domains. Further extraction of those
inline blocks into per-domain functions is follow-up work; it requires
either preserving the exact interleaved emission order (test-coupled) or
proving the order doesn't matter (whole-suite re-validation).
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from api.crawler.parser import ParsedPage

# ── Back-compat re-exports from the new checkers package ────────────────
# Every name historically importable from ``api.crawler.issue_checker`` is
# re-exported here so that engine.py, routers, services, the docs
# generator, and the test suite continue to work without rewrites.
from api.crawler.checkers.registry import (  # noqa: F401
    Issue,
    _IssueSpec,
    _ISSUE_SCORING,
    _CATALOGUE,
    _AI_READINESS_CONFIDENCE,
    _STOP_WORDS,
    _GENERIC_ANCHOR_TEXTS,
    _DEFAULT_PAGE_SIZE_LIMIT_KB,
    _PDF_SIZE_LIMIT,
    _IMAGE_SIZE_LIMIT_KB,
    make_issue,
    _sig_words,
    _titles_mismatch,
)
from api.crawler.checkers.cross_page import check_cross_page  # noqa: F401
from api.crawler.checkers.images import check_asset  # noqa: F401
from api.crawler.checkers.url_structure import check_url_structure  # noqa: F401
from api.crawler.checkers.crawlability import (  # noqa: F401
    check_amphtml_links,
    _check_crawlability,
)
from api.crawler.checkers.links import (  # noqa: F401
    issue_for_status,
    issues_for_redirect,
    _is_trailing_slash_only,
    _is_case_normalise_only,
)
from api.crawler.checkers.security import _check_security  # noqa: F401
from api.crawler.checkers.metadata import _check_canonical  # noqa: F401
from api.crawler.checkers.headings import _check_headings  # noqa: F401
from api.crawler.checkers.ai_readiness import _run_geo_checks  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-page orchestrator
# ---------------------------------------------------------------------------
#
# This function is intentionally NOT factored into per-domain helpers in this
# cycle. The emission order across domains is interleaved (e.g. canonical →
# canonical-self → lang → title-h1 mismatch → headings, then favicon →
# crawlability → sitemap → security → pagination → ...), and several tests
# depend on issue-list contents that are order-sensitive to filter logic.
# A pure-delegation rewrite of this function is tracked as follow-up work.


def check_page(
    page: ParsedPage,
    *,
    sitemap_urls: set[str] | None = None,
    favicon_emitted: bool = False,
    hsts_checked_hosts: set[str] | None = None,
    page_size_limit_kb: int = _DEFAULT_PAGE_SIZE_LIMIT_KB,
    suppress_h1_strings: list[str] | None = None,
    suppress_banner_h1: bool = False,
    exempt_anchor_urls: set[str] | None = None,
    ignored_image_patterns: list[str] | None = None,
) -> list[Issue]:
    """Run all per-page issue checks.

    Args:
        page: The parsed page to check.
        sitemap_urls: Set of normalised URLs found in the sitemap (or None if no sitemap).
        favicon_emitted: True if FAVICON_MISSING has already been emitted this job.
        hsts_checked_hosts: Mutable set of hosts already checked for HSTS (pass the same
            set across all pages in a job so we only emit once per host).

    Returns:
        List of issues found. Cross-page checks (duplicates, near-duplicates) are
        not included — call :func:`check_cross_page` after all pages are crawled.
    """
    issues: list[Issue] = []
    url = page.url

    # Pages with noindex directives are intentionally excluded from search — skip SEO
    # checks that would only apply to indexed pages. We still run crawlability checks
    # (to surface the noindex issue itself) and security checks.
    is_indexable = page.is_indexable

    # Build effective H1 list — filter out theme-injected headings the user
    # has explicitly suppressed (e.g. a Salient page-header banner title that
    # repeats on every post page).
    # Normalise both sides: strip whitespace and compare case-insensitively so
    # that minor variations (trailing \xa0, different capitalisation) don't
    # silently defeat the suppression.
    _suppress_norm = {s.strip().casefold() for s in (suppress_h1_strings or [])}
    effective_h1s = [h for h in page.h1_tags if h.strip().casefold() not in _suppress_norm]
    effective_outline = [
        h for h in page.headings_outline
        if not (h["level"] == 1 and h["text"].strip().casefold() in _suppress_norm)
    ]

    # When suppress_banner_h1 is enabled, detect and remove the theme-injected
    # banner H1.  Two signals identify a banner:
    #   1. Position: the first H1 in the DOM (themes inject banners before content)
    #   2. CSS class: common theme banner classes (entry-title, page-title, etc.)
    # The first H1 is removed if it mismatches the title OR has a banner class.
    # Only applied when there are 2+ H1s so we never remove the only heading.
    _BANNER_CLASSES = re.compile(
        r'entry-title|page-title|page-header|banner-title|hero-title|archive-title',
        re.IGNORECASE,
    )

    if suppress_banner_h1 and page.title and len(effective_h1s) >= 2:
        first_h1 = effective_h1s[0]
        # Check CSS classes on the first H1 in the outline
        first_h1_outline = next(
            (h for h in effective_outline if h.get("level") == 1),
            None,
        )
        # Defensive: `.get("classes", "")` returns None when the key is
        # present with an explicit None value (common parser artifact for
        # malformed tags). `re.search(None)` raises TypeError and would
        # crash the entire crawl for the affected domain. The `or ""`
        # coalesces both "key missing" and "key present with None" to "".
        has_banner_class = bool(
            first_h1_outline
            and _BANNER_CLASSES.search(first_h1_outline.get("classes") or "")
        )
        is_mismatch = _titles_mismatch(page.title, first_h1)

        if is_mismatch or has_banner_class:
            _banner_text = first_h1.strip().casefold()
            effective_h1s = effective_h1s[1:]
            effective_outline = [
                h for h in effective_outline
                if not (
                    h["level"] == 1
                    and h.get("text", "").strip().casefold() == _banner_text
                )
            ]

    if is_indexable:
        # ── Title ──────────────────────────────────────────────────────────
        if not page.title:
            issues.append(make_issue("TITLE_MISSING", url,
                                     extra={"h1": effective_h1s[0] if effective_h1s else None}))
        else:
            length = len(page.title)
            if length < 30:
                issue = make_issue("TITLE_TOO_SHORT", url)
                issue.extra = {"title": page.title, "length": length}
                issues.append(issue)
            elif length > 60:
                issue = make_issue("TITLE_TOO_LONG", url)
                issue.extra = {"title": page.title, "length": length}
                issues.append(issue)

        # ── Meta description ───────────────────────────────────────────────
        if not page.meta_description:
            issues.append(make_issue("META_DESC_MISSING", url))
        else:
            length = len(page.meta_description)
            if length < 70:
                issue = make_issue("META_DESC_TOO_SHORT", url)
                issue.extra = {"description": page.meta_description, "length": length}
                issues.append(issue)
            elif length > 160:
                issue = make_issue("META_DESC_TOO_LONG", url)
                issue.extra = {"description": page.meta_description, "length": length}
                issues.append(issue)

        # ── OG tags ────────────────────────────────────────────────────────
        if not page.og_title:
            issues.append(make_issue("OG_TITLE_MISSING", url,
                                     extra={"title": page.title}))
        if not page.og_description:
            issues.append(make_issue("OG_DESC_MISSING", url,
                                     extra={"meta_description": page.meta_description}))
        if not page.og_image:
            issues.append(make_issue("OG_IMAGE_MISSING", url))
        if not page.twitter_card:
            issues.append(make_issue("TWITTER_CARD_MISSING", url))

        # ── Canonical tag ──────────────────────────────────────────────────
        _check_canonical(page, issues)

        # ── Canonical self (best-practice for all indexable pages) ──────────
        # Only emit if CANONICAL_MISSING hasn't already fired — that issue is
        # more specific and actionable; emitting both on the same page is redundant.
        if page.canonical_url is None and not any(i.code == "CANONICAL_MISSING" for i in issues):
            issues.append(make_issue("CANONICAL_SELF_MISSING", url,
                                     extra={"expected_canonical": url}))

        # ── Language attribute ─────────────────────────────────────────────
        if not page.lang_attr:
            issues.append(make_issue("LANG_MISSING", url))

        # ── Title vs H1 consistency ────────────────────────────────────────
        # Use effective_h1s (suppressed strings removed) so theme-injected
        # headings don't trigger a false mismatch.
        if page.title and effective_h1s:
            if all(_titles_mismatch(page.title, h1) for h1 in effective_h1s):
                # Before flagging, check whether the title matches an H2.
                # Many WordPress themes inject the parent-page title as an H1
                # banner on sub-pages, while the real content heading is an H2.
                # If the title shares significant words with any H2 we treat
                # the H1 as a structural/navigation element and skip the flag.
                h2_texts = [
                    h["text"] for h in (page.headings_outline or [])
                    if h.get("level") == 2 and h.get("text")
                ]
                title_matches_h2 = any(
                    not _titles_mismatch(page.title, h2) for h2 in h2_texts
                )
                if not title_matches_h2:
                    issues.append(make_issue("TITLE_H1_MISMATCH", url,
                                             extra={"title": page.title, "h1": effective_h1s[0]}))

        # ── Headings ───────────────────────────────────────────────────────
        _check_headings(page, issues, effective_h1s=effective_h1s, effective_outline=effective_outline)

    # ── Favicon (homepage only, once per job — checked regardless of noindex) ──
    if page.has_favicon is False and not favicon_emitted:
        issues.append(make_issue("FAVICON_MISSING", url))

    # ── Crawlability ───────────────────────────────────────────────────────
    _check_crawlability(page, issues)

    # ── Not in sitemap (only meaningful for indexable pages) ──────────────
    # Skip pages with query strings — paginated URLs, search results, and
    # filtered views are intentionally absent from sitemaps.
    if sitemap_urls is not None and is_indexable and not urlparse(url).query:
        if page.final_url not in sitemap_urls and page.url not in sitemap_urls:
            issues.append(make_issue("NOT_IN_SITEMAP", url))

    # ── Security (§E1) ────────────────────────────────────────────────────
    _check_security(page, issues, hsts_checked_hosts=hsts_checked_hosts)

    # ── Pagination links (§E3) ────────────────────────────────────────────
    if page.pagination_next or page.pagination_prev:
        issues.append(make_issue(
            "PAGINATION_LINKS_PRESENT", url,
            extra={"next": page.pagination_next, "prev": page.pagination_prev},
        ))

    # ── Meta refresh redirect (§E4) ───────────────────────────────────────
    if page.meta_refresh_url is not None:
        issues.append(make_issue("META_REFRESH_REDIRECT", url,
                                 extra={"refresh_url": page.meta_refresh_url}))

    # ── Thin content (§E5) ────────────────────────────────────────────────
    if page.word_count is not None and 0 < page.word_count < 300 and page.is_indexable:
        issues.append(make_issue("THIN_CONTENT", url, extra={"word_count": page.word_count}))

    # ── Crawl depth (§E7) ────────────────────────────────────────────────
    if page.crawl_depth is not None and page.crawl_depth > 4:
        issues.append(make_issue("HIGH_CRAWL_DEPTH", url,
                                 extra={"crawl_depth": page.crawl_depth}))

    # ── Content staleness ────────────────────────────────────────────────
    if page.last_modified and page.is_indexable:
        try:
            from email.utils import parsedate_to_datetime
            from datetime import timezone as _tz
            lm_dt = parsedate_to_datetime(page.last_modified)
            if lm_dt.tzinfo is None:
                lm_dt = lm_dt.replace(tzinfo=_tz.utc)
            age_days = (datetime.now(_tz.utc) - lm_dt).days
            if age_days > 365:
                issues.append(make_issue("CONTENT_STALE", url,
                    extra={"last_modified": page.last_modified, "age_days": age_days}))
        except Exception:
            pass

    # ── Image alt text ────────────────────────────────────────────────────
    if page.img_missing_alt_count > 0:
        srcs = page.img_missing_alt_srcs or []
        # Filter out images matching ignored patterns (e.g. theme SVG icons)
        if ignored_image_patterns:
            srcs = [s for s in srcs if not any(p in s for p in ignored_image_patterns)]
        if srcs:
            issue = make_issue("IMG_ALT_MISSING", url,
                               extra={"missing_alt_count": len(srcs),
                                      "img_missing_alt_srcs": srcs[:10]})
            listed = ", ".join(srcs[:5])
            suffix = f" and {len(srcs) - 5} more" if len(srcs) > 5 else ""
            issue.description = (
                f"{len(srcs)} image{'s' if len(srcs) > 1 else ''} "
                f"missing alt text: {listed}{suffix}"
            )
            issues.append(issue)

    # ── Viewport meta (mobile-friendliness) ──────────────────────────────
    if not page.has_viewport_meta:
        issues.append(make_issue("MISSING_VIEWPORT_META", url))

    # ── Structured data (schema.org) ──────────────────────────────────────
    if not page.schema_types and is_indexable:
        issues.append(make_issue("SCHEMA_MISSING", url))

    # ── Empty anchor text ─────────────────────────────────────────────────
    if page.empty_anchor_count > 0:
        raw_anchors = page.empty_anchor_hrefs or []
        # Normalise every entry to a {"href", "aria_label", "has_children"} dict.
        # Both formats are supported (legacy list[str], current list[dict]) and
        # malformed entries are dropped silently rather than crashing the crawl
        # — three sites below blindly read a["href"], so any dict without a
        # usable href would raise KeyError and kill the entire job.
        # The previous `isinstance(anchors[0], str)` sniff only inspected the
        # first element; a mixed list (legacy strings interleaved with new
        # dicts) skipped coercion and crashed downstream.
        anchors: list[dict] = []
        for a in raw_anchors:
            if isinstance(a, str):
                if a:
                    anchors.append({"href": a, "aria_label": None, "has_children": False})
            elif isinstance(a, dict):
                href = a.get("href")
                if isinstance(href, str) and href:
                    anchors.append(a)
            # else: malformed entry — drop
        # Filter out URLs the user has explicitly exempted (e.g. social media icon links)
        if exempt_anchor_urls:
            anchors = [a for a in anchors if a["href"] not in exempt_anchor_urls]
        if anchors:
            issue = make_issue("LINK_EMPTY_ANCHOR", url,
                               extra={"empty_anchor_count": len(anchors),
                                      "empty_anchors": anchors[:10],
                                      # Keep legacy field for backwards compat
                                      "empty_anchor_hrefs": [a["href"] for a in anchors[:10]]})
            href_list = [a["href"] for a in anchors[:5]]
            listed = ", ".join(href_list)
            suffix = f" and {len(anchors) - 5} more" if len(anchors) > 5 else ""
            issue.description = (
                f"{len(anchors)} link{'s' if len(anchors) > 1 else ''} "
                f"with no anchor text: {listed}{suffix}"
            )
            issues.append(issue)

    # ── Generic anchor text ──────────────────────────────────────────────
    if page.is_indexable and page.links:
        generic_links = [
            link for link in page.links
            if link.text and link.text.strip().lower() in _GENERIC_ANCHOR_TEXTS
        ]
        if generic_links:
            issues.append(make_issue("ANCHOR_TEXT_GENERIC", url,
                extra={"count": len(generic_links),
                        "examples": [{"href": l.url, "text": l.text} for l in generic_links[:5]]}))

    # ── Internal nofollow links ───────────────────────────────────────────
    if page.internal_nofollow_count > 0:
        issues.append(make_issue("INTERNAL_NOFOLLOW", url,
                                 extra={"internal_nofollow_count": page.internal_nofollow_count}))

    # ── Page size ─────────────────────────────────────────────────────────
    _page_size_threshold = page_size_limit_kb * 1024
    if page.response_size_bytes > _page_size_threshold:
        size_kb = round(page.response_size_bytes / 1024, 1)
        issue = make_issue("PAGE_SIZE_LARGE", url,
                           extra={"size_bytes": page.response_size_bytes,
                                  "size_kb": size_kb,
                                  "limit_kb": page_size_limit_kb})
        issue.description = f"Page HTML is {size_kb} KB (exceeds {page_size_limit_kb} KB limit)"
        issues.append(issue)

    # ── AI Readiness (§1.7) ───────────────────────────────────────────────
    # Semantic Density (Text-to-HTML ratio < 10%)
    if page.text_to_html_ratio is not None and page.text_to_html_ratio < 0.10 and page.is_indexable:
        extra: dict = {
            "ratio": round(page.text_to_html_ratio, 4),
            "ratio_pct": f"{page.text_to_html_ratio * 100:.1f}%",
        }
        if page.code_breakdown:
            extra["breakdown"] = page.code_breakdown
            # Diagnose the biggest contributor
            bd = page.code_breakdown
            parts = [
                ("Inline scripts", bd.get("script_kb", 0)),
                ("Inline styles", bd.get("style_kb", 0)),
                ("SVG graphics", bd.get("svg_kb", 0)),
                ("HTML markup", bd.get("markup_kb", 0)),
            ]
            parts.sort(key=lambda x: x[1], reverse=True)
            biggest = parts[0]
            total = bd.get("html_total_kb", 1)
            if biggest[1] > 0:
                extra["diagnosis"] = (
                    f"{biggest[0]} ({biggest[1]} KB) account for "
                    f"{biggest[1] / total * 100:.0f}% of the page. "
                    f"Visible text is only {bd.get('text_kb', 0)} KB "
                    f"out of {total} KB total."
                )
        issues.append(make_issue("SEMANTIC_DENSITY_LOW", url, extra=extra))

    # JSON-LD Missing
    if not page.has_json_ld and page.is_indexable and not url.endswith(".pdf"):
        issues.append(make_issue("JSON_LD_MISSING", url))

    # Conversational H2s — also fires when no H2s exist on a substantial page
    if page.is_indexable and not url.endswith(".pdf"):
        h2s = [h["text"] for h in (page.headings_outline or []) if h.get("level") == 2]
        if not h2s and page.word_count and page.word_count >= 300:
            # Substantial content with zero H2s — AI has nothing to anchor citations to
            issues.append(make_issue("CONVERSATIONAL_H2_MISSING", url,
                                     extra={"h2_headings": [], "word_count": page.word_count}))
        elif h2s:
            interrogatives = re.compile(r"\b(how|what|why|who|where|when|which)\b", re.I)
            if not any(interrogatives.search(h) for h in h2s):
                issues.append(make_issue("CONVERSATIONAL_H2_MISSING", url,
                                         extra={"h2_headings": h2s[:8]}))

    # Blog/article pages without enough heading sections for AI citation
    if page.is_indexable and page.word_count and page.word_count >= 500:
        is_blog_like = (
            "BlogPosting" in (page.schema_types or [])
            or "Article" in (page.schema_types or [])
            or any(seg in url for seg in ["/blog/", "/post/", "/article/", "/news/", "/stories/", "/insight"])
        )
        if is_blog_like:
            meaningful_headings = [
                h for h in (page.headings_outline or [])
                if h.get("level") in (2, 3) and len(h.get("text", "").strip()) > 5
            ]
            if len(meaningful_headings) < 3:
                issues.append(make_issue("BLOG_SECTIONS_MISSING", url, extra={
                    "word_count": page.word_count,
                    "heading_count": len(meaningful_headings),
                }))

    # ── Schema Typing (v2.0) ─────────────────────────────────────────────────
    if page.is_indexable and page.schema_types:
        try:
            from api.services.schema_typing import validate_schema_typing
            is_appropriate, issue_reason = validate_schema_typing(page)
            if not is_appropriate and issue_reason:
                if issue_reason.startswith("deprecated_schema:"):
                    issues.append(make_issue("SCHEMA_DEPRECATED_TYPE", url,
                                            extra={"schema_types": page.schema_types}))
                elif issue_reason.startswith("schema_conflict:"):
                    issues.append(make_issue("SCHEMA_TYPE_CONFLICT", url,
                                            extra={"schema_types": page.schema_types}))
                elif issue_reason.startswith("schema_mismatch:"):
                    page_type = issue_reason.split(":")[-1]
                    issues.append(make_issue("SCHEMA_TYPE_MISMATCH", url,
                                            extra={"inferred_page_type": page_type,
                                                   "schema_types": page.schema_types}))
        except Exception as e:
            logger.warning("schema_typing_error", extra={"url": url, "error": str(e)})

    # ── Schema Visible Mismatch (M3.1) ──────────────────────────────────────────
    # Pre-computed at parse time — the field is a list of mismatch labels.
    if page.schema_visible_mismatch_fields:
        issues.append(make_issue("SCHEMA_VISIBLE_MISMATCH", url,
                                 extra={"mismatched_fields": page.schema_visible_mismatch_fields}))

    # ── Content Not in Text (M3.2) ───────────────────────────────────────────
    # Pre-computed at parse time — requires soup to inspect media elements.
    if page.is_indexable and page.content_not_in_text_reason:
        issues.append(make_issue("AI_CONTENT_NOT_IN_TEXT", url,
                                 extra={"reason": page.content_not_in_text_reason,
                                        "word_count": page.word_count}))

    # ── X-Robots-Tag AI-preview controls (M3.3) ──────────────────────────────
    if page.is_indexable and page.ai_preview_suppressed:
        issues.append(make_issue("AI_PREVIEW_SUPPRESSED", url,
                                 extra={"directive": page.ai_preview_directive}))

    if page.is_indexable and page.ai_bot_blocked:
        issues.append(make_issue("AI_PREVIEW_BLOCKED_AT_BOT", url,
                                 extra={"directive": page.ai_bot_blocked_directive}))

    # ── Answerability (Cycle GG): GEO_SUMMARY_BURIED ──────────────────────────
    # Inserted BEFORE the existing extractability/quality block per the
    # Cycle GG continuation-prompt Q6: structural issues caught early
    # can inform downstream quality scoring. Pure CPU; the auditor reads
    # the pre-computed `page.is_answer_buried` flag that the parser
    # populated while soup was in scope (no re-parsing here).
    #
    # The literal-string emission below (rather than dispatching on the
    # auditor's return value) satisfies the catalogue-liveness test in
    # tests/test_class1_invariants.py — it greps for
    # make_issue("CODE", ...) literals to surface dead-code entries.
    # The auditor still returns a string (uniform with
    # diagnose_extractability) so future codes can be added without
    # widening the API.
    if page.is_indexable:
        try:
            from api.services.extractability import audit_answerability
            if audit_answerability(page) == "GEO_SUMMARY_BURIED":
                issues.append(make_issue("GEO_SUMMARY_BURIED", url))
        except Exception as e:
            logger.warning("answerability_error", extra={"url": url, "error": str(e)})

    # ── Content Extractability (v2.0) ─────────────────────────────────────────
    if page.is_indexable:
        try:
            from api.services.extractability import diagnose_extractability, assess_extractability
            extractability_issue = diagnose_extractability(page)
            if extractability_issue:
                assessment = assess_extractability(page)
                issues.append(make_issue(extractability_issue, url,
                                        extra={"score": assessment["score"],
                                               "issues": assessment["issues"]}))
        except Exception as e:
            logger.warning("extractability_error", extra={"url": url, "error": str(e)})

    # ── Citation Assessment (v2.0) ────────────────────────────────────────────
    if page.is_indexable and page.word_count and page.word_count > 200:
        try:
            from api.services.citation_model import PageCitations, assess_citation_readiness, diagnose_citation_issue
            page_citations = PageCitations(
                url=url,
                citations=[],
                attribution_style="none",
            )
            citation_issue = assess_citation_readiness(page_citations, page.word_count)
            diagnosis = diagnose_citation_issue(citation_issue)
            if diagnosis:
                issues.append(make_issue(diagnosis, url,
                                        extra={"word_count": page.word_count}))
        except Exception as e:
            logger.warning("citation_check_error", extra={"url": url, "error": str(e)})

    # PDF Metadata
    if url.lower().endswith(".pdf") and page.pdf_metadata is not None:
        meta = page.pdf_metadata
        if not meta.get("title") or not meta.get("subject"):
            issues.append(make_issue("DOCUMENT_PROPS_MISSING", url, extra=meta))

    # ── v2.1 GEO Analyzer static checks ─────────────────────────────────────
    _run_geo_checks(page, url, issues)

    return issues
