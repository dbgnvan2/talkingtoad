"""CI guard: every registered API endpoint must be touched by at least one test.

v2.5 M8.8 — prevents the v2.0 fixes.py refactor disaster from recurring,
where 30+ endpoints existed in the codebase but had zero contract tests
and silently went un-wired. With this guard, adding a new endpoint with
no test causes the build to fail with a clear list of what to test.

The check is intentionally generous: it looks for ANY test that issues
an HTTP call to the endpoint's path (regex over test files). Doesn't
care which test or how deep. Just that someone exercises the path.

Allowlist exists for:
- /api/health: trivially covered by a non-typical test
- /docs, /redoc, /openapi.json: FastAPI built-ins (not our routes)
"""

from __future__ import annotations

import os
import re

import pytest

from api.main import app


# Endpoints intentionally excluded from the coverage check.
_ALLOWLIST: set[str] = {
    # FastAPI built-ins, not application endpoints
    "/docs",
    "/redoc",
    "/openapi.json",
    "/docs/oauth2-redirect",
}

# Routes auto-skipped: anything not under /api/ (we only care about API
# contract coverage; static assets and root redirects don't apply).
_SCOPE_PREFIX = "/api"


def _registered_api_paths() -> set[str]:
    """All API paths registered on the FastAPI app, normalised."""
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or not path.startswith(_SCOPE_PREFIX):
            continue
        if path in _ALLOWLIST:
            continue
        paths.add(path)
    return paths


def _path_to_test_pattern(path: str) -> str:
    """Convert a FastAPI path with {param} placeholders to a regex matching
    test-file string literals.

    The match is intentionally loose:
        /api/fixes/{job_id}        -> matches "/api/fixes/SOMETHING"
        /api/crawl/{id}/export/csv -> matches "/api/crawl/SOMETHING/export/csv"
    Test code typically writes literals like "/api/crawl/abc-123/export/csv",
    so the {param} segments become "[^/\"]+" in the search regex.
    """
    # Escape regex specials EXCEPT we'll handle path params below.
    parts = []
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            parts.append(r"[^/\"' )]+")
        else:
            parts.append(re.escape(segment))
    return "/".join(parts)


def _read_all_test_files_content() -> str:
    """Concatenate all test file contents into one searchable blob."""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    blob_parts: list[str] = []
    for fname in os.listdir(tests_dir):
        if not fname.startswith("test_") or not fname.endswith(".py"):
            continue
        with open(os.path.join(tests_dir, fname)) as f:
            blob_parts.append(f.read())
    return "\n".join(blob_parts)


@pytest.fixture(scope="module")
def _all_tests_content() -> str:
    return _read_all_test_files_content()


# ===================================================================
# The actual guard
# ===================================================================


class TestEndpointCoverage:
    """Every /api/* endpoint must be referenced by at least one test."""

    def test_every_registered_api_path_has_at_least_one_test_reference(
        self, _all_tests_content
    ):
        api_paths = _registered_api_paths()
        assert api_paths, "Sanity check: no /api/ paths found — did the app load?"

        uncovered: list[str] = []
        for path in sorted(api_paths):
            pattern = _path_to_test_pattern(path)
            if not re.search(pattern, _all_tests_content):
                uncovered.append(path)

        assert not uncovered, (
            "v2.5 M8.8 endpoint coverage guard: the following /api/* paths "
            "are registered but no test file references them. Add at least "
            "an auth/validation contract test (see tests/test_title_router.py "
            "for the established pattern):\n\n  "
            + "\n  ".join(uncovered)
            + "\n\nIf an endpoint is genuinely test-exempt (e.g. internal-only), "
            "add its path to _ALLOWLIST in this file with a comment explaining why."
        )


class TestAllowlistDiscipline:
    """The allowlist itself must stay small and intentional."""

    def test_allowlist_does_not_grow_unchecked(self):
        """Adversarial: catch a future commit that adds tons of paths to
        _ALLOWLIST to silence the coverage guard. Cap at 10 entries; if you
        legitimately need more, bump this number AND justify in the commit."""
        assert len(_ALLOWLIST) <= 10, (
            f"_ALLOWLIST has {len(_ALLOWLIST)} entries — keep it small. "
            "Each exemption should be justified in a comment."
        )

    def test_allowlist_entries_dont_collide_with_real_app_routes(self):
        """Allowlist entries must actually correspond to real routes, OR
        be FastAPI built-ins. Catches typos."""
        api_paths = _registered_api_paths()
        fastapi_builtins = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
        for entry in _ALLOWLIST:
            assert entry in api_paths or entry in fastapi_builtins, (
                f"_ALLOWLIST entry {entry!r} matches no registered route "
                f"and is not a FastAPI built-in. Typo?"
            )
