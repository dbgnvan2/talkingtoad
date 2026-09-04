"""P5.4 — the prevalence table and the issue lists must name the same codes.

`compute_prevalence` was handed `(issue_code, page_url)` pairs and nothing else,
so the stored `impact` and `severity` were discarded at the boundary and every
downstream property was re-derived from TODAY's catalogue — while the lists, the
counts and the health score use the value stored at crawl time.

Measured before the fix:

    IMG_ALT_MISSING stored impact 3, job at info_detail="key"
      before recalibration        list=True   prevalence=True
      after  recalibration 3 -> 2 list=True   prevalence=False

    META_DESC_MISSING stored impact 2, recalibrated to 3
      list=False  prevalence=True     <- names a code no list contains

    SCHEMA_MISSING (deleted from the catalogue in the §7 merge; 1025 rows live)
      in issue list=True  in prevalence=False
      counted in by_severity  health_score 95, not 100

The third is not a latent hazard: a deleted code is a recalibration to impact
"none", and 4,559 rows across six deleted codes sit in the live database whose
findings the health score charges and prevalence drops without a word.

The decision this item makes (spec §2): the STORED value wins. Every other
surface reads it, and `scoring_model_version` / `ISSUE_EMISSION_VERSION` exist
precisely so an old job is not restated under today's rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage

BASE = "https://example.com"
# Deleted in the §7 merge; still 1,025 rows in the live database.
DELETED_CODE = "SCHEMA_MISSING"


async def _job(store, *, job_id="j1", info_detail="key", rows):
    """`rows` is (code, category, severity, impact, n_pages)."""
    await store.create_job(CrawlJob(
        job_id=job_id, target_url=BASE, status="complete", pages_crawled=10,
        settings=CrawlSettings(info_detail=info_detail),
        started_at=datetime.now(timezone.utc)))
    await store.save_pages([
        CrawledPage(job_id=job_id, url=f"{BASE}/p{i}", status_code=200, title=f"p{i}",
                    crawled_at=datetime.now(timezone.utc))
        for i in range(10)
    ])
    await store.save_issues([
        Issue(job_id=job_id, page_url=f"{BASE}/p{i}", category=cat, severity=sev,
              issue_code=code, description="d", recommendation="r", impact=imp)
        for code, cat, sev, imp, n in rows for i in range(n)
    ])


async def _codes_in_list(api_client, auth_headers, job_id="j1") -> set[str]:
    r = await api_client.get(f"/api/crawl/{job_id}/results?limit=100", headers=auth_headers)
    assert r.status_code == 200, r.text
    return {i["issue_code"] for i in r.json()["issues"]}


async def _prevalence_rows(store, job_id="j1"):
    from api.routers.crawl import _prevalence_for_display
    job = await store.get_job(job_id)
    return await _prevalence_for_display(store, job, job_id)


async def _codes_in_prevalence(store, job_id="j1") -> set[str]:
    return {r.code for r in await _prevalence_rows(store, job_id)}


# ---------------------------------------------------------------------------
# 4.1 / 4.2 — a simulated recalibration, in both directions
# ---------------------------------------------------------------------------


class TestRecalibrationCannotSplitTheTwoTables:
    async def test_prevalence_survives_a_recalibration_downward(
        self, api_client, auth_headers, test_store
    ):
        """4.1 — stored 3 (kept at `key`), catalogue recalibrated to 2.

        The list keeps the code because the row says 3. Prevalence dropped it
        because `derive_impact` now says 2. Same job, same code, two tables.
        """
        from api.crawler.checkers.registry import _IMPACT_OVERRIDES

        await _job(test_store, rows=[("IMG_ALT_MISSING", "image", "info", 3, 6)])
        with patch.dict(_IMPACT_OVERRIDES, {"IMG_ALT_MISSING": 2}):
            in_list = "IMG_ALT_MISSING" in await _codes_in_list(api_client, auth_headers)
            in_prev = "IMG_ALT_MISSING" in await _codes_in_prevalence(test_store)
        assert in_list is True, "the list should still show it — the row says impact 3"
        assert in_prev is True, (
            "prevalence dropped a code the list still shows, because it re-derived "
            "the impact from today's catalogue instead of reading the row"
        )

    async def test_prevalence_does_not_name_a_code_no_list_contains(
        self, api_client, auth_headers, test_store
    ):
        """4.2 — the other direction, and the worse one.

        Stored 2 is below the `key` floor, so the code is in no list. Recalibrated
        to 3, prevalence started naming it — which `_prevalence_for_display`'s own
        docstring calls "the quick win you cannot find", the thing it exists to
        prevent.
        """
        from api.crawler.checkers.registry import _IMPACT_OVERRIDES

        await _job(test_store, rows=[("META_DESC_MISSING", "metadata", "info", 2, 6)])
        with patch.dict(_IMPACT_OVERRIDES, {"META_DESC_MISSING": 3}):
            in_list = "META_DESC_MISSING" in await _codes_in_list(api_client, auth_headers)
            in_prev = "META_DESC_MISSING" in await _codes_in_prevalence(test_store)
        assert in_list is False, "stored impact 2 is below the `key` floor"
        assert in_prev is False, (
            "prevalence named a code that appears in no list on this job"
        )

    @pytest.mark.parametrize("level", ["all", "notable", "key", "none"])
    @pytest.mark.parametrize("stored_impact", [0, 1, 2, 3, 5])
    async def test_prevalence_and_the_list_agree_across_the_whole_impact_grid(
        self, api_client, auth_headers, test_store, level, stored_impact
    ):
        """4.3 — the test that matters, written per LEARNINGS item 13.

        For every (stored impact x level) pair it reads BOTH live surfaces and
        asserts they name the same code. Recomputing `info_row_excluded` on each
        side would agree with itself forever — which is how this shipped. The
        catalogue is recalibrated away from the stored value throughout, so a
        surface that re-derives cannot accidentally match.
        """
        from api.crawler.checkers.registry import _IMPACT_OVERRIDES

        code, sev = "IMG_ALT_MISSING", ("info" if stored_impact < 4 else "warning")
        await _job(test_store, info_detail=level,
                   rows=[(code, "image", sev, stored_impact, 6)])
        # Recalibrate to the far end of the band so re-deriving gives a different
        # answer at every level it can.
        recal = 0 if stored_impact >= 3 else 5
        with patch.dict(_IMPACT_OVERRIDES, {code: recal}):
            in_list = code in await _codes_in_list(api_client, auth_headers)
            in_prev = code in await _codes_in_prevalence(test_store)
        assert in_list == in_prev, (
            f"stored={stored_impact} level={level!r} recalibrated={recal}: "
            f"list={in_list} prevalence={in_prev}"
        )


# ---------------------------------------------------------------------------
# 4.4 / 4.5 — a code today's catalogue has forgotten
# ---------------------------------------------------------------------------


class TestCodesTheCatalogueForgot:
    async def test_a_code_deleted_from_the_catalogue_still_appears_in_prevalence(
        self, api_client, auth_headers, test_store
    ):
        """4.4 — the live case: 4,559 rows across six §7-deleted codes.

        Their rows are listed, counted in by_severity, and charge the health
        score. Prevalence dropped them on `_CATALOGUE.get(code) is None`.
        """
        from api.crawler.checkers.registry import _CATALOGUE

        assert DELETED_CODE not in _CATALOGUE, (
            f"{DELETED_CODE} is back in the catalogue — pick another deleted code"
        )
        await _job(test_store, info_detail="all",
                   rows=[(DELETED_CODE, "metadata", "info", 5, 6)])

        assert DELETED_CODE in await _codes_in_list(api_client, auth_headers)
        summary = await test_store.get_summary("j1")
        assert summary["health_score"] < 100, "premise: these rows charge the score"
        assert DELETED_CODE in await _codes_in_prevalence(test_store), (
            "prevalence dropped a code whose findings the health score charged"
        )

    async def test_deleted_code_prevalence_row_uses_the_stored_severity(
        self, api_client, auth_headers, test_store
    ):
        """4.5 — guards the plausible wrong fix for 4.4.

        Keeping unknown codes but labelling them
        `severity_from_impact(stored_impact)` looks equivalent and is not: it is
        the derived value again, one step removed. Here the stored row says
        `info` at impact 5, which `severity_from_impact` would call `warning` —
        a combination a live crawl would not emit, chosen precisely so the two
        answers differ.
        """
        from api.crawler.checkers.registry import severity_from_impact

        await _job(test_store, info_detail="all",
                   rows=[(DELETED_CODE, "metadata", "info", 5, 6)])
        row = next(r for r in await _prevalence_rows(test_store) if r.code == DELETED_CODE)
        assert severity_from_impact(5) == "warning", "premise of this test"
        assert row.severity == "info", (
            f"the row was labelled {row.severity!r} — derived from the impact "
            "rather than read from the stored finding"
        )
        assert row.impact == 5

    async def test_a_KNOWN_code_also_uses_the_stored_severity(
        self, api_client, auth_headers, test_store
    ):
        """4.5c — found by mutation, not by review.

        4.5 covers a code the catalogue has forgotten, so it only exercises the
        `else` branch. `severity=spec.severity if spec else severity` — keeping
        the catalogue for known codes, which is the obvious partial fix — passed
        every other test in this file. A known code whose stored severity differs
        from the catalogue's is the case that separates them, and it is the whole
        point of P5.4: after a recalibration across the 3/4 boundary that is
        exactly what an old job holds.
        """
        from api.crawler.checkers.registry import _CATALOGUE

        assert _CATALOGUE["IMG_ALT_MISSING"].severity == "info", "premise"
        await _job(test_store, info_detail="all",
                   rows=[("IMG_ALT_MISSING", "image", "warning", 5, 6)])
        row = next(r for r in await _prevalence_rows(test_store)
                   if r.code == "IMG_ALT_MISSING")
        assert row.severity == "warning", (
            f"the row was labelled {row.severity!r} — taken from today's catalogue "
            "rather than from the finding that was stored"
        )
        assert row.impact == 5

    async def test_a_forgotten_code_keeps_its_stored_category(
        self, api_client, auth_headers, test_store
    ):
        """4.5b — the catalogue cannot supply a category it does not have, so the
        stored one is the only honest source."""
        await _job(test_store, info_detail="all",
                   rows=[(DELETED_CODE, "metadata", "info", 5, 6)])
        row = next(r for r in await _prevalence_rows(test_store) if r.code == DELETED_CODE)
        assert row.category == "metadata"
        assert DELETED_CODE in row.human_description, (
            "with no catalogue entry the code itself is the only description"
        )


# ---------------------------------------------------------------------------
# 4.6 / 4.7 — mixed stored impacts, and what still comes from the catalogue
# ---------------------------------------------------------------------------


class TestMixedAndDescriptive:
    @pytest.mark.parametrize("order", ["low_first", "high_first"])
    async def test_mixed_stored_impacts_take_the_maximum(
        self, api_client, auth_headers, test_store, order
    ):
        """4.6 — a rescan under a new model can leave one job holding two
        impacts for one code.

        Both orders are seeded, so an implementation that takes "the last row
        seen" fails on one of them. The maximum is chosen because prevalence
        escalates: it must never demote a code below a value some row in the job
        actually carries.
        """
        impacts = [1, 3] if order == "low_first" else [3, 1]
        await _job(test_store, info_detail="all", rows=[])
        await test_store.save_issues([
            Issue(job_id="j1", page_url=f"{BASE}/p{i}", category="image",
                  severity="info", issue_code="IMG_ALT_MISSING", description="d",
                  recommendation="r", impact=impacts[i % 2])
            for i in range(6)
        ])
        row = next(r for r in await _prevalence_rows(test_store)
                   if r.code == "IMG_ALT_MISSING")
        assert row.impact == 3, f"{order}: took {row.impact}, not the maximum"

    async def test_catalogue_still_supplies_the_description_and_category(
        self, api_client, auth_headers, test_store
    ):
        """4.7 — the split, asserted so it cannot be inverted.

        Impact and severity are judgements and come from the row; description and
        category are labels and come from the catalogue, which is where an
        improved wording should reach an old report.
        """
        from api.crawler.checkers.registry import _CATALOGUE

        await _job(test_store, info_detail="all",
                   rows=[("IMG_ALT_MISSING", "heading", "info", 3, 6)])  # NOT its catalogue category (image)
        row = next(r for r in await _prevalence_rows(test_store)
                   if r.code == "IMG_ALT_MISSING")
        spec = _CATALOGUE["IMG_ALT_MISSING"]
        assert row.human_description == (spec.human_description or "IMG_ALT_MISSING")
        assert row.category == spec.category, (
            "a known code takes its category from the catalogue, not the row"
        )
