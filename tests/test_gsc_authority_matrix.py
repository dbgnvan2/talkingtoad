"""V4 — GSC Authority-Matrix: pure quadrant/correlation logic tests.

Spec: docs/pending/2026-07-06_deploy-gate-validation.md#V4

The LIVE run (real GSC fetch) is integration-only and NOT covered here — it
needs an OAuth session (creds in api.routers.gsc._creds_cache) and is flagged as
blocked-on-connection. These tests exercise the pure correlation/quadrant math
with a synthetic fixture.
"""

from __future__ import annotations

from scripts.gsc_authority_matrix import (
    DISAGREEMENT_QUADRANTS,
    PageMetric,
    Q_HIDDEN_GEM,
    Q_STRONG,
    Q_UNDERRATED,
    Q_WEAK,
    build_authority_matrix,
    classify_quadrant,
    health_clicks_correlation,
    render_matrix_report,
)


def _fixture() -> list[PageMetric]:
    return [
        PageMetric("https://x/strong-1", health=90, clicks=500),
        PageMetric("https://x/strong-2", health=85, clicks=300),
        PageMetric("https://x/hidden-gem", health=88, clicks=5),
        PageMetric("https://x/underrated", health=40, clicks=420),
        PageMetric("https://x/weak-1", health=35, clicks=2),
        PageMetric("https://x/weak-2", health=50, clicks=10),
    ]


def test_v4_quadrant_assignment_median_split():
    """Each fixture page lands in its designed quadrant using the median split."""
    metrics = _fixture()
    # medians: health of {90,85,88,40,35,50} -> 67.5 ; clicks {500,300,5,420,2,10} -> 155
    matrix = build_authority_matrix(metrics)
    by_url = {m.url: q for q, ms in matrix.items() for m in ms}

    assert by_url["https://x/strong-1"] == Q_STRONG        # 90>67.5, 500>155
    assert by_url["https://x/strong-2"] == Q_STRONG        # 85>67.5, 300>155
    assert by_url["https://x/hidden-gem"] == Q_HIDDEN_GEM  # 88>67.5, 5<155
    assert by_url["https://x/underrated"] == Q_UNDERRATED  # 40<67.5, 420>155
    assert by_url["https://x/weak-1"] == Q_WEAK            # 35<67.5, 2<155
    assert by_url["https://x/weak-2"] == Q_WEAK            # 50<67.5, 10<155

    # Every page classified exactly once; all four keys present.
    assert set(matrix) == {Q_STRONG, Q_HIDDEN_GEM, Q_UNDERRATED, Q_WEAK}
    assert sum(len(v) for v in matrix.values()) == len(metrics)


def test_v4_disagreement_quadrants_are_the_calibration_signal():
    """The two 'disagree' quadrants isolate exactly the health/clicks mismatches."""
    metrics = _fixture()
    matrix = build_authority_matrix(metrics)
    disagree = {m.url for q in DISAGREEMENT_QUADRANTS for m in matrix[q]}
    assert disagree == {"https://x/hidden-gem", "https://x/underrated"}


def test_v4_correlation_sign():
    """Health↔clicks correlation is defined and, for a mostly-aligned fixture,
    the disagreement pages pull it below a perfect 1.0 but it stays computable."""
    corr = health_clicks_correlation(_fixture())
    assert corr is not None
    assert -1.0 <= corr <= 1.0
    # Degenerate inputs return None rather than raising.
    assert health_clicks_correlation([]) is None
    assert health_clicks_correlation([PageMetric("u", 50, 10)]) is None
    assert (
        health_clicks_correlation(
            [PageMetric("a", 50, 10), PageMetric("b", 50, 99)]
        )
        is None  # constant health series -> undefined
    )


def test_v4_classify_boundary_is_strict_greater_than():
    """A page exactly AT the split is 'low' (strict >), so a median-valued page
    is never counted as high on that axis."""
    m = PageMetric("u", health=50, clicks=100)
    assert classify_quadrant(m, health_split=50.0, clicks_split=100.0) == Q_WEAK
    assert classify_quadrant(m, health_split=49.0, clicks_split=99.0) == Q_STRONG


def test_v4_synthetic_report_renders_and_is_marked_synthetic():
    """The rendered report is honest about being synthetic (never implies live)."""
    report = render_matrix_report(
        site="https://x/", days=30, metrics=_fixture(), synthetic=True
    )
    assert "SYNTHETIC" in report
    assert "hidden-gem" in report or "healthy_but_unfound" in report
    assert "Authority-Matrix" in report
