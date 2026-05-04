"""
Tests for geo_scoring_map.py (GEO Rewrite Prompt Generator — Phase A+B).

Spec: docs/implementation_plan_geo_rewrite_prompt_2026-05-03.md

Tests:
  A.1 — compute_score_from_findings matches geo_analyzer._compute_scores()
  A.2 — GEO_CHECKS inventory is complete (all 22 checks present)
  B.1 — compute_90_path correctly identifies mandatory checks
  B.2 — no mandatory checks have can_fix_without_fabrication=False AND fabrication risk
"""

import pytest

from api.services.geo_scoring_map import (
    GEO_CHECKS,
    TIER_WEIGHTS,
    WEAK_CHECK_CODES,
    compute_90_path,
    compute_score_from_findings,
)

# ---------------------------------------------------------------------------
# Helper: build a finding dict (matches GEOFinding.to_dict() shape)
# ---------------------------------------------------------------------------

def _f(code: str, tier: str, pass_fail: str, score: float = 0.0) -> dict:
    return {
        "code": code,
        "label": code,
        "evidence_tier": tier,
        "pass_fail": pass_fail,
        "score": score,
    }


# ---------------------------------------------------------------------------
# A.1 — compute_score_from_findings matches geo_analyzer._compute_scores()
# ---------------------------------------------------------------------------

class TestComputeScoreFromFindings:
    def test_a1_empty_findings_returns_1(self):
        """A.1: no findings → score = 1.0 (same as geo_analyzer)."""
        assert compute_score_from_findings([]) == 1.0

    def test_a1_single_fail_empirical(self):
        """A.1: one Empirical fail → score = (3 × 0.0) / 3 = 0.0."""
        findings = [_f("STATISTICS_COUNT_LOW", "Empirical", "fail")]
        assert compute_score_from_findings(findings) == 0.0

    def test_a1_single_fail_conventional(self):
        """A.1: one Conventional fail → score = (1 × 0.0) / 1 = 0.0."""
        findings = [_f("JSON_LD_INVALID", "Conventional", "fail")]
        assert compute_score_from_findings(findings) == 0.0

    def test_a1_query_match_pass(self):
        """A.1: QUERY_MATCH_SCORE pass with score=0.85 → overall = 0.85."""
        findings = [_f("QUERY_MATCH_SCORE", "Empirical", "pass", score=0.85)]
        assert compute_score_from_findings(findings) == pytest.approx(0.85, abs=0.001)

    def test_a1_query_match_fail(self):
        """A.1: QUERY_MATCH_SCORE fail (score=0.60) → effective score is 0.0 (fail branch)."""
        findings = [_f("QUERY_MATCH_SCORE", "Empirical", "fail", score=0.60)]
        assert compute_score_from_findings(findings) == 0.0

    def test_a1_mixed_findings(self):
        """A.1: QUERY_MATCH_SCORE pass=0.85 + one Conventional fail."""
        # total_weight = 3 + 1 = 4
        # weighted_score = 3*0.85 + 1*0.0 = 2.55
        # overall = 2.55 / 4 = 0.6375
        findings = [
            _f("QUERY_MATCH_SCORE", "Empirical", "pass", score=0.85),
            _f("JSON_LD_INVALID", "Conventional", "fail"),
        ]
        assert compute_score_from_findings(findings) == pytest.approx(0.6375, abs=0.001)

    def test_a1_info_pass_fail(self):
        """A.1: info pass_fail → effective score = 0.75."""
        findings = [_f("SOMETHING", "Mechanistic", "info", score=0.0)]
        # total_weight = 2, weighted_score = 2 * 0.75 = 1.5, overall = 0.75
        assert compute_score_from_findings(findings) == pytest.approx(0.75, abs=0.001)

    def test_a1_multiple_empirical_fails(self):
        """A.1: 3 Empirical fails → score = 0.0."""
        findings = [
            _f("STATISTICS_COUNT_LOW", "Empirical", "fail"),
            _f("EXTERNAL_CITATIONS_LOW", "Empirical", "fail"),
            _f("QUOTATIONS_MISSING", "Empirical", "fail"),
        ]
        assert compute_score_from_findings(findings) == 0.0


# ---------------------------------------------------------------------------
# A.2 — GEO_CHECKS inventory completeness
# ---------------------------------------------------------------------------

