"""R3 calibration (2026-07-03) — triangulated Model B: derived impact, derived
severity, priority formula, quick-win flag.

Spec: docs/pending/OLD/2026-07-03_r3-FINAL-calibration.md
"""

import pytest

from api.crawler.checkers.registry import (
    _CALIBRATION,
    _CATALOGUE,
    _IMPACT_MATRIX,
    _IMPACT_OVERRIDES,
    _ISSUE_SCORING,
    _MEASURED_MATRIX,
    _PAGE_FATAL_10,
    derive_impact,
    make_issue,
    severity_from_impact,
)
from api.models.issue import Issue


def test_every_code_has_calibration():
    assert set(_CALIBRATION) == set(_ISSUE_SCORING) == set(_CATALOGUE)


def test_impact_equals_derivation():
    """Every impact in _ISSUE_SCORING is reproducible from the calibration
    record via the matrix (+ measured lane / 10-tier / documented override)."""
    bad = {c: (_ISSUE_SCORING[c][0], derive_impact(c))
           for c in _ISSUE_SCORING if _ISSUE_SCORING[c][0] != derive_impact(c)}
    assert not bad, f"impact != derive_impact for: {bad}"


def test_overrides_are_real_deviations():
    """Each override actually deviates from the pure matrix (no dead overrides)."""
    for code, val in _IMPACT_OVERRIDES.items():
        conf, eff, measured = _CALIBRATION[code]
        matrix = _MEASURED_MATRIX[eff] if measured else _IMPACT_MATRIX[(conf, eff)]
        assert val != matrix or code in _PAGE_FATAL_10, f"{code} override == matrix; drop it"


def test_severity_derived_from_impact():
    bad = {c: _CATALOGUE[c].severity for c in _CATALOGUE
           if _CATALOGUE[c].severity != severity_from_impact(_ISSUE_SCORING[c][0])}
    assert not bad, f"severity != severity_from_impact for: {bad}"


@pytest.mark.parametrize("impact,expected", [(10, "critical"), (8, "critical"),
                                             (7, "warning"), (4, "warning"),
                                             (3, "info"), (0, "info")])
def test_severity_thresholds(impact, expected):
    assert severity_from_impact(impact) == expected


def test_page_fatal_10_tier():
    for code in _PAGE_FATAL_10:
        assert _ISSUE_SCORING[code][0] == 10, code
    # ROBOTS_BLOCKED is deliberately 9, NOT 10 (URL-only indexing still possible)
    assert _ISSUE_SCORING["ROBOTS_BLOCKED"][0] == 9


def test_broken_links_downweighted():
    """Regression guard: broken outbound links are not a ranking factor."""
    assert _ISSUE_SCORING["BROKEN_LINK_404"][0] <= 2
    assert _ISSUE_SCORING["BROKEN_LINK_410"][0] <= 2


def test_geo_no_text_upweighted():
    """AI fetchers can't run JS — no-text/app-shell pages are near-gating."""
    assert _ISSUE_SCORING["RAW_HTML_JS_DEPENDENT"][0] >= 8
    assert _ISSUE_SCORING["CONTENT_NOT_EXTRACTABLE_NO_TEXT"][0] >= 8


def test_measured_lane_applied():
    """Aggarwal 'measured' codes use the Heuristic-measured row, not plain Heuristic."""
    conf, eff, measured = _CALIBRATION["STATISTICS_COUNT_LOW"]
    assert measured is True
    assert derive_impact("STATISTICS_COUNT_LOW") == _MEASURED_MATRIX[eff]


def test_priority_rank_formula():
    issue = make_issue("TITLE_MISSING", "https://x/")
    assert issue.priority_rank == issue.impact * 10 - issue.effort * 6


def test_quick_win_computed():
    base = dict(job_id="j", category="metadata", severity="warning",
                issue_code="X", description="d", recommendation="r")
    assert Issue(**base, impact=6, effort=1).quick_win is True
    assert Issue(**base, impact=4, effort=1).quick_win is True
    assert Issue(**base, impact=3, effort=0).quick_win is False   # impact too low
    assert Issue(**base, impact=10, effort=3).quick_win is False  # effort too high


def test_make_issue_severity_matches_impact():
    """make_issue emits the derived severity (no impact/severity drift)."""
    for code in ("NOINDEX_META", "BROKEN_LINK_404", "TITLE_MISSING", "OG_TITLE_MISSING"):
        i = make_issue(code, "https://x/")
        assert i.severity == severity_from_impact(i.impact), code
