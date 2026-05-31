"""Content extractability assessment for AI readiness.

Detects whether pages contain well-structured, AI-extractable content
(paragraphs, lists, tables, structured markup) vs. presentation-only content
(images, videos, unstructured layouts).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.5
Tests: tests/test_extractability.py

Cycle GG: adds :class:`ContentNodeAuditor` and
:func:`audit_answerability` for the new ``GEO_SUMMARY_BURIED`` issue.
Spec: docs/pending/2026-05-30_cycle_gg_answerability_audit.md
"""

from typing import Any

from api.crawler.parser import ParsedPage

# ── Cycle GG / GA1 fix: tag filters for the answerability walker ───────
# Tags that occupy DOM space but carry no body content (decorative or
# script-level). Skipped entirely — they never count toward depth, so a
# section with three decorative <svg> icons followed by a real <p> still
# reports depth=1.
_DECORATIVE_TAGS = frozenset({"svg", "script", "style", "noscript"})

# Tags that count as substantive, AI-extractable answer content under a
# heading. A leading node of one of these means the answer is up top.
# GA1 fix (2026-05-31): <ol> and <table> added alongside <ul>/<p>/<li>
# (decisions B + C) — an ordered list or table is just as extractable as a
# bulleted list. Layout containers (<div>) are deliberately NOT content;
# they are treated transparently (see _section_first_content_depth).
_CONTENT_TAGS = frozenset({"p", "ul", "ol", "li", "table"})

# GA1 fix (2026-05-31): POSITIONAL threshold. A section's answer is
# "buried" when the first content node appears at this depth or later —
# i.e. it is NOT within the first two slots under the heading. This counts
# how far DOWN the first answer node sits (push-down blocks before it),
# NOT how many paragraphs follow it. Locked at 3 ("answer must reside in
# the first two p/ul/li nodes"); the Gemini 3.1 "depth 4" example still
# triggers (4 >= 3). Spec: docs/pending/2026-05-31_ga1_positional_answerability.md
_BURIED_THRESHOLD = 3


def assess_extractability(parsed_page: ParsedPage) -> dict:
    """Assess how well-structured content is for AI extraction.

    Purpose: Check if page has extractable content vs. presentation-only
    Spec:    docs/specs/ai-readiness/v2-extended-module.md § 3.5
    Tests:   tests/test_extractability.py::test_assess_extractability_*

    Args:
        parsed_page: Parsed page with headings, images, word count, etc.

    Returns:
        Dictionary with extractability metrics:
        - score: 0-100 (higher = more extractable)
        - is_extractable: bool (score >= 50)
        - issues: list of specific extractability problems found
        - metrics: dict of diagnostic data
    """
    metrics = {
        "word_count": parsed_page.word_count or 0,
        "heading_count": len(parsed_page.headings_outline or []),
        "link_count": len(parsed_page.links or []),
        "image_count": len(parsed_page.image_urls or []) if parsed_page.image_urls else 0,
        "has_json_ld": parsed_page.has_json_ld,
        "has_viewport_meta": parsed_page.has_viewport_meta,
    }

    issues = []
    score = 100  # Start at max, deduct for issues

    # No text content = not extractable
    if metrics["word_count"] == 0:
        issues.append("no_text_content")
        score -= 50

    # Very low word count
    elif metrics["word_count"] < 100:
        issues.append("thin_content")
        score -= 60

    # No headings = unstructured
    if metrics["heading_count"] == 0 and metrics["word_count"] > 200:
        issues.append("no_headings")
        score -= 55

    # Poor heading structure (too many images, not enough text between headings)
    if metrics["image_count"] > metrics["heading_count"] * 2:
        issues.append("image_heavy")
        score -= 10

    # No structured data
    if not metrics["has_json_ld"] and metrics["word_count"] > 500:
        issues.append("no_structured_data")
        score -= 5

    # Very high text-to-HTML ratio indicates minimal markup
    if parsed_page.text_to_html_ratio and parsed_page.text_to_html_ratio > 0.5:
        issues.append("unstructured_markup")
        score -= 5

    score = max(0, min(100, score))
    is_extractable = score > 50

    return {
        "score": score,
        "is_extractable": is_extractable,
        "issues": issues,
        "metrics": metrics,
    }


