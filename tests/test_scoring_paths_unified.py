"""R5.0 — the three health-score paths must agree.

Historically three code paths computed page health differently:
  - the canonical capped+suppressed model in ``compute_impact_health``
    (``api/services/job_store_base.py``),
  - the summary/refresh endpoint (``api/routers/crawl.py`` — a RAW uncapped sum),
  - the citations endpoint (``api/routers/citations.py`` — a RAW uncapped sum).

A raw sum ignores the per-category cap AND cluster suppression, so a page that
trips both would score differently depending on which endpoint you asked. This
test builds exactly such a page and asserts all three paths produce the SAME
score — and that the score reflects cap+suppression, not the raw sum.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.0
"""

from __future__ import annotations

from api.crawler.checkers.registry import _CATALOGUE, _ISSUE_SCORING
from api.services.job_store_base import (
    _CATEGORY_IMPACT_CAP,
    compute_impact_health,
    compute_page_health,
)


def _imp(code: str) -> int:
    return _ISSUE_SCORING[code][0]


def _row(code: str) -> tuple[str, int, str]:
    return (code, _imp(code), _CATALOGUE[code].category)


def _build_fixture_rows() -> list[tuple[str, int, str]]:
    """One page that trips BOTH the category cap AND a suppression cluster.

    - A suppression cluster: SCHEMA_MISSING (parent) + JSON_LD_MISSING +
      SCHEMA_ORG_MISSING (children → contribute 0).
    - The category cap: many META_DESC_DUPLICATE rows summing over the cap.
    """
    rows: list[tuple[str, int, str]] = [
        _row("SCHEMA_MISSING"),
        _row("JSON_LD_MISSING"),
        _row("SCHEMA_ORG_MISSING"),
    ]
    rows += [_row("META_DESC_DUPLICATE") for _ in range(15)]
    return rows


def test_all_health_paths_agree():
    rows = _build_fixture_rows()

    # Precondition: raw sum is strictly larger than the capped+suppressed score,
    # so a raw-sum path would visibly diverge.
    raw_sum = sum(i for _, i, _ in rows)
    raw_score = max(0, 100 - raw_sum)

    # 1) canonical site model on a single page
    canonical_site, _ = compute_impact_health(["https://x/p"], {"https://x/p": rows}, {"critical": 0, "warning": 0, "info": 0})

    # 2) the shared single-page helper both secondary sites now use
    page_score = compute_page_health(rows)

    assert canonical_site == page_score

    # And it reflects cap+suppression, not a raw sum:
    # schema cluster charged once (SCHEMA_MISSING), metadata capped at the cap.
    expected = 100 - _imp("SCHEMA_MISSING") - _CATEGORY_IMPACT_CAP
    assert page_score == expected
    assert page_score > raw_score  # the raw sum would have scored lower


def test_secondary_sites_use_shared_helper():
    """crawl.py and citations.py must import/derive from the canonical helper,
    not recompute a raw ``100 - sum``.  A grep-style guard against regression."""
    import inspect

    from api.routers import citations, crawl

    crawl_src = inspect.getsource(crawl)
    cite_src = inspect.getsource(citations)
    assert "compute_page_health" in crawl_src
    assert "compute_page_health" in cite_src
