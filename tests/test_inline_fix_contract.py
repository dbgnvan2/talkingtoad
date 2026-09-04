"""Contract tests for the inline-fix seam — POST /api/fixes/apply-one and
GET /api/fixes/wp-value (micro-spec 2026-09-03_p5-1-inline-fix-contract, TODO P5.1).

Why this file exists
--------------------
Both endpoints are called only by `FixInlinePanel.jsx`, and until 2026-09-03 neither
had a success-path test on either side of the wire:

* `apply-one` built a fix record with no ``field`` and no ``wp_post_id``, so
  ``apply_fix`` returned ``(False, "No fix spec for field ''")`` for every one of the
  ten codes the panel offers — the inline fix had never applied.
* `wp-value` returned ``{"value": ...}`` while both consumers read
  ``data.current_value``, so the editor opened blank and the auto-proposal (the whole
  point of ``TITLE_TOO_LONG``) had nothing to trim.
* The two one-click codes (``NOT_IN_SITEMAP``, ``JSON_LD_MISSING``) never received
  their predetermined value, because ``Results.jsx`` renders the panel without the
  ``predefinedValue`` prop.

The vitest suite was green throughout, because its mocks were written from the
component rather than from the server (P27). These tests assert against the endpoint,
so a mock cannot satisfy them.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.models.job import CrawlJob
from api.services.wp_shared import _CODE_TO_FIELD, _FIELD_SPECS, PREDEFINED_FIX_VALUES

_SITE = "https://example.com"
_PAGE = "https://example.com/about"


# ---------------------------------------------------------------------------
# Fakes — a WP client that records what was written, rather than a mock that
# agrees with the caller (P32: an oracle computed from the code under test).
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _FakeWP:
    """Records every PATCH so a test can assert the meta key and value written."""

    def __init__(self, get_payload: dict | None = None):
        self.patches: list[tuple[str, dict]] = []
        self._get_payload = get_payload or {}

    async def __aenter__(self) -> "_FakeWP":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, endpoint: str, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(200, self._get_payload)

    async def patch(self, endpoint: str, **kwargs: object) -> _FakeResponse:
        self.patches.append((endpoint, kwargs.get("json", {})))
        return _FakeResponse(200, {})


@pytest.fixture
def creds(tmp_path):
    """A credentials file whose domain matches _SITE, so domain validation passes."""
    path = tmp_path / "wp-credentials.json"
    path.write_text(json.dumps({
        "site_url": _SITE,
        "login_url": f"{_SITE}/wp-login.php",
        "username": "admin",
        "password": "secret",
    }))
    return path


@pytest.fixture
async def seeded_job(api_client, test_store):
    job_id = str(uuid4())
    await test_store.create_job(CrawlJob(
        job_id=job_id, target_url=_SITE, status="complete", pages_crawled=1,
    ))
    return api_client, job_id


class _WPHarness:
    """Patches the WP surface of link_router and hands back the fake client."""

    _DEFAULT_POST = {"id": 12, "type": "page"}

    def __init__(self, creds_path, *, wp: _FakeWP | None = None,
                 post_info: dict | None = _DEFAULT_POST,
                 seo_plugin: str | None = "yoast"):
        # `post_info=None` must mean "find_post_by_url found nothing", not "use the
        # default" — a `None`-means-default harness silently made the 404 test pass
        # against code that had no 404 in it.
        self.wp = wp if wp is not None else _FakeWP()
        self._post_info = post_info
        self._seo_plugin = seo_plugin
        self._patches = [
            patch("api.routers.link_router._CREDS_PATH", creds_path),
            patch("api.routers.fixes_shared._CREDS_PATH", creds_path),
            patch("api.routers.link_router.WPClient.from_credentials_file",
                  return_value=self.wp),
            patch("api.routers.link_router.detect_seo_plugin",
                  AsyncMock(return_value=self._seo_plugin)),
            patch("api.routers.link_router.find_post_by_url",
                  AsyncMock(return_value=self._post_info)),
        ]

    def __enter__(self) -> "_WPHarness":
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *args: object) -> None:
        for p in reversed(self._patches):
            p.stop()


# ---------------------------------------------------------------------------
# 3.1 / 3.2 / 3.6 — apply-one builds a record apply_fix can actually use
# ---------------------------------------------------------------------------


class TestApplyOneBuildsAUsableRecord:
    @pytest.mark.asyncio
    async def test_apply_one_passes_field_and_post_id_to_apply_fix(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.1 — assert on the RECORD handed to apply_fix, not on `success`.

        A mocked apply_fix returning (True, None) makes a `success is True`
        assertion pass with the record still empty (P32). The record is the thing
        in doubt, so the record is what gets asserted.
        """
        api_client, job_id = seeded_job
        spy = AsyncMock(return_value=(True, None))
        with _WPHarness(creds), patch("api.routers.link_router.apply_fix", spy):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id,
                    "page_url": _PAGE,
                    "issue_code": "TITLE_TOO_LONG",
                    "proposed_value": "A trimmed title",
                },
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        spy.assert_awaited_once()
        record = spy.await_args.args[1]
        assert record["field"] == "seo_title", (
            "apply_fix reads fix['field'] and refuses an empty one — the endpoint "
            f"must derive it from _CODE_TO_FIELD. Got: {record!r}"
        )
        assert record["wp_post_id"] == 12, (
            "apply_fix refuses a record with no wp_post_id — the endpoint must "
            f"resolve the post first. Got: {record!r}"
        )
        assert record["wp_post_type"] == "page"
        assert record["proposed_value"] == "A trimmed title"

    @pytest.mark.asyncio
    async def test_apply_one_derives_the_field_from_the_backend_map_not_the_body(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.1b — a client that disagrees with _CODE_TO_FIELD must not win.

        The panel sends `field` in the body today. Accepting it would make the
        client authoritative over the backend map, which is the drift P5.1 exists
        to close: a stale bundle would write the wrong Yoast meta key.
        """
        api_client, job_id = seeded_job
        spy = AsyncMock(return_value=(True, None))
        with _WPHarness(creds), patch("api.routers.link_router.apply_fix", spy):
            await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id,
                    "page_url": _PAGE,
                    "issue_code": "TITLE_TOO_LONG",
                    "field": "meta_description",      # a lying client
                    "proposed_value": "A trimmed title",
                },
                headers=auth_headers,
            )
        record = spy.await_args.args[1]
        assert record["field"] == _CODE_TO_FIELD["TITLE_TOO_LONG"] == "seo_title", (
            "the endpoint took `field` from the request body — the backend map is "
            "the source of truth"
        )

    @pytest.mark.asyncio
    async def test_apply_one_title_h1_mismatch_applies(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.2 — the code TODO P5.1 names, end to end through the REAL apply_fix.

        apply_fix is deliberately NOT patched here: the assertion is the meta key
        and value that reached WordPress, so both halves of the record fix are
        exercised rather than described.
        """
        api_client, job_id = seeded_job
        wp = _FakeWP()
        with _WPHarness(creds, wp=wp):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id,
                    "page_url": _PAGE,
                    "issue_code": "TITLE_H1_MISMATCH",
                    "proposed_value": "Our Programs",
                },
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True, f"apply-one failed: {body}"
        assert body["error"] is None
        assert wp.patches == [("pages/12", {"meta": {"_yoast_wpseo_title": "Our Programs"}})], (
            f"wrong WordPress write: {wp.patches!r}"
        )

    @pytest.mark.asyncio
    async def test_apply_one_post_not_found_is_404(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.6 — an unresolvable page URL is its own error, not a WP failure."""
        api_client, job_id = seeded_job
        with _WPHarness(creds, post_info=None):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id,
                    "page_url": "https://example.com/not-a-post",
                    "issue_code": "TITLE_TOO_LONG",
                    "proposed_value": "x",
                },
                headers=auth_headers,
            )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "POST_NOT_FOUND"


# ---------------------------------------------------------------------------
# 3.3 — an unfixable code is refused, and refused BEFORE any WordPress call
# ---------------------------------------------------------------------------


class TestApplyOneRefusesUnfixableCodes:
    @pytest.mark.asyncio
    async def test_apply_one_unfixable_code_is_refused_before_any_wp_call(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.3 — adversarial: asserts apply_fix was NEVER awaited.

        Asserting only the 400 would still pass if someone later "passed the code
        through and let WordPress decide" while keeping the status. The call count
        is what pins the guarantee.
        """
        api_client, job_id = seeded_job
        spy = AsyncMock(return_value=(True, None))
        with _WPHarness(creds), patch("api.routers.link_router.apply_fix", spy):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id,
                    "page_url": _PAGE,
                    "issue_code": "H1_MISSING",     # real code, not wp-fixable
                    "proposed_value": "anything",
                },
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "CODE_NOT_FIXABLE"
        assert "H1_MISSING" in r.json()["error"]["message"]
        spy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_every_code_the_panel_offers_is_accepted(self, api_client, auth_headers,
                                                           seeded_job, creds):
        """3.3b — the refusal must not catch a code the panel legitimately offers.

        Guards the other direction of the same branch: a too-broad CODE_NOT_FIXABLE
        would disable the whole feature and 3.3 alone would still be green.
        """
        api_client, job_id = seeded_job
        for code in sorted(_CODE_TO_FIELD):
            spy = AsyncMock(return_value=(True, None))
            with _WPHarness(creds), patch("api.routers.link_router.apply_fix", spy):
                r = await api_client.post(
                    "/api/fixes/apply-one",
                    json={
                        "job_id": job_id, "page_url": _PAGE,
                        "issue_code": code, "proposed_value": "a value",
                    },
                    headers=auth_headers,
                )
            assert r.status_code == 200, f"{code} was refused: {r.text}"
            spy.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3.4 / 3.5 — wp-value returns the key the panel actually reads
