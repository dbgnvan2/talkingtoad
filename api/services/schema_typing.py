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

    # NOTE: Person + Organization together is NOT a conflict. In the standard
    # @graph pattern (Yoast/RankMath/most WP SEO plugins) a page carries a
    # publisher Organization node AND an author/person node as SEPARATE entities
    # in one graph — that is valid and near-universal. Flagging it here false-
    # positived on essentially every WordPress site (audit accuracy fix
    # 2026-07-04). A true "same entity typed two ways" conflict can't be
    # detected from the flat schema_types list, so we don't guess.

    return None


# ---------------------------------------------------------------------------
# M3.1 — SCHEMA_VISIBLE_MISMATCH helper
# ---------------------------------------------------------------------------
# Compares JSON-LD declared values against visible page text.
# Called at parse time (where soup is in scope) and the result is stored
# as a compact list of mismatched field labels on ParsedPage.

# Fields to check, keyed by lowercase @type → list of (field_path, label_prefix)
_SCHEMA_FIELDS_TO_CHECK: dict[str, list[tuple[str, str]]] = {
    "article": [("headline", "Article.headline")],
    "newsarticle": [("headline", "Article.headline")],
    "blogposting": [("headline", "Article.headline")],
    "product": [("name", "Product.name")],
    "person": [("name", "Person.name")],
    "organization": [("name", "Organization.name")],
    "localbusiness": [
        ("name", "LocalBusiness.name"),
    ],
}


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip — used for substring comparison."""
    return " ".join(text.lower().split())


def _is_machine_identifier(value: str) -> bool:
    """True if *value* is a machine identifier (email / URL) rather than display
    content. SEO plugins inject author/publisher Person nodes whose ``name`` is
    an email or agency URL; those are not expected to appear in visible text, so
    they must not trip SCHEMA_VISIBLE_MISMATCH (audit accuracy fix 2026-07-04)."""
    v = value.strip().lower()
    return ("@" in v and "." in v.split("@")[-1]) or v.startswith(("http://", "https://", "www."))


def _assemble_address(block: dict) -> str | None:
    """Assemble a PostalAddress block into a single comparable string.

    Returns None if the address field is missing or empty.
    """
    addr = block.get("address")
    if not addr:
        return None
    if isinstance(addr, str):
        return addr.strip() or None
    if isinstance(addr, dict):
        parts = [
            addr.get("streetAddress", ""),
            addr.get("addressLocality", ""),
            addr.get("addressRegion", ""),
            addr.get("postalCode", ""),
            addr.get("addressCountry", ""),
        ]
        assembled = " ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
        return assembled or None
    return None


def _check_block_fields(
    block: dict,
    normalized_visible: str,
    mismatched: list[str],
    *,
    prefix: str = "",
) -> None:
    """Check a single schema block's fields against visible text."""
    block_type = block.get("@type", "")
    if isinstance(block_type, list):
        types_to_check = [t.lower() for t in block_type if isinstance(t, str)]
    elif isinstance(block_type, str):
        types_to_check = [block_type.lower()]
    else:
        return

    for type_key in types_to_check:
        # Standard field checks
        for field_name, label in _SCHEMA_FIELDS_TO_CHECK.get(type_key, []):
            value = block.get(field_name)
            if not isinstance(value, str) or not value.strip():
                continue  # absent or empty → not a mismatch
            if _is_machine_identifier(value):
                continue  # email/URL identifier, not display content
            if _normalize(value) not in normalized_visible:
                mismatched.append(f"{prefix}{label}")

        # LocalBusiness.address — special assembly
        if type_key == "localbusiness":
            addr_str = _assemble_address(block)
            if addr_str:
                # Check each non-empty part individually; if ANY part is missing,
                # flag. But for the label, use the whole address.
                if _normalize(addr_str) not in normalized_visible:
                    mismatched.append(f"{prefix}LocalBusiness.address")

        # FAQPage.mainEntity — array of Question objects
        if type_key == "faqpage":
            main_entity = block.get("mainEntity")
            if isinstance(main_entity, list):
                for idx, item in enumerate(main_entity):
                    if not isinstance(item, dict):
                        continue
                    # Question name
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        if _normalize(name) not in normalized_visible:
                            mismatched.append(f"{prefix}FAQPage.mainEntity[{idx}].name")
                    # acceptedAnswer.text
                    accepted = item.get("acceptedAnswer")
                    if isinstance(accepted, dict):
                        ans_text = accepted.get("text")
                        if isinstance(ans_text, str) and ans_text.strip():
                            if _normalize(ans_text) not in normalized_visible:
                                mismatched.append(
                                    f"{prefix}FAQPage.mainEntity[{idx}].acceptedAnswer.text"
                                )


def check_schema_visible_mismatch(
    schema_blocks: list[dict],
    visible_text: str,
) -> list[str]:
    """Return labels of JSON-LD fields whose values are not in *visible_text*.

    Args:
        schema_blocks: Flattened list of JSON-LD objects (already unwrapped
            from ``@graph``). Each is a dict with ``@type`` and field values.
        visible_text: Full visible text of the page (``soup.get_text()``).

    Returns:
        List of field labels like ``"Article.headline"``,
        ``"FAQPage.mainEntity[0].name"``, etc. Empty list means all checked
        values are visible. Callers should pass the result to ParsedPage's
        ``schema_visible_mismatch_fields``.
    """
    if not schema_blocks or not visible_text:
        return []

    normalized_visible = _normalize(visible_text)
    mismatched: list[str] = []

    for block in schema_blocks:
        if not isinstance(block, dict):
            continue
        _check_block_fields(block, normalized_visible, mismatched)
        # Walk @graph nesting (already flattened by parser, but be safe)
        graph = block.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict):
                    _check_block_fields(node, normalized_visible, mismatched)

    return mismatched
