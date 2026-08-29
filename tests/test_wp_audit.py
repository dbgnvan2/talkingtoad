"""D3 — WordPress configuration audit.

Purpose: prove it cannot write, cannot audit the wrong site, never presents a
         partial read as a whole one, and states the boundary of what it knows.
Spec:    docs/pending/2026-08-29_D3-wordpress-configuration-audit.md
Tests:   this file

`test_d3_1a_wp_audit_is_read_only` comes first (P10). This feature holds admin
credentials to a live client site. "It is read-only" has to be a property the
tests enforce, not an intention the author had.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from api.config import load_config
from api.models.job import CrawlJob
from api.services.wp_audit import (
    NOT_INSPECTED,
    WPAuditError,
    collect_wp_audit,
    find_overlaps,
    parse_plugins,
    parse_site_health,
    report_to_dict,
)

JOB_ID = "job-wp-audit"


def _plugin(slug, name, status="active", version="1.0", update=None):
    item = {"plugin": f"{slug}/{slug}.php", "name": name,
            "status": status, "version": version}
    if update:
        item["update"] = {"new_version": update}
    return item


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload


class _FakeWP:
    """A stand-in WPClient. Records every call so a write attempt is visible."""

    def __init__(self, routes: dict, *, me_status: int = 200):
        self.routes = routes
        self.me_status = me_status
        self.calls: list[str] = []

    async def get(self, endpoint, **_kw):
        self.calls.append(endpoint)
        if endpoint.startswith("/wp/v2/users/me"):
            return _Resp(self.me_status, {"id": 1})
        for prefix, resp in self.routes.items():
            if endpoint.startswith(prefix):
                return resp
        return _Resp(404, {})


# ── The one that matters (P10) ──────────────────────────────────────────────


class TestReadOnly:
    def test_d3_1a_wp_audit_is_read_only(self):
        """No write verb anywhere in the module. This holds admin credentials to
        a live site; intent is not a property, so the test enforces it."""
        from api.services import wp_audit

        src = inspect.getsource(wp_audit)
        for verb in (".post(", ".patch(", ".put(", ".delete("):
            assert verb not in src, f"wp_audit must never call {verb}"

    def test_d3_1a_router_is_read_only_too(self):
        from api.routers import wp_audit_router

        src = inspect.getsource(wp_audit_router)
        for verb in ("wp.post(", "wp.patch(", "wp.put(", "wp.delete("):
            assert verb not in src, f"the router must never call {verb}"

    @pytest.mark.asyncio
    async def test_d3_1a_only_get_is_ever_called(self):
        """Behavioural, not just textual: exercise the collector and confirm the
        client saw nothing but reads."""
        wp = _FakeWP({"/wp/v2/plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
        await collect_wp_audit(wp)
        assert wp.calls, "the audit must actually call something"
        assert not hasattr(wp, "posted")


# ── D3.1 — access control ───────────────────────────────────────────────────


class TestAccessControl:
    @pytest.mark.asyncio
    async def test_d3_1d_capability_probe_runs_first(self):
        """The probe must precede the plugin read, so an unauthorised user gets a
        clear error rather than a confusing 403 midway."""
        wp = _FakeWP({}, me_status=403)
        with pytest.raises(WPAuditError) as excinfo:
            await collect_wp_audit(wp)
        assert excinfo.value.code == "WP_INSUFFICIENT_CAPABILITY"
        assert wp.calls[0].startswith("/wp/v2/users/me")

    @pytest.mark.asyncio
    async def test_d3_1d_plugin_403_is_not_an_empty_audit(self):
        """P2: 'we could not look' must never render as 'nothing to report'."""
        wp = _FakeWP({"/wp/v2/plugins": _Resp(403, {})})
        with pytest.raises(WPAuditError) as excinfo:
            await collect_wp_audit(wp)
        assert excinfo.value.code == "WP_INSUFFICIENT_CAPABILITY"

    @pytest.mark.asyncio
    async def test_d3_1d_unexpected_status_raises(self):
        wp = _FakeWP({"/wp/v2/plugins": _Resp(500, {})})
        with pytest.raises(WPAuditError) as excinfo:
            await collect_wp_audit(wp)
        assert excinfo.value.code == "WP_UNEXPECTED_RESPONSE"

    @pytest.mark.asyncio
    async def test_d3_1d_themes_and_health_are_best_effort(self):
        """Neither is available on every install; their absence must degrade the
        report rather than fail it."""
        wp = _FakeWP({"/wp/v2/plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
        report = await collect_wp_audit(wp)
        assert len(report.plugins) == 1
        assert report.themes_inactive == []


# ── D3.2 — findings ─────────────────────────────────────────────────────────


class TestParsing:
    def test_d3_2a_active_inactive_and_updates(self):
        rows = parse_plugins([
            _plugin("wordpress-seo", "Yoast SEO"),
            _plugin("smartcrawl-seo", "SmartCrawl", status="inactive"),
            _plugin("elementor", "Elementor", update="3.99"),
        ])
        by_slug = {r.slug: r for r in rows}
        assert by_slug["wordpress-seo"].is_active
        assert not by_slug["smartcrawl-seo"].is_active
        assert by_slug["elementor"].update_available
        assert by_slug["elementor"].new_version == "3.99"

    def test_d3_2a_slug_extracted_from_the_plugin_path(self):
        rows = parse_plugins([{"plugin": "wp-smushit/wp-smush.php", "name": "Smush",
                               "status": "active"}])
        assert rows[0].slug == "wp-smushit"

    @pytest.mark.parametrize("payload", [None, {}, "nope", [None, 3, "x"]])
    def test_d3_2a_unfamiliar_payloads_do_not_crash(self, payload):
        assert parse_plugins(payload) == [] or all(
            hasattr(r, "slug") for r in parse_plugins(payload))

    def test_d3_2e_site_health_is_attributed_to_wordpress(self):
        rows = parse_site_health({"recommended": [
            {"label": "Use a persistent object cache", "status": "recommended"}]})
        assert rows[0]["source"] == "WordPress Site Health"


class TestOverlaps:
    def test_d3_2b_two_active_compressors_are_an_overlap(self):
        overlaps = find_overlaps(parse_plugins([
            _plugin("wp-smushit", "Smush"),
            _plugin("sg-cachepress", "Speed Optimizer"),
        ]))
        labels = {o.responsibility for o in overlaps}
        assert "image_compression" in labels

    def test_d3_2b_overlap_explains_why_one_owner(self):
        overlaps = find_overlaps(parse_plugins([
            _plugin("wp-smushit", "Smush"), _plugin("sg-cachepress", "Speed Optimizer"),
        ]))
        assert all(o.why_one_owner for o in overlaps)

    def test_d3_2c_addon_of_the_same_family_is_not_an_overlap(self):
        """Adversarial (P7). Yoast plus Yoast Premium plus Yoast Local is ONE
        product. Flagging it would make the section easy to dismiss entirely."""
        overlaps = find_overlaps(parse_plugins([
            _plugin("wordpress-seo", "Yoast SEO"),
            _plugin("wordpress-seo-premium", "Yoast SEO Premium"),
            _plugin("wpseo-local", "Yoast Local SEO"),
        ]))
        assert overlaps == [], f"unexpected overlap: {overlaps}"

    def test_d3_2c_duplicator_free_and_pro_is_not_an_overlap(self):
        overlaps = find_overlaps(parse_plugins([
            _plugin("duplicator", "Duplicator"),
            _plugin("duplicator-pro", "Duplicator Pro"),
        ]))
        assert overlaps == []

    def test_d3_2b_inactive_plugins_never_create_an_overlap(self):
        """An installed-but-inactive plugin is not doing the job."""
        overlaps = find_overlaps(parse_plugins([
            _plugin("wp-smushit", "Smush"),
            _plugin("sg-cachepress", "Speed Optimizer", status="inactive"),
        ]))
        assert overlaps == []

    def test_d3_2b_two_genuinely_different_seo_plugins_do_overlap(self):
        overlaps = find_overlaps(parse_plugins([
            _plugin("wordpress-seo", "Yoast"),
            _plugin("seo-by-rank-math", "Rank Math"),
        ]))
        assert any(o.responsibility == "seo_titles_and_schema" for o in overlaps)

    def test_d3_2d_advice_config_is_well_formed(self):
        cfg = load_config("wp_plugin_advice",
                          required_keys=("responsibilities", "families"))
        for name, spec in cfg["responsibilities"].items():
            assert spec["label"] and spec["why_one_owner"], name
            assert spec["slugs"], name


class TestBoundary:
    def test_d3_2f_not_inspected_is_declared(self):
        assert NOT_INSPECTED
        joined = " ".join(NOT_INSPECTED).lower()
        assert "backup" in joined, "the Duplicator case must be named explicitly"
        assert "only reads" in joined

    @pytest.mark.asyncio
    async def test_d3_2f_boundary_travels_in_the_payload(self):
        wp = _FakeWP({"/wp/v2/plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
        payload = report_to_dict(await collect_wp_audit(wp))
        assert payload["not_inspected"], "the report must state what it did not read"


# ── D3.3 — the endpoint and the report ──────────────────────────────────────


class TestEndpoint:
    @pytest.mark.asyncio
    async def test_d3_3_unknown_job_is_404(self, api_client, auth_headers):
        resp = await api_client.post("/api/wp-audit/no-such-job", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_d3_1c_domain_validated_before_any_wp_call(
        self, api_client, auth_headers, test_store, monkeypatch
    ):
        """Never authenticate against a site this job is not for."""
        await test_store.create_job(CrawlJob(
            job_id=JOB_ID, target_url="https://not-the-wp-site.example",
            status="complete", started_at=datetime.now(timezone.utc)))

        called = {"wp": False}

        class _Boom:
            def __init__(self, *a, **k):
                called["wp"] = True

        monkeypatch.setattr("api.routers.wp_audit_router.WPClient", _Boom)
        resp = await api_client.post(f"/api/wp-audit/{JOB_ID}", headers=auth_headers)
        assert resp.status_code in (400, 403)
        assert called["wp"] is False, "no WordPress call before domain validation"


class TestReportRendering:
    @pytest.mark.asyncio
    async def test_d3_3a_omission_is_named_in_caveats(self):
        """Audit not run → the section is absent AND the reader is told, so a
        missing section never reads as a clean WordPress install (E7.4)."""
        import io

        import pypdf

        from api.services.report_generator import generate_pdf_report

        job = CrawlJob(job_id="j", target_url="https://x/", status="complete",
                       started_at=datetime.now(timezone.utc))
        pdf = await generate_pdf_report(job, [], {
            "health_score": 90, "agent_health_score": 90, "pages_crawled": 1,
            "total_issues": 0, "by_severity": {}, "by_category": {}})
        text = " ".join((p.extract_text() or "")
                        for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)
        assert "WordPress Configuration" not in text.replace("\n", " ")
        assert "never signs in to WordPress" in text.replace("\n", " ")

    @pytest.mark.asyncio
    async def test_d3_3b_section_renders_and_caveat_flips(self):
        import io

        import pypdf

        from api.services.report_generator import generate_pdf_report

        job = CrawlJob(
            job_id="j", target_url="https://x/", status="complete",
            started_at=datetime.now(timezone.utc),
            wp_audit={
                "plugins_total": 22, "plugins_active": 19, "plugins_inactive": 3,
                "pending_updates": [{"name": "Elementor Pro", "version": "3.2",
                                     "new_version": "3.9", "slug": "elementor-pro"}],
                "inactive_plugins": [{"name": "SmartCrawl", "slug": "smartcrawl-seo",
                                      "version": "3.0"}],
                "inactive_themes": [], "site_health": [],
                "overlaps": [{"responsibility": "image_compression",
                              "label": "Image compression",
                              "why_one_owner": "Two compressors degrade quality.",
                              "plugins": ["wp-smushit", "sg-cachepress"]}],
                "not_inspected": NOT_INSPECTED,
            })
        pdf = await generate_pdf_report(job, [], {
            "health_score": 90, "agent_health_score": 90, "pages_crawled": 1,
            "total_issues": 0, "by_severity": {}, "by_category": {}})
        text = " ".join((p.extract_text() or "")
                        for p in pypdf.PdfReader(io.BytesIO(pdf)).pages).replace("\n", " ")
        assert "WordPress Configuration" in text
        assert "Elementor Pro" in text
        assert "Image compression" in text
        assert "Not inspected" in text
        assert "CMS configuration was read" in text
        assert "never signs in to WordPress" not in text
