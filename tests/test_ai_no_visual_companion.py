"""Tests for AI_NO_VISUAL_COMPANION issue detection (M3.4).

Spec: docs/pending/2026-05-31_m3_4_ai_no_visual_companion.md

Unit tests for _check_ai_no_visual_companion() and integration with
check_page via the infer_page_type() classifier.
"""

import pytest

from api.crawler.issue_checker import _check_ai_no_visual_companion, check_page
from api.crawler.parser import ParsedPage


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_page(url="https://example.com/page", *, word_count=400,
               image_urls=None, is_indexable=True, **kw):
    """Construct a minimal ParsedPage for testing."""
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=5000,
        title="Test Page",
        meta_description="A test page",
        og_title="Test Page",
        og_description="A test page",
        og_image="https://example.com/og.jpg",
        twitter_card="summary",
        canonical_url=url,
        h1_tags=["Test Page"],
        headings_outline=[{"level": 1, "text": "Test Page"}],
        is_indexable=is_indexable,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=[],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=word_count,
        lang_attr="en",
        image_urls=image_urls if image_urls is not None else [],
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — _check_ai_no_visual_companion
# ═══════════════════════════════════════════════════════════════════════════


def test_article_400_words_no_images_flagged():
    """Article with 400 words and no images should be flagged."""
    page = _make_page(
        url="https://example.com/blog/my-post",
        word_count=400,
        image_urls=[],
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/blog/my-post", page, is_indexable=True,
    )
    assert len(issues) == 1
    assert issues[0].code == "AI_NO_VISUAL_COMPANION"
    assert issues[0].extra["page_type"] == "article"
    assert issues[0].extra["word_count"] == 400


def test_service_350_words_no_images_flagged():
    """Service page with 350 words and no images should be flagged."""
    page = _make_page(
        url="https://example.com/services/landscaping",
        word_count=350,
        image_urls=[],
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/services/landscaping", page, is_indexable=True,
    )
    assert len(issues) == 1
    assert issues[0].code == "AI_NO_VISUAL_COMPANION"
    assert issues[0].extra["page_type"] == "service"


def test_faq_400_words_no_images_flagged():
    """FAQ page with 400 words and no images should be flagged."""
    page = _make_page(
        url="https://example.com/faq",
        word_count=400,
        image_urls=[],
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/faq", page, is_indexable=True,
    )
    assert len(issues) == 1
    assert issues[0].code == "AI_NO_VISUAL_COMPANION"
    assert issues[0].extra["page_type"] == "faq"


# ═══════════════════════════════════════════════════════════════════════════
# Adversarial guards
# ═══════════════════════════════════════════════════════════════════════════


def test_article_with_image_not_flagged():
    """Article with 400 words and 1 image should NOT be flagged."""
    page = _make_page(
        url="https://example.com/blog/my-post",
        word_count=400,
        image_urls=["https://example.com/img.jpg"],
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/blog/my-post", page, is_indexable=True,
    )
    assert len(issues) == 0


def test_article_under_300_words_not_flagged():
    """Article with only 120 words should NOT be flagged (under 300 threshold)."""
    page = _make_page(
        url="https://example.com/blog/short-post",
        word_count=120,
        image_urls=[],
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/blog/short-post", page, is_indexable=True,
    )
    assert len(issues) == 0


def test_article_exactly_300_words_not_flagged():
    """Article with exactly 300 words should NOT be flagged (threshold is >300)."""
    page = _make_page(
        url="https://example.com/blog/boundary-post",
        word_count=300,
        image_urls=[],
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/blog/boundary-post", page, is_indexable=True,
    )
    assert len(issues) == 0


def test_wrong_page_type_not_flagged():
    """about/home/unknown/team_member/contact pages should NOT be flagged."""
    for url_path, expected_type in [
        ("/about", "about"),
        ("/", "home"),
        ("/random-page", "unknown"),
        ("/team/john", "team_member"),
        ("/contact", "contact"),
    ]:
        page = _make_page(
            url=f"https://example.com{url_path}",
            word_count=400,
            image_urls=[],
        )
        issues = _check_ai_no_visual_companion(
            f"https://example.com{url_path}", page, is_indexable=True,
        )
        assert len(issues) == 0, f"URL path '{url_path}' should not be flagged"


def test_non_indexable_page_not_flagged():
    """Non-indexable pages should NOT emit the issue."""
    page = _make_page(
        url="https://example.com/blog/hidden-post",
        word_count=400,
        image_urls=[],
        is_indexable=False,
    )
    issues = _check_ai_no_visual_companion(
        "https://example.com/blog/hidden-post", page, is_indexable=False,
    )
    assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Integration with check_page
# ═══════════════════════════════════════════════════════════════════════════


def test_check_page_emits_ai_no_visual_companion():
    """check_page should emit AI_NO_VISUAL_COMPANION for qualifying pages."""
    page = _make_page(
        url="https://example.com/blog/my-article",
        word_count=400,
        image_urls=[],
    )
    issues = check_page(page)
    codes = [i.code for i in issues]
    assert "AI_NO_VISUAL_COMPANION" in codes
    visual_issue = next(i for i in issues if i.code == "AI_NO_VISUAL_COMPANION")
    assert visual_issue.extra["page_type"] == "article"
    assert visual_issue.extra["word_count"] == 400


def test_check_page_does_not_emit_when_images_present():
    """check_page should NOT emit AI_NO_VISUAL_COMPANION when images exist."""
    page = _make_page(
        url="https://example.com/blog/illustrated-article",
        word_count=400,
        image_urls=["https://example.com/photo.jpg"],
    )
    issues = check_page(page)
    codes = [i.code for i in issues]
    assert "AI_NO_VISUAL_COMPANION" not in codes
