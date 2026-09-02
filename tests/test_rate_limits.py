"""The rate limits are bounds, keyed on the bearer token — the first 429 the suite has seen.

Spec:    docs/pending/2026-09-02_phase1-trust-holes.md#P1.1
Tests:   this file

Before this file, `tests/conftest.py` set RATE_LIMIT_ENABLED=false, the limit
strings flipped to 10000/hour at import, and the limiter keyed on a header the
caller controls. Three reasons no test could observe a limit, and none did.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from api.services import rate_limiter as rl


def _request(headers: dict | None = None, host: str = "203.0.113.9") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "method": "GET", "path": "/x", "headers": raw,
             "client": (host, 1234), "query_string": b""}
    return Request(scope)


class TestKey:
    def test_key_is_token_hash_not_forwarded_header(self):
        a = rl.rate_limit_key(_request({"Authorization": "Bearer secret-1", "X-Forwarded-For": "10.0.0.1"}))
        b = rl.rate_limit_key(_request({"Authorization": "Bearer secret-1", "X-Forwarded-For": "10.0.0.2"}, host="198.51.100.7"))
        assert a == b, "the same token must land in one bucket whatever the caller puts in the headers"
        assert "secret-1" not in a and a.startswith("tok:")

    def test_different_tokens_are_different_buckets(self):
        a = rl.rate_limit_key(_request({"Authorization": "Bearer one"}))
        b = rl.rate_limit_key(_request({"Authorization": "Bearer two"}))
        assert a != b

    def test_no_token_falls_back_to_the_socket_address(self):
        k = rl.rate_limit_key(_request({"X-Forwarded-For": "10.0.0.1"}, host="203.0.113.9"))
        assert k == "ip:203.0.113.9", "the forwarded header must never be the key"

    def test_limit_strings_are_the_documented_values(self):
        """P29: docs/thresholds.md 'API rate limits' pins these."""
        assert (rl.CRAWL_START_LIMIT, rl.EXPORT_LIMIT, rl.AI_ANALYSIS_LIMIT, rl.DETAILS_LIMIT) == (
            "10/hour", "30/hour", "60/hour", "60/hour")


@pytest.fixture
def live_limiter():
    """Switch the shared limiter on for one test and clear its buckets after."""
    rl.limiter.reset()
    rl.limiter.enabled = True
    try:
        yield rl.limiter
    finally:
        rl.limiter.enabled = False
        rl.limiter.reset()


class TestLimitFires:
    # /export/pdf on an unknown job is the cheapest limited route (csv is not limited): it is
    # counted on entry and returns 404 without touching the network.
    PATH = "/api/crawl/no-such-job/export/pdf"

    async def test_limit_fires_with_the_real_strings(self, api_client, auth_headers, live_limiter):
        codes = [(await api_client.get(self.PATH, headers=auth_headers)).status_code for _ in range(31)]
        assert codes[:30] == [404] * 30, codes
        assert codes[30] == 429, "the 31st export in an hour must be refused"

    async def test_rotating_forwarded_for_does_not_escape(self, api_client, auth_headers, live_limiter):
        """The exact bypass: a fresh X-Forwarded-For on every call."""
        codes = []
        for n in range(31):
            h = {**auth_headers, "X-Forwarded-For": f"10.0.0.{n}"}
            codes.append((await api_client.get(self.PATH, headers=h)).status_code)
        assert codes[30] == 429, "a rotating forwarded address escaped the limit"

    async def test_disabled_limiter_never_fires(self, api_client, auth_headers):
        rl.limiter.reset()
        assert rl.limiter.enabled is False
        codes = {(await api_client.get(self.PATH, headers=auth_headers)).status_code for _ in range(32)}
        assert codes == {404}
