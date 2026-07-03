"""Tests for the 2026-07-03 audit P0 correctness bugs + Phase 5 code-quality fixes.

Each test maps to a remediation item in
docs/review/2026-07-03_remediation-plan.md. See that plan + the audit report
for the finding each fix addresses.
"""

import socket
from unittest.mock import patch

import httpx
import pytest

from api.crawler.issue_checker import _CATALOGUE, _ISSUE_SCORING, check_page, make_issue
from api.crawler.fetcher import fetch_page
from api.crawler.engine import _classify_fetch_error
from api.services.ai_bots import AI_BOTS

# Reuse the comprehensive ParsedPage factory from the issue-checker tests.
from tests.test_issue_checker import _page

_VALID_SEVERITIES = {"critical", "warning", "info"}
_PUBLIC_RESOLUTION = [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
]


# ── R2/R5: scoring-value migration locked in (impact, effort) ─────────────────
_MIGRATED_SCORING = {
    "BROKEN_LINK_5XX": (7, 2), "CANONICAL_EXTERNAL": (5, 3), "CONTENT_STALE": (3, 3),
    "EXTERNAL_CITATIONS_LOW": (5, 2), "FAQ_SCHEMA_MISSING": (2, 2), "GEO_SUMMARY_BURIED": (5, 3),
    "H1_MISSING": (6, 1), "H1_MULTIPLE": (5, 2), "LLMS_TXT_INVALID": (2, 2),
    "LLMS_TXT_MISSING": (3, 1), "ORPHAN_PAGE": (6, 2), "QUERY_COVERAGE_WEAK": (5, 2),
    "QUOTATIONS_MISSING": (4, 2), "REDIRECT_302": (4, 2), "SEMANTIC_DENSITY_LOW": (3, 3),
    "STATISTICS_COUNT_LOW": (5, 2), "THIN_CONTENT": (6, 3), "URL_HAS_SPACES": (5, 2),
    "URL_HAS_UNDERSCORES": (2, 2), "URL_TOO_LONG": (2, 2),
}


@pytest.mark.parametrize("code,expected", sorted(_MIGRATED_SCORING.items()))
def test_scoring_migration_applied(code, expected):
    """The 20 evidence-based Phase-4 scoring changes are present in _ISSUE_SCORING."""
    assert _ISSUE_SCORING[code] == expected


def test_fixability_corrections_applied():
    """BROKEN_LINK_5XX and ORPHAN_PAGE reclassified to content_edit (audit R5)."""
    assert _CATALOGUE["BROKEN_LINK_5XX"].fixability == "content_edit"
    assert _CATALOGUE["ORPHAN_PAGE"].fixability == "content_edit"


# ── R0.5: no invalid severity values in the catalogue ─────────────────────────
def test_all_catalogue_severities_valid():
    """CONTENT_CLOAKING_DETECTED had severity='error', which is not in the
    Severity Literal. Guard the whole catalogue against invalid severities."""
    invalid = {
        code: spec.severity
        for code, spec in _CATALOGUE.items()
        if spec.severity not in _VALID_SEVERITIES
    }
    assert not invalid, f"Invalid severities (must be critical/warning/info): {invalid}"


# ── R-Q1: make_issue fails fast on an unknown code ────────────────────────────
def test_make_issue_unknown_code_raises_keyerror():
    with pytest.raises(KeyError) as exc:
        make_issue("NOT_A_REAL_CODE", "https://example.com/")
    assert "NOT_A_REAL_CODE" in str(exc.value)


def test_make_issue_known_code_still_works():
    issue = make_issue("TITLE_MISSING", "https://example.com/")
    assert issue.code == "TITLE_MISSING"
    assert issue.impact > 0  # populated from _ISSUE_SCORING


# ── R-Q2: catalogue <-> scoring bijection (docstring counts were stale) ───────
def test_scoring_catalogue_bijection():
    assert set(_CATALOGUE) == set(_ISSUE_SCORING)
    assert len(_ISSUE_SCORING) == len(_CATALOGUE) == 151


