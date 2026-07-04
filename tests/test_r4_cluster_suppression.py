"""R4 cluster suppression + R3 structural page-health model (audit 2026-07-03).

Covers: cluster suppression (charge one root cause once), per-category caps,
page-fatal bypass, and store-parity (both stores route through
``compute_impact_health``). Suppression/caps are SCORING-ONLY — they never remove
issues from the list.

Spec: docs/pending/2026-07-03_r4-cluster-suppression.md
      docs/pending/2026-07-03_r3-model-b-calibration.md (§2 page-health model)
"""

import pytest

from api.crawler.issue_checker import _CATALOGUE, _ISSUE_SCORING
from api.services.job_store_base import (
    _CATEGORY_IMPACT_CAP,
    _CLUSTER_SUPPRESSION,
    _PAGE_FATAL_CODES,
    compute_impact_health,
    page_suppressed_codes,
)

_NO_SEV = {"critical": 0, "warning": 0, "info": 0}


def _imp(code: str) -> int:
    return _ISSUE_SCORING[code][0]


def _r(code: str, impact: int | None = None) -> tuple[str, int, str]:
    """(code, impact, category) row using the code's real category."""
    return (code, _imp(code) if impact is None else impact, _CATALOGUE[code].category)


# ── page_suppressed_codes ─────────────────────────────────────────────────────
def test_suppresses_children_when_parent_present():
    codes = {"SCHEMA_MISSING", "JSON_LD_MISSING", "SCHEMA_ORG_MISSING", "H1_MISSING"}
    assert page_suppressed_codes(codes) == {"JSON_LD_MISSING", "SCHEMA_ORG_MISSING"}


def test_no_suppression_when_parent_absent():
    assert page_suppressed_codes({"JSON_LD_MISSING", "SCHEMA_ORG_MISSING"}) == set()


def test_only_present_children_suppressed():
    assert page_suppressed_codes({"SCHEMA_MISSING", "JSON_LD_MISSING"}) == {"JSON_LD_MISSING"}


def test_js_shell_cluster_includes_nav():
    codes = {"RAW_HTML_JS_DEPENDENT", "JS_DEPENDENT_NAVIGATION", "AI_CONTENT_NOT_IN_TEXT"}
    assert page_suppressed_codes(codes) == {"JS_DEPENDENT_NAVIGATION", "AI_CONTENT_NOT_IN_TEXT"}


@pytest.mark.parametrize("parent,children", list(_CLUSTER_SUPPRESSION.items()))
def test_every_rule_fires(parent, children):
    assert page_suppressed_codes({parent} | set(children)) == set(children)


# ── clusters charged once ─────────────────────────────────────────────────────
def test_schemaless_page_charged_once():
    p = "https://x/"
    per_page = {p: [_r("SCHEMA_MISSING"), _r("JSON_LD_MISSING"), _r("SCHEMA_ORG_MISSING")]}
    site, _ = compute_impact_health([p], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("SCHEMA_MISSING")


def test_duplicate_pair_not_triple_charged():
    p = "https://x/"
    per_page = {p: [_r("TITLE_META_DUPLICATE_PAIR"), _r("TITLE_DUPLICATE"), _r("META_DESC_DUPLICATE")]}
    site, _ = compute_impact_health([p], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("TITLE_META_DUPLICATE_PAIR")


def test_thin_content_pick_one():
    p = "https://x/"
    per_page = {p: [_r("THIN_CONTENT"), _r("CONTENT_THIN")]}
    site, _ = compute_impact_health([p], per_page, dict(_NO_SEV))
    assert site == 100 - _imp("THIN_CONTENT")


def test_job_level_suppression_of_parent_frees_children():
    p = "https://x/"
    per_page = {p: [_r("SCHEMA_MISSING"), _r("JSON_LD_MISSING")]}
    site, _ = compute_impact_health([p], per_page, dict(_NO_SEV), suppressed_codes={"SCHEMA_MISSING"})
    assert site == 100 - _imp("JSON_LD_MISSING")


# ── per-category cap + page-fatal bypass ──────────────────────────────────────
def test_category_cap_bounds_stacking():
    """Many issues in one (non-fatal) category cap at _CATEGORY_IMPACT_CAP."""
    p = "https://x/"
    # repeats of one metadata code, summing well over the cap
    rows = [_r("META_DESC_DUPLICATE") for _ in range(15)]
    raw_sum = sum(i for _, i, _ in rows)
    assert raw_sum > _CATEGORY_IMPACT_CAP  # precondition
    site, _ = compute_impact_health([p], {p: rows}, dict(_NO_SEV))
    assert site == 100 - _CATEGORY_IMPACT_CAP


def test_broken_link_per_occurrence_capped():
    """15 broken 404 links on one page deduct the category cap, not 150."""
    p = "https://x/"
    per_page = {p: [_r("BROKEN_LINK_404") for _ in range(15)]}
    site, _ = compute_impact_health([p], per_page, dict(_NO_SEV))
    assert site == 100 - _CATEGORY_IMPACT_CAP  # 80, not 0


def test_page_fatal_bypasses_cap():
    """A page-fatal code's impact is charged on top of (not merged into) the
    capped category total, so a broken page scores worse than the cap alone."""
    p = "https://x/"
    assert "NOINDEX_META" in _PAGE_FATAL_CODES
    # NOINDEX (fatal) + a maxed-out (over-cap) metadata category
    meta = [_r("META_DESC_DUPLICATE") for _ in range(15)]
    rows = [_r("NOINDEX_META")] + meta
    site, _ = compute_impact_health([p], {p: rows}, dict(_NO_SEV))
    assert site == 100 - _imp("NOINDEX_META") - _CATEGORY_IMPACT_CAP


def test_fatal_sum_not_capped():
    """Multiple page-fatal codes sum uncapped (unlike a normal category)."""
    p = "https://x/"
    fatal = [_r("NOINDEX_META"), _r("ROBOTS_BLOCKED"), _r("HTTP_PAGE")]  # all fatal, sum > 20
    total = sum(i for _, i, _ in fatal)
    assert total > _CATEGORY_IMPACT_CAP
    site, _ = compute_impact_health([p], {p: fatal}, dict(_NO_SEV))
    assert site == max(0, 100 - total)  # not capped at 20


# ── site aggregation / fallbacks ──────────────────────────────────────────────
def test_site_health_is_mean_and_clean_pages_score_100():
    pages = ["https://x/a", "https://x/b"]
    per_page = {"https://x/a": [_r("H1_MISSING")]}
    site, n = compute_impact_health(pages, per_page, dict(_NO_SEV))
    assert n == 2
    assert site == round(((100 - _imp("H1_MISSING")) + 100) / 2)


def test_no_pages_returns_100():
    assert compute_impact_health([], {}, dict(_NO_SEV)) == (100, 0)


def test_pre_v15_density_fallback():
    pages = ["https://x/a"]
    per_page = {"https://x/a": [("OLD_CODE", 0, "metadata"), ("OLD_CODE2", 0, "metadata")]}
    by_sev = {"critical": 1, "warning": 0, "info": 0}
    site, _ = compute_impact_health(pages, per_page, by_sev)
    assert site == 50  # critical density 1/1 × 50
