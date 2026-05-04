"""
Tests for v2.1 GEO Analyzer static checks.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md
Tests: test_geo_static_checks.py

All checks run through check_page() → _run_geo_checks().
"""

import pytest
from api.crawler.parser import ParsedPage, ParsedLink
from api.crawler.issue_checker import check_page, make_issue


# ---------------------------------------------------------------------------
# Minimal ParsedPage factory
# ---------------------------------------------------------------------------

def _page(
    url: str = "https://example.com/page",
    *,
    word_count: int = 600,
    is_indexable: bool = True,
    schema_types: list[str] | None = None,
    headings_outline: list[dict] | None = None,
    links: list[ParsedLink] | None = None,
    schema_blocks: list[dict] | None = None,
    # GEO fields
    is_spa_shell: bool = False,
    text_to_html_ratio: float = 0.3,
    author_detected: bool = True,
    date_published: str | None = "2024-01-01",
    date_modified: str | None = "2024-06-01",
    code_block_count: int = 0,
    table_count: int = 0,
    structured_element_count: int = 1,
    first_150_words: str | None = None,
    blockquote_count: int = 0,
) -> ParsedPage:
    if first_150_words is None:
        first_150_words = (
            "This page is a comprehensive guide. It covers many topics. "
            "According to experts, the results are significant. "
            "We explain everything you need to know in detail here."
        )
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=5000,
        title="A Good Title",
        meta_description="A good description.",
        og_title="OG Title",
        og_description="OG Desc",
        og_image="https://example.com/img.jpg",
        twitter_card="summary",
        canonical_url=None,
        h1_tags=["A Good Title"],
        headings_outline=headings_outline or [{"level": 1, "text": "A Good Title"}],
        is_indexable=is_indexable,
        robots_directive=None,
        robots_source="meta",
        links=links or [],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=schema_types or [],
        schema_blocks=schema_blocks,
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=word_count,
        text_to_html_ratio=text_to_html_ratio,
        has_json_ld=False,
        lang_attr="en",
        # GEO v2.1 fields
        is_spa_shell=is_spa_shell,
        author_detected=author_detected,
        date_published=date_published,
        date_modified=date_modified,
        code_block_count=code_block_count,
        table_count=table_count,
        structured_element_count=structured_element_count,
        first_150_words=first_150_words,
        blockquote_count=blockquote_count,
    )


def _codes(page: ParsedPage) -> set[str]:
    return {i.code for i in check_page(page)}


# ---------------------------------------------------------------------------
# GEO.1.3a: RAW_HTML_JS_DEPENDENT
# ---------------------------------------------------------------------------

def test_raw_html_js_dependent_fires_for_spa_shell():
    page = _page(is_spa_shell=True, text_to_html_ratio=0.01)
    assert "RAW_HTML_JS_DEPENDENT" in _codes(page)


def test_raw_html_js_dependent_not_fired_good_ratio():
    page = _page(is_spa_shell=True, text_to_html_ratio=0.3)
    assert "RAW_HTML_JS_DEPENDENT" not in _codes(page)


def test_raw_html_js_dependent_not_fired_no_spa_shell():
    page = _page(is_spa_shell=False, text_to_html_ratio=0.01)
    assert "RAW_HTML_JS_DEPENDENT" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.A.1: STATISTICS_COUNT_LOW
# ---------------------------------------------------------------------------

def test_statistics_count_low_fires_on_zero():
    page = _page(
        word_count=600,
        first_150_words="This is a page about our product. It helps customers succeed. We believe in quality.",
    )
    assert "STATISTICS_COUNT_LOW" in _codes(page)


def test_statistics_count_low_not_fired_with_statistic():
    page = _page(
        word_count=600,
        first_150_words="Our platform processes 10,000 requests per second with 99.9% uptime.",
    )
    assert "STATISTICS_COUNT_LOW" not in _codes(page)


def test_statistics_count_low_not_fired_below_500_words():
    page = _page(
        word_count=400,
        first_150_words="This page has no numbers at all.",
    )
    assert "STATISTICS_COUNT_LOW" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.A.2: EXTERNAL_CITATIONS_LOW
# ---------------------------------------------------------------------------

def test_external_citations_low_fires():
    page = _page(word_count=600, links=[])
    assert "EXTERNAL_CITATIONS_LOW" in _codes(page)


def test_external_citations_low_not_fired_with_external_link():
    ext_link = ParsedLink(url="https://nih.gov/study", text="NIH study", is_internal=False)
    page = _page(word_count=600, links=[ext_link])
    assert "EXTERNAL_CITATIONS_LOW" not in _codes(page)


def test_external_citations_low_not_fired_below_500_words():
    page = _page(word_count=400, links=[])
    assert "EXTERNAL_CITATIONS_LOW" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.A.3: QUOTATIONS_MISSING
# ---------------------------------------------------------------------------

def test_quotations_missing_fires():
    page = _page(
        word_count=600,
        blockquote_count=0,
        first_150_words="This is a page about many things. No quotes here at all.",
    )
    assert "QUOTATIONS_MISSING" in _codes(page)


