"""R5.2 + R5.3 — remaining suppression clusters and noindex scope-reduction.

Every cluster is scoring-time: children stay VISIBLE in the issue list and only
contribute 0 to the health score when their parent is present. All codes are
kept (no merges/deletions) per the owner decision — the three external "merge"
clusters (§6.4 answer-first, §6.6 chunk, §6.10 social) are implemented as
suppress-children with one elected parent.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.2 / §R5.3
      external talkingtoad-scoring-change-spec.md §6.1–6.15
"""

from __future__ import annotations

import pytest

from api.crawler.checkers.registry import _CATALOGUE, _ISSUE_SCORING
from api.services.job_store_base import (
    _CLUSTER_SUPPRESSION,
    compute_impact_health,
    page_suppressed_codes,
)

_NO_SEV = {"critical": 0, "warning": 0, "info": 0}


def _imp(code: str) -> int:
    return _ISSUE_SCORING[code][0]


def _row(code: str) -> tuple[str, int, str]:
    return (code, _imp(code), _CATALOGUE[code].category)


# The NEW/CHANGED clusters this phase adds (parent, representative child).
# One parametrized case each per spec §10(d).
_NEW_CLUSTERS = {
    "js_shell": ("RAW_HTML_JS_DEPENDENT",
                 ["JS_RENDERED_CONTENT_DIFFERS", "SEMANTIC_DENSITY_LOW",
                  "CONTENT_UNSTRUCTURED", "THIN_CONTENT", "CONTENT_THIN"]),
    "jsonld": ("JSON_LD_MISSING",
               ["SCHEMA_ORG_MISSING", "FAQ_SCHEMA_MISSING", "DATE_PUBLISHED_MISSING",
                "DATE_MODIFIED_MISSING", "SCHEMA_TYPE_CONFLICT", "SCHEMA_TYPE_MISMATCH",
                "SCHEMA_VISIBLE_MISMATCH", "SCHEMA_DEPRECATED_TYPE", "JSON_LD_INVALID"]),
    "answer_first": ("CENTRAL_CLAIM_BURIED",
                     ["FIRST_VIEWPORT_NO_ANSWER", "GEO_SUMMARY_BURIED"]),
    "citations": ("CITATIONS_MISSING_SUBSTANTIAL_CONTENT",
                  ["EXTERNAL_CITATIONS_LOW", "ORPHAN_CLAIM_TECHNICAL", "QUOTATIONS_MISSING",
                   "LINK_PROFILE_PROMOTIONAL", "CITATIONS_ORPHANED",
                   "CITATIONS_SOURCES_INACCESSIBLE"]),
    "chunk": ("CHUNKS_NOT_SELF_CONTAINED",
              ["SECTION_CROSS_REFERENCES", "SECTION_VAGUE_OPENER"]),
    "heavy_image": ("IMG_OVERSIZED",
                    ["IMG_POOR_COMPRESSION", "IMG_OVERSCALED", "IMG_FORMAT_LEGACY",
                     "IMG_SLOW_LOAD", "IMG_NO_SRCSET"]),
    "alt_missing": ("IMG_ALT_MISSING", ["IMG_ALT_TOO_SHORT"]),
    "alt_generic": ("IMG_ALT_GENERIC",
                    ["IMG_ALT_TOO_SHORT", "IMG_ALT_DUP_FILENAME", "IMG_ALT_MISUSED"]),
    "social": ("OG_TITLE_MISSING",
               ["OG_DESC_MISSING", "OG_IMAGE_MISSING", "TWITTER_CARD_MISSING"]),
    "robots": ("AI_BOT_BLANKET_DISALLOW",
               ["AI_BOT_SEARCH_BLOCKED", "AI_BOT_USER_FETCH_BLOCKED", "ROBOTS_BLOCKED",
                "AI_BOT_NO_AI_DIRECTIVES"]),
    "redirect_chain": ("REDIRECT_CHAIN", ["REDIRECT_301", "REDIRECT_302"]),
    "thin": ("CONTENT_THIN",
             ["THIN_CONTENT", "CONTENT_UNSTRUCTURED", "STRUCTURED_ELEMENTS_LOW",
              "SEMANTIC_DENSITY_LOW"]),
}


@pytest.mark.parametrize("name,cluster", list(_NEW_CLUSTERS.items()))
def test_cluster_suppresses_children(name, cluster):
    """R5.2.1 / spec §10(d): parent present ⇒ each listed child contributes 0."""
    parent, children = cluster
    # 1) page_suppressed_codes drops exactly the present children.
    codes = {parent} | set(children)
    assert page_suppressed_codes(codes) == set(children), name

    # 2) score charges the parent once — children add nothing.
    p = "https://x/p"
    rows = [_row(parent)] + [_row(c) for c in children]
    # (the parent may itself be capped/fatal; compare parent-only vs parent+children)
    site_all, _ = compute_impact_health([p], {p: rows}, dict(_NO_SEV))
    site_parent_only, _ = compute_impact_health([p], {p: [_row(parent)]}, dict(_NO_SEV))
    assert site_all == site_parent_only, name


