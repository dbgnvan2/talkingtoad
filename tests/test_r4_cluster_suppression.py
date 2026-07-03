"""R4 — cluster suppression + store-parity impact health (audit 2026-07-03, Path A).

Spec: docs/pending/2026-07-03_r4-cluster-suppression.md
Both stores route their health scores through
``api.services.job_store_base.compute_impact_health``, so testing that pure
function covers SQLite and Redis alike. Suppression is SCORING-ONLY: it never
removes issues from the list (that path doesn't call these functions).
"""

import pytest

from api.crawler.issue_checker import _ISSUE_SCORING
from api.services.job_store_base import (
    _CLUSTER_SUPPRESSION,
    compute_impact_health,
    page_suppressed_codes,
)

_NO_SEV = {"critical": 0, "warning": 0, "info": 0}


def _imp(code: str) -> int:
    return _ISSUE_SCORING[code][0]


# ── page_suppressed_codes ─────────────────────────────────────────────────────
def test_suppresses_children_when_parent_present():
    codes = {"SCHEMA_MISSING", "JSON_LD_MISSING", "SCHEMA_ORG_MISSING", "H1_MISSING"}
    assert page_suppressed_codes(codes) == {"JSON_LD_MISSING", "SCHEMA_ORG_MISSING"}


def test_no_suppression_when_parent_absent():
    codes = {"JSON_LD_MISSING", "SCHEMA_ORG_MISSING", "H1_MISSING"}
    assert page_suppressed_codes(codes) == set()


def test_only_present_children_are_suppressed():
    codes = {"SCHEMA_MISSING", "JSON_LD_MISSING"}  # SCHEMA_ORG_MISSING not present
    assert page_suppressed_codes(codes) == {"JSON_LD_MISSING"}


def test_unrelated_codes_untouched():
    codes = {"H1_MISSING", "META_DESC_MISSING", "BROKEN_LINK_404"}
    assert page_suppressed_codes(codes) == set()


@pytest.mark.parametrize("parent,children", list(_CLUSTER_SUPPRESSION.items()))
def test_every_rule_fires(parent, children):
    codes = {parent} | set(children)
    assert page_suppressed_codes(codes) == set(children)


# ── compute_impact_health: clusters charged once ──────────────────────────────
def test_schemaless_page_charged_once():
    page = "https://x/"
    per_page = {page: [("SCHEMA_MISSING", _imp("SCHEMA_MISSING")),
                       ("JSON_LD_MISSING", _imp("JSON_LD_MISSING")),
                       ("SCHEMA_ORG_MISSING", _imp("SCHEMA_ORG_MISSING"))]}
    site, n = compute_impact_health([page], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("SCHEMA_MISSING")  # only the parent charged
    # sanity: that is strictly better than charging all three
    naive = 100 - (_imp("SCHEMA_MISSING") + _imp("JSON_LD_MISSING") + _imp("SCHEMA_ORG_MISSING"))
    assert site > naive


def test_duplicate_pair_not_triple_charged():
    page = "https://x/"
    per_page = {page: [("TITLE_META_DUPLICATE_PAIR", _imp("TITLE_META_DUPLICATE_PAIR")),
                       ("TITLE_DUPLICATE", _imp("TITLE_DUPLICATE")),
                       ("META_DESC_DUPLICATE", _imp("META_DESC_DUPLICATE"))]}
    site, _ = compute_impact_health([page], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("TITLE_META_DUPLICATE_PAIR")


def test_spa_not_in_text_cluster_charged_once():
    page = "https://x/"
    per_page = {page: [("RAW_HTML_JS_DEPENDENT", _imp("RAW_HTML_JS_DEPENDENT")),
                       ("AI_CONTENT_NOT_IN_TEXT", _imp("AI_CONTENT_NOT_IN_TEXT")),
                       ("CONTENT_NOT_EXTRACTABLE_NO_TEXT", _imp("CONTENT_NOT_EXTRACTABLE_NO_TEXT")),
                       ("CONTACT_INFO_NOT_IN_HTML", _imp("CONTACT_INFO_NOT_IN_HTML"))]}
    site, _ = compute_impact_health([page], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("RAW_HTML_JS_DEPENDENT")


def test_thin_content_pick_one():
    page = "https://x/"
    per_page = {page: [("THIN_CONTENT", _imp("THIN_CONTENT")),
                       ("CONTENT_THIN", _imp("CONTENT_THIN"))]}
    site, _ = compute_impact_health([page], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("THIN_CONTENT")


# ── interactions ──────────────────────────────────────────────────────────────
def test_job_level_suppression_of_parent_frees_children():
    """If the parent is globally suppressed (removed before scoring), its
    children are the real signal and MUST be charged."""
    page = "https://x/"
    per_page = {page: [("SCHEMA_MISSING", _imp("SCHEMA_MISSING")),
                       ("JSON_LD_MISSING", _imp("JSON_LD_MISSING"))]}
    site, _ = compute_impact_health([page], per_page, dict(_NO_SEV),
                                    suppressed_codes={"SCHEMA_MISSING"})
    assert site == 100 - _imp("JSON_LD_MISSING")  # child now charged, parent gone


def test_per_occurrence_codes_not_suppressed():
    """Repeated per-target codes (e.g. two 404s) are both charged — suppression
    only collapses correlated DIFFERENT codes, not repeats of one code."""
    page = "https://x/"
    per_page = {page: [("BROKEN_LINK_404", 10), ("BROKEN_LINK_404", 10)]}
    site, _ = compute_impact_health([page], per_page, dict(_NO_SEV))
    assert site == max(0, 100 - 20)


def test_site_health_is_mean_and_clean_pages_score_100():
    pages = ["https://x/a", "https://x/b"]
    per_page = {"https://x/a": [("H1_MISSING", _imp("H1_MISSING"))]}  # b is clean
    site, n = compute_impact_health(pages, per_page, dict(_NO_SEV))
    assert n == 2
    assert site == round(((100 - _imp("H1_MISSING")) + 100) / 2)


def test_floor_at_zero():
    page = "https://x/"
    per_page = {page: [("BROKEN_LINK_404", 10)] * 15}  # 150 impact
    site, _ = compute_impact_health([page], per_page, dict(_NO_SEV))
    assert site == 0


def test_no_pages_returns_100():
    assert compute_impact_health([], {}, dict(_NO_SEV)) == (100, 0)


def test_pre_v15_density_fallback():
    """Issues exist but every impact is 0 (pre-v1.5 data) → density model."""
    pages = ["https://x/a"]
    per_page = {"https://x/a": [("OLD_CODE", 0), ("OLD_CODE2", 0)]}
    by_sev = {"critical": 1, "warning": 0, "info": 0}
    site, n = compute_impact_health(pages, per_page, by_sev)
    # density: critical density 1/1 * 50 = 50 → 100-50 = 50
    assert site == 50
