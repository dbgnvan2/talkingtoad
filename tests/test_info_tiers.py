"""Info tiers — grade info notices, and let a scan choose how much info counts.

Purpose: 123 of 170 catalogue codes are `info`, and the band is not flat
         (impact 0–3). A tier is derived from impact; a scan's ``info_detail``
         names which tiers are SHOWN and SCORED. Same predicate on both sides.
Spec:    docs/pending/2026-09-01_info-tiers.md
Tests:   this file (unit + scoring), tests/test_info_tiers_integration.py (API)

The test that matters most is ``test_score_at_all_is_identical_to_before``:
the default level must be byte-identical to the model that existed before the
setting did, or every stored score in every audit silently moves.
"""

from __future__ import annotations

import pytest

from api.crawler.checkers.registry import (
    _CATALOGUE,
    INFO_DETAIL_LEVELS,
    INFO_DETAIL_MIN_IMPACT,
    INFO_TIER_HIGH_MIN_IMPACT,
    INFO_TIER_MEDIUM_MIN_IMPACT,
    derive_impact,
    info_detail_rank,
    info_row_excluded,
    info_tier,
    severity_from_impact,
)
from api.models.issue import Issue
from api.services import job_store_base as jsb
from api.services.job_store_base import (
    compute_citability_grade,
    compute_impact_health,
    compute_page_health,
    info_detail_rows,
)
from api.services.info_tier_filter import (
    annotate_scored,
    apply_info_detail,
    filter_issue_models,
    info_caveat_note,
    resolve_info_detail,
)


# ── §3 tier definition ────────────────────────────────────────────────────


class TestTierDefinition:
    def test_every_info_code_maps_to_exactly_one_tier(self):
        for code, spec in _CATALOGUE.items():
            tier = info_tier(derive_impact(code))
            if spec.severity == "info":
                assert tier in ("high", "medium", "low"), code
            else:
                assert tier is None, f"{code} is {spec.severity} yet got tier {tier!r}"

    def test_tier_is_monotonic_in_impact(self):
        order = {"low": 0, "medium": 1, "high": 2}
        tiers = [order[info_tier(i)] for i in range(0, 4)]
        assert tiers == sorted(tiers), "a higher impact yielded a lower tier"

    def test_tier_and_severity_agree_on_the_band(self):
        """The tier exists only where severity says info — the two are one function of impact."""
        for impact in range(0, 11):
            assert (info_tier(impact) is None) == (severity_from_impact(impact) != "info"), impact

    def test_counts_snapshot_9_61_53(self):
        """A recalibration that crosses a tier boundary must be a visible diff."""
        counts = {"high": 0, "medium": 0, "low": 0}
        for code, spec in _CATALOGUE.items():
            if spec.severity == "info":
                counts[info_tier(derive_impact(code))] += 1
        assert counts == {"high": 9, "medium": 61, "low": 53}, counts

    def test_thresholds_are_the_documented_values(self):
        assert INFO_TIER_HIGH_MIN_IMPACT == 3
        assert INFO_TIER_MEDIUM_MIN_IMPACT == 2
        assert INFO_DETAIL_MIN_IMPACT == {"all": 0, "notable": 2, "key": 3, "none": None}
        assert INFO_DETAIL_LEVELS == ("all", "notable", "key", "none")

    def test_rank_orders_all_to_none_loosest_first(self):
        ranks = [info_detail_rank(l) for l in INFO_DETAIL_LEVELS]
        assert ranks == sorted(ranks) and len(set(ranks)) == 4
        assert info_detail_rank("bogus") == info_detail_rank("all")


class TestExclusionPredicate:
    @pytest.mark.parametrize("impact,level,excluded", [
        (0, "all", False), (1, "all", False), (3, "all", False),
        (0, "notable", True), (1, "notable", True), (2, "notable", False), (3, "notable", False),
        (2, "key", True), (3, "key", False),
        (0, "none", True), (3, "none", True),
    ])
    def test_table(self, impact, level, excluded):
        assert info_row_excluded(impact, level) is excluded

    def test_none_never_drops_a_warning_or_critical(self):
        """Adversarial: the tightest level must still keep every non-info row."""
        for impact in range(4, 11):
            for level in INFO_DETAIL_LEVELS:
                assert info_row_excluded(impact, level) is False, (impact, level)

    def test_unknown_level_behaves_as_all(self):
        assert info_row_excluded(0, "whatever") is False


