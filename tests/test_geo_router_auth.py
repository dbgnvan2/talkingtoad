"""
Integration tests for bearer auth on the GEO router (v2.6 M2 prep / Cycle X).

Mirrors `test_advisor_auth.py` / `test_ai_router_auth.py`. The GEO router
in `api/routers/geo.py` is declared with
`dependencies=[Depends(require_auth)]` at the router level (line 21) —
every endpoint inherits the auth check. These tests enforce that contract:

    GET    /api/geo/settings
    POST   /api/geo/settings
    DELETE /api/geo/settings
    GET    /api/geo/test
    GET    /api/geo/ai-model
    POST   /api/geo/ai-model

CLAUDE.md "API Contract Tests (Non-Negotiable)" — assert every endpoint
on this router rejects unauthenticated requests. Catches both the
"router dependency removed" and "new endpoint added without inheriting
auth" regression classes.

Body shape is irrelevant for the auth check (it fires before body
validation). Bodies below are minimal-realistic.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Endpoints under test (method, path, minimal_body)
# ---------------------------------------------------------------------------

GEO_ENDPOINTS = [
    ("get", "/api/geo/settings?domain=example.com", None),
    ("post", "/api/geo/settings", {"domain": "example.com", "org_name": "x", "locations": [], "topics": []}),
    ("delete", "/api/geo/settings?domain=example.com", None),
    ("get", "/api/geo/test", None),
    ("get", "/api/geo/ai-model", None),
    ("post", "/api/geo/ai-model", {"provider": "openai", "model": "gpt-4o"}),
]


class TestGEORouterAuth:
    """Every endpoint on /api/geo/* must require bearer auth."""

    @pytest.mark.parametrize("method,path,body", GEO_ENDPOINTS)
    async def test_endpoint_rejects_missing_auth(
        self, api_client, method, path, body
    ):
        """Calling without an Authorization header → 401 UNAUTHORIZED."""
        if method == "post":
            r = await api_client.post(path, json=body)
        elif method == "delete":
            r = await api_client.delete(path)
        else:
            r = await api_client.get(path)

        assert r.status_code == 401, (
            f"{method.upper()} {path} returned {r.status_code} without auth; "
            f"expected 401. Body: {r.text[:200]}"
        )
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.parametrize("method,path,body", GEO_ENDPOINTS)
    async def test_endpoint_rejects_wrong_bearer_token(
        self, api_client, method, path, body
    ):
        """Calling with the wrong bearer token → 401 UNAUTHORIZED."""
        bad_headers = {"Authorization": "Bearer not-the-token"}
        if method == "post":
            r = await api_client.post(path, json=body, headers=bad_headers)
        elif method == "delete":
            r = await api_client.delete(path, headers=bad_headers)
        else:
            r = await api_client.get(path, headers=bad_headers)

        assert r.status_code == 401, (
            f"{method.upper()} {path} returned {r.status_code} with bad token; "
            f"expected 401."
        )
        assert r.json()["error"]["code"] == "UNAUTHORIZED"


class TestGEORouterRegistration:
    """Architecture test — protect the router declaration itself.

    Catches the regression class where someone removes
    `dependencies=[...]` from the router declaration (parameterized
    behavioural tests would all still pass against the new public
    routes until an actual user noticed paid LLM calls being burned
    by unauthenticated traffic)."""

    def test_geo_router_has_require_auth_dependency(self):
        """The GEO router's dependency list must contain require_auth."""
        from api.routers.geo import router
        from api.services.auth import require_auth

        dep_callables = [d.dependency for d in router.dependencies]
        assert require_auth in dep_callables, (
            "api/routers/geo.py router is missing the router-level "
            "`dependencies=[Depends(require_auth)]` — every GEO "
            "endpoint would be public. GEO settings include AI model "
            "selection and locations that should not be exposed."
        )