EXPECTED_CODES = {
    # Empirical
    "STATISTICS_COUNT_LOW",
    "EXTERNAL_CITATIONS_LOW",
    "QUOTATIONS_MISSING",
    "ORPHAN_CLAIM_TECHNICAL",
    "QUERY_MATCH_SCORE",
    # Mechanistic
    "RAW_HTML_JS_DEPENDENT",
    "JS_RENDERED_CONTENT_DIFFERS",
    "CONTENT_CLOAKING_DETECTED",
    "UA_CONTENT_DIFFERS",
    "FIRST_VIEWPORT_NO_ANSWER",
    "AUTHOR_BYLINE_MISSING",
    "DATE_PUBLISHED_MISSING",
    "DATE_MODIFIED_MISSING",
    "CODE_BLOCK_MISSING_TECHNICAL",
    "COMPARISON_TABLE_MISSING",
    "CHUNKS_NOT_SELF_CONTAINED",
    "CENTRAL_CLAIM_BURIED",
    "LINK_PROFILE_PROMOTIONAL",
    "STRUCTURED_ELEMENTS_LOW",
    # Conventional
    "JSON_LD_INVALID",
    "FAQ_SCHEMA_MISSING",
    "PROMOTIONAL_CONTENT_INTERRUPTS",
}


class TestGeoChecksInventory:
    def test_a2_all_codes_present(self):
        """A.2: GEO_CHECKS contains all 22 expected codes."""
        actual_codes = {c["code"] for c in GEO_CHECKS}
        missing = EXPECTED_CODES - actual_codes
        assert not missing, f"Missing codes: {missing}"

    def test_a2_no_extra_codes(self):
        """A.2: no undocumented codes in GEO_CHECKS."""
        actual_codes = {c["code"] for c in GEO_CHECKS}
        extra = actual_codes - EXPECTED_CODES
        assert not extra, f"Undocumented codes: {extra}"

    def test_a2_tier_weights_match(self):
        """A.2: every check's tier_weight matches TIER_WEIGHTS[tier]."""
        for check in GEO_CHECKS:
            expected = TIER_WEIGHTS[check["tier"]]
            assert check["tier_weight"] == expected, (
                f"{check['code']}: tier_weight={check['tier_weight']} "
                f"but TIER_WEIGHTS[{check['tier']}]={expected}"
            )

    def test_a2_required_fields_present(self):
        """A.2: every check has all required fields."""
        required = {
            "code", "label", "tier", "tier_weight", "source",
            "pass_condition", "threshold_description", "page_type_conditions",
            "fix_effort", "can_fix_without_fabrication",
            "rubric_instruction", "weak_check_note",
        }
        for check in GEO_CHECKS:
            missing = required - set(check.keys())
            assert not missing, f"{check['code']} missing fields: {missing}"

    def test_a2_empirical_checks_are_weight_3(self):
        """A.2: all Empirical checks have weight 3."""
        for check in GEO_CHECKS:
            if check["tier"] == "Empirical":
                assert check["tier_weight"] == 3, f"{check['code']} should be weight 3"

    def test_a2_source_values_valid(self):
        """A.2: source is 'static' or 'llm' for every check."""
        for check in GEO_CHECKS:
            assert check["source"] in ("static", "llm"), (
                f"{check['code']} has invalid source: {check['source']}"
            )


# ---------------------------------------------------------------------------
# B.1 — compute_90_path identifies mandatory checks correctly
# ---------------------------------------------------------------------------

