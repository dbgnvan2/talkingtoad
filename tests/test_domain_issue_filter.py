"""Per-domain issue-code filter.

Owner request: for a specific domain, hide selected issue codes and/or every
`info`-severity finding, so the results list shows only what that site's
operator cares about.

Three decisions, the owner's:
  1. Hide from results, KEEP the data — checks still run, findings are still
     stored, the filter applies at read time and is reversible with no re-crawl.
  2. The health score does NOT change. LEARNINGS records that suppressing
     ORPHAN_PAGE *raised* the score — coverage fell and the grade improved,
     flagged there as the wrong direction. A per-domain filter is a far easier
     lever to pull, so it must not touch scoring at all.
  3. Reuse the existing suppression pattern rather than inventing a mechanism.

Deliberately a SEPARATE table from `suppressed_issue_codes`: that one feeds
compute_impact_health() and changes the score by design. One table meaning two
things depending on whether `domain` is NULL is how the two get confused, and
someone's presentational filter starts moving their grade.

Scale note: 123 of 170 catalogue codes are `info`, so the severity rule hides
about 72% of findings. That is exactly why every filtered response has to
declare what it hid.

Spec: docs/pending/2026-08-31_per-domain-issue-filter.md
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.crawler.checkers.registry import _CATALOGUE
from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.services.sqlite_store import SQLiteJobStore


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


class TestTheRulesRoundTripPerDomain:
    async def test_filter_rules_round_trip_per_domain(self, store):
        await store.add_domain_filter("example.com", issue_code="TITLE_TOO_SHORT")
        await store.add_domain_filter("example.com", severity="info")
        await store.add_domain_filter("other.org", issue_code="H1_MISSING")

        ex = await store.get_domain_filters("example.com")
        assert {r["issue_code"] for r in ex if r["issue_code"]} == {"TITLE_TOO_SHORT"}
        assert {r["severity"] for r in ex if r["severity"]} == {"info"}

        other = await store.get_domain_filters("other.org")
        assert {r["issue_code"] for r in other if r["issue_code"]} == {"H1_MISSING"}, (
            "one domain's rules leaked into another's"
        )

    async def test_removing_a_rule_leaves_the_others(self, store):
        await store.add_domain_filter("example.com", issue_code="TITLE_TOO_SHORT")
        await store.add_domain_filter("example.com", severity="info")
        await store.remove_domain_filter("example.com", issue_code="TITLE_TOO_SHORT")
        left = await store.get_domain_filters("example.com")
        assert [r["severity"] for r in left] == ["info"]

    async def test_adding_the_same_rule_twice_is_a_no_op(self, store):
        await store.add_domain_filter("example.com", severity="info")
        await store.add_domain_filter("example.com", severity="info")
        assert len(await store.get_domain_filters("example.com")) == 1


class TestDomainNormalisation:
    @pytest.mark.parametrize("given", [
        "example.com",
        "EXAMPLE.COM",
        "www.example.com",
        "https://example.com/some/path",
        "https://WWW.Example.COM:443/",
        "example.com:8000",
    ])
    async def test_domain_is_normalised_before_storage(self, store, given):
        """Two spellings of one site must not produce two rule sets that each
        look empty — the operator would set a filter and see nothing happen."""
        from api.services.domain_filter import normalise_filter_domain
        assert normalise_filter_domain(given) == "example.com"

    async def test_rules_are_found_however_the_domain_is_spelled(self, store):
        await store.add_domain_filter("https://WWW.Example.COM/", severity="info")
        assert len(await store.get_domain_filters("example.com")) == 1


class TestTheFilterHidesWhatItShould:
    def _issues(self):
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        codes = ["TITLE_TOO_SHORT", "H1_MISSING", "IMG_ALT_MISSING"]
        out = []
        for c in codes:
            i = _engine_issue_to_model(make_issue(c, "https://example.com/p"), "j1")
            i.page_url = "https://example.com/p"
            out.append(i)
        return out

    async def test_info_severity_rule_hides_every_info_finding(self, store):
        """The owner's headline case."""
        from api.services.domain_filter import apply_domain_filter
        issues = [i.model_dump() for i in self._issues()]
        rules = [{"issue_code": None, "severity": "info"}]
        kept, report = apply_domain_filter(issues, rules)
        assert all(k["severity"] != "info" for k in kept)
        assert report["hidden"] == sum(1 for i in issues if i["severity"] == "info")

    async def test_a_code_rule_hides_only_that_code(self, store):
        from api.services.domain_filter import apply_domain_filter
        issues = [i.model_dump() for i in self._issues()]
        kept, report = apply_domain_filter(
            issues, [{"issue_code": "H1_MISSING", "severity": None}])
        assert "H1_MISSING" not in {k["issue_code"] for k in kept}
        assert report["by_rule"] == {"H1_MISSING": 1}

    async def test_filtered_response_declares_what_it_hid(self, store):
        from api.services.domain_filter import apply_domain_filter
        issues = [i.model_dump() for i in self._issues()]
        kept, report = apply_domain_filter(
            issues, [{"issue_code": None, "severity": "info"}])
        assert report["hidden"] == len(issues) - len(kept)
        assert report["by_rule"], (
            "a shorter list with no account of what was removed reads as a "
            "cleaner site (P31/P24)"
        )


