"""
Integration tests for bearer auth on the AI router (v2.6 M2 prep / Cycle X).

Mirrors the pattern of `test_advisor_auth.py`. The AI router in
`api/routers/ai.py` is declared with `dependencies=[Depends(require_auth)]`
at the router level (line 18) — every endpoint inherits the auth check.
These tests enforce that contract:

    POST /api/ai/analyze
    GET  /api/ai/test
    POST /api/ai/page-advisor
    POST /api/ai/site-advisor
    POST /api/ai/image/analyze-geo
    POST /api/ai/image/apply-geo-metadata

These are CLAUDE.md "API Contract Tests (Non-Negotiable)" — they assert
that every endpoint on this router rejects unauthenticated requests. If
anyone removes the router-level dependency or adds a new endpoint
without verifying it inherits auth, these tests catch it.

Body shape is irrelevant — the auth check fires before any body
validation. Bodies below are minimal-realistic so the file also
documents the contract for future maintainers.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Endpoints under test (method, path, minimal_body)
# ---------------------------------------------------------------------------

AI_ENDPOINTS = [
    ("post", "/api/ai/analyze", {"page_url": "https://example.com", "html": "<html></html>"}),
    ("get", "/api/ai/test", None),
    ("post", "/api/ai/page-advisor", {"job_id": "x", "page_url": "https://example.com"}),
    ("post", "/api/ai/site-advisor", {"job_id": "x"}),
    ("post", "/api/ai/image/analyze-geo", {"job_id": "x", "image_url": "https://example.com/img.jpg"}),
    ("post", "/api/ai/image/apply-geo-metadata", {"job_id": "x", "image_url": "https://example.com/img.jpg", "alt": "x", "description": "y", "caption": "z"}),
]


class TestAIRouterAuth:
    """Every endpoint on /api/ai/* must require bearer auth.

    Pre-Cycle-X, none of these endpoints had a 401 contract test —
    even though the router-level dependency was already in place, the
    invariant was unprotected: a future commit could have removed
    `dependencies=[...]` from the router declaration and every test
    would still pass.
    """

    @pytest.mark.parametrize("method,path,body", AI_ENDPOINTS)
    async def test_endpoint_rejects_missing_auth(
        self, api_client, method, path, body
    ):
        """Calling without an Authorization header → 401 UNAUTHORIZED."""
        if method == "post":
            r = await api_client.post(path, json=body)
        else:
            r = await api_client.get(path)

        assert r.status_code == 401, (
            f"{method.upper()} {path} returned {r.status_code} without auth; "
            f"expected 401. Body: {r.text[:200]}"
        )
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize("method,path,body", AI_ENDPOINTS)
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


class TestAIRouterRegistration:
    """Architecture test — protect the router declaration itself.

    Same self-review reasoning as TestAdvisorRouterRegistration: the
    behavioural tests above only catch a regression on one specific
    call. A structural test against the router object catches the
    case where someone removes `dependencies=[...]` and registers a
    new endpoint that gets no parameterized coverage.
    """

    def test_ai_router_has_require_auth_dependency(self):
        """The AI router's dependency list must contain require_auth."""
        from api.routers.ai import router
        from api.services.auth import require_auth

        dep_callables = [d.dependency for d in router.dependencies]
        assert require_auth in dep_callables, (
            "api/routers/ai.py router is missing the router-level "
            "`dependencies=[Depends(require_auth)]` — every AI endpoint "
            "would be public. This is the missing-auth class of bug "
            "that test_advisor_auth.py was created to prevent on the "
            "advisor router; the same protection is needed here."
        )
