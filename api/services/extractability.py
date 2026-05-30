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

# ── Cycle GG: tag filters for the H2 content-node walker ───────────────
# Tags that occupy DOM space but carry no body content (decorative or
# script-level). Skipped during the depth walk so a section with three
# decorative <svg> icons followed by a real <p> still reports depth=1.
_DECORATIVE_TAGS = frozenset({"svg", "script", "style", "noscript"})

# Tags that count as substantive body content under an H2 section. Limited
# to the three core prose containers — extending beyond these (e.g. to
# <div>) would dilute the "buried answer" signal because <div> is used
# heavily for layout, not content.
_CONTENT_TAGS = frozenset({"p", "ul", "li"})

# Cycle GG: when the first content node under an H2 appears at this index
# or later, the answer is considered buried. Calibrated against peer
# checks (FIRST_VIEWPORT_NO_ANSWER, CENTRAL_CLAIM_BURIED); see
# docs/pending/2026-05-30_cycle_gg_answerability_audit.md §3 for the
# rationale. Locked at 4 per the user's continuation prompt Q5.
_BURIED_THRESHOLD = 4


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
    """Walks the DOM under each ``<h2>`` heading, reporting where the
    first substantive content node (``<p>``/``<ul>``/``<li>``) appears.

    Cycle GG. Pure CPU work — no network, no LLM. Decorative tags
    (``svg``/``script``/``style``/``noscript``) are skipped in the
    depth count so they don't mask an early answer.

    Spec: docs/pending/2026-05-30_cycle_gg_answerability_audit.md
    """

    @staticmethod
    def walk_h2_content_nodes(soup) -> list[dict[str, Any]]:
        """For each ``<h2>`` in ``soup``, walk following siblings until
        the next heading and report where the first content node lands.

        Returns one dict per ``<h2>``:
            - ``h2_text``: heading text (truncated to 80 chars).
            - ``first_content_tag``: tag name of the first content node
              found, or None if the section has no content nodes.
            - ``first_content_depth``: 1-indexed position of the first
              content node among content nodes only (decoratives are
              ignored in the count). 0 when no content node is found.

        Why "depth among content nodes" instead of "total siblings":
        the intent is to model how a reader/AI encounters the answer.
        A section can have 6 decorative SVG icons and a real <p> at
        position 7, but the reader hits the <p> "first" content-wise.
        Counting decorative nodes would falsely inflate the burial.
        """
        results: list[dict[str, Any]] = []
        if soup is None:
            return results

        h2_tags = soup.find_all("h2")
        for h2 in h2_tags:
            content_count = 0
            first_content_tag: str | None = None
            for sibling in h2.find_next_siblings():
                # Stop at next heading — that's the start of a different
                # section and shouldn't influence this section's depth.
                if sibling.name and sibling.name.startswith("h") and sibling.name[1:].isdigit():
                    break
                if sibling.name in _DECORATIVE_TAGS:
                    continue
                if sibling.name in _CONTENT_TAGS:
                    content_count += 1
                    if first_content_tag is None:
                        first_content_tag = sibling.name
            results.append({
                "h2_text": h2.get_text(strip=True)[:80],
                "first_content_tag": first_content_tag,
                "first_content_depth": content_count if first_content_tag else 0,
            })
        return results

    @staticmethod
    def is_answer_buried(
        results: list[dict[str, Any]],
        threshold: int = _BURIED_THRESHOLD,
    ) -> bool:
        """Return True if any H2 section's first content node appears at
        or beyond ``threshold``. Honours the project default threshold
        constant; callers can override for testing or calibration."""
        for r in results:
            if r["first_content_depth"] >= threshold:
                return True
        return False


def audit_answerability(parsed_page: ParsedPage, soup=None) -> str | None:
    """Cycle GG: entry point for the ``GEO_SUMMARY_BURIED`` check.

    Two integration paths, both honoured (per the continuation prompt
    Q2: "soup as an optional parameter, do not bloat ParsedPage"):

    1. **Soup provided** (preferred at parse time, where soup is in
       scope): walk soup directly, return code if buried.
    2. **Soup omitted** (call-time): read the pre-computed
       ``parsed_page.is_h2_answer_buried`` flag that the parser sets
       while soup is in scope. This is the path taken by
       :func:`api.crawler.issue_checker.check_page`, which has no
       soup of its own.

    Returns the string ``"GEO_SUMMARY_BURIED"`` when the section is
    buried, or ``None`` when:
        - the page has no ``<h2>`` tags (Q4: silent skip);
        - the page has H2s but none cross the burial threshold;
        - no soup was provided and ``is_h2_answer_buried`` is unset.
    """
    if soup is not None:
        results = ContentNodeAuditor.walk_h2_content_nodes(soup)
        # No H2s → silent skip (Q4 from continuation prompt).
        if not results:
            return None
        if ContentNodeAuditor.is_answer_buried(results):
            return "GEO_SUMMARY_BURIED"
        return None

    # Fall back to the pre-computed flag set by the parser. Defaults to
    # None on legacy ParsedPage instances that pre-date Cycle GG —
    # treated as "no signal" so we don't falsely flag.
    if getattr(parsed_page, "is_h2_answer_buried", None) is True:
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
