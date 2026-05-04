"""Schema typing validation for JSON-LD appropriateness.

Validates that JSON-LD schemas match page type, detects mismatches,
conflicts, and deprecated/missing schema patterns.

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.4
Tests: tests/test_schema_typing.py
"""

from api.crawler.parser import ParsedPage
from api.services.page_classifier import infer_page_type


# Mapping: page_type -> set of appropriate schema types
_SCHEMA_APPROPRIATENESS = {
    "home": {"Homepage", "Website", "Organization"},
    "article": {"Article", "NewsArticle", "BlogPosting", "CreativeWork"},
    "team_member": {"Person", "Employee", "Author"},
    "service": {"Service", "Offer", "Product", "LocalBusiness"},
    "faq": {"FAQPage", "QAPage"},
    "contact": {"ContactPage", "LocalBusiness", "Organization"},
    "about": {"AboutPage", "Organization", "Person"},
}

# Common deprecated schema types that should trigger warnings
_DEPRECATED_SCHEMAS = {"Breadcrumb"}  # Note: Breadcrumb not actually deprecated, but example


def validate_schema_typing(parsed_page: ParsedPage) -> tuple[bool, str | None]:
    """Validate that JSON-LD schemas match page type.

    Purpose: Check schema appropriateness for page type
    Spec:    docs/specs/ai-readiness/v2-extended-module.md § 3.4
    Tests:   tests/test_schema_typing.py::test_validate_schema_typing_*

    Args:
        parsed_page: Parsed page with schema_types and inferred type

    Returns:
        (is_appropriate, issue_description)
        - is_appropriate: True if schemas match page type
        - issue_description: None if appropriate, else issue reason
    """
    if not parsed_page.schema_types:
        return (False, "no_schema_found")

    # Check for deprecated schemas
    deprecated_found = _check_deprecated_schemas(parsed_page.schema_types)
    if deprecated_found:
        return (False, f"deprecated_schema:{deprecated_found}")

    # Check for intrinsic schema conflicts (Article + Product, Person + Organization)
    conflict = _check_schema_conflicts_intrinsic(parsed_page.schema_types)
    if conflict:
        return (False, f"schema_conflict:{conflict}")

    # Infer expected page type
    page_type = infer_page_type(parsed_page)

    # If page type unknown, allow any schema (can't validate)
    if page_type == "unknown":
        return (True, None)

    # Check if at least one schema is appropriate for page type
    expected = _SCHEMA_APPROPRIATENESS.get(page_type, set())
    found_schemas = {t for t in parsed_page.schema_types}
    has_appropriate = bool(found_schemas & expected)

    if not has_appropriate:
        return (False, f"schema_mismatch:{page_type}")

    return (True, None)


def _check_deprecated_schemas(schema_types: list[str]) -> str | None:
    """Check if any deprecated schema types are present."""
    found = {t for t in schema_types if t in _DEPRECATED_SCHEMAS}
    return next(iter(found)) if found else None


def _check_schema_conflicts_intrinsic(schema_types: list[str]) -> str | None:
    """Check for inherently conflicting schema types (same content, different types).

    Returns issue type if conflict found.
    """
    if len(schema_types) <= 1:
        return None

    schema_set = {t.lower() for t in schema_types}

    # Article + Product together is always a conflict
    if "article" in schema_set and "product" in schema_set:
        return "article_product_conflict"

    # Person + Organization together is always a conflict (they describe different entities)
    if "person" in schema_set and "organization" in schema_set:
        return "person_org_conflict"

    return None