class TestTheFilterCannotFlatterTheSite:
    """The adversarial half. A filtered scan showing 4 issues and a health
    score of 96 is indistinguishable from a genuinely clean site.
    """

    async def test_adversarial_filtering_does_not_change_the_health_score(self, store):
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        job = CrawlJob(job_id="j1", target_url="https://example.com",
                       started_at=datetime.now(timezone.utc))
        await store.create_job(job)
        await store.save_pages([CrawledPage(
            job_id="j1", url="https://example.com/p", status_code=200,
            title="t", crawled_at=datetime.now(timezone.utc))])
        issues = []
        for c in ("TITLE_TOO_SHORT", "H1_MISSING", "IMG_ALT_MISSING"):
            i = _engine_issue_to_model(make_issue(c, "https://example.com/p"), "j1")
            i.page_url = "https://example.com/p"
            issues.append(i)
        await store.save_issues(issues)

        before = (await store.get_summary("j1"))["health_score"]
        await store.add_domain_filter("example.com", severity="info")
        after = (await store.get_summary("j1"))["health_score"]
        assert before == after, (
            f"the filter moved the health score {before} -> {after}. Hiding "
            "findings must never improve a grade."
        )

    async def test_adversarial_a_filter_never_increases_the_finding_count(self, store):
        """Monotonicity: filtering can only remove."""
        from api.services.domain_filter import apply_domain_filter
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        issues = [_engine_issue_to_model(make_issue(c, "https://example.com/p"), "j1").model_dump()
                  for c in ("TITLE_TOO_SHORT", "H1_MISSING")]
        for rules in ([], [{"issue_code": "H1_MISSING", "severity": None}],
                      [{"issue_code": None, "severity": "info"}]):
            kept, _ = apply_domain_filter(issues, rules)
            assert len(kept) <= len(issues)

    async def test_adversarial_no_rules_is_a_true_no_op(self, store):
        """A bug must not be able to hide behind 'no filter configured'."""
        from api.services.domain_filter import apply_domain_filter
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        issues = [_engine_issue_to_model(make_issue(c, "https://example.com/p"), "j1").model_dump()
                  for c in ("TITLE_TOO_SHORT", "H1_MISSING")]
        kept, report = apply_domain_filter(issues, [])
        assert kept == issues and report["hidden"] == 0

    async def test_adversarial_an_unknown_code_rule_hides_nothing(self, store):
        """A rule naming a code that does not exist must be inert, not a
        wildcard. Validation rejects these at the API, but a stale row from a
        deleted code must never start hiding real findings."""
        from api.services.domain_filter import apply_domain_filter
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        issues = [_engine_issue_to_model(make_issue("H1_MISSING", "https://example.com/p"), "j1").model_dump()]
        kept, report = apply_domain_filter(
            issues, [{"issue_code": "CODE_THAT_NEVER_EXISTED", "severity": None}])
        assert kept == issues and report["hidden"] == 0