class TestCompute90Path:
    def test_b1_single_fail_is_mandatory(self):
        """B.1: a single fail check (s_c=0.0) is always mandatory (0.0 < 0.90)."""
        findings = [_f("STATISTICS_COUNT_LOW", "Empirical", "fail")]
        result = compute_90_path(findings)
        assert len(result["mandatory"]) == 1
        assert result["mandatory"][0]["code"] == "STATISTICS_COUNT_LOW"
        assert len(result["high_value"]) == 0

    def test_b1_query_match_pass_high_score_not_mandatory(self):
        """B.1: QUERY_MATCH_SCORE pass=0.95 is NOT mandatory (s_c=0.95 >= 0.90)."""
        findings = [_f("QUERY_MATCH_SCORE", "Empirical", "pass", score=0.95)]
        result = compute_90_path(findings)
        assert len(result["mandatory"]) == 0
        # score_if_fixed = 1.0 (no findings), current_score = 0.95
        # gain = 1.0 - 0.95 = 0.05 -> exactly high_value threshold
        assert len(result["high_value"]) == 1

    def test_b1_query_match_pass_low_score_is_mandatory(self):
        """B.1: QUERY_MATCH_SCORE pass=0.80 is mandatory (0.80 < 0.90)."""
        findings = [_f("QUERY_MATCH_SCORE", "Empirical", "pass", score=0.80)]
        result = compute_90_path(findings)
        assert len(result["mandatory"]) == 1
        assert result["mandatory"][0]["code"] == "QUERY_MATCH_SCORE"

    def test_b1_current_score_correct(self):
        """B.1: current_score in result matches compute_score_from_findings."""
        findings = [
            _f("QUERY_MATCH_SCORE", "Empirical", "pass", score=0.85),
            _f("JSON_LD_INVALID", "Conventional", "fail"),
        ]
        result = compute_90_path(findings)
        expected = compute_score_from_findings(findings)
        assert result["current_score"] == pytest.approx(expected, abs=0.001)

    def test_b1_gain_is_additive(self):
        """B.1: gain for a finding = score_if_fixed - current_score."""
        findings = [
            _f("QUERY_MATCH_SCORE", "Empirical", "pass", score=0.85),
            _f("JSON_LD_INVALID", "Conventional", "fail"),
        ]
        result = compute_90_path(findings)
        current = result["current_score"]
        for bucket in ("mandatory", "high_value", "low_value"):
            for entry in result[bucket]:
                assert entry["gain"] == pytest.approx(
                    entry["score_if_fixed"] - current, abs=0.001
                ), f"{entry['code']}: gain mismatch"

    def test_b1_empty_findings(self):
        """B.1: empty findings → all buckets empty, current_score=1.0."""
        result = compute_90_path([])
        assert result["current_score"] == 1.0
        assert result["mandatory"] == []
        assert result["high_value"] == []
        assert result["low_value"] == []

    def test_b1_multiple_fails_all_mandatory(self):
        """B.1: multiple static fail checks → all mandatory (each has s_c=0.0)."""
        findings = [
            _f("STATISTICS_COUNT_LOW", "Empirical", "fail"),
            _f("EXTERNAL_CITATIONS_LOW", "Empirical", "fail"),
            _f("FIRST_VIEWPORT_NO_ANSWER", "Mechanistic", "fail"),
        ]
        result = compute_90_path(findings)
        assert len(result["mandatory"]) == 3


# ---------------------------------------------------------------------------
# B.2 — mandatory checks that require fabrication are flagged
# ---------------------------------------------------------------------------

class TestFabricationFlags:
    def test_b2_infeasible_checks_flagged(self):
        """B.2: JS-dependent checks should not be can_fix_without_fabrication=True."""
        infeasible_codes = {
            "RAW_HTML_JS_DEPENDENT",
            "JS_RENDERED_CONTENT_DIFFERS",
            "CONTENT_CLOAKING_DETECTED",
            "UA_CONTENT_DIFFERS",
        }
        for check in GEO_CHECKS:
            if check["code"] in infeasible_codes:
                assert not check["can_fix_without_fabrication"], (
                    f"{check['code']} requires engineering changes, "
                    "should be can_fix_without_fabrication=False"
                )

    def test_b2_content_fixable_checks(self):
        """B.2: purely content-fixable checks should be can_fix_without_fabrication=True."""
        content_fixable = {
            "FIRST_VIEWPORT_NO_ANSWER",
            "COMPARISON_TABLE_MISSING",
            "CHUNKS_NOT_SELF_CONTAINED",
            "CENTRAL_CLAIM_BURIED",
            "STRUCTURED_ELEMENTS_LOW",
            "QUERY_MATCH_SCORE",
            "PROMOTIONAL_CONTENT_INTERRUPTS",
        }
        for check in GEO_CHECKS:
            if check["code"] in content_fixable:
                assert check["can_fix_without_fabrication"], (
                    f"{check['code']} should be content-fixable without fabrication"
                )

    def test_b2_compute_90_path_includes_fabrication_flag(self):
        """B.2: each entry in compute_90_path result has can_fix_without_fabrication."""
        findings = [
            _f("STATISTICS_COUNT_LOW", "Empirical", "fail"),
            _f("FIRST_VIEWPORT_NO_ANSWER", "Mechanistic", "fail"),
        ]
        result = compute_90_path(findings)
        all_entries = (
            result["mandatory"] + result["high_value"] + result["low_value"]
        )
        for entry in all_entries:
            assert "can_fix_without_fabrication" in entry, (
                f"Entry {entry.get('code')} missing can_fix_without_fabrication"
            )

    def test_b2_weak_check_codes_flagged_in_path(self):
        """B.2: weak checks are flagged as is_weak_check=True in path output."""
        weak_code = next(iter(WEAK_CHECK_CODES))  # pick any weak check
        findings = [_f(weak_code, "Empirical", "fail")]
        result = compute_90_path(findings)
        all_entries = (
            result["mandatory"] + result["high_value"] + result["low_value"]
        )
        if all_entries:
            assert all_entries[0]["is_weak_check"] is True