@pytest.mark.parametrize("name,cluster", list(_NEW_CLUSTERS.items()))
def test_cluster_absent_parent_no_suppression(name, cluster):
    """R5.2.1: parent absent ⇒ this parent adds no suppression.

    Some children are themselves parents of OTHER clusters (e.g. CONTENT_THIN),
    so we can't assert the whole child-set is unsuppressed. Instead: pick a
    child that is not itself a cluster parent, present it alone, and assert it is
    not suppressed when its parent is absent."""
    parent, children = cluster
    leaf_children = [c for c in children if c not in _CLUSTER_SUPPRESSION]
    assert leaf_children, f"{name}: expected at least one non-parent child"
    child = leaf_children[0]
    assert page_suppressed_codes({child}) == set(), f"{name}: {child}"


def test_thin_cluster_direction_reconciled():
    """R4 had THIN_CONTENT→{CONTENT_THIN}; spec §6.15 flips this: CONTENT_THIN
    (<100 words, the stricter subset) is the parent. The old direction must be
    gone so a strict-thin page isn't double-charged."""
    # CONTENT_THIN present ⇒ THIN_CONTENT suppressed.
    assert "THIN_CONTENT" in page_suppressed_codes({"CONTENT_THIN", "THIN_CONTENT"})
    # THIN_CONTENT alone must NOT suppress CONTENT_THIN (old, wrong direction).
    assert "CONTENT_THIN" not in page_suppressed_codes({"THIN_CONTENT", "CONTENT_THIN"})


def test_clusters_never_touch_security_redirect():
    """R5.2.2: no cluster suppresses a `security` code, and `redirect` children
    appear ONLY under the intentional redirect-chain cluster (REDIRECT_CHAIN)."""
    for parent, children in _CLUSTER_SUPPRESSION.items():
        for child in children:
            cat = _CATALOGUE[child].category
            assert cat != "security", f"{parent}→{child} suppresses a security code"
            if cat == "redirect":
                assert parent == "REDIRECT_CHAIN", (
                    f"{parent}→{child} suppresses a redirect code outside the "
                    f"intentional redirect-chain cluster"
                )


# ── R5.3 noindex scope-reduction ──────────────────────────────────────────────
def test_noindex_scope_reduction():
    """R5.3.1 / spec §10(g): a noindexed page with many content issues across
    categories deducts ONLY the noindex — except a security-category and a
    redirect-category issue, which still count."""
    p = "https://x/noindexed"
    content_codes = [
        "TITLE_MISSING", "META_DESC_MISSING", "H1_MISSING", "THIN_CONTENT",
        "SEMANTIC_DENSITY_LOW", "STRUCTURED_ELEMENTS_LOW", "IMG_ALT_MISSING",
        "OG_TITLE_MISSING", "OG_DESC_MISSING", "JSON_LD_MISSING",
        "SCHEMA_ORG_MISSING", "DATE_PUBLISHED_MISSING", "CONTENT_UNSTRUCTURED",
        "QUOTATIONS_MISSING", "EXTERNAL_CITATIONS_LOW",
    ]
    assert len(content_codes) == 15
    # A security-category and a redirect-category issue that must STILL count.
    # (MISSING_HSTS is site-scoped, so use a non-scoped security code:
    # UNSAFE_CROSS_ORIGIN_LINK is page-scoped security.)
    security_code = "UNSAFE_CROSS_ORIGIN_LINK"
    redirect_code = "REDIRECT_302"
    assert _CATALOGUE[security_code].category == "security"
    assert _CATALOGUE[redirect_code].category == "redirect"

    rows = ([_row("NOINDEX_META")]
            + [_row(c) for c in content_codes]
            + [_row(security_code), _row(redirect_code)])
    site, _ = compute_impact_health([p], {p: rows}, dict(_NO_SEV))

    # Expected deduction: NOINDEX_META (fatal) + security + redirect, capped by
    # category for the two non-fatal ones (each alone, below the cap).
    from api.services.job_store_base import _page_deduction
    expected_rows = [_row("NOINDEX_META"), _row(security_code), _row(redirect_code)]
    expected = max(0, 100 - _page_deduction(expected_rows))
    assert site == expected


def test_noindex_header_also_reduces():
    p = "https://x/n"
    rows = [_row("NOINDEX_HEADER"), _row("TITLE_MISSING"), _row("H1_MISSING")]
    site, _ = compute_impact_health([p], {p: rows}, dict(_NO_SEV))
    assert site == 100 - _imp("NOINDEX_HEADER")


def test_no_noindex_no_reduction():
    """Without a noindex code, content issues score normally."""
    p = "https://x/n"
    rows = [_row("TITLE_MISSING"), _row("H1_MISSING")]
    from api.services.job_store_base import _page_deduction
    site, _ = compute_impact_health([p], {p: rows}, dict(_NO_SEV))
    assert site == max(0, 100 - _page_deduction(rows))