class TestTheApiValidates:
    async def test_unknown_issue_code_is_rejected(self, store):
        from api.routers.utility import add_domain_filter, DomainFilterRequest
        resp = await add_domain_filter(
            DomainFilterRequest(domain="example.com", issue_code="NOT_A_REAL_CODE"),
            store=store)
        assert getattr(resp, "status_code", 200) == 404, (
            "an unknown code accepted silently is a filter that never fires"
        )

    async def test_unknown_severity_is_rejected(self, store):
        from api.routers.utility import add_domain_filter, DomainFilterRequest
        resp = await add_domain_filter(
            DomainFilterRequest(domain="example.com", severity="catastrophic"),
            store=store)
        assert getattr(resp, "status_code", 200) == 422

    async def test_a_rule_must_name_exactly_one_of_code_or_severity(self, store):
        from api.routers.utility import add_domain_filter, DomainFilterRequest
        for kw in ({}, {"issue_code": "H1_MISSING", "severity": "info"}):
            resp = await add_domain_filter(
                DomainFilterRequest(domain="example.com", **kw), store=store)
            assert getattr(resp, "status_code", 200) == 422, (
                f"a rule with {kw or 'neither field'} should be refused"
            )

    async def test_every_catalogue_severity_is_accepted(self, store):
        """Guards the guard: if the severity allowlist drifted from the
        catalogue, valid rules would be refused and the test above would still
        pass."""
        from api.routers.utility import add_domain_filter, DomainFilterRequest
        for sev in {s.severity for s in _CATALOGUE.values()}:
            resp = await add_domain_filter(
                DomainFilterRequest(domain="example.com", severity=sev), store=store)
            assert getattr(resp, "status_code", 200) == 200, f"{sev} was refused"


class TestTheEndpointsTheFrontendCalls:
    """API contract, written before the frontend reads any of these fields
    (CLAUDE.md's non-negotiable rule).
    """

    async def _job_with_issues(self, store):
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        job = CrawlJob(job_id="j1", target_url="https://example.com",
                       started_at=datetime.now(timezone.utc))
        await store.create_job(job)
        await store.save_pages([CrawledPage(
            job_id="j1", url="https://example.com/p", status_code=200,
            title="t", crawled_at=datetime.now(timezone.utc))])
        issues = []
        for c in ("TITLE_TOO_SHORT", "H1_MISSING", "IMG_ALT_MISSING"):
            i = _engine_issue_to_model(make_issue(c, "https://example.com/p"), "j1")
            i.page_url = "https://example.com/p"
            issues.append(i)
        await store.save_issues(issues)
        return {i.issue_code for i in issues}

    async def test_results_endpoint_always_carries_the_filtered_block(self, store):
        """Present even with no rules — the frontend can render the control
        without having to handle an absent key."""
        from api.routers.crawl import get_results
        await self._job_with_issues(store)
        resp = await get_results(job_id="j1", page=1, limit=50, severity=None, store=store)
        assert "filtered" in resp
        assert resp["filtered"]["hidden"] == 0
        assert resp["filtered"]["domain"] == "example.com"

    async def test_results_endpoint_hides_and_declares(self, store):
        from api.routers.crawl import get_results
        seeded = await self._job_with_issues(store)
        await store.add_domain_filter("https://example.com", issue_code="H1_MISSING")
        resp = await get_results(job_id="j1", page=1, limit=50, severity=None, store=store)
        shown = {i["issue_code"] for i in resp["issues"]}
        assert "H1_MISSING" not in shown
        assert resp["filtered"]["hidden"] == 1
        assert resp["filtered"]["by_rule"] == {"H1_MISSING": 1}
        # and the finding is still in the store — the filter is presentational
        all_issues = await store.get_all_issues("j1")
        assert "H1_MISSING" in {i.issue_code for i in all_issues}, (
            "the filter deleted data; it is supposed to hide it"
        )

    async def test_adversarial_the_summary_score_is_untouched_by_the_endpoint(self, store):
        """The endpoint returns both a filtered list and a summary. They must
        disagree: fewer rows, same score. If they ever agree, hiding findings
        has started improving the grade."""
        from api.routers.crawl import get_results
        await self._job_with_issues(store)
        before = (await get_results(job_id="j1", page=1, limit=50, severity=None, store=store))["summary"]["health_score"]
        await store.add_domain_filter("example.com", severity="info")
        after_resp = await get_results(job_id="j1", page=1, limit=50, severity=None, store=store)
        assert after_resp["summary"]["health_score"] == before
        assert after_resp["filtered"]["hidden"] > 0, (
            "the fixture stopped exercising the filter — this test would then "
            "pass without comparing anything"
        )


