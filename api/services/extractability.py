"""Content extractability assessment for AI readiness.

Detects whether pages contain well-structured, AI-extractable content
(paragraphs, lists, tables, structured markup) vs. presentation-only content
(images, videos, unstructured layouts).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.5
Tests: tests/test_extractability.py
"""

from api.crawler.parser import ParsedPage


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
