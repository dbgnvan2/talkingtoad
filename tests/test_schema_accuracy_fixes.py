"""Schema detector accuracy fixes (audit 2026-07-04).

Root cause: three schema checks false-positived on the standard WordPress
SEO-plugin @graph (Organization + WebSite + Person in one graph), which is what
most of the tool's audience uses. Verified on livingsystems.ca's homepage.
"""

from api.services.schema_typing import (
    check_schema_visible_mismatch, validate_schema_typing, _check_schema_conflicts_intrinsic,
)
from tests.test_issue_checker import _page
from api.crawler.issue_checker import check_page


# ── #1 JSON_LD_INVALID: @graph children inherit @context ──────────────────────
def test_graph_nodes_without_context_are_valid():
    """Nodes flattened out of an @graph have @type but no per-node @context
    (it lives on the root) — they must NOT be flagged JSON_LD_INVALID."""
    page = _page(url="https://wp.example/", schema_types=["Organization", "Person"])
    page.schema_blocks = [
        {"@type": "Organization", "name": "Living Systems"},   # no @context (inherited)
        {"@type": "WebSite", "name": "Living Systems"},
        {"@type": "Person", "name": "digital@agency.ca"},
    ]
    assert "JSON_LD_INVALID" not in {i.code for i in check_page(page)}


def test_block_without_type_still_invalid():
    """A genuinely broken node (no @type at all) is still flagged."""
    page = _page(url="https://wp.example/", schema_types=["Thing"])
    page.schema_blocks = [{"name": "no type here"}]
    assert "JSON_LD_INVALID" in {i.code for i in check_page(page)}


# ── #2 SCHEMA_TYPE_CONFLICT: Person + Organization is not a conflict ───────────
def test_person_plus_organization_not_conflict():
    assert _check_schema_conflicts_intrinsic(["Person", "Organization"]) is None


def test_article_plus_product_still_conflict():
    assert _check_schema_conflicts_intrinsic(["Article", "Product"]) == "article_product_conflict"


# ── #3 SCHEMA_VISIBLE_MISMATCH: machine identifiers aren't display content ─────
def test_email_person_name_not_flagged():
    blocks = [{"@type": "Person", "name": "digital@anchormarketing.ca"}]
    assert check_schema_visible_mismatch(blocks, "Some visible page text about therapy.") == []


def test_url_person_name_not_flagged():
    blocks = [{"@type": "Person", "name": "https://anchormarketing.ca"}]
    assert check_schema_visible_mismatch(blocks, "Some visible page text.") == []


def test_real_hidden_name_still_flagged():
    """A genuine display name absent from the page still fires (true positive)."""
    blocks = [{"@type": "Person", "name": "Jane Smith"}]
    assert "Person.name" in check_schema_visible_mismatch(blocks, "Totally unrelated body text.")


def test_visible_name_not_flagged():
    blocks = [{"@type": "Person", "name": "Jane Smith"}]
    assert check_schema_visible_mismatch(blocks, "Our therapist Jane Smith helps families.") == []