class TestTheHttpContract:
    """Over the real path, not by calling the function. Covers auth/validation
    at the HTTP boundary and satisfies the endpoint-coverage guard, which
    exists precisely so a new endpoint cannot ship reachable-but-unexercised.
    """

    async def test_domain_filters_round_trip_over_http(self, api_client, auth_headers):
        add = await api_client.post(
            "/api/domain-filters",
            json={"domain": "https://Example.COM/x", "issue_code": "H1_MISSING"},
            headers=auth_headers)
        assert add.status_code == 200, add.text
        assert add.json()["domain"] == "example.com", "the domain was not normalised"

        listed = await api_client.get("/api/domain-filters?domain=example.com", headers=auth_headers)
        assert listed.status_code == 200
        assert listed.json()["rules"] == [{"issue_code": "H1_MISSING", "severity": None}]

        gone = await api_client.delete(
            "/api/domain-filters?domain=example.com&issue_code=H1_MISSING",
            headers=auth_headers)
        assert gone.status_code == 200
        assert (await api_client.get("/api/domain-filters?domain=example.com",
                                     headers=auth_headers)).json()["rules"] == []

    async def test_domain_filters_rejects_an_unknown_code_over_http(self, api_client, auth_headers):
        resp = await api_client.post(
            "/api/domain-filters",
            json={"domain": "example.com", "issue_code": "NOT_A_REAL_CODE"},
            headers=auth_headers)
        assert resp.status_code == 404

    async def test_domain_filters_rejects_a_rule_naming_both_or_neither(self, api_client, auth_headers):
        for payload in ({"domain": "example.com"},
                        {"domain": "example.com", "issue_code": "H1_MISSING",
                         "severity": "info"}):
            resp = await api_client.post("/api/domain-filters", json=payload,
                                         headers=auth_headers)
            assert resp.status_code == 422, f"{payload} should be refused"

    async def test_domain_filters_requires_auth(self, api_client):
        """CLAUDE.md: every /api/* utility route is behind require_auth. Pinned
        explicitly rather than discovered by a 401 in another test."""
        for call in (
            api_client.get("/api/domain-filters?domain=example.com"),
            api_client.post("/api/domain-filters",
                            json={"domain": "example.com", "severity": "info"}),
            api_client.delete("/api/domain-filters?domain=example.com&severity=info"),
        ):
            assert (await call).status_code == 401


