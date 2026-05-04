"""Tests for content extractability assessment (v2.0).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.5
"""

import pytest
from api.crawler.parser import ParsedPage
from api.services.extractability import assess_extractability, diagnose_extractability


def _make_page(url, *, title=None, word_count=None, heading_count=0, image_count=0,
               link_count=0, has_json_ld=False, text_to_html_ratio=None, **kw):
    """Helper to create a minimal ParsedPage for testing."""
    headings = [{"level": i % 3 + 1, "text": f"Heading {i}"} for i in range(heading_count)]
    images = [f"https://example.com/image{i}.jpg" for i in range(image_count)]
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=3000,
        title=title,
        meta_description=None,
        og_title=None,
        og_description=None,
        og_image=None,
        twitter_card=None,
        canonical_url=None,
        h1_tags=[title] if title else [],
        headings_outline=headings,
        is_indexable=True,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=False,
        schema_types=[],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=word_count,
        image_urls=images if images else None,
        has_json_ld=has_json_ld,
        text_to_html_ratio=text_to_html_ratio,
        **kw,
    )


class TestExtractableContent:
    """Test assessment of well-extractable content."""

    def test_good_content_no_issues(self):
        """Article with text, headings, and structured data should be extractable."""
        page = _make_page(
            "https://example.com/article",
            title="Article Title",
            word_count=1000,
            heading_count=5,
            image_count=2,
            has_json_ld=True,
        )
        assessment = assess_extractability(page)
        assert assessment["is_extractable"] is True
        assert assessment["score"] >= 80
        assert len(assessment["issues"]) == 0

    def test_article_with_text_and_headings(self):
        """Article with 500 words and clear heading structure is extractable."""
        page = _make_page(
            "https://example.com/blog/post",
            title="Blog Post",
            word_count=500,
            heading_count=3,
        )
        assessment = assess_extractability(page)
        assert assessment["is_extractable"] is True
        assert assessment["score"] >= 60

    def test_substantial_content_with_headings(self):
        """Substantial text with headings should be extractable even without JSON-LD."""
        page = _make_page(
            "https://example.com/guide",
            title="Guide",
            word_count=2000,
            heading_count=4,
        )
        assessment = assess_extractability(page)
        assert assessment["is_extractable"] is True


class TestNonExtractableContent:
    """Test detection of content that's not extractable by AI."""

    def test_no_text_content(self):
        """Page with no text is not extractable."""
        page = _make_page(
            "https://example.com/image-gallery",
            title="Gallery",
            word_count=0,
            image_count=10,
        )
        assessment = assess_extractability(page)
        assert assessment["is_extractable"] is False
        assert assessment["score"] < 50
        assert "no_text_content" in assessment["issues"]

    def test_thin_content(self):
        """Page with < 100 words is not well extractable."""
        page = _make_page(
            "https://example.com/landing",
            title="Landing",
            word_count=50,
        )
        assessment = assess_extractability(page)
        assert assessment["is_extractable"] is False
        assert "thin_content" in assessment["issues"]

    def test_unstructured_content(self):
        """Page with 500+ words but no headings is unstructured."""
        page = _make_page(
            "https://example.com/wall-of-text",
            title="Content",
            word_count=1000,
            heading_count=0,
        )
        assessment = assess_extractability(page)
        # Unstructured content is less ideal but may still be extractable
        # Score penalty for lack of headings
        assert "no_headings" in assessment["issues"]

    def test_image_heavy_content(self):
        """Page with many more images than text sections is problematic."""
        page = _make_page(
            "https://example.com/photo-essay",
            title="Photo Essay",
            word_count=200,
            heading_count=2,
            image_count=10,  # Much more than headings
        )
        assessment = assess_extractability(page)
        assert "image_heavy" in assessment["issues"]


class TestDiagnosisFunction:
    """Test the diagnostic function that returns a single issue code."""

    def test_diagnose_no_text(self):
        """No text → CONTENT_NOT_EXTRACTABLE_NO_TEXT."""
        page = _make_page(
            "https://example.com/video",
            title="Video",
            word_count=0,
        )
        diagnosis = diagnose_extractability(page)
        assert diagnosis == "CONTENT_NOT_EXTRACTABLE_NO_TEXT"

    def test_diagnose_thin_content(self):
        """< 100 words → CONTENT_THIN."""
        page = _make_page(
            "https://example.com/stub",
            title="Stub",
            word_count=50,
        )
        diagnosis = diagnose_extractability(page)
        assert diagnosis == "CONTENT_THIN"

    def test_diagnose_no_headings(self):
        """500+ words but no headings → CONTENT_UNSTRUCTURED."""
        page = _make_page(
            "https://example.com/essay",
            title="Essay",
            word_count=1000,
            heading_count=0,
        )
        diagnosis = diagnose_extractability(page)
        assert diagnosis == "CONTENT_UNSTRUCTURED"

    def test_diagnose_good_content(self):
        """Well-structured content → None."""
        page = _make_page(
            "https://example.com/article",
            title="Article",
            word_count=1000,
            heading_count=4,
        )
        diagnosis = diagnose_extractability(page)
        assert diagnosis is None


class TestMetrics:
    """Test the metrics calculation."""

    def test_metrics_include_all_fields(self):
        """Assessment metrics should include word count, headings, images, etc."""
        page = _make_page(
            "https://example.com/page",
            title="Page",
            word_count=500,
            heading_count=3,
            image_count=2,
            has_json_ld=True,
        )
        assessment = assess_extractability(page)
        metrics = assessment["metrics"]
        assert "word_count" in metrics
        assert "heading_count" in metrics
        assert "image_count" in metrics
        assert "has_json_ld" in metrics
        assert metrics["word_count"] == 500
        assert metrics["heading_count"] == 3
        assert metrics["image_count"] == 2
        assert metrics["has_json_ld"] is True

    def test_zero_images_handled(self):
        """Pages with no images should have image_count = 0."""
        page = _make_page(
            "https://example.com/text-only",
            title="Text",
            word_count=1000,
            heading_count=5,
        )
        assessment = assess_extractability(page)
        assert assessment["metrics"]["image_count"] == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_100_words_not_thin(self):
        """100 words should not trigger thin content (boundary check)."""
        page = _make_page(
            "https://example.com/borderline",
            title="Page",
            word_count=100,
        )
        assessment = assess_extractability(page)
        # 100 words is the threshold; < 100 is thin
        assert "thin_content" not in assessment["issues"]

    def test_score_bounds(self):
        """Score should always be between 0 and 100."""
        # No content
        page1 = _make_page("https://example.com/1", word_count=0)
        assert 0 <= assess_extractability(page1)["score"] <= 100

        # Excellent content
        page2 = _make_page(
            "https://example.com/2",
            word_count=2000,
            heading_count=10,
            has_json_ld=True,
        )
        assert 0 <= assess_extractability(page2)["score"] <= 100

    def test_no_word_count_assumed_zero(self):
        """None word_count should be treated as 0."""
        page = _make_page("https://example.com/unknown", word_count=None)
        assessment = assess_extractability(page)
        assert assessment["metrics"]["word_count"] == 0
