"""D2 — Core Web Vitals: field data from CrUX, lab data from PSI.

Purpose: prove field and lab are never conflated, that only field data raises a
         finding, that an unmeasured page is never reported as a fast one, and
         that quota exhaustion is retryable rather than terminal.
Spec:    docs/pending/2026-08-29_D2-core-web-vitals.md
Tests:   this file

`test_d2_3b_lab_data_never_raises_a_finding` comes first (P10). Conflating a
synthetic Lighthouse run with real user experience is the one mistake that would
make this section actively misleading rather than merely incomplete.

FIXTURE WARNING: the checked-in payloads are CONSTRUCTED from the documented API
contracts, not recorded from the live APIs — see
tests/fixtures/web_vitals/README.md. `TestLiveApiContract` closes that gap and is
skipped unless TT_PSI_API_KEY is set.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
import respx

from api.crawler.checkers.registry import _CATALOGUE
from api.services.web_vitals import (
    VitalsRow,
    WebVitalsError,
    WebVitalsReport,
    _cfg,
    fetch_lab_vitals,
    parse_crux,
    parse_psi,
    vitals_issues,
)

FIXTURES = Path(__file__).parent / "fixtures" / "web_vitals"
URL = "https://livingsystems.ca/emotional-pain-and-suffering/"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _field(**kw) -> VitalsRow:
    return VitalsRow(url=URL, source="field", **kw)


def _report(*rows: VitalsRow) -> WebVitalsReport:
    return WebVitalsReport(rows=list(rows), requested=len(rows))


# ── The one that matters (P10) ──────────────────────────────────────────────


class TestLabNeverRaisesAFinding:
    def test_d2_3b_lab_data_never_raises_a_finding(self):
        """A synthetic run in a Google datacentre is not evidence about this
        site's real users. Lab data is diagnostic context, never a defect."""
        lab = VitalsRow(url=URL, source="lab", lcp_ms=9999, cls=0.9,
                        performance_score=12)
        assert vitals_issues(_report(lab)) == []

    def test_d2_3b_field_data_with_the_same_numbers_does_raise(self):
        """Same numbers, real users — now it is a finding. This is the pair that
        proves the distinction is doing work."""
        codes = {i.code for i in vitals_issues(_report(_field(lcp_ms=9999, cls=0.9)))}
        assert codes == {"CWV_LCP_POOR", "CWV_CLS_POOR"}

    def test_d2_3b_unavailable_rows_raise_nothing(self):
        row = VitalsRow(url=URL, source="unavailable",
                        unavailable_reason="no record")
        assert vitals_issues(_report(row)) == []


# ── D2.3 — the poor band, and only the poor band ────────────────────────────


class TestPoorBandOnly:
    def test_d2_3a_lcp_over_the_boundary_fires(self):
        codes = {i.code for i in vitals_issues(_report(_field(lcp_ms=4500)))}
        assert "CWV_LCP_POOR" in codes

    def test_d2_3a_lcp_in_the_needs_improvement_band_does_not_fire(self):
        """3.0s is not good, but flagging two thirds of the web is noise."""
        assert vitals_issues(_report(_field(lcp_ms=3000))) == []

    @pytest.mark.parametrize("metric,value,code", [
        ("inp_ms", 800, "CWV_INP_POOR"),
        ("cls", 0.4, "CWV_CLS_POOR"),
    ])
    def test_d2_3a_each_metric_has_its_own_boundary(self, metric, value, code):
        codes = {i.code for i in vitals_issues(_report(_field(**{metric: value})))}
        assert code in codes

    @pytest.mark.parametrize("metric,value", [("inp_ms", 300), ("cls", 0.15)])
    def test_d2_3a_needs_improvement_is_silent(self, metric, value):
        assert vitals_issues(_report(_field(**{metric: value}))) == []

    def test_d2_3a_thresholds_come_from_config_not_code(self):
        poor = _cfg()["poor_thresholds"]
        assert poor["lcp_ms"] == 4000 and poor["inp_ms"] == 500 and poor["cls"] == 0.25

    def test_d2_3a_missing_metric_is_not_a_finding(self):
        """A field record with only CLS must not imply anything about LCP."""
        assert {i.code for i in vitals_issues(_report(_field(cls=0.4)))} == {"CWV_CLS_POOR"}

    def test_d2_3a_issue_states_the_28_day_window(self):
        issue = vitals_issues(_report(_field(lcp_ms=5000)))[0]
        assert "28-day" in issue.extra["diagnosis"]
        assert issue.extra["source"] == "field"