class TestTheExportsMatchTheScreen:
    """Owner: "I want the ability to send a report of what shows on the screen
    — not something different."

    So the exports apply the same filter as the results list. They also STATE
    that they are a filtered view: that is not different content, it is
    provenance. A PDF is the artefact that leaves the building — the reader who
    opens it is usually not the operator who set the filter, and a report that
    silently omits 72% of findings while looking complete is the one failure
    mode worth guarding here.
    """

    async def _job(self, store):
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model
        job = CrawlJob(job_id="j1", target_url="https://example.com",
                       started_at=datetime.now(timezone.utc))
        await store.create_job(job)
        await store.save_pages([CrawledPage(
            job_id="j1", url="https://example.com/p", status_code=200,
            title="t", crawled_at=datetime.now(timezone.utc))])
        issues = []
        for c in ("TITLE_TOO_SHORT", "H1_MISSING", "IMG_ALT_MISSING"):
            i = _engine_issue_to_model(make_issue(c, "https://example.com/p"), "j1")
            i.page_url = "https://example.com/p"
            issues.append(i)
        await store.save_issues(issues)
        return issues

    async def test_model_filter_and_dict_filter_agree(self, store):
        """One rule engine, two callers. If these ever disagree, the screen and
        the report are describing different sites — which is the whole class
        this codebase has been fighting."""
        from api.services.domain_filter import apply_domain_filter, filter_issue_models
        issues = await self._job(store)
        rules = [{"issue_code": None, "severity": "info"}]
        kept_models, rep_m = filter_issue_models(issues, rules)
        kept_dicts, rep_d = apply_domain_filter([i.model_dump() for i in issues], rules)
        assert {i.issue_code for i in kept_models} == {d["issue_code"] for d in kept_dicts}
        assert rep_m == rep_d

    async def test_csv_export_reflects_the_filter(self, test_store, auth_headers, api_client):
        await self._job(test_store)
        await test_store.add_domain_filter("example.com", issue_code="H1_MISSING")
        r = await api_client.get("/api/crawl/j1/export/csv", headers=auth_headers)
        assert r.status_code == 200
        assert "H1_MISSING" not in r.text, "the CSV shows a finding the screen hides"
        assert "TITLE_TOO_SHORT" in r.text, "the CSV lost findings the screen shows"

    async def test_excel_export_reflects_the_filter(self, test_store, auth_headers, api_client):
        await self._job(test_store)
        await test_store.add_domain_filter("example.com", issue_code="H1_MISSING")
        r = await api_client.get("/api/crawl/j1/export/excel", headers=auth_headers)
        assert r.status_code == 200 and len(r.content) > 0

    async def test_the_report_says_it_is_a_filtered_view(self, store):
        """Provenance, not different content. Without it, a forwarded PDF
        showing 4 findings is indistinguishable from a healthy site."""
        from api.services.domain_filter import filter_caveat_note
        note = filter_caveat_note({"domain": "example.com", "hidden": 31,
                                   "by_rule": {"severity:info": 28, "H1_MISSING": 3}})
        assert note and "31" in note
        assert "info" in note and "H1_MISSING" in note, (
            "the note must name the rules, or the reader cannot tell what is missing"
        )

    async def test_adversarial_an_unfiltered_report_carries_no_note(self, store):
        """The note must appear only when something was hidden, or every report
        acquires a caveat nobody reads and the signal is lost."""
        from api.services.domain_filter import filter_caveat_note
        assert filter_caveat_note({"domain": "x", "hidden": 0, "by_rule": {}}) is None
        assert filter_caveat_note(None) is None

    async def test_adversarial_an_unfiltered_export_is_byte_identical(self, test_store, auth_headers, api_client):
        """With no rules the export must be exactly what it was before this
        feature — so a bug cannot hide behind 'no filter configured'."""
        await self._job(test_store)
        a = (await api_client.get("/api/crawl/j1/export/csv", headers=auth_headers)).text
        await test_store.add_domain_filter("example.com", issue_code="H1_MISSING")
        await test_store.remove_domain_filter("example.com", issue_code="H1_MISSING")
        b = (await api_client.get("/api/crawl/j1/export/csv", headers=auth_headers)).text
        assert a == b

    async def test_the_pdf_states_it_is_filtered(self, test_store, auth_headers, api_client):
        """Wiring asserted at the artefact, not at the call. A note passed to a
        generator that never renders it is the unwired-disclosure trap this
        repo hit on 2026-08-30."""
        await self._job(test_store)
        await test_store.add_domain_filter("example.com", severity="info")
        r = await api_client.get("/api/crawl/j1/export/pdf", headers=auth_headers)
        assert r.status_code == 200
        # Extract the text rather than grepping bytes: fpdf2 compresses
        # streams, so a byte search would fail for the wrong reason.
        import io
        from pypdf import PdfReader
        text = " ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(r.content)).pages)
        assert "Filtered view" in text, (
            "the PDF does not say it is a filtered view — a forwarded report "
            "would look like a complete audit"
        )

    async def test_the_excel_states_it_is_filtered(self, test_store, auth_headers, api_client):
        import io
        from openpyxl import load_workbook
        await self._job(test_store)
        await test_store.add_domain_filter("example.com", severity="info")
        r = await api_client.get("/api/crawl/j1/export/excel", headers=auth_headers)
        assert r.status_code == 200
        wb = load_workbook(io.BytesIO(r.content))
        text = " ".join(str(c.value) for c in wb["Summary"]["D"] if c.value)
        assert "Filtered view" in text, f"Summary D column carries no filter note: {text!r}"
