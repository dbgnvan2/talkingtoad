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
        """WA1 (2026-09-02): endpoints are `wp/v2`-relative, exactly as
        `WPClient.get` documents. This stub used to key on `/wp/v2/plugins` —
        the form the code passed and the real client turns into
        `/wp-json/wp/v2//wp/v2/plugins`, a 404 on every WordPress install. Stub
        and code agreed with each other about a URL that does not exist, and
        the audit shipped broken with this file green (P26/P32). A stub cannot
        police URL construction; tests/test_wp_client_routes.py does that over
        a real transport. What it CAN do is refuse to answer a spelling the
        real client would not produce.
        """
        assert not endpoint.startswith("/"), (
            f"endpoint {endpoint!r} is not wp/v2-relative — WPClient.get would "
            f"request /wp-json/wp/v2/{endpoint.lstrip('/')} and 404")
        assert not endpoint.startswith("wp/v2/"), (
            f"endpoint {endpoint!r} repeats the namespace WPClient.get adds")
        self.calls.append(endpoint)
        if endpoint.startswith("users/me"):
            return _Resp(self.me_status, {"id": 1})
        for prefix, resp in self.routes.items():
            if endpoint.startswith(prefix):
                return resp
        return _Resp(404, {})

    async def get_route(self, route, **_kw):
        """WA2 — Site Health is in the `wp-site-health/v1` namespace, which
        `get()` structurally cannot reach."""
        assert not route.startswith("/"), (
            f"route {route!r} has a leading slash; get_route joins it to /wp-json/")
        assert ".." not in route, f"route {route!r} escapes /wp-json/"
        self.calls.append(f"route:{route}")
        for prefix, resp in self.routes.items():
            if route.startswith(prefix):
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
        wp = _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
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
        assert wp.calls[0].startswith("users/me")

    @pytest.mark.asyncio
    async def test_d3_1d_plugin_403_is_not_an_empty_audit(self):
        """P2: 'we could not look' must never render as 'nothing to report'."""
        wp = _FakeWP({"plugins": _Resp(403, {})})
        with pytest.raises(WPAuditError) as excinfo:
            await collect_wp_audit(wp)
        assert excinfo.value.code == "WP_INSUFFICIENT_CAPABILITY"

    @pytest.mark.asyncio
    async def test_d3_1d_unexpected_status_raises(self):
        wp = _FakeWP({"plugins": _Resp(500, {})})
        with pytest.raises(WPAuditError) as excinfo:
            await collect_wp_audit(wp)
        assert excinfo.value.code == "WP_UNEXPECTED_RESPONSE"

    @pytest.mark.asyncio
    async def test_d3_1d_themes_and_health_are_best_effort(self):
        """Neither is available on every install; their absence must degrade the
        report rather than fail it."""
        wp = _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
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
        wp = _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
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