# ── D2.2 — parsing ──────────────────────────────────────────────────────────


class TestParsing:
    def test_d2_2a_crux_record_parsed_as_field(self):
        row = parse_crux(_fixture("crux_record_poor.json"), URL)
        assert row is not None and row.source == "field"
        assert row.lcp_ms == 4600 and row.inp_ms == 232
        assert row.cls == pytest.approx(0.31)

    def test_d2_2a_crux_error_body_yields_no_row(self):
        assert parse_crux(_fixture("crux_no_record.json"), URL) is None

    def test_d2_2a_psi_parsed_as_lab(self):
        row = parse_psi(_fixture("psi_lab_slow.json"), URL)
        assert row is not None and row.source == "lab"
        assert row.lcp_ms == pytest.approx(5820.4)
        assert row.performance_score == 42

    def test_d2_2a_psi_never_populates_inp(self):
        """Lighthouse has no INP audit. Mapping Total Blocking Time onto INP
        would be exactly the field/lab conflation this module exists to avoid."""
        row = parse_psi(_fixture("psi_lab_slow.json"), URL)
        assert row.inp_ms is None

    @pytest.mark.parametrize("payload", [
        {}, None, {"record": {}}, {"record": {"metrics": {}}},
        {"lighthouseResult": {}}, {"lighthouseResult": {"audits": "not-a-dict"}},
    ])
    def test_d2_2a_unrecognised_shapes_degrade_to_none(self, payload):
        """P19 mitigation: the fixtures are constructed, so a contract drift must
        yield 'not measured' rather than a crash or a confident wrong number."""
        assert parse_crux(payload, URL) is None
        assert parse_psi(payload, URL) is None


# ── D2.2 — hardening (P1/P5) ────────────────────────────────────────────────


