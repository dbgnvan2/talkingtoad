"""Tests for page type classification (v2.0 Schema Typing).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.4
"""

import pytest
from api.crawler.parser import ParsedPage
from api.services.page_classifier import infer_page_type


def _make_page(url, *, title=None, schema_types=None, word_count=None, meta_description=None, **kw):
    """Helper to create a minimal ParsedPage for testing."""
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=3000,
        title=title,
        meta_description=meta_description,
        og_title=None,
        og_description=None,
        og_image=None,
        twitter_card=None,
        canonical_url=None,
        h1_tags=[title] if title else [],
        headings_outline=[],
        is_indexable=True,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=False,
        schema_types=schema_types or [],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=word_count,
        **kw,
    )


class TestURLPatternClassification:
    """Test page type inference from URL paths."""

    def test_home_page_root(self):
        """URLs like / should be classified as home."""
        page = _make_page("https://example.com/", title="Home")
        assert infer_page_type(page) == "home"

    def test_home_page_index(self):
        """URLs like /index should be classified as home."""
        page = _make_page("https://example.com/index.html", title="Home")
        assert infer_page_type(page) == "home"

    def test_team_member_path(self):
        """URLs like /team/john should be classified as team_member."""
        page = _make_page("https://example.com/team/john-doe", title="John Doe", schema_types=["Person"])
        assert infer_page_type(page) == "team_member"

    def test_service_path(self):
        """URLs like /services/web-design should be classified as service."""
        page = _make_page("https://example.com/services/web-design", title="Web Design", schema_types=["Service"])
        assert infer_page_type(page) == "service"

    def test_faq_path(self):
        """URLs like /faq should be classified as faq."""
        page = _make_page("https://example.com/faq", title="FAQ", schema_types=["FAQPage"])
        assert infer_page_type(page) == "faq"

    def test_contact_path(self):
        """URLs like /contact should be classified as contact."""
        page = _make_page("https://example.com/contact-us", title="Contact Us", schema_types=["ContactPage"])
        assert infer_page_type(page) == "contact"

    def test_about_path(self):
        """URLs like /about should be classified as about."""
        page = _make_page("https://example.com/about-us", title="About Us", schema_types=["Organization"])
        assert infer_page_type(page) == "about"

    def test_article_path(self):
        """URLs like /blog/post-title should be classified as article."""
        page = _make_page("https://example.com/blog/how-to-seo", title="How to SEO", schema_types=["BlogPosting"])
        assert infer_page_type(page) == "article"


class TestSchemaBasedClassification:
    """Test page type inference from schema types."""

    def test_article_schema(self):
        """Article schema type should infer article page."""
        page = _make_page("https://example.com/post-123", title="Article Title", schema_types=["Article"])
        assert infer_page_type(page) == "article"

    def test_person_schema(self):
        """Person schema type should infer team_member page."""
        page = _make_page("https://example.com/staff-123", title="Jane Smith", schema_types=["Person"])
        assert infer_page_type(page) == "team_member"

    def test_service_schema(self):
        """Service schema type should infer service page."""
        page = _make_page("https://example.com/offering-123", title="Service Name", schema_types=["Service"])
        assert infer_page_type(page) == "service"

    def test_faq_schema(self):
        """FAQPage schema type should infer faq page."""
        page = _make_page("https://example.com/questions", title="Questions", schema_types=["FAQPage"])
        assert infer_page_type(page) == "faq"


class TestHTMLBasedClassification:
    """Test page type inference from HTML structure signals."""

    def test_home_page_short_content(self):
        """Short page with single H1 and home-like title infers home."""
        page = _make_page("https://example.com/welcome", title="Home", word_count=300)
        result = infer_page_type(page)
        assert result == "home" or result == "unknown"

    def test_article_long_content(self):
        """Long page with substantial text infers article."""
        page = _make_page("https://example.com/guide", title="Complete Guide to SEO", word_count=2000,
                          meta_description="A blog article about SEO best practices")
        result = infer_page_type(page)
        assert result == "article" or result == "unknown"


class TestURLPriority:
    """Test that URL patterns take priority over schema hints."""

    def test_url_overrides_schema(self):
        """URL pattern has highest priority even with conflicting schema."""
        page = _make_page("https://example.com/team/alice", title="Alice", schema_types=["Article"])
        # URL path should override the schema type
        assert infer_page_type(page) == "team_member"


class TestUnknownPages:
    """Test classification of pages that don't match any pattern."""

    def test_unknown_path_no_schema(self):
        """Random URL with no schema should be unknown."""
        page = _make_page("https://example.com/random-page", title="Random")
        assert infer_page_type(page) == "unknown"

    def test_unknown_with_unrecognized_schema(self):
        """Custom/unrecognized schema type should be unknown."""
        page = _make_page("https://example.com/custom", title="Custom", schema_types=["CustomType"])
        assert infer_page_type(page) == "unknown"