class TestPanelContract:
    """Phase 4 U4.4 — the WordPress audit is triggered from the app; the panel
    (frontend/src/components/WpAuditPanel.jsx) reads these keys."""

    async def test_response_carries_the_keys_the_panel_reads(self, api_client, auth_headers, test_store,
                                                             monkeypatch, tmp_path):
        import json
        from contextlib import asynccontextmanager
        from datetime import datetime, timezone
        from api.models.job import CrawlJob
        await test_store.create_job(CrawlJob(job_id="wp1", target_url="https://example.com",
                                             status="complete", started_at=datetime.now(timezone.utc)))

        async def ok(*a, **k):
            return None
        monkeypatch.setattr("api.routers.wp_audit_router._validate_wp_domain_for_job", ok)
        creds = tmp_path / "wp-credentials.json"
        creds.write_text(json.dumps({"site_url": "https://example.com", "username": "u", "app_password": "p"}))
        monkeypatch.setattr("api.routers.wp_audit_router._CREDS_PATH", creds)

        class _FakeWP:
            @staticmethod
            @asynccontextmanager
            async def from_credentials_file(path):
                yield object()
        monkeypatch.setattr("api.routers.wp_audit_router.WPClient", _FakeWP)

        # Only the WordPress read is faked; the real serializer runs, so a
        # renamed key in report_to_dict fails here (sweep: the first version
        # pinned the keys of its own fixture — P32).
        from api.services.wp_audit import PluginRow, WPAuditReport

        async def fake_collect(wp):
            return WPAuditReport(
                plugins=[PluginRow("a", "A", "1", "active", True, "2"), PluginRow("c", "C", "1", "active"),
                         PluginRow("b", "B", "1", "inactive")],
                not_inspected=["backup contents"])
        monkeypatch.setattr("api.services.wp_audit.collect_wp_audit", fake_collect)

        r = await api_client.post("/api/wp-audit/wp1", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("plugins_total", "plugins_active", "plugins_inactive", "pending_updates",
                    "inactive_plugins", "not_inspected", "job_id"):
            assert key in body, f"WpAuditPanel reads {key}"
        assert body["pending_updates"][0]["new_version"] == "2"
        # ...and the PDF's copy is stored on the job.
        assert (await test_store.get_job("wp1")).wp_audit["plugins_total"] == 3

    async def test_no_credentials_is_a_named_400(self, api_client, auth_headers, test_store, monkeypatch, tmp_path):
        from datetime import datetime, timezone
        from api.models.job import CrawlJob
        await test_store.create_job(CrawlJob(job_id="wp2", target_url="https://example.com",
                                             status="complete", started_at=datetime.now(timezone.utc)))

        async def ok(*a, **k):
            return None
        monkeypatch.setattr("api.routers.wp_audit_router._validate_wp_domain_for_job", ok)
        monkeypatch.setattr("api.routers.wp_audit_router._CREDS_PATH", tmp_path / "missing.json")
        r = await api_client.post("/api/wp-audit/wp2", headers=auth_headers)
        assert r.status_code == 400 and r.json()["error"]["code"] == "NO_CREDENTIALS"


# ── WA1/WA2/WA3 (2026-09-02) — the audit against a real client ──────────────


class TestTheAuditAgainstARealClient:
    """The audit shipped 2026-09-02 and never returned a report against a real
    site: every call went to `/wp-json/wp/v2//wp/v2/...` and 404ed. This file
    stayed green because `_FakeWP` was keyed by the same wrong strings.

    These drive `collect_wp_audit` through a real `WPClient` over a mocked
    transport, so the URL is part of what is asserted.

    Spec: docs/functional-specification.md §7.8 (WA1-WA5, folded 2026-09-02)
    """

    SITE = "https://wp.test"
    NONCE = "abc123def456"

    def _login(self, mock):
        import httpx as _httpx
        admin = ("<html><script>wp.apiFetch.use( wp.apiFetch.createNonceMiddleware( "
                 f'"{self.NONCE}" ) );</script></html>')
        mock.get(f"{self.SITE}/wp-login.php").mock(
            return_value=_httpx.Response(200, text="<form/>"))
        mock.post(f"{self.SITE}/wp-login.php").mock(return_value=_httpx.Response(
            302, headers={"location": f"{self.SITE}/wp-admin/",
                          "set-cookie": "wordpress_logged_in_x=y; Path=/"}))
        mock.get(f"{self.SITE}/wp-admin/").mock(
            return_value=_httpx.Response(200, text=admin))

    def _client(self):
        from api.services.wp_client import WPClient
        return WPClient(site_url=self.SITE, login_url=f"{self.SITE}/wp-login.php",
                        username="u", password="p")

    async def test_a_real_client_reaches_every_route_the_audit_needs(self):
        """The regression, end to end. Only the CORRECT urls are mocked; any
        doubled namespace falls through to the catch-all 404 and the audit
        raises, exactly as it did in production."""
        import httpx as _httpx
        import respx as _respx
        from api.services.wp_client import invalidate_session

        invalidate_session(f"{self.SITE}/wp-login.php", "u")
        with _respx.mock(assert_all_called=False) as mock:
            self._login(mock)
            mock.get(f"{self.SITE}/wp-json/wp/v2/users/me?context=edit").mock(
                return_value=_httpx.Response(200, json={"id": 1}))
            mock.get(f"{self.SITE}/wp-json/wp/v2/plugins").mock(
                return_value=_httpx.Response(200, json=[_plugin("wordpress-seo", "Yoast")]))
            mock.get(f"{self.SITE}/wp-json/wp/v2/themes").mock(
                return_value=_httpx.Response(200, json=[
                    {"stylesheet": "twentytwenty", "status": "inactive",
                     "name": {"raw": "Twenty Twenty"}}]))
            mock.get(f"{self.SITE}/wp-json/wp-site-health/v1/tests/background-updates").mock(
                return_value=_httpx.Response(200, json=REAL_SITE_HEALTH))
            # Anything else on the host is a wrong URL.
            mock.route(host="wp.test").mock(return_value=_httpx.Response(404, json={}))

            async with self._client() as wp:
                report = await collect_wp_audit(wp)

        assert len(report.plugins) == 1
        assert report.themes_inactive == ["Twenty Twenty"], (
            "themes are best-effort, so a wrong URL there degrades SILENTLY — "
            "this assertion is the only thing that would notice")
        assert report.site_health, (
            "Site Health is in the wp-site-health/v1 namespace and never rendered")
        invalidate_session(f"{self.SITE}/wp-login.php", "u")

    async def test_the_doubled_namespace_url_is_never_requested(self):
        import httpx as _httpx
        import respx as _respx
        from api.services.wp_client import invalidate_session

        invalidate_session(f"{self.SITE}/wp-login.php", "u")
        with _respx.mock(assert_all_called=False) as mock:
            self._login(mock)
            mock.route(host="wp.test").mock(return_value=_httpx.Response(200, json=[]))
            async with self._client() as wp:
                try:
                    await collect_wp_audit(wp)
                except Exception:
                    pass
            urls = [str(c.request.url) for c in mock.calls if "/wp-json/" in str(c.request.url)]
        assert urls, "no REST call was made"
        for u in urls:
            assert "/wp/v2//" not in u, f"doubled namespace: {u}"
        invalidate_session(f"{self.SITE}/wp-login.php", "u")


class TestTheCapabilityProbeCannotPassOnA404:
    """WA3 — the probe checked `status_code in (401, 403)`. A 404 is neither, so
    it passed on a response that proved nothing: the route was wrong and the
    audit carried on as though the account had been verified (P2). 'Could not
    look' must never be indistinguishable from 'looked, and it was fine'."""

    # The plugin route WORKS in these fixtures. The first version passed an
    # empty routes dict, so `plugins` 404ed too and the pre-existing
    # `resp.status_code != 200` check raised — satisfying both assertions from a
    # DIFFERENT line. Deleting the probe left all 38 tests green (P27, proven by
    # mutation in the 2026-09-02 sweep). With a working plugin route the probe
    # is the only thing that can raise, and the call log proves the audit
    # stopped before reading anything.
    GOOD_PLUGINS = {"plugins": None}   # filled per-test; see _wp()

    def _wp(self, me_status):
        return _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])},
                       me_status=me_status)

    async def test_a_404_probe_raises_rather_than_continuing(self):
        wp = self._wp(404)
        with pytest.raises(WPAuditError) as excinfo:
            await collect_wp_audit(wp)
        assert excinfo.value.code != "WP_INSUFFICIENT_CAPABILITY", (
            "a 404 is a wrong route or REST disabled, not a permissions answer")
        assert "404" in str(excinfo.value)
        assert wp.calls == ["users/me?context=edit"], (
            f"the audit read on past an unverified probe: {wp.calls}")

    async def test_a_500_probe_raises_too(self):
        wp = self._wp(500)
        with pytest.raises(WPAuditError):
            await collect_wp_audit(wp)
        assert wp.calls == ["users/me?context=edit"]

    async def test_a_200_probe_still_proceeds(self):
        wp = _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
        report = await collect_wp_audit(wp)
        assert len(report.plugins) == 1