# ── R0.2: Claude-User honors robots.txt (was wrongly False) ───────────────────
def test_claude_user_honors_robots():
    assert AI_BOTS["Claude-User"]["honors_robots"] is True


def test_chatgpt_and_perplexity_user_still_do_not_honor():
    # These remain non-honoring — the fix is Claude-specific, not category-wide.
    assert AI_BOTS["ChatGPT-User"]["honors_robots"] is False
    assert AI_BOTS["Perplexity-User"]["honors_robots"] is False


def test_user_fetch_recommendation_not_blanket_ineffective():
    """The recommendation must no longer claim Claude-User ignores robots.txt
    or that the block is universally ineffective."""
    spec = _CATALOGUE["AI_BOT_USER_FETCH_BLOCKED"]
    rec = spec.recommendation.lower()
    assert "claude-user" not in rec or "honors robots" in rec
    assert "no effect" not in spec.description.lower()


# ── R0.1: citation misfire quarantined ────────────────────────────────────────
def test_citation_missing_not_emitted_on_substantial_page():
    """With the citation model fed hardcoded-empty data, this code fired on
    every >200-word page. Quarantined until R6 wires a real parser."""
    page = _page(url="https://example.com/long", word_count=800, is_indexable=True)
    codes = {i.code for i in check_page(page)}
    assert "CITATIONS_MISSING_SUBSTANTIAL_CONTENT" not in codes
    assert "CITATIONS_ORPHANED" not in codes
    assert "CITATIONS_SOURCES_INACCESSIBLE" not in codes


# ── R0.4: fetch-error classification ──────────────────────────────────────────
def test_classify_fetch_error_ssrf_returns_none():
    assert _classify_fetch_error("SSRF_BLOCKED: private network") is None


@pytest.mark.parametrize("err,expected", [
    ("ReadTimeout: request timed out", "timeout"),
    ("Connection refused", "connection"),
    ("[Errno 8] nodename nor servname provided", "dns"),
    ("some unexpected error", "other"),
])
def test_classify_fetch_error_types(err, expected):
    assert _classify_fetch_error(err) == expected


# ── R0.3: retry + backoff on transient failures ──────────────────────────────
@pytest.mark.asyncio
async def test_transient_5xx_retried_then_success(monkeypatch):
    monkeypatch.setattr("api.crawler.fetcher._RETRY_BACKOFF_S", 0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, headers={"Content-Type": "text/html"},
                              content=b"<html><body>ok</body></html>")

    transport = httpx.MockTransport(handler)
    with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=_PUBLIC_RESOLUTION):
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page("https://example.com/", client)

    assert result.status_code == 200
    assert len(calls) == 2  # one retry


@pytest.mark.asyncio
async def test_persistent_5xx_still_returns_5xx(monkeypatch):
    monkeypatch.setattr("api.crawler.fetcher._RETRY_BACKOFF_S", 0)
    from api.crawler import fetcher
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=_PUBLIC_RESOLUTION):
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page("https://example.com/", client)

    assert result.status_code == 500
    assert len(calls) == fetcher._MAX_RETRIES + 1  # exhausted retries, still fires downstream


@pytest.mark.asyncio
async def test_network_error_retried_then_success(monkeypatch):
    monkeypatch.setattr("api.crawler.fetcher._RETRY_BACKOFF_S", 0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("Connection refused", request=request)
        return httpx.Response(200, headers={"Content-Type": "text/html"},
                              content=b"<html><body>ok</body></html>")

    transport = httpx.MockTransport(handler)
    with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=_PUBLIC_RESOLUTION):
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page("https://example.com/", client)

    assert result.status_code == 200
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_success_not_retried(monkeypatch):
    monkeypatch.setattr("api.crawler.fetcher._RETRY_BACKOFF_S", 0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, headers={"Content-Type": "text/html"},
                              content=b"<html><body>ok</body></html>")

    transport = httpx.MockTransport(handler)
    with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=_PUBLIC_RESOLUTION):
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page("https://example.com/", client)

    assert result.status_code == 200
    assert len(calls) == 1  # happy path never retried