class TestIssueModelTier:
    def _issue(self, severity, impact):
        return Issue(job_id="j", category="metadata", severity=severity, issue_code="X",
                     description="", recommendation="", impact=impact)

    def test_info_issue_carries_its_tier_from_stored_impact(self):
        assert self._issue("info", 3).info_tier == "high"
        assert self._issue("info", 2).info_tier == "medium"
        assert self._issue("info", 0).info_tier == "low"

    def test_non_info_issue_has_no_tier(self):
        assert self._issue("warning", 5).info_tier is None

    def test_stale_row_is_tiered_by_stored_impact_not_catalogue(self):
        """P8: a pre-recalibration row keeps the tier it was scored under."""
        code = next(c for c, s in _CATALOGUE.items() if s.severity == "info" and derive_impact(c) == 1)
        stale = Issue(job_id="j", category=_CATALOGUE[code].category, severity="info",
                      issue_code=code, description="", recommendation="", impact=3)
        assert stale.info_tier == "high"  # stored 3, catalogue says 1

    def test_serialises_in_model_dump(self):
        assert "info_tier" in self._issue("info", 2).model_dump()


# ── §5 scoring ────────────────────────────────────────────────────────────


def _rows(*impacts, category="metadata"):
    return [(f"C{i}_{n}", i, category) for n, i in enumerate(impacts)]


class TestScoring:
    def test_score_at_all_is_identical_to_before(self):
        """Golden: the default level is the pre-setting model, row for row."""
        per_page = {"a": _rows(1, 2, 3, 5), "b": _rows(0, 1)}
        before = compute_impact_health(["a", "b"], per_page, {})
        after = compute_impact_health(["a", "b"], per_page, {}, info_detail="all")
        assert before == after == (round(((100 - 11) + (100 - 1)) / 2), 2)

    def test_score_never_decreases_as_the_level_tightens(self):
        """P7 monotonicity: more excluded ⇒ never a lower score."""
        per_page = {"a": _rows(0, 1, 2, 3, 4, 6), "b": _rows(2, 2, 2, 1)}
        scores = [compute_impact_health(["a", "b"], per_page, {}, info_detail=l)[0]
                  for l in INFO_DETAIL_LEVELS]
        assert scores == sorted(scores), scores
        assert scores[0] < scores[-1], "the fixture did not exercise the filter"

    def test_none_keeps_every_warning(self):
        per_page = {"a": _rows(4, 3)}
        assert compute_impact_health(["a"], per_page, {}, info_detail="none")[0] == 96

    def test_page_health_and_citability_follow_the_level(self):
        rows = _rows(1, 2, 3, category="ai_readiness")
        assert compute_page_health(rows) == 94
        assert compute_page_health(rows, info_detail="notable") == 95
        assert compute_page_health(rows, info_detail="key") == 97
        assert compute_citability_grade(rows, info_detail="none") == 100

    def test_info_detail_rows_is_identity_at_all(self):
        rows = _rows(0, 1, 2)
        assert info_detail_rows(rows, "all") is rows

    def test_excluded_parent_does_not_silence_a_charged_child(self, monkeypatch):
        """Cluster order: the level runs BEFORE R4, so a medium parent left out
        under `key` cannot go on suppressing a high child that is still charged."""
        monkeypatch.setattr(jsb, "_CLUSTER_SUPPRESSION", {"PARENT": frozenset({"CHILD"})})
        rows = [("PARENT", 2, "metadata"), ("CHILD", 3, "metadata")]
        # At `all` the parent is present, so the child is suppressed: only 2 charged.
        assert compute_page_health(rows, info_detail="all") == 98
        # At `key` the parent is out of the audit; the child is charged in full.
        assert compute_page_health(rows, info_detail="key") == 97

    def test_excluded_site_scoped_code_is_not_elected_anywhere(self):
        """MISSING_HSTS is site-scoped and low-tier (impact 1): charged once at
        `all`, charged nowhere at `notable`."""
        code = "MISSING_HSTS"
        assert _CATALOGUE[code].scope == "site" and info_tier(derive_impact(code)) == "low"
        per_page = {"a": [(code, 1, "security")], "b": [(code, 1, "security")]}
        assert compute_impact_health(["a", "b"], per_page, {}, info_detail="all")[0] == round(99.5)
        assert compute_impact_health(["a", "b"], per_page, {}, info_detail="notable")[0] == 100

    def test_density_fallback_untouched_for_legacy_jobs(self):
        """Pre-v1.5 rows (all impact 0) still take the density path."""
        per_page = {"a": [("X", 0, "metadata")]}
        legacy = compute_impact_health(["a"], per_page, {"info": 1, "warning": 0, "critical": 0})
        assert legacy == compute_impact_health(["a"], per_page, {"info": 1, "warning": 0, "critical": 0},
                                               info_detail="all")