# Captured verbatim from `GET /wp-json/wp-site-health/v1/tests/background-updates`
# on a live WordPress install (livingsystems.ca, 2026-09-02). WordPress returns
# ONE test result — not the `{"recommended": [...], "critical": [...]}` aggregate
# `parse_site_health` was written for, which is why the section rendered empty
# even once the route was reachable. Fixtures invented from the parser's own
# expectations cannot catch that (P32); this one came off the wire.
REAL_SITE_HEALTH = {
    "test": "background_updates",
    "label": "Background updates are not working as expected",
    "status": "critical",
    "badge": {"label": "Security", "color": "blue"},
    "description": "<p>Background updates ensure that WordPress can auto-update.</p>",
    "actions": "",
}


class TestSiteHealthParsesWhatWordPressActuallySends:
    """WA2, second half. Reaching the route is not the same as reading it."""

    def test_the_single_test_shape_is_parsed(self):
        rows = parse_site_health(REAL_SITE_HEALTH)
        assert rows, "the real WordPress payload parsed to nothing"
        assert rows[0]["label"] == "Background updates are not working as expected"
        assert rows[0]["status"] == "critical"
        assert rows[0]["source"] == "WordPress Site Health"

    def test_a_passing_test_is_not_reported_as_a_finding(self):
        """Adversarial: `status: "good"` is WordPress saying the check PASSED.
        Listing it beside the critical ones turns a clean result into a
        recommendation the operator will go and act on."""
        ok = dict(REAL_SITE_HEALTH, status="good",
                  label="Background updates are working")
        assert parse_site_health(ok) == []

    def test_the_aggregate_shape_still_parses(self):
        """Kept for any endpoint that does return the grouped form."""
        rows = parse_site_health({"critical": [{"label": "A thing", "status": "critical"}]})
        assert rows and rows[0]["label"] == "A thing"

    def test_junk_is_not_a_crash(self):
        for payload in (None, [], "text", {}, {"critical": None}, {"label": ""}):
            assert parse_site_health(payload) == []


