"""
Rate limiting for the TalkingToad API (spec §6.6).

Limits:
  - 10 crawl starts per hour per IP
  - 3 concurrent crawls per IP  (enforced separately in the router)

Uses slowapi with in-memory storage for dev; Redis-backed in prod when
DATABASE_URL is set to a Redis URL.

Set RATE_LIMIT_ENABLED=false to disable rate limiting (useful in tests).
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"

# One limiter instance shared across the app
limiter = Limiter(key_func=get_remote_address, enabled=_enabled)

# Limit strings applied per endpoint
CRAWL_START_LIMIT = "10/hour" if _enabled else "10000/hour"
