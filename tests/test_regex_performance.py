"""AF12 — parsing must not degrade quadratically on a long unbroken token.

Audit: found while authoring code contracts (docs/audit/2026-08-30_full-check-audit.md)

`_EMAIL_RE` used unbounded quantifiers, so on text containing no "@" it retried
from every starting position — quadratic. Measured through `parse_page`:

    120 KB single token   16s
    400 KB single token   41s
    400 KB realistic prose 0.1s   <- the cost is backtracking, not size

A page carrying a long minified or base64 blob in body text would stall the
crawl for the better part of a minute, and a handful of them would dominate a
500-page budget. Bounding the quantifiers to RFC 5321 limits (local part <= 64,
domain <= 255) removes the backtracking without narrowing what is matched.
"""
from __future__ import annotations

import time

import pytest

from api.crawler.fetcher import FetchResult
from api.crawler.parser import _EMAIL_RE, parse_page

BASE = "https://example.com/"

#: Generous ceiling — the fix measures ~0.06s for 400 KB; the pre-fix code
#: took over 40s. Anything in between still means the backtracking is back.
_BUDGET_SECONDS = 5.0


def _page(body: str):
    html = ("<!DOCTYPE html><html lang='en'><head><title>A Reasonably Long Page Title</title>"
            "<meta name='description' content='A description long enough to pass the checks here.'>"
            f"</head><body>{body}</body></html>")
    return parse_page(
        FetchResult(url=BASE, final_url=BASE, status_code=200, headers={},
                    html=html, content_type="text/html"),
        BASE, is_homepage=True)


class TestEmailRegexPerformance:
    @pytest.mark.parametrize("size", [60_000, 400_000])
    def test_af12_long_unbroken_token_is_linear(self, size):
        started = time.time()
        _EMAIL_RE.search("x" * size)
        assert time.time() - started < 1.0, "email regex is backtracking again"

    def test_af12_parse_of_a_large_single_token_page_is_fast(self):
        """The path that actually stalled: _has_contact_info_in_text runs during
        parse_page on the homepage."""
        started = time.time()
        _page("<h1>H</h1><p>" + "x" * 400_000 + "</p>")
        elapsed = time.time() - started
        assert elapsed < _BUDGET_SECONDS, f"parse took {elapsed:.1f}s (pre-fix: >40s)"

    def test_af12_realistic_large_page_still_fast(self):
        """Control: size was never the problem."""
        body = "<h1>H</h1>" + "".join(
            f"<p>{' '.join(['word'] * 100)}</p>" for _ in range(700))
        started = time.time()
        _page(body)
        assert time.time() - started < _BUDGET_SECONDS


class TestEmailRegexCorrectness:
    """Bounding the quantifiers must not change what is matched."""

    @pytest.mark.parametrize("text", [
        "write to info@livingsystems.ca today",
        "Contact: first.last+tag@sub.domain.co.uk",
        "a@b.io",
    ])
    def test_af12_real_addresses_still_match(self, text):
        assert _EMAIL_RE.search(text)

    @pytest.mark.parametrize("text", [
        "no at sign here",
        "just @ alone",
        "trailing@dot.",
    ])
    def test_af12_non_addresses_still_rejected(self, text):
        assert _EMAIL_RE.search(text) is None