class ContentNodeAuditor:
    """Walks each ``<h2>``/``<h3>`` section in document order, reporting
    the **positional depth** of the first substantive content node
    (``<p>``/``<ul>``/``<ol>``/``<li>``/``<table>``).

    GA1 fix (2026-05-31): positional, not count-based. ``depth`` is how
    many non-decorative *push-down* blocks (images, figures, video,
    embeds, empty wrappers) precede the first content node, +1. A section
    whose answer leads is depth 1 no matter how many paragraphs follow;
    a section whose answer is pushed below media is flagged. Now covers
    ``<h3>`` as well as ``<h2>`` (FAQ-style answers live under ``<h3>``).

    Pure CPU work — no network, no LLM. Decorative tags
    (``svg``/``script``/``style``/``noscript``) never count toward depth.
    Layout wrappers that *contain* a content node are transparent (the
    content inside is the answer); wrappers with no content descendant are
    push-down blocks.

    Spec: docs/pending/2026-05-31_ga1_positional_answerability.md
    (supersedes the count-based Cycle GG walker).
    """

    _HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

    @staticmethod
    def _section_first_content_depth(heading) -> tuple[str | None, int]:
        """Return ``(first_content_tag, depth)`` for one heading's section.

        Walks the heading's following siblings in document order until the
        next heading of any level. Decoratives are skipped (no effect on
        depth). A non-content block that *contains* a content node is
        transparent — the content inside is the answer, found at the
        current depth. A non-content block with no content descendant is a
        push-down block and increments depth. Returns ``(None, 0)`` when
        the section has no content node at all.
        """
        depth = 1
        for sibling in heading.find_next_siblings():
            name = sibling.name
            if name in ContentNodeAuditor._HEADING_TAGS:
                break  # next section begins
            if name is None or name in _DECORATIVE_TAGS:
                continue  # text node / decorative — no effect on depth
            if name in _CONTENT_TAGS:
                return name, depth
            # Non-content block: transparent if it wraps a content node
            # (descend — the answer is inside, at this depth); otherwise it
            # pushes the answer further down.
            inner = sibling.find(lambda t: t.name in _CONTENT_TAGS)
            if inner is not None:
                return inner.name, depth
            depth += 1
        return None, 0

    @staticmethod
    def walk_sections(soup) -> list[dict[str, Any]]:
        """For each ``<h2>``/``<h3>`` in ``soup`` (document order), report
        where the first content node lands.

        Returns one dict per heading:
            - ``heading_text``: heading text (truncated to 80 chars).
            - ``heading_level``: ``"h2"`` or ``"h3"``.
            - ``first_content_tag``: tag name of the first content node, or
              None if the section has no content node.
            - ``first_content_depth``: 1-indexed positional depth of the
              first content node (1 = leads the section). 0 when no content
              node is found.
        """
        results: list[dict[str, Any]] = []
        if soup is None:
            return results
        for heading in soup.find_all(["h2", "h3"]):
            tag, depth = ContentNodeAuditor._section_first_content_depth(heading)
            results.append({
                "heading_text": heading.get_text(strip=True)[:80],
                "heading_level": heading.name,
                "first_content_tag": tag,
                "first_content_depth": depth,
            })
        return results

    @staticmethod
    def is_answer_buried(
        results: list[dict[str, Any]],
        threshold: int = _BURIED_THRESHOLD,
    ) -> bool:
        """Return True if any ``<h2>``/``<h3>`` section's first content node
        appears at or beyond ``threshold``. Sections with no content node
        (depth 0) are never "buried" — that is a different problem (empty
        section), not a buried answer. Callers may override the threshold
        for testing/calibration."""
        return any(
            r["first_content_tag"] is not None
            and r["first_content_depth"] >= threshold
            for r in results
        )


def audit_answerability(parsed_page: ParsedPage, soup=None) -> str | None:
    """Entry point for the ``GEO_SUMMARY_BURIED`` check (GA1 positional).

    Two integration paths, both honoured (per the Cycle GG continuation
    prompt Q2: "soup as an optional parameter, do not bloat ParsedPage"):

    1. **Soup provided** (preferred at parse time, where soup is in
       scope): walk soup directly, return code if buried.
    2. **Soup omitted** (call-time): read the pre-computed
       ``parsed_page.is_answer_buried`` flag that the parser sets while
       soup is in scope. This is the path taken by
       :func:`api.crawler.issue_checker.check_page`, which has no soup of
       its own.

    Returns the string ``"GEO_SUMMARY_BURIED"`` when any ``<h2>``/``<h3>``
    section's answer is buried, or ``None`` when:
        - the page has no ``<h2>``/``<h3>`` tags (silent skip);
        - the page has headings but none cross the burial threshold;
        - no soup was provided and the pre-computed flag is unset.
    """
    if soup is not None:
        results = ContentNodeAuditor.walk_sections(soup)
        # No H2/H3 sections → silent skip.
        if not results:
            return None
        if ContentNodeAuditor.is_answer_buried(results):
            return "GEO_SUMMARY_BURIED"
        return None

    # Fall back to the pre-computed flag set by the parser. GA1 renamed the
    # field is_h2_answer_buried -> is_answer_buried; accept both so any
    # in-flight ParsedPage built before this fix resolves to "no signal"
    # rather than crashing. Defaults to None (treated as no signal).
    flag = getattr(parsed_page, "is_answer_buried", None)
    if flag is None:
        flag = getattr(parsed_page, "is_h2_answer_buried", None)
    if flag is True:
        return "GEO_SUMMARY_BURIED"
    return None


def diagnose_extractability(parsed_page: ParsedPage) -> str | None:
    """Get a human-readable diagnosis of extractability problems.

    Returns a single issue code if a critical extractability problem exists,
    or None if the page is sufficiently extractable.
    """
    assessment = assess_extractability(parsed_page)

    if not assessment["is_extractable"]:
        # Priority order: worst problems first
        if "no_text_content" in assessment["issues"]:
            return "CONTENT_NOT_EXTRACTABLE_NO_TEXT"
        if "thin_content" in assessment["issues"]:
            return "CONTENT_THIN"
        if "no_headings" in assessment["issues"]:
            return "CONTENT_UNSTRUCTURED"
        if "image_heavy" in assessment["issues"]:
            return "CONTENT_IMAGE_HEAVY"

    return None