class TestHardening:
    @pytest.mark.asyncio
    async def test_d2_2b_quota_exhaustion_is_retryable_not_terminal(self):
        """A 429 on page 8 of 10 must not make pages 9 and 10 look fine. This is
        the real failure mode — the shared keyless PSI pool returned exactly this
        while D2 was being written."""
        with respx.mock:
            respx.get(url__startswith=_cfg()["psi_endpoint"]).mock(
                return_value=httpx.Response(429, json={"error": {"code": 429}})
            )
            async with httpx.AsyncClient(timeout=5) as client:
                with pytest.raises(WebVitalsError) as excinfo:
                    await fetch_lab_vitals(client, URL)
        assert excinfo.value.retryable is True

    @pytest.mark.asyncio
    async def test_d2_2b_client_error_is_terminal(self):
        with respx.mock:
            respx.get(url__startswith=_cfg()["psi_endpoint"]).mock(
                return_value=httpx.Response(400, json={"error": {"code": 400}})
            )
            async with httpx.AsyncClient(timeout=5) as client:
                with pytest.raises(WebVitalsError) as excinfo:
                    await fetch_lab_vitals(client, URL)
        assert excinfo.value.retryable is False

    @pytest.mark.asyncio
    async def test_d2_2c_retries_then_succeeds(self):
        """P5: bounded retry with backoff, like every other external call here."""
        with respx.mock:
            route = respx.get(url__startswith=_cfg()["psi_endpoint"])
            route.side_effect = [
                httpx.Response(503),
                httpx.Response(200, json=_fixture("psi_lab_slow.json")),
            ]
            async with httpx.AsyncClient(timeout=5) as client:
                row = await fetch_lab_vitals(client, URL)
        assert row is not None and row.source == "lab"

    @pytest.mark.asyncio
    async def test_d2_2c_gives_up_after_bounded_retries(self):
        with respx.mock:
            respx.get(url__startswith=_cfg()["psi_endpoint"]).mock(
                return_value=httpx.Response(503)
            )
            async with httpx.AsyncClient(timeout=5) as client:
                with pytest.raises(WebVitalsError):
                    await fetch_lab_vitals(client, URL)

    def test_d2_2c_config_declares_timeout_and_retries(self):
        cfg = _cfg()
        assert cfg["request_timeout_s"] > 0
        assert cfg["max_retries"] >= 2
        # The binding published constraint is 100 queries per 100 seconds.
        assert cfg["min_interval_s"] >= 1.0

    def test_d2_2e_key_read_from_env_only(self, monkeypatch):
        from api.services import web_vitals as mod

        monkeypatch.setenv("TT_PSI_API_KEY", "secret-value")
        assert mod.api_key() == "secret-value"
        monkeypatch.delenv("TT_PSI_API_KEY")
        assert mod.api_key() is None

    def test_d2_2e_key_scrubbed_from_error_text(self, monkeypatch):
        """Google takes the key as a query parameter, so an httpx transport
        error — whose message includes the request URL — carries it. Without
        scrubbing, a timeout writes the key into the log AND into the 502 body."""
        from api.services import web_vitals as mod

        monkeypatch.setenv("TT_PSI_API_KEY", "SUPER-SECRET-KEY")
        leaked = ("transport error: ConnectTimeout for "
                  "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
                  "?url=https://x/&key=SUPER-SECRET-KEY")
        cleaned = mod.scrub(leaked)
        assert "SUPER-SECRET-KEY" not in cleaned
        assert "***" in cleaned

    def test_d2_2e_key_scrubbed_even_when_env_is_unset(self, monkeypatch):
        """A key can appear in a URL the caller never set — scrub on the pattern
        as well as on the known value."""
        from api.services import web_vitals as mod

        monkeypatch.delenv("TT_PSI_API_KEY", raising=False)
        assert "abc123" not in mod.scrub("https://x/?url=y&key=abc123")

    @pytest.mark.asyncio
    async def test_d2_2e_key_never_reaches_the_unavailable_reason(self, monkeypatch):
        """The reason string is persisted on the job and rendered in the PDF."""
        from api.services import web_vitals as mod

        monkeypatch.setenv("TT_PSI_API_KEY", "LEAKY-KEY")
        with respx.mock:
            # With a key set, _collect_one tries CrUX first, then PSI. Both must
            # fail for the row to carry an unavailable_reason at all.
            respx.post(url__startswith=_cfg()["crux_endpoint"]).mock(
                side_effect=httpx.ConnectTimeout(
                    "timed out for https://chromeuxreport.googleapis.com/"
                    "v1/records:queryRecord?key=LEAKY-KEY")
            )
            respx.get(url__startswith=_cfg()["psi_endpoint"]).mock(
                side_effect=httpx.ConnectTimeout(
                    "timed out for https://www.googleapis.com/pagespeedonline/"
                    "v5/runPagespeed?url=https://x/&key=LEAKY-KEY")
            )
            async with httpx.AsyncClient(timeout=1) as client:
                row = await mod._collect_one(client, URL)
        assert row.source == "unavailable"
        assert row.unavailable_reason, "a failure must say why"
        assert "LEAKY-KEY" not in row.unavailable_reason
        assert "***" in row.unavailable_reason


# ── D2.3c — unmeasured is not good ──────────────────────────────────────────


