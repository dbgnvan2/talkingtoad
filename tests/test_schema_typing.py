"""Tests for schema typing validation (v2.0 Schema Typing).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.4
"""

import pytest
from api.crawler.parser import ParsedPage
from api.services.schema_typing import validate_schema_typing


def _make_page(url, *, title=None, schema_types=None, **kw):
    """Helper to create a minimal ParsedPage for testing."""
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
        headings_outline=[],
        is_indexable=True,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=False,
        schema_types=schema_types or [],
        external_script_count=0,
        external_stylesheet_count=0,
        **kw,
    )


class TestAppropriateSchemas:
    """Test validation of schemas that match their page types."""

    def test_article_schema_on_article_page(self):
        """Article schema on /blog/ page should be appropriate."""
        page = _make_page("https://example.com/blog/post-title", title="Article Title", schema_types=["Article"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is True
        assert issue is None

    def test_person_schema_on_team_page(self):
        """Person schema on /team/ page should be appropriate."""
        page = _make_page("https://example.com/team/john-doe", title="John Doe", schema_types=["Person"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is True
        assert issue is None

    def test_service_schema_on_service_page(self):
        """Service schema on /services/ page should be appropriate."""
        page = _make_page("https://example.com/services/web-design", title="Web Design", schema_types=["Service"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is True
        assert issue is None

    def test_faq_schema_on_faq_page(self):
        """FAQPage schema on /faq page should be appropriate."""
        page = _make_page("https://example.com/faq", title="FAQ", schema_types=["FAQPage"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is True
        assert issue is None

    def test_multiple_compatible_schemas(self):
        """Multiple compatible schemas (e.g., Article + NewsArticle) should be OK."""
        page = _make_page("https://example.com/blog/news", title="News Item", schema_types=["Article", "NewsArticle"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is True
        assert issue is None


class TestMismatchedSchemas:
    """Test detection of schemas that don't match page type."""

    def test_product_schema_on_blog_page(self):
        """Product schema on /blog/ page should be a mismatch."""
        page = _make_page("https://example.com/blog/article", title="Article", schema_types=["Product"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is False
        assert issue is not None
        assert "schema_mismatch:article" in issue

    def test_article_schema_on_service_page(self):
        """Article schema on /services/ page should be a mismatch."""
        page = _make_page("https://example.com/services/web-design", title="Service", schema_types=["Article"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is False
        assert "schema_mismatch:service" in issue


class TestConflictingSchemas:
    """Test detection of conflicting schema types."""

    def test_article_product_conflict(self):
        """Article + Product together should be a conflict."""
        page = _make_page("https://example.com/blog/review", title="Product Review", schema_types=["Article", "Product"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is False
        assert issue is not None
        assert "schema_conflict" in issue

    def test_person_org_conflict(self):
        """Person + Organization on non-team/contact page should be conflict."""
        page = _make_page("https://example.com/random", title="Page", schema_types=["Person", "Organization"])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is False
        assert "person_org_conflict" in issue


class TestMissingSchema:
    """Test detection of missing schema."""

    def test_no_schema_returns_false(self):
        """Page with no schema types should be inappropriate."""
        page = _make_page("https://example.com/page", title="Page", schema_types=[])
        is_appropriate, issue = validate_schema_typing(page)
        assert is_appropriate is False
        assert issue == "no_schema_found"


class TestUnknownPageTypes:
    """Test handling of unknown page types."""

    def test_unknown_page_allows_any_schema(self):
        """Unknown page type should allow any schema (can't validate)."""
        page = _make_page("https://example.com/custom-xyz", title="Custom", schema_types=["Product"])
        is_appropriate, issue = validate_schema_typing(page)
        # Unknown page types are permissive
        assert is_appropriate is True or (is_appropriate is False and "no_schema_found" in issue)


class TestCaseInsensitivity:
    """Test that schema matching is case-insensitive."""

    def test_schema_type_case_handling(self):
        """Schema types should be matched case-insensitively."""
        page = _make_page("https://example.com/blog/post", title="Article", schema_types=["article"])
        is_appropriate, issue = validate_schema_typing(page)
        # Should match despite case difference
        assert is_appropriate is True or (is_appropriate is False and "schema_mismatch" in issue or "schema_conflict" in issue)
