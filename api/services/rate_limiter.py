"""
Rate limiting for the TalkingToad API (spec §6.6).

Limits (per bearer token — see ``rate_limit_key``):
  - 10 crawl starts per hour
  - 30 exports per hour
  - 60 AI analyses per hour
  - 60 live page-details fetches per hour

Set RATE_LIMIT_ENABLED=false to disable rate limiting (the test suite does).
The limit strings are constants: only ``limiter.enabled`` is env-controlled,
so a test can switch the limiter on at runtime and observe a real 429. (Until
2026-09-02 the strings themselves flipped to 10000/hour when disabled, which is
why no test in the repo had ever seen a 429.)
"""

import hashlib
import os

from fastapi import Request
from slowapi import Limiter

_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"


def rate_limit_key(request: Request) -> str:
    """Bucket key: the bearer token's hash, else the direct socket address.

    Phase 1 (2026-09-02, docs/pending/2026-09-02_phase1-trust-holes.md#P1.1).
    The container runs uvicorn with ``--forwarded-allow-ips=*``, so the client
    address slowapi used to key on was the first, client-supplied
    ``X-Forwarded-For`` entry — a token holder rotating that header got a fresh
    bucket per request and no limit ever fired. Every /api route requires the
    token, so keying on it makes each limit a real bound for the caller who
    holds it, whatever headers they send. The token itself never becomes a
    storage key or a log line: only its SHA-256 does.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and auth[7:].strip():
        return "tok:" + hashlib.sha256(auth[7:].strip().encode()).hexdigest()[:32]
    client = request.client
    return "ip:" + (client.host if client else "unknown")


# One limiter instance shared across the app
limiter = Limiter(key_func=rate_limit_key, enabled=_enabled)

# Limit strings applied per endpoint (docs/thresholds.md "API rate limits")
CRAWL_START_LIMIT = "10/hour"
EXPORT_LIMIT = "30/hour"
AI_ANALYSIS_LIMIT = "60/hour"
# D6 — /page-details fetches the live page on every click, so it is a fetch
# amplifier pointed at the operator's own site. Matched to AI_ANALYSIS_LIMIT:
# an operator-initiated single-page fetch, cheaper than an AI call and far
# cheaper than a crawl.
DETAILS_LIMIT = "60/hour"