class TestUnmeasuredIsNotGood:
    def test_d2_3c_unavailable_row_carries_a_reason(self):
        row = VitalsRow(url=URL, source="unavailable",
                        unavailable_reason="no field or lab data for this URL")
        assert row.unavailable_reason
        assert row.lcp_ms is None

    def test_d2_3c_report_counts_unmeasured_separately(self):
        report = _report(
            _field(lcp_ms=1000),
            VitalsRow(url="https://x/b", source="lab", lcp_ms=2000),
            VitalsRow(url="https://x/c", source="unavailable", unavailable_reason="no record"),
        )
        report.field_count = 1
        report.lab_count = 1
        report.unavailable_count = 1
        assert len(report.measured) == 2, "an unmeasured page is not a measured one"


# ── D2.1 — architecture and registry ────────────────────────────────────────


class TestArchitectureAndRegistry:
    def test_d2_1b_scan_never_calls_web_vitals_apis(self):
        """The crawl's speed and universality are load-bearing. Same guard shape
        as the existing 'scan must never call the WP API' constraint."""
        import inspect

        from api.crawler import engine

        src = inspect.getsource(engine)
        for forbidden in ("web_vitals", "pagespeedonline", "chromeuxreport"):
            assert forbidden not in src, (
                f"the crawl engine must not reference {forbidden}"
            )

    @pytest.mark.parametrize("code", ["CWV_LCP_POOR", "CWV_INP_POOR", "CWV_CLS_POOR"])
    def test_d2_3d_codes_registered_consistently(self, code):
        spec = _CATALOGUE[code]
        assert spec.category == "rendering"
        assert spec.severity == "warning"
        assert spec.fixability == "developer_needed"

    def test_d2_1a_top_n_is_capped_by_config(self):
        cfg = _cfg()
        assert cfg["default_top_n"] <= cfg["max_top_n"] <= 25


# ── The gap the fixtures cannot close ───────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("TT_PSI_API_KEY"),
    reason="No TT_PSI_API_KEY — the constructed fixtures cannot verify the real "
           "response contract. Set the key to run this (see fixtures README).",
)
class TestLiveApiContract:
    """Verifies the parsers against what the API actually emits (P19).

    The checked-in fixtures are constructed from documentation, which is exactly
    the setup that lets a parser drift from reality. This closes that gap the
    moment a key exists.
    """

    @pytest.mark.asyncio
    async def test_d2_live_psi_response_parses(self):
        async with httpx.AsyncClient(timeout=120) as client:
            row = await fetch_lab_vitals(client, "https://example.com/")
        assert row is not None, "the live PSI contract no longer matches parse_psi"
        assert row.source == "lab"
        assert row.lcp_ms is not None or row.performance_score is not None


# ── D2.4 — the endpoint (P25: the surface, not just the library) ────────────