def test_quotations_missing_not_fired_with_blockquote():
    page = _page(word_count=600, blockquote_count=1)
    assert "QUOTATIONS_MISSING" not in _codes(page)


def test_quotations_missing_not_fired_with_attribution():
    page = _page(
        word_count=600,
        blockquote_count=0,
        first_150_words="According to Dr. Smith, the results are clear. This changes everything.",
    )
    assert "QUOTATIONS_MISSING" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.A.4: ORPHAN_CLAIM_TECHNICAL
# ---------------------------------------------------------------------------

def test_orphan_claim_technical_fires():
    page = _page(
        url="https://example.com/guide/setup",
        word_count=400,
        links=[],
        first_150_words=(
            "The system supports high availability. "
            "The platform enables real-time processing. "
            "The tool provides automatic failover. "
            "Additional features allow custom configuration."
        ),
    )
    assert "ORPHAN_CLAIM_TECHNICAL" in _codes(page)


def test_orphan_claim_technical_not_fired_non_technical():
    page = _page(
        url="https://example.com/about",
        word_count=400,
        links=[],
        first_150_words="The system supports high availability. The platform enables processing.",
    )
    assert "ORPHAN_CLAIM_TECHNICAL" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.2.3: FIRST_VIEWPORT_NO_ANSWER
# ---------------------------------------------------------------------------

def test_first_viewport_no_answer_fires():
    page = _page(
        word_count=300,
        first_150_words=(
            "This page covers many topics. We discuss various aspects of the subject. "
            "There is a lot to learn here. Join us as we explore the details."
        ),
    )
    assert "FIRST_VIEWPORT_NO_ANSWER" in _codes(page)


def test_first_viewport_no_answer_not_fired_with_definition():
    page = _page(
        word_count=300,
        first_150_words="OpenBrain is a personal AI memory database. It stores and retrieves context.",
    )
    assert "FIRST_VIEWPORT_NO_ANSWER" not in _codes(page)


def test_first_viewport_no_answer_not_fired_with_tldr():
    page = _page(
        word_count=300,
        first_150_words="TL;DR: This guide shows you how to set up the system in 5 steps.",
    )
    assert "FIRST_VIEWPORT_NO_ANSWER" not in _codes(page)


def test_first_viewport_no_answer_not_fired_below_200_words():
    page = _page(word_count=100, first_150_words="A short page with no answer signal.")
    assert "FIRST_VIEWPORT_NO_ANSWER" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.4.2: AUTHOR_BYLINE_MISSING
# ---------------------------------------------------------------------------

def test_author_byline_missing_fires():
    page = _page(
        url="https://example.com/blog/my-post",
        schema_types=["BlogPosting"],
        author_detected=False,
    )
    assert "AUTHOR_BYLINE_MISSING" in _codes(page)


def test_author_byline_missing_not_fired_when_detected():
    page = _page(
        url="https://example.com/blog/my-post",
        schema_types=["BlogPosting"],
        author_detected=True,
    )
    assert "AUTHOR_BYLINE_MISSING" not in _codes(page)


def test_author_byline_missing_not_fired_non_article():
    page = _page(
        url="https://example.com/products",
        schema_types=["Product"],
        author_detected=False,
    )
    assert "AUTHOR_BYLINE_MISSING" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.4.3: DATE_PUBLISHED_MISSING, DATE_MODIFIED_MISSING
# ---------------------------------------------------------------------------

def test_date_published_missing_fires():
    page = _page(
        url="https://example.com/blog/post",
        schema_types=["BlogPosting"],
        date_published=None,
        date_modified="2024-01-01",
    )
    assert "DATE_PUBLISHED_MISSING" in _codes(page)


def test_date_modified_missing_fires():
    page = _page(
        url="https://example.com/blog/post",
        schema_types=["BlogPosting"],
        date_published="2024-01-01",
        date_modified=None,
    )
    assert "DATE_MODIFIED_MISSING" in _codes(page)


def test_date_signals_not_fired_non_article():
    page = _page(
        url="https://example.com/contact",
        date_published=None,
        date_modified=None,
    )
    codes = _codes(page)
    assert "DATE_PUBLISHED_MISSING" not in codes
    assert "DATE_MODIFIED_MISSING" not in codes


# ---------------------------------------------------------------------------
# GEO.8.1: CODE_BLOCK_MISSING_TECHNICAL
# ---------------------------------------------------------------------------

def test_code_block_missing_technical_fires():
    page = _page(
        url="https://example.com/guide/install",
        word_count=300,
        code_block_count=0,
        first_150_words=(
            "Follow these steps:\n1. Download the package\n2. Run the installer\n3. Configure settings"
        ),
    )
    assert "CODE_BLOCK_MISSING_TECHNICAL" in _codes(page)


def test_code_block_missing_technical_not_fired_with_code():
    page = _page(
        url="https://example.com/guide/install",
        word_count=300,
        code_block_count=2,
        first_150_words="1. Run the command\n2. Open the config file\n3. Set the variable",
    )
    assert "CODE_BLOCK_MISSING_TECHNICAL" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.8.2: COMPARISON_TABLE_MISSING
