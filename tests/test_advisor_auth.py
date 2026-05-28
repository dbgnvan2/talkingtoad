"""
Integration tests for bearer auth on advisor router endpoints (v2.3 / M0.5).

Before v2.3, the advisor router in api/routers/advisor.py was registered without
`dependencies=[Depends(require_auth)]`, leaving all six endpoints public:

    POST /api/ai/advisor
    POST /api/ai/advisor/prompt
    POST /api/ai/rewriter
    POST /api/ai/rewrite-url
    POST /api/ai/geo-report
    GET  /api/ai/geo-report/pages

This burned AI credits per request and exposed /rewrite-url as an
unauthenticated SSRF vector (since /rewrite-url fetches arbitrary URLs
server-side).

These tests are CLAUDE.md "API Contract Tests (Non-Negotiable)" — they assert
that every endpoint on this router rejects unauthenticated requests. If anyone
removes the auth dependency or accidentally registers a new endpoint on this
router without auth, these tests catch it.

Auth pattern follows test_api.py "TestAuth" — uses the shared `api_client` and
`auth_headers` fixtures from conftest.py (AUTH_TOKEN is set to "test-token"
for the test process).
"""

from __future__ import annotations

import pytest

# Note: pytest.ini sets `asyncio_mode = auto`, so async tests are detected
# automatically. The synchronous architecture test below intentionally is not
# async, so we don't use a module-level pytest.mark.asyncio.


# ---------------------------------------------------------------------------
# Endpoints under test
# ---------------------------------------------------------------------------

# Tuple of (method, path, minimal_body_if_post). Body shape is irrelevant
# for auth tests — the auth check fires before any body validation.
ADVISOR_ENDPOINTS = [
    ("post", "/api/ai/advisor", {"url": "https://example.com"}),
    ("post", "/api/ai/advisor/prompt", {"report_json": {}}),
    ("post", "/api/ai/rewriter", {"content": "x", "prompt": "y"}),
    ("post", "/api/ai/rewrite-url", {"url": "https://example.com", "prompt": "y"}),
    ("post", "/api/ai/geo-report", {"job_id": "x"}),
    ("get", "/api/ai/geo-report/pages?job_id=x", None),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAdvisorRouterAuth:
    """Every endpoint on the advisor router must require bearer auth."""

    @pytest.mark.parametrize("method,path,body", ADVISOR_ENDPOINTS)
    async def test_endpoint_rejects_missing_auth(
        self, api_client, method, path, body
    ):
        """Calling without an Authorization header → 401 UNAUTHORIZED.

        Adversarial: this is the exact attack the missing dependency enabled.
        Pre-v2.3, every endpoint here returned 200 + executed work (or 422 for
        body validation) without any auth check.
        """
        if method == "post":
            r = await api_client.post(path, json=body)
        else:
            r = await api_client.get(path)

        assert r.status_code == 401, (
            f"{method.upper()} {path} returned {r.status_code} without auth; "
            f"expected 401. Body: {r.text[:200]}"
        )
        # Matches the structured error shape from api/services/auth.py
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize("method,path,body", ADVISOR_ENDPOINTS)
    async def test_endpoint_rejects_wrong_bearer_token(
        self, api_client, method, path, body
    ):
        """Calling with the wrong bearer token → 401 UNAUTHORIZED."""
        bad_headers = {"Authorization": "Bearer not-the-token"}
        if method == "post":
            r = await api_client.post(path, json=body, headers=bad_headers)
        else:
            r = await api_client.get(path, headers=bad_headers)

        assert r.status_code == 401, (
            f"{method.upper()} {path} returned {r.status_code} with bad token; "
            f"expected 401."
        )
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize("method,path,body", ADVISOR_ENDPOINTS)
    async def test_endpoint_accepts_valid_bearer_token(
        self, api_client, auth_headers, method, path, body
    ):
        """Calling with the correct bearer token must NOT return 401.

        The downstream handler may return 200 / 422 / 500 / etc. depending on
        body, store state, or AI provider availability. We don't care — we
        only assert the auth layer let the request through.
        """
        if method == "post":
            r = await api_client.post(path, json=body, headers=auth_headers)
        else:
            r = await api_client.get(path, headers=auth_headers)

        assert r.status_code != 401, (
            f"{method.upper()} {path} returned 401 with valid auth headers; "
            f"the auth dependency may be misconfigured. Body: {r.text[:200]}"
        )


class TestAdvisorRouterRegistration:
    """Architecture test — protect the router declaration itself.

    Per CLAUDE.md self-review protocol: 'What would a correct-looking but wrong
    result look like?' Answer: a future commit removes `dependencies=[...]`
    from the router declaration, and all the per-endpoint tests above still
    pass because they only check behaviour for one specific bad call.

    This test inspects the router object directly so a structural regression
    fails fast.
    """

    def test_advisor_router_has_require_auth_dependency(self):
        """The advisor router's dependency list must contain require_auth."""
        from api.routers.advisor import router
        from api.services.auth import require_auth

        # FastAPI stores router-level dependencies on `router.dependencies`
        # as a list of Depends() instances. We check the dependency callable.
        dep_callables = [d.dependency for d in router.dependencies]
        assert require_auth in dep_callables, (
            "api/routers/advisor.py router was registered without "
            "dependencies=[Depends(require_auth)]. Every endpoint on this "
            "router is now reachable unauthenticated. Re-add the dependency."
        )
