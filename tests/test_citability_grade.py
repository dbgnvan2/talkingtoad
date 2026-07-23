"""E5 — per-page GEO/citability grade (rollup of ai_readiness issues).

Search Everywhere P3. A dedicated 0–100 lens on AI-extractability, derived from
already-emitted ai_readiness issues (no new detection).
"""

from api.services.job_store_base import compute_citability_grade, compute_page_health


def test_e5_1_only_ai_readiness_counts():
    """A metadata/security issue must not move the citability grade — only
    ai_readiness issues do."""
    rows = [
        ("META_DESC_MISSING", 6, "metadata"),
        ("GEO_SUMMARY_BURIED", 2, "ai_readiness"),
    ]
    assert compute_citability_grade(rows) == 100 - 2
    # overall health, by contrast, counts both.
    assert compute_page_health(rows) < 100 - 2


def test_e5_1_monotonic():
    """More ai_readiness issues ⇒ a not-higher grade (monotonicity, P7)."""
    base = [("GEO_SUMMARY_BURIED", 2, "ai_readiness")]
    worse = base + [("CONTENT_THIN", 4, "ai_readiness")]
    assert compute_citability_grade(worse) <= compute_citability_grade(base)
    assert compute_citability_grade(worse) == 100 - (2 + 4)


def test_e5_no_ai_issues_is_100():
    assert compute_citability_grade([("HTTP_PAGE", 6, "security")]) == 100
    assert compute_citability_grade([]) == 100


def test_e5_suppression_not_double_counted():
    """A suppressed child (its cluster parent is present) must not deduct from
    the grade — the rollup reuses the same suppression the health score uses."""
    # RAW_HTML_JS_DEPENDENT suppresses SEMANTIC_DENSITY_LOW (§6.1). With both
    # present, only the parent should count.
    rows = [
        ("RAW_HTML_JS_DEPENDENT", 4, "ai_readiness"),
        ("SEMANTIC_DENSITY_LOW", 1, "ai_readiness"),
    ]
    parent_only = [("RAW_HTML_JS_DEPENDENT", 4, "ai_readiness")]
    assert compute_citability_grade(rows) == compute_citability_grade(parent_only)


def test_e5_floors_at_zero():
    rows = [(f"CODE{i}", 20, "ai_readiness") for i in range(10)]
    assert compute_citability_grade(rows) == 0
