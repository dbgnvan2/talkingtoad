"""R5.4 — Quick Wins finish (external spec §4).

A "quick win" is an issue that is worthwhile AND cheap to fix:
``impact >= 4 AND effort <= 1``. The predicate already lives as a computed
field on both the Pydantic ``Issue`` model and the engine ``Issue`` dataclass;
R5.4 (a) serialises it in ``_issue_dict`` (both list endpoints) and (b) exposes
a Quick-Wins list on the summary/results endpoint, independent of priority
ordering.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.4
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob


def _issue(job_id: str, code: str, impact: int, effort: int, category: str = "metadata") -> Issue:
    """Build a persisted-shape Issue with explicit impact/effort so the
    quick_win predicate (impact>=4 AND effort<=1) is exercised directly."""
    return Issue(
        job_id=job_id,
        page_url="https://example.com/",
        category=category,
        severity="warning",
        issue_code=code,
        description="d",
        recommendation="r",
        impact=impact,
        effort=effort,
    )


def test_issue_dict_includes_quick_win():
    """R5.4.1 / API-contract — both issue-list endpoints go through
    ``_issue_dict``; it must emit ``quick_win`` derived from impact/effort."""
    from api.routers.crawl import _issue_dict

    qw = _issue("j", "TITLE_MISSING", impact=5, effort=1)
    not_qw = _issue("j", "H1_MULTIPLE", impact=5, effort=3)

    qw_payload = _issue_dict(qw)
    not_qw_payload = _issue_dict(not_qw)

    assert "quick_win" in qw_payload, "_issue_dict omitted quick_win from the payload"
    assert qw_payload["quick_win"] is True
    assert not_qw_payload["quick_win"] is False


@pytest.mark.asyncio
async def test_summary_exposes_quick_wins_list(api_client, auth_headers, test_store):
    """R5.4.2 — the results/summary endpoint exposes a Quick-Wins list of exactly
    the issues satisfying impact>=4 AND effort<=1, independent of priority order.

    Adversarial coverage: a high-impact/high-effort issue and a low-impact/
    low-effort issue must BOTH be excluded — the predicate is a conjunction, not
    an OR.
    """
    job_id = str(uuid4())
    await test_store.create_job(CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
        pages_crawled=1,
    ))
    await test_store.save_issues([
        # A genuine quick win: impact>=4 AND effort<=1.
        _issue(job_id, "TITLE_MISSING", impact=5, effort=1),
        # Adversarial 1: impact>=4 but effort>=2 → NOT a quick win.
        _issue(job_id, "H1_MULTIPLE", impact=6, effort=3),
        # Adversarial 2: effort<=1 but impact<4 → NOT a quick win.
        _issue(job_id, "META_DESCRIPTION_MISSING", impact=2, effort=0),
    ])

    resp = await api_client.get(f"/api/crawl/{job_id}/results", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert "quick_wins" in body, "results payload omitted quick_wins list"
    codes = {qw["issue_code"] for qw in body["quick_wins"]}
    assert codes == {"TITLE_MISSING"}, (
        "quick_wins must contain exactly the impact>=4 AND effort<=1 issue; "
        f"got {codes}"
    )
    # Every entry in the list is genuinely a quick win.
    for qw in body["quick_wins"]:
        assert qw["quick_win"] is True