# ---------------------------------------------------------------------------


class TestWpValueResponseContract:
    @pytest.mark.asyncio
    async def test_wp_value_returns_the_key_the_panel_reads(
        self, api_client, auth_headers, creds
    ):
        """3.4 — the key is read out of FixInlinePanel.jsx, not spelled here.

        Renaming either side alone turns this red. The value is asserted too, so
        a response that always carries `current_value: None` does not pass.
        """
        from pathlib import Path
        import re

        panel = (Path(__file__).resolve().parent.parent / "frontend" / "src"
                 / "components" / "FixInlinePanel.jsx").read_text()
        keys = set(re.findall(r"data\.(\w+)\s*\?\?", panel))
        assert keys, "FixInlinePanel no longer reads a value off the wp-value response"

        with _WPHarness(creds), patch(
            "api.routers.link_router.get_current_value",
            AsyncMock(return_value="Living Systems — Home"),
        ):
            r = await api_client.get(
                f"/api/fixes/wp-value?page_url={_PAGE}&field=seo_title",
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in keys:
            assert key in body, (
                f"FixInlinePanel.jsx reads data.{key} from /api/fixes/wp-value, "
                f"but the response carries {sorted(body)}"
            )
            assert body[key] == "Living Systems — Home", (
                f"data.{key} did not carry the WordPress value"
            )

    @pytest.mark.asyncio
    async def test_the_vitest_fixture_matches_the_endpoint(
        self, api_client, auth_headers, creds
    ):
        """3.4b — pin the vitest mock's shape to the server's actual response.

        The vitest suite was green for weeks against a response the server never
        sent, because each test hand-wrote its own mock object. The mocks now come
        from frontend/src/test/wpValueResponse.js, and this test is what stops that
        file drifting in turn: a key added, removed or renamed on either side turns
        it red. Without it the fixture is just a tidier place to be wrong.
        """
        from pathlib import Path
        import re

        fixture = (Path(__file__).resolve().parent.parent / "frontend" / "src"
                   / "test" / "wpValueResponse.js").read_text()
        body = re.search(r"return \{(.*?)\n\s*\}", fixture, re.S)
        assert body, "wpValueResponse.js no longer returns an object literal"
        fixture_keys = set(re.findall(r"^\s*(\w+)\s*[,:]", body.group(1), re.M))

        with _WPHarness(creds), patch(
            "api.routers.link_router.get_current_value", AsyncMock(return_value="v"),
        ):
            r = await api_client.get(
                f"/api/fixes/wp-value?page_url={_PAGE}&field=seo_title",
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        assert fixture_keys == set(r.json()), (
            "the vitest wp-value fixture drifted from the endpoint.\n"
            f"  only in fixture:  {sorted(fixture_keys - set(r.json()))}\n"
            f"  only in response: {sorted(set(r.json()) - fixture_keys)}"
        )

    @pytest.mark.asyncio
    async def test_wp_value_unknown_field_is_400_not_a_null_value(
        self, api_client, auth_headers, creds
    ):
        """3.5 — a bad field name and an empty field must not look identical (P14).

        get_current_value returns None for a field it does not know, which the
        panel renders as "WordPress has no value here".
        """
        with _WPHarness(creds):
            r = await api_client.get(
                f"/api/fixes/wp-value?page_url={_PAGE}&field=not_a_field",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "UNKNOWN_FIELD"

    @pytest.mark.asyncio
    async def test_wp_value_accepts_every_field_the_panel_names(
        self, api_client, auth_headers, creds
    ):
        """3.5b — the UNKNOWN_FIELD guard must not reject a real field."""
        for field in sorted(_FIELD_SPECS):
            with _WPHarness(creds), patch(
                "api.routers.link_router.get_current_value",
                AsyncMock(return_value="v"),
            ):
                r = await api_client.get(
                    f"/api/fixes/wp-value?page_url={_PAGE}&field={field}",
                    headers=auth_headers,
                )
            assert r.status_code == 200, f"{field} was rejected: {r.text}"


# ---------------------------------------------------------------------------
# 3.7 / 3.8 / 3.9 — P5.1b: the two one-click codes reach WordPress
# ---------------------------------------------------------------------------


class TestPredefinedOneClickFixes:
    @pytest.mark.asyncio
    async def test_wp_value_publishes_the_predefined_value_for_one_click_fields(
        self, api_client, auth_headers, creds
    ):
        """3.7 — asserts against PREDEFINED_FIX_VALUES, never the literal "always".

        A test spelling the literal would stay green while the constant moved and
        the two sides drifted (P32).
        """
        with _WPHarness(creds), patch(
            "api.routers.link_router.get_current_value", AsyncMock(return_value=None),
        ):
            r = await api_client.get(
                f"/api/fixes/wp-value?page_url={_PAGE}&field=sitemap_include",
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        assert r.json()["predefined_value"] == PREDEFINED_FIX_VALUES["sitemap_include"]

    @pytest.mark.asyncio
    async def test_wp_value_predefined_is_null_for_a_free_text_field(
        self, api_client, auth_headers, creds
    ):
        """3.7b — the panel switches mode on this key, so it must not be truthy
        for a field the user is supposed to type into."""
        with _WPHarness(creds), patch(
            "api.routers.link_router.get_current_value", AsyncMock(return_value="t"),
        ):
            r = await api_client.get(
                f"/api/fixes/wp-value?page_url={_PAGE}&field=seo_title",
                headers=auth_headers,
            )
        assert r.json()["predefined_value"] is None

    @pytest.mark.asyncio
    async def test_apply_one_fills_a_blank_predefined_value_from_the_constant(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.8 — NOT_IN_SITEMAP with no body value must still reach WordPress.

        For a predetermined field an empty body is a missing constant, not a
        missing edit. Asserted through the real apply_fix on the meta actually
        written.
        """
        api_client, job_id = seeded_job
        wp = _FakeWP()
        with _WPHarness(creds, wp=wp):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id, "page_url": _PAGE,
                    "issue_code": "NOT_IN_SITEMAP", "proposed_value": "",
                },
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True, r.json()
        assert wp.patches == [(
            "pages/12",
            {"meta": {"_yoast_wpseo_sitemap-include":
                      PREDEFINED_FIX_VALUES["sitemap_include"]}},
        )], f"wrong WordPress write: {wp.patches!r}"

    @pytest.mark.asyncio
    async def test_apply_one_blank_value_on_a_free_text_field_is_still_refused(
        self, api_client, auth_headers, seeded_job, creds
    ):
        """3.9 — the adversarial half of 3.8.

        3.8 alone passes if the substitution is written as "blank ⇒ use whatever we
        can find", which would let an empty title overwrite a live one. This pins
        the substitution to the two predetermined fields.
        """
        api_client, job_id = seeded_job
        wp = _FakeWP()
        with _WPHarness(creds, wp=wp):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id, "page_url": _PAGE,
                    "issue_code": "TITLE_TOO_LONG", "proposed_value": "   ",
                },
                headers=auth_headers,
            )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is False
        assert "empty" in (r.json()["error"] or "").lower()
        assert wp.patches == [], "a blank seo_title reached WordPress"
