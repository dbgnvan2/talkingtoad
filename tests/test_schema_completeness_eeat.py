"""E3/E4 — schema completeness (HowTo, Product) + author E-E-A-T.

Spec: PLAN-SEARCH-EVERYWHERE.md (P2). All three codes are PAGE-TYPE-GATED on the
relevant schema @type being present — they flag incomplete markup, never absent
markup, so pages without the schema stay silent (adversarial P7).
"""

import pytest

from api.crawler.parser import ParsedPage
from api.crawler.checkers.ai_readiness import _run_geo_checks


def _page(url="https://x.org/blog/post", *, schema_blocks=None, schema_types=None,
          word_count=600, is_indexable=True):
    return ParsedPage(
        url=url, final_url=url, status_code=200, response_size_bytes=2000,
        title="A Good Long Title For This Article Here", meta_description="A long enough meta description here.",
        og_title=None, og_description=None, og_image=None, twitter_card=None,
        canonical_url=None, h1_tags=["H1"], headings_outline=[{"level": 1, "text": "H1"}],
        is_indexable=is_indexable, robots_directive=None, links=[], has_favicon=None,
        has_viewport_meta=True, schema_types=schema_types or [], external_script_count=0,
        external_stylesheet_count=0, schema_blocks=schema_blocks, word_count=word_count,
        first_200_words="This article explains the topic clearly and answers the question directly. " * 3,
        author_detected=True,
    )


def _codes(page):
    issues = []
    _run_geo_checks(page, page.url, issues)
    return {i.code for i in issues}


class TestHowToCompleteness:
    def test_howto_without_steps_fires(self):
        blocks = [{"@type": "HowTo", "name": "How to knot a tie"}]
        assert "HOWTO_SCHEMA_INCOMPLETE" in _codes(_page(schema_blocks=blocks))

    def test_howto_with_steps_silent(self):
        blocks = [{"@type": "HowTo", "name": "How to knot a tie",
                   "step": [{"@type": "HowToStep", "text": "Cross the ends"}]}]
        assert "HOWTO_SCHEMA_INCOMPLETE" not in _codes(_page(schema_blocks=blocks))

    def test_no_howto_schema_silent(self):
        """Adversarial: a page with no HowTo schema must never fire (flags
        incomplete markup, not absent markup)."""
        blocks = [{"@type": "Article", "headline": "Something"}]
        assert "HOWTO_SCHEMA_INCOMPLETE" not in _codes(_page(schema_blocks=blocks))


class TestProductReview:
    def test_product_without_rating_fires(self):
        blocks = [{"@type": "Product", "name": "Widget", "offers": {"price": "9.99"}}]
        assert "PRODUCT_REVIEW_SCHEMA_MISSING" in _codes(_page(schema_blocks=blocks))

    def test_product_with_aggregate_rating_silent(self):
        blocks = [{"@type": "Product", "name": "Widget",
                   "aggregateRating": {"ratingValue": "4.5", "reviewCount": "12"}}]
        assert "PRODUCT_REVIEW_SCHEMA_MISSING" not in _codes(_page(schema_blocks=blocks))

    def test_no_product_schema_silent(self):
        assert "PRODUCT_REVIEW_SCHEMA_MISSING" not in _codes(_page(schema_blocks=[{"@type": "WebPage"}]))


class TestAuthorCredentials:
    def test_bare_author_fires(self):
        blocks = [{"@type": "BlogPosting", "author": {"@type": "Person", "name": "Jane Doe"}}]
        assert "AUTHOR_CREDENTIALS_MISSING" in _codes(_page(schema_blocks=blocks))

    def test_credentialed_author_silent(self):
        blocks = [{"@type": "BlogPosting", "author": {
            "@type": "Person", "name": "Jane Doe", "jobTitle": "Registered Counsellor",
            "sameAs": ["https://x.org/author/jane"]}}]
        assert "AUTHOR_CREDENTIALS_MISSING" not in _codes(_page(schema_blocks=blocks))

    def test_no_author_schema_silent(self):
        """Adversarial: a plain text byline with no author schema must NOT fire —
        otherwise every nonprofit blog post would be flagged."""
        blocks = [{"@type": "BlogPosting", "headline": "Post"}]
        assert "AUTHOR_CREDENTIALS_MISSING" not in _codes(_page(schema_blocks=blocks))

    def test_graph_nested_author_detected(self):
        """@graph nesting (Yoast/RankMath) must be descended."""
        blocks = [{"@context": "https://schema.org", "@graph": [
            {"@type": "BlogPosting", "author": {"@type": "Person", "name": "Bare Name"}},
        ]}]
        assert "AUTHOR_CREDENTIALS_MISSING" in _codes(_page(schema_blocks=blocks))
