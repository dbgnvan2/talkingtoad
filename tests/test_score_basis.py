"""S1/S3 — the health score must carry the coverage it was computed over.

Spec:  docs/pending/2026-08-30_score-coverage-basis.md
Audit: docs/audit/2026-08-30_full-check-audit.md

Measured on livingsystems.ca, two crawls 49 minutes apart:

    d1394998  enabled_analyses=['link_integrity']   356 issues   health 100
    a87e2d61  enabled_analyses=None (all)         2,206 issues   health  87

The scan that skipped eight categories scored a perfect 100. Page Health is
`100 - sum(impact)`, so a category that never runs costs nothing and "we did not
look" is arithmetically identical to "we found nothing".

The fix is NOT to deduct for unchecked categories — inventing a penalty for a
check that did not run would fabricate a finding. A partial scan's score is not
worse, it is NOT COMPARABLE, and this record is what says so.
"""
from __future__ import annotations

from api.crawler.checkers.registry import SCORING_MODEL_VERSION
from api.crawler.engine import (_ANALYSIS_CATEGORY_MAP, _UNGROUPED_CATEGORIES,
                                CrawlSettings, _build_analysis_coverage)
from api.services.job_store_base import health_score_basis


def _every_category() -> set[str]:
    every = set(_UNGROUPED_CATEGORIES)
    for cats in _ANALYSIS_CATEGORY_MAP.values():
        every |= cats
    return every


class TestScoreBasis:
    def test_s1_1_partial_scan_is_marked_not_comparable(self):
        cov = _build_analysis_coverage(CrawlSettings(enabled_analyses=["link_integrity"]))
        basis = health_score_basis(cov)
        assert basis["mode"] == "partial"
        assert basis["comparable"] is False
        assert "metadata" in basis["categories_unscored"]
        assert "broken_link" in basis["categories_scored"]

    def test_s1_2_full_scan_is_comparable(self):
        """Adversarial: a normal scan must not be labelled partial."""
        basis = health_score_basis(_build_analysis_coverage(CrawlSettings()))
        assert basis["mode"] == "all"
        assert basis["comparable"] is True
        assert basis["categories_unscored"] == []

    def test_s1_3_legacy_job_basis_recovered_from_its_settings(self):
        """A crawl from before the coverage record existed still has its
        `enabled_analyses` in persisted settings, so the basis is RECOVERED for
        the whole job history rather than assumed complete."""
        basis = health_score_basis(None, CrawlSettings(enabled_analyses=["link_integrity"]))
        assert basis["mode"] == "partial"
        assert basis["comparable"] is False

    def test_s1_3b_legacy_full_scan_reports_comparable(self):
        """Adversarial: a legacy job that really was a full scan must not be
        downgraded to 'partial' just because the record is absent."""
        assert health_score_basis(None, CrawlSettings()) ["comparable"] is True
        assert health_score_basis(None, None)["comparable"] is True

    def test_s1_4_basis_partitions_every_category(self):
        cov = _build_analysis_coverage(CrawlSettings(enabled_analyses=["image"]))
        basis = health_score_basis(cov)
        scored, unscored = set(basis["categories_scored"]), set(basis["categories_unscored"])
        assert scored | unscored == _every_category()
        assert not scored & unscored

    def test_s1_5_security_is_always_scored(self):
        """security runs regardless of the toggles, so it can never be unscored."""
        basis = health_score_basis(_build_analysis_coverage(
            CrawlSettings(enabled_analyses=["link_integrity"])))
        assert "security" in basis["categories_scored"]

    def test_s3_1_scoring_model_version_bumped(self):
        """The stamp is what lets a later comparison know the basis field exists."""
        assert SCORING_MODEL_VERSION == "2026-08-30-r6"


class TestExportsNameTheBasis:
    def test_s2_2_partial_note_states_the_score_is_not_comparable(self):
        from types import SimpleNamespace

        from api.services.coverage_notes import analysis_coverage_note

        note = analysis_coverage_note(SimpleNamespace(analysis_coverage={
            "mode": "partial", "categories_checked": ["broken_link", "redirect", "security"],
            "categories_unchecked": ["metadata", "heading"]}))
        assert note and "3 of 5 categories" in note
        assert "not comparable" in note


def test_s1_empty_analysis_selection_is_not_a_full_scan():
    """`enabled_analyses=[]` means every group OFF, not "no selection made".

    The legacy-recovery branch tested truthiness, so [] fell through to the
    full-scan default and returned mode "all" with comparable: True — for the
    least-covered scan the system can produce (only `security` runs). The one
    job where the basis matters most was the one job that lied about it.
    """
    from api.crawler.engine import CrawlSettings, _enabled_categories
    from api.services.job_store_base import health_score_basis

    assert sorted(_enabled_categories([])) == ["security"], (
        "precondition: [] must mean only security runs")

    basis = health_score_basis(None, CrawlSettings(enabled_analyses=[]))
    assert basis["mode"] == "partial", (
        f"an empty selection reported mode={basis['mode']!r}")
    assert basis["comparable"] is False, (
        "a scan of one category was reported as comparable to a full audit")
    assert basis["categories_scored"] == ["security"]
    assert len(basis["categories_unscored"]) > 5, (
        "the categories that did not run were not reported as unscored")