# ── §5 display filter ─────────────────────────────────────────────────────


def _dicts():
    return [
        {"issue_code": "W", "severity": "warning", "impact": 4},
        {"issue_code": "K", "severity": "info", "impact": 3},
        {"issue_code": "N", "severity": "info", "impact": 2},
        {"issue_code": "L", "severity": "info", "impact": 1},
        {"issue_code": "Z", "severity": "info", "impact": 0},
    ]


class TestDisplayFilter:
    @pytest.mark.parametrize("level,kept_codes,hidden", [
        ("all", ["W", "K", "N", "L", "Z"], 0),
        ("notable", ["W", "K", "N"], 2),
        ("key", ["W", "K"], 3),
        ("none", ["W"], 4),
    ])
    def test_kept_plus_hidden_is_the_whole_list(self, level, kept_codes, hidden):
        kept, report = apply_info_detail(_dicts(), level)
        assert [k["issue_code"] for k in kept] == kept_codes
        assert report["hidden"] == hidden
        assert len(kept) + report["hidden"] == 5
        assert sum(report["by_tier"].values()) == hidden
        assert report["info_detail"] == level

    def test_by_tier_names_only_the_removed_rows(self):
        _, report = apply_info_detail(_dicts(), "key")
        assert report["by_tier"] == {"medium": 1, "low": 2}

    def test_scored_flag_is_relative_to_the_job_level_not_the_view(self):
        rows = annotate_scored(_dicts(), "notable")
        assert {r["issue_code"]: r["scored"] for r in rows} == {
            "W": True, "K": True, "N": True, "L": False, "Z": False}

    def test_reveal_can_loosen_but_never_tighten(self):
        assert resolve_info_detail("notable", "all") == "all"
        assert resolve_info_detail("notable", "key") == "notable"
        assert resolve_info_detail("notable", "none") == "notable"
        assert resolve_info_detail("notable", None) == "notable"
        assert resolve_info_detail("notable", "bogus") == "notable"
        assert resolve_info_detail("all", "key") == "all"

    def test_model_filter_matches_dict_filter(self):
        models = [Issue(job_id="j", category="metadata", severity=d["severity"], issue_code=d["issue_code"],
                        description="", recommendation="", impact=d["impact"]) for d in _dicts()]
        kept, report = filter_issue_models(models, "key")
        assert [i.issue_code for i in kept] == ["W", "K"]
        assert report["hidden"] == 3

    def test_caveat_only_when_something_was_excluded(self):
        assert info_caveat_note({"hidden": 0, "by_tier": {}, "info_detail": "notable"}) is None
        note = info_caveat_note({"hidden": 3, "by_tier": {"medium": 1, "low": 2}, "info_detail": "key"})
        assert "3 info notices" in note and "'key'" in note and "health score" in note
        assert "Low 2" in note and "Notable 1" in note