# ---------------------------------------------------------------------------

def test_comparison_table_missing_fires():
    page = _page(
        headings_outline=[
            {"level": 1, "text": "Main Title"},
            {"level": 2, "text": "Plan A vs Plan B"},
        ],
        table_count=0,
    )
    assert "COMPARISON_TABLE_MISSING" in _codes(page)


def test_comparison_table_missing_not_fired_with_table():
    page = _page(
        headings_outline=[
            {"level": 1, "text": "Main Title"},
            {"level": 2, "text": "Plan A vs Plan B"},
        ],
        table_count=1,
    )
    assert "COMPARISON_TABLE_MISSING" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.8.3: LINK_PROFILE_PROMOTIONAL
# ---------------------------------------------------------------------------

def test_link_profile_promotional_fires():
    # All external links go to same-org subdomains with affiliate params
    promo_links = [
        ParsedLink(url=f"https://shop.example.com/product?ref=main&aff=1", text="Buy", is_internal=False)
        for _ in range(5)
    ]
    page = _page(
        url="https://example.com/article",
        word_count=400,
        links=promo_links,
    )
    assert "LINK_PROFILE_PROMOTIONAL" in _codes(page)


# ---------------------------------------------------------------------------
# GEO.5.1: JSON_LD_INVALID
# ---------------------------------------------------------------------------

def test_json_ld_invalid_fires():
    page = _page(schema_blocks=[{"name": "MyPage"}])  # missing @type and @context
    assert "JSON_LD_INVALID" in _codes(page)


def test_json_ld_invalid_not_fired_for_valid_block():
    page = _page(schema_blocks=[{"@type": "BlogPosting", "@context": "https://schema.org"}])
    assert "JSON_LD_INVALID" not in _codes(page)


def test_json_ld_invalid_not_fired_when_no_blocks():
    page = _page(schema_blocks=None)
    assert "JSON_LD_INVALID" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.5.2: FAQ_SCHEMA_MISSING
# ---------------------------------------------------------------------------

def test_faq_schema_missing_fires_on_faq_heading():
    page = _page(
        headings_outline=[
            {"level": 1, "text": "Our Service"},
            {"level": 2, "text": "Frequently Asked Questions"},
            {"level": 3, "text": "What is included?"},
        ],
        schema_types=[],
    )
    assert "FAQ_SCHEMA_MISSING" in _codes(page)


def test_faq_schema_missing_fires_on_question_headings():
    page = _page(
        headings_outline=[
            {"level": 1, "text": "Guide"},
            {"level": 2, "text": "What is X?"},
            {"level": 2, "text": "How does Y work?"},
            {"level": 2, "text": "When should I use Z?"},
        ],
        schema_types=[],
    )
    assert "FAQ_SCHEMA_MISSING" in _codes(page)


def test_faq_schema_missing_not_fired_with_faqpage_schema():
    page = _page(
        headings_outline=[
            {"level": 1, "text": "FAQ"},
            {"level": 2, "text": "Frequently Asked Questions"},
        ],
        schema_types=["FAQPage"],
    )
    assert "FAQ_SCHEMA_MISSING" not in _codes(page)


# ---------------------------------------------------------------------------
# GEO.2.2: STRUCTURED_ELEMENTS_LOW
# ---------------------------------------------------------------------------

def test_structured_elements_low_fires_on_zero():
    page = _page(word_count=600, structured_element_count=0)
    assert "STRUCTURED_ELEMENTS_LOW" in _codes(page)


def test_structured_elements_low_not_fired_with_elements():
    page = _page(word_count=600, structured_element_count=3)
    assert "STRUCTURED_ELEMENTS_LOW" not in _codes(page)


def test_structured_elements_low_not_fired_below_500_words():
    page = _page(word_count=400, structured_element_count=0)
    assert "STRUCTURED_ELEMENTS_LOW" not in _codes(page)


# ---------------------------------------------------------------------------
# Non-indexable pages should not trigger GEO checks
# ---------------------------------------------------------------------------

def test_geo_checks_not_fired_for_noindex():
    page = _page(
        url="https://example.com/blog/my-post",
        is_indexable=False,
        word_count=800,
        schema_types=["BlogPosting"],
        author_detected=False,
        date_published=None,
        blockquote_count=0,
        links=[],
        first_150_words="No numbers here at all.",
    )
    codes = _codes(page)
    geo_codes = {
        "STATISTICS_COUNT_LOW", "EXTERNAL_CITATIONS_LOW", "QUOTATIONS_MISSING",
        "AUTHOR_BYLINE_MISSING", "DATE_PUBLISHED_MISSING", "DATE_MODIFIED_MISSING",
        "FIRST_VIEWPORT_NO_ANSWER",
    }
    assert geo_codes.isdisjoint(codes), f"GEO codes fired on noindex page: {codes & geo_codes}"