class TestEndpoint:
    """`POST /api/crawl/{job_id}/web-vitals`.

    A test at `collect_web_vitals` proves the collector works; it says nothing
    about whether the route exposes it, persists it, or records the findings.
    """

    @pytest.mark.asyncio
    async def test_d2_4_unknown_job_is_404(self, api_client, auth_headers):
        resp = await api_client.post("/api/crawl/no-such-job/web-vitals",
                                     headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_d2_4_top_n_is_capped_at_25(self, api_client, auth_headers):
        """Config caps it; the route must not accept a larger request at all."""
        resp = await api_client.post("/api/crawl/any/web-vitals?top_n=500",
                                     headers=auth_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_d2_4_records_findings_and_persists_the_payload(
        self, api_client, auth_headers, test_store, monkeypatch
    ):
        """The P21 guard, end to end: a poor field measurement must become a
        stored issue, not merely a number in a JSON response."""
        from datetime import datetime, timezone

        from api.models.job import CrawlJob
        from api.models.page import CrawledPage
        from api.services import web_vitals as mod

        job_id = "job-cwv"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://livingsystems.ca",
            status="complete", started_at=datetime.now(timezone.utc)))
        await test_store.save_pages([
            CrawledPage(job_id=job_id, url=URL, status_code=200)])

        async def _fake(store, jid, *, top_n=None):
            return WebVitalsReport(
                rows=[VitalsRow(url=URL, source="field", lcp_ms=5200, cls=0.4)],
                requested=1, field_count=1, strategy="mobile")

        monkeypatch.setattr(mod, "collect_web_vitals", _fake)

        resp = await api_client.post(f"/api/crawl/{job_id}/web-vitals",
                                     headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["field_count"] == 1
        assert body["rows"][0]["source"] == "field"
        assert body["issues_recorded"] == 2  # LCP + CLS

        stored = {i.issue_code for i in await test_store.get_all_issues(job_id)}
        assert {"CWV_LCP_POOR", "CWV_CLS_POOR"} <= stored

        job = await test_store.get_job(job_id)
        assert job.web_vitals and job.web_vitals["field_count"] == 1

    @pytest.mark.asyncio
    async def test_d2_4_rerun_replaces_rather_than_duplicates(
        self, api_client, auth_headers, test_store, monkeypatch
    ):
        """Dirty-state (P8). The measurement is a snapshot of a 28-day window;
        a second run must replace the first, not accumulate beside it."""
        from datetime import datetime, timezone

        from api.models.job import CrawlJob
        from api.models.page import CrawledPage
        from api.services import web_vitals as mod

        job_id = "job-cwv-2"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://livingsystems.ca",
            status="complete", started_at=datetime.now(timezone.utc)))
        await test_store.save_pages([
            CrawledPage(job_id=job_id, url=URL, status_code=200)])

        async def _fake(store, jid, *, top_n=None):
            return WebVitalsReport(
                rows=[VitalsRow(url=URL, source="field", lcp_ms=5200)],
                requested=1, field_count=1, strategy="mobile")

        monkeypatch.setattr(mod, "collect_web_vitals", _fake)

        for _ in range(3):
            resp = await api_client.post(f"/api/crawl/{job_id}/web-vitals",
                                         headers=auth_headers)
            assert resp.status_code == 200

        lcp = [i for i in await test_store.get_all_issues(job_id)
               if i.issue_code == "CWV_LCP_POOR"]
        assert len(lcp) == 1, f"three runs produced {len(lcp)} rows"

    @pytest.mark.asyncio
    async def test_d2_4_a_page_that_improves_loses_its_finding(
        self, api_client, auth_headers, test_store, monkeypatch
    ):
        """The other half of P8: once the measurement is good, the old finding
        must go away rather than linger as a stale negative (P1)."""
        from datetime import datetime, timezone

        from api.models.job import CrawlJob
        from api.models.page import CrawledPage
        from api.services import web_vitals as mod

        job_id = "job-cwv-3"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://livingsystems.ca",
            status="complete", started_at=datetime.now(timezone.utc)))
        await test_store.save_pages([
            CrawledPage(job_id=job_id, url=URL, status_code=200)])

        async def _poor(store, jid, *, top_n=None):
            return WebVitalsReport(rows=[VitalsRow(url=URL, source="field", lcp_ms=5200)],
                                   requested=1, field_count=1)

        async def _good(store, jid, *, top_n=None):
            return WebVitalsReport(rows=[VitalsRow(url=URL, source="field", lcp_ms=1800)],
                                   requested=1, field_count=1)

        monkeypatch.setattr(mod, "collect_web_vitals", _poor)
        await api_client.post(f"/api/crawl/{job_id}/web-vitals", headers=auth_headers)
        monkeypatch.setattr(mod, "collect_web_vitals", _good)
        await api_client.post(f"/api/crawl/{job_id}/web-vitals", headers=auth_headers)

        codes = {i.issue_code for i in await test_store.get_all_issues(job_id)}
        assert "CWV_LCP_POOR" not in codes
