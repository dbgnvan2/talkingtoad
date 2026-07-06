"""V3 — before/after HealthScore report: pure-logic tests.

Spec: docs/pending/2026-07-06_deploy-gate-validation.md#V3
Covers:
  - test_baseline_reconstruction_matches_r3_cur_column (AC V3.1)
  - test_delta_computation (AC V3.2)

The live-crawl path (AC V3.3) is integration-only and NOT covered here — it is
exercised by running scripts/before_after_healthscore.py against the real site
and is flagged as untested (per the fix->test map).
"""

from __future__ import annotations

from scripts.before_after_healthscore import (
    OLD_ISSUE_SCORING,
    PageDelta,
    compute_page_deltas,
    load_old_issue_scoring,
    remap_rows_to_old,
    site_health,
)
from api.crawler.checkers.registry import _CATALOGUE, _ISSUE_SCORING
from api.services.job_store_base import compute_page_health


def test_baseline_reconstruction_matches_r3_cur_column():
    """AC V3.1: OLD_ISSUE_SCORING == the `cur` column of the R3 §4 table.

    Spot-check the known rows the plan names, plus structural invariants:
    all 151 codes parsed, and the reconstructed OLD values DIFFER from the
    shipped (post-R3) impacts where the calibration said they should.
    """
    old = load_old_issue_scoring()
    # Same object the script exposes.
    assert old == OLD_ISSUE_SCORING

    # All 151 calibrated codes reconstructed.
    assert len(old) == 151

    # Named spot-checks (cur column):
    assert old["BROKEN_LINK_404"] == 10          # cur 10 -> now 2
    assert old["TITLE_MISSING"] == 9             # cur 9  -> now 6
    assert old["NOINDEX_META"] == 10             # cur 10 (unchanged)
    assert old["SEMANTIC_DENSITY_LOW"] == 3      # cur 3  -> now 1

    # The reconstruction must reflect the DROP the calibration made, not the
    # current values: broken-link 404 fell 10 -> 2, semantic-density 3 -> 1.
    assert _ISSUE_SCORING["BROKEN_LINK_404"][0] == 2
    assert _ISSUE_SCORING["SEMANTIC_DENSITY_LOW"][0] == 1
    assert old["BROKEN_LINK_404"] != _ISSUE_SCORING["BROKEN_LINK_404"][0]
    assert old["SEMANTIC_DENSITY_LOW"] != _ISSUE_SCORING["SEMANTIC_DENSITY_LOW"][0]
    # A genuinely-unchanged page-fatal code stays equal.
    assert old["NOINDEX_META"] == _ISSUE_SCORING["NOINDEX_META"][0] == 10


def _row(code: str) -> tuple[str, int, str]:
    """Current (code, impact, category) row using the shipped scoring."""
    return (code, _ISSUE_SCORING[code][0], _CATALOGUE[code].category)


def test_delta_computation():
    """AC V3.2: per-page delta = new_health − old_health, both via the SAME
    compute_page_health path; site health is the mean of page scores.

    Uses a page dominated by broken links — the single biggest R3 distortion
    (404 fell 10 -> 2) — so old health is much LOWER than new health and the
    delta is strongly positive.
    """
    # Five 404s on one page: OLD impact 10 each, NEW impact 2 each. The broken_link
    # category is capped at 20, so both columns hit the cap boundary differently.
    page = "https://x/dead-links"
    rows = [_row("BROKEN_LINK_404") for _ in range(5)]
    per_page = {page: rows}

    deltas = compute_page_deltas(per_page, OLD_ISSUE_SCORING)
    assert len(deltas) == 1
    d = deltas[0]
    assert isinstance(d, PageDelta)

    # Ground-truth both columns via the canonical health function directly.
    new_expected = compute_page_health(rows)
    old_rows = remap_rows_to_old(rows, OLD_ISSUE_SCORING)
    old_expected = compute_page_health(old_rows)

    assert d.new_health == new_expected
    assert d.old_health == old_expected
    assert d.delta == d.new_health - d.old_health

    # Direction: broken links got cheaper, so the page scores HIGHER now.
    assert d.new_health > d.old_health
    assert d.delta > 0

    # Old rows carry the OLD impact (10), new rows the current impact (2).
    assert old_rows[0] == ("BROKEN_LINK_404", 10, _CATALOGUE["BROKEN_LINK_404"].category)
    assert rows[0][1] == 2


def test_site_health_mean_of_pages():
    """Site health is the rounded mean of page scores; an issue-free page = 100."""
    clean = "https://x/clean"
    noisy = "https://x/noisy"
    per_page = {
        clean: [],
        noisy: [_row("BROKEN_LINK_404") for _ in range(5)],
    }
    deltas = compute_page_deltas(per_page, OLD_ISSUE_SCORING)
    new_site = site_health(deltas, "new")
    old_site = site_health(deltas, "old")

    by_url = {d.url: d for d in deltas}
    assert by_url[clean].new_health == 100
    assert by_url[clean].old_health == 100
    # Mean of the two pages.
    assert new_site == round((by_url[clean].new_health + by_url[noisy].new_health) / 2)
    assert old_site == round((by_url[clean].old_health + by_url[noisy].old_health) / 2)
    # Site rose overall (broken-link downweight).
    assert new_site >= old_site


def test_empty_site_scores_100():
    assert site_health([], "new") == 100
    assert site_health([], "old") == 100
