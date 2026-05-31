"""Tests for content extractability assessment (v2.0).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.5

Cycle GG (2026-05-30): adds tests for ``ContentNodeAuditor`` and the
``GEO_SUMMARY_BURIED`` issue code. Spec:
docs/pending/2026-05-30_cycle_gg_answerability_audit.md.
"""

from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from api.crawler.parser import ParsedPage
from api.services.extractability import (
    ContentNodeAuditor,
    assess_extractability,
    audit_answerability,
    diagnose_extractability,
)


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


# ───────────────────────────────────────────────────────────────────────
# Cycle GG: ContentNodeAuditor + audit_answerability
# ───────────────────────────────────────────────────────────────────────


def _soup(html: str) -> BeautifulSoup:
    """Local helper — uses lxml to match the production parser."""
    return BeautifulSoup(html, "lxml")


class TestContentNodeAuditor:
    """Positional answerability auditor behind GEO_SUMMARY_BURIED.

    GA1 fix (2026-05-31): the check measures *where* the first content
    node sits under an <h2>/<h3>, not *how many* content nodes follow.
    Threshold = 3 (answer must lead in the first two slots).
    Spec: docs/pending/2026-05-31_ga1_positional_answerability.md
    """

    def test_answer_leads_depth_one_not_buried(self):
        """First node is the answer → depth 1 → not buried."""
        soup = _soup("""
        <html><body>
          <h2>What is the answer?</h2>
          <p>The answer leads the section, right under the heading.</p>
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["first_content_tag"] == "p"
        assert results[0]["first_content_depth"] == 1
        assert ContentNodeAuditor.is_answer_buried(results) is False
        assert audit_answerability(_make_page("https://example.com/lead"),
                                   soup=soup) is None

    def test_depth_two_not_buried_depth_three_buried(self):
        """Pin the positional boundary: one push-down block (depth 2) is
        still acceptable; two push-down blocks (depth 3) is buried."""
        # img then p → depth 2 → NOT buried.
        soup2 = _soup("""
        <html><body>
          <h2>Heading</h2>
          <img src="hero.jpg">
          <p>The answer, just below one image.</p>
        </body></html>
        """)
        results2 = ContentNodeAuditor.walk_sections(soup2)
        assert results2[0]["first_content_depth"] == 2
        assert ContentNodeAuditor.is_answer_buried(results2) is False

        # img + img then p → depth 3 → BURIED (boundary 2↔3).
        soup3 = _soup("""
        <html><body>
          <h2>Heading</h2>
          <img src="hero.jpg">
          <img src="second.jpg">
          <p>The answer, now pushed below two images.</p>
        </body></html>
        """)
        results3 = ContentNodeAuditor.walk_sections(soup3)
        assert results3[0]["first_content_depth"] == 3
        assert ContentNodeAuditor.is_answer_buried(results3) is True
        assert audit_answerability(
            _make_page("https://example.com/three", word_count=200),
            soup=soup3,
        ) == "GEO_SUMMARY_BURIED"

    def test_gemini_depth_four_case_buried(self):
        """Gemini 3.1 evaluator: answer buried at depth 4 (three media
        blocks before the first <p>) must trigger GEO_SUMMARY_BURIED."""
        soup = _soup("""
        <html><body>
          <h2>What is the answer?</h2>
          <img src="a.jpg"><video src="b.mp4"></video><iframe src="c"></iframe>
          <p>FINALLY the actual answer is here, at depth 4.</p>
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["first_content_depth"] == 4
        assert ContentNodeAuditor.is_answer_buried(results) is True
        assert audit_answerability(
            _make_page("https://example.com/buried", word_count=200),
            soup=soup,
        ) == "GEO_SUMMARY_BURIED"

    def test_verbose_section_with_leading_answer_not_buried(self):
        """ADVERSARIAL — the false positive the old count-based code
        produced. A section with a leading answer followed by FOUR more
        paragraphs is GOOD content, not buried. The pre-GA1 code flagged
        this (count ≥ 4); the positional check must NOT.

        "What would a correct-looking but wrong result look like?" →
        GEO_SUMMARY_BURIED returned here. Assert it is not.
        """
        soup = _soup("""
        <html><body>
          <h2>What is the answer?</h2>
          <p>The answer leads in one crisp sentence.</p>
          <p>Supporting detail one.</p>
          <p>Supporting detail two.</p>
          <p>Supporting detail three.</p>
          <p>Supporting detail four.</p>
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["first_content_depth"] == 1
        assert ContentNodeAuditor.is_answer_buried(results) is False
        assert audit_answerability(
            _make_page("https://example.com/verbose", word_count=200),
            soup=soup,
        ) is None

    def test_h3_section_buried(self):
        """ADVERSARIAL — the case the old <h2>-only code missed. A FAQ-style
        <h3> whose answer is pushed to depth 4 must now flag."""
        soup = _soup("""
        <html><body>
          <h3>How do I reset my password?</h3>
          <img src="a.jpg"><img src="b.jpg"><figure><img src="c.jpg"></figure>
          <p>Click the reset link in the email we send you.</p>
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["heading_level"] == "h3"
        assert results[0]["first_content_depth"] == 4
        assert ContentNodeAuditor.is_answer_buried(results) is True
        assert audit_answerability(
            _make_page("https://example.com/faq", word_count=200),
            soup=soup,
        ) == "GEO_SUMMARY_BURIED"

    def test_wrapper_div_is_transparent(self):
        """A content node wrapped in a <div> directly under the heading is
        found at depth 1 — the wrapper does not push the answer down. Proves
        the document-order descent (vs the old direct-siblings-only walk)."""
        soup = _soup("""
        <html><body>
          <h2>Heading</h2>
          <div class="entry"><p>The answer lives inside a layout wrapper.</p></div>
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["first_content_tag"] == "p"
        assert results[0]["first_content_depth"] == 1
        assert ContentNodeAuditor.is_answer_buried(results) is False

    def test_table_and_ordered_list_count_as_content(self):
        """Decisions B + C: a leading <ol> or <table> is extractable answer
        content → depth 1 → not buried."""
        soup_ol = _soup("""
        <html><body><h2>Steps</h2><ol><li>First.</li><li>Second.</li></ol></body></html>
        """)
        r_ol = ContentNodeAuditor.walk_sections(soup_ol)
        assert r_ol[0]["first_content_tag"] == "ol"
        assert r_ol[0]["first_content_depth"] == 1

        soup_tbl = _soup("""
        <html><body><h2>Pricing</h2><table><tr><td>Plan</td></tr></table></body></html>
        """)
        r_tbl = ContentNodeAuditor.walk_sections(soup_tbl)
        assert r_tbl[0]["first_content_tag"] == "table"
        assert r_tbl[0]["first_content_depth"] == 1
        assert ContentNodeAuditor.is_answer_buried(r_tbl) is False

    def test_decorative_tags_skipped(self):
        """SVG/script/style/noscript never count toward depth — answer
        right after them is still depth 1."""
        soup = _soup("""
        <html><body>
          <h2>Quick answer</h2>
          <svg width="10"></svg><script>var x=1;</script>
          <style>.foo{}</style><noscript>Enable JS</noscript>
          <p>The answer is right here, just after some icons.</p>
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["first_content_depth"] == 1
        assert ContentNodeAuditor.is_answer_buried(results) is False

    def test_section_with_no_content_node_not_buried(self):
        """A heading followed only by media (no p/list/table) is an empty
        section, not a buried answer → not flagged (depth 0)."""
        soup = _soup("""
        <html><body>
          <h2>Gallery</h2><img src="a.jpg"><img src="b.jpg">
        </body></html>
        """)
        results = ContentNodeAuditor.walk_sections(soup)
        assert results[0]["first_content_tag"] is None
        assert results[0]["first_content_depth"] == 0
        assert ContentNodeAuditor.is_answer_buried(results) is False

    def test_no_headings_silent_skip(self):
        """A page with no <h2>/<h3> → walk returns empty → audit None."""
        soup = _soup("<html><body><h1>Title</h1><p>Body.</p></body></html>")
        assert ContentNodeAuditor.walk_sections(soup) == []
        assert audit_answerability(_make_page("https://example.com/h1only"),
                                   soup=soup) is None

    def test_precomputed_flag_path_and_backcompat(self):
        """The call-time path (no soup) reads the pre-computed flag. Covers
        both polarities, the None default, and back-compat with the legacy
        ``is_h2_answer_buried`` field name (renamed to ``is_answer_buried``
        in GA1)."""
        # No flag set / no headings → None.
        assert audit_answerability(
            _make_page("https://example.com/none", word_count=200)) is None

        # New field explicitly False → None; True → code.
        assert audit_answerability(_make_page(
            "https://example.com/clean", word_count=200,
            is_answer_buried=False)) is None
        assert audit_answerability(_make_page(
            "https://example.com/buried", word_count=200,
            is_answer_buried=True)) == "GEO_SUMMARY_BURIED"

        # Back-compat: a pre-GA1 object carrying only the legacy field name
        # still resolves (must not crash, must honour the legacy True).
        legacy_buried = SimpleNamespace(is_h2_answer_buried=True)
        assert audit_answerability(legacy_buried) == "GEO_SUMMARY_BURIED"
        legacy_none = SimpleNamespace(is_h2_answer_buried=None)
        assert audit_answerability(legacy_none) is None
