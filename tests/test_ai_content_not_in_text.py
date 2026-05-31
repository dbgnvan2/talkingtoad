"""Tests for AI_CONTENT_NOT_IN_TEXT detection (M3.2).

Spec: docs/pending/2026-05-31_m3_2_ai_content_not_in_text.md

Unit tests for detect_content_not_in_text() helper, adversarial guards,
and integration with issue_checker via the pre-computed ParsedPage field.
"""

import pytest
from bs4 import BeautifulSoup

from api.services.extractability import detect_content_not_in_text
from api.crawler.parser import ParsedPage
from api.crawler.issue_checker import check_page


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_page(url="https://example.com/page", *, content_not_in_text_reason=None,
               word_count=500, is_indexable=True, **kw):
    """Construct a minimal ParsedPage for integration testing."""
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=5000,
        title="Test Page",
        meta_description="A test page",
        og_title="Test Page",
        og_description="A test page",
        og_image="https://example.com/img.jpg",
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
        content_not_in_text_reason=content_not_in_text_reason,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — the detect_content_not_in_text helper
# ═══════════════════════════════════════════════════════════════════════════


def test_media_dominated():
    """H1 + 10 words + one <img> → 'media_dominated'."""
    soup = BeautifulSoup(
        "<html><body><h1>Title</h1><p>Short text</p><img src='x.jpg'/></body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 10) == "media_dominated"


def test_answer_in_embed_iframe():
    """H1 + 30 words + one <iframe> → 'answer_in_embed'."""
    soup = BeautifulSoup(
        "<html><body><h1>Title</h1><p>" + "word " * 30 + "</p><iframe src='x'/></body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 30) == "answer_in_embed"


def test_answer_in_embed_object():
    """H1 + <object>/<embed> + low text → 'answer_in_embed'."""
    soup = BeautifulSoup(
        "<html><body><h1>Title</h1><p>" + "word " * 40 + "</p>"
        "<object data='file.pdf'></object></body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 40) == "answer_in_embed"


# ═══════════════════════════════════════════════════════════════════════════
# Adversarial tests — "correct-looking but wrong"
# ═══════════════════════════════════════════════════════════════════════════


def test_text_rich_page_with_images_not_flagged():
    """Text-rich page WITH images (H1 + 800 words + 5 <img>) → NOT flagged.
    Key false positive: a normal illustrated article is fine."""
    soup = BeautifulSoup(
        "<html><body><h1>Title</h1><p>" + "word " * 800 + "</p>"
        + "<img src='x.jpg'/>" * 5 + "</body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 800) is None


def test_article_with_embedded_video_not_flagged():
    """Embedded video on a real article (H1 + 600 words + <iframe>) → NOT flagged.
    Text carries the content; wc >= 100."""
    soup = BeautifulSoup(
        "<html><body><h1>Title</h1><p>" + "word " * 600 + "</p><iframe src='x'/></body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 600) is None


def test_thin_page_no_media_not_flagged():
    """Thin page with NO media (H1 + 20 words, no img/video/iframe) → NOT flagged.
    That's a thin-content code, not this one — proves no double-flagging."""
    soup = BeautifulSoup(
        "<html><body><h1>Title</h1><p>" + "word " * 20 + "</p></body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 20) is None


def test_no_h1_not_flagged():
    """No H1 (media-only splash, no heading) → NOT flagged (require an H1)."""
    soup = BeautifulSoup(
        "<html><body><p>" + "word " * 10 + "</p><img src='x.jpg'/></body></html>",
        "html.parser",
    )
    assert detect_content_not_in_text(soup, 10) is None


# ═══════════════════════════════════════════════════════════════════════════
# Integration tests — issue_checker emission
# ═══════════════════════════════════════════════════════════════════════════


def test_issue_checker_emits_with_extra_reason():
    """A page with content_not_in_text_reason set yields AI_CONTENT_NOT_IN_TEXT
    with extra.reason and extra.word_count."""
    page = _make_page(
        content_not_in_text_reason="media_dominated",
        word_count=30,
    )
    issues = check_page(page)
    ai_issues = [i for i in issues if i.code == "AI_CONTENT_NOT_IN_TEXT"]
    assert len(ai_issues) == 1
    issue = ai_issues[0]
    assert issue.extra["reason"] == "media_dominated"
    assert issue.extra["word_count"] == 30


def test_non_indexable_page_does_not_emit():
    """A non-indexable page with content_not_in_text_reason set does NOT emit
    AI_CONTENT_NOT_IN_TEXT (consistent with spec: only for indexable pages)."""
    page = _make_page(
        content_not_in_text_reason="answer_in_embed",
        word_count=30,
        is_indexable=False,
    )
    issues = check_page(page)
    ai_codes = [i.code for i in issues if i.code == "AI_CONTENT_NOT_IN_TEXT"]
    assert ai_codes == []
