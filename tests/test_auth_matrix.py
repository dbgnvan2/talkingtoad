"""Every /api route rejects a missing or wrong bearer token — derived from the app, not a list.

Purpose: eight router test files each carried a hand-maintained (method, path)
         list and a byte-identical "returns 401" body — 16 duplicate groups, 42
         tests, and a new endpoint was covered only if someone remembered to add
         it to the right list. This file walks the registered routes instead, so
         an endpoint that forgets `require_auth` fails here the day it is added.
Spec:    CLAUDE.md "Security Defaults" — /api/health is the only public endpoint.
Tests:   this file (replaces the per-router auth classes, 2026-09-02)

The 401 must come from the auth dependency BEFORE validation, so no body is
sent and path parameters are filled with a placeholder: a 422 or 404 in place
of a 401 is a route that let an anonymous caller past the door.
"""

from __future__ import annotations

import re

import pytest

from api.main import app

# Routes that are public on purpose. Adding to this list is a security decision:
# say why, and keep it short.
_PUBLIC: dict[str, str] = {
    "/api/health": "liveness probe — CLAUDE.md names it the only public endpoint",
}

# FastAPI built-ins, not application routes.
_NOT_APP = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def _api_routes() -> list[tuple[str, str]]:
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if not path.startswith("/api") or path in _NOT_APP or path in _PUBLIC:
            continue
        concrete = re.sub(r"\{[^}]+\}", "x", path)
        for m in sorted(methods - {"HEAD", "OPTIONS"}):
            out.append((m.lower(), concrete))
    return sorted(set(out))


ROUTES = _api_routes()
_IDS = [f"{m.upper()} {p}" for m, p in ROUTES]


def test_the_matrix_is_not_empty():
    """A refactor that stopped registering routers would otherwise pass vacuously."""
    assert len(ROUTES) > 80, f"only {len(ROUTES)} /api routes registered"


@pytest.mark.parametrize("method,path", ROUTES, ids=_IDS)
async def test_missing_token_is_401(api_client, method, path):
    r = await api_client.request(method, path)
    assert r.status_code == 401, (
        f"{method.upper()} {path} returned {r.status_code} without a token — "
        f"if this route is meant to be public, add it to _PUBLIC with a reason")
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("method,path", ROUTES, ids=_IDS)
async def test_wrong_token_is_401(api_client, method, path):
    r = await api_client.request(method, path, headers={"Authorization": "Bearer not-the-token"})
    assert r.status_code == 401, f"{method.upper()} {path} accepted a wrong bearer token"


# Routes whose ONLY test is the 401 pair above. The per-router lists this file
# replaced hid that fact — a path in a list looked covered. Each entry is a
# behavioural contract test still to write (TODO.md, 2026-09-02); the text-
# based guard in test_endpoint_coverage.py needs the literal path to see it.
_AUTH_ONLY_COVERAGE = [
    "/api/crawl/recent",
    "/api/crawl/{job_id}/export/ai-images-pdf",
    "/api/crawl/{job_id}/fix-focus/regenerate",
    "/api/crawl/{job_id}/images/analyze-ai",
]


def test_auth_only_routes_still_exist():
    """An entry for a route that was removed is a stale TODO, not coverage."""
    paths = {getattr(r, "path", "") for r in app.routes}
    for p in _AUTH_ONLY_COVERAGE:
        assert p in paths, f"_AUTH_ONLY_COVERAGE names {p}, which is no longer registered"


def test_public_routes_really_exist():
    """A stale allowlist entry is a public route nobody is checking."""
    paths = {getattr(r, "path", "") for r in app.routes}
    for p in _PUBLIC:
        assert p in paths, f"_PUBLIC names {p}, which is not a registered route"