class TestSiteHealthAbsenceIsDeclared:
    """P2, and the exact sentence WA2 was written to remove. WA2 fixed the
    PARSE; the FETCH was left as `try/except` + `status_code == 200`, so a
    security plugin blocking the `wp-site-health/v1` namespace (Wordfence,
    SiteGround and most managed hosts do) produced a client report
    byte-identical to one where the check ran and passed."""

    async def test_a_blocked_site_health_route_is_recorded_as_not_inspected(self):
        wp = _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")])})
        # No site-health route in the fake -> 404, the blocked-host case.
        report = await collect_wp_audit(wp)
        assert report.site_health == []
        assert any("site health" in n.lower() for n in report.not_inspected), (
            "a blocked Site Health check is indistinguishable from a passing one: "
            f"{report.not_inspected}")

    async def test_a_successful_read_does_not_claim_it_was_skipped(self):
        wp = _FakeWP({"plugins": _Resp(200, [_plugin("wordpress-seo", "Yoast")]),
                      "wp-site-health": _Resp(200, REAL_SITE_HEALTH)})
        report = await collect_wp_audit(wp)
        assert report.site_health, "the route answered but nothing was parsed"
        assert not any("could not be read" in n.lower() for n in report.not_inspected)

    def test_only_the_one_test_that_was_read_is_claimed(self):
        """WordPress has ~20 Site Health tests; the audit reads one. The report
        must not imply the whole panel was covered (P31)."""
        from api.services.wp_audit import NOT_INSPECTED
        joined = " ".join(NOT_INSPECTED).lower()
        assert "site health" in joined and "background" in joined, (
            "the report does not say which Site Health tests it left unread")


class TestAStatusLessFindingIsNotSilentlyDropped:
    """P2 nit from the sweep: `status` was lowercased through
    `str(x or "")` and `""` sat in the pass-list, so a finding WordPress sent
    with no status was treated as a pass and dropped. "good" is WordPress
    asserting a pass; "" is WordPress asserting nothing."""

    def test_a_missing_status_is_reported_not_dropped(self):
        rows = parse_site_health({"test": "x", "label": "Something is wrong"})
        assert rows, "a finding with no status vanished"
        assert rows[0]["label"] == "Something is wrong"

    def test_an_explicit_pass_is_still_dropped(self):
        assert parse_site_health({"test": "x", "label": "All good", "status": "good"}) == []
