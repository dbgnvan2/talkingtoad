"""PB1 round-trip + dirty-state merge on the PRODUCTION store (Redis).

Review F2: the SQLite path is well-covered but Redis is the production store and
its GA4/index merge logic (`redis_store.py` — write GA4 only when present, decode
absent → None, rely on HSET field-merge so a GSC-only write can't wipe GA4) had no
tests. This drives `RedisJobStore` against a field-merging fake so no real Redis is
needed.

Spec: docs/functional-specification.md §4.8 (Performance Bundle ingestion)
"""

from __future__ import annotations

import fnmatch

import pytest

from api.models.performance import PerformanceRecord
from api.services.redis_store import RedisJobStore


class _FakeRedis:
    """Minimal in-memory stand-in for the upstash hash ops the ledger uses.
    `hset(..., values=)` MERGES fields (like real HSET) — the property the
    GSC-only-can't-wipe-GA4 guarantee depends on."""

    def __init__(self):
        self.hashes: dict[str, dict[str, str]] = {}

    async def hset(self, key, values=None):
        self.hashes.setdefault(key, {}).update({k: str(v) for k, v in values.items()})

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def keys(self, pattern):
        return [k for k in self.hashes if fnmatch.fnmatch(k, pattern)]


@pytest.fixture
def redis_store():
    s = RedisJobStore(url="http://fake", token="fake")
    s._r = _FakeRedis()
    return s


async def test_redis_pb1_ga4_and_index_round_trip(redis_store):
    await redis_store.save_performance_records([PerformanceRecord(
        url="https://example.org/a", period="2026-07",
        gsc_clicks_mo=40, ga4_sessions_mo=180, ga4_engagement_rate_mo=0.67,
        ga4_conversions_mo=6, ga4_ai_referral_sessions_mo=9,
        index_state="indexed", source_generated_at="2026-08-01T00:00:00Z",
    )])
    r = (await redis_store.get_performance_records(url="https://example.org/a"))[0]
    assert r.ga4_sessions_mo == 180
    assert r.ga4_engagement_rate_mo == pytest.approx(0.67)
    assert r.ga4_conversions_mo == 6
    assert r.ga4_ai_referral_sessions_mo == 9
    assert r.index_state == "indexed"
    assert r.source_generated_at == "2026-08-01T00:00:00Z"


async def test_redis_absent_ga4_reads_back_as_none_not_zero(redis_store):
    await redis_store.save_performance_records([PerformanceRecord(
        url="https://example.org/b", period="2026-07", gsc_clicks_mo=5,
    )])
    r = (await redis_store.get_performance_records(url="https://example.org/b"))[0]
    assert r.ga4_sessions_mo is None
    assert r.ga4_conversions_mo is None
    assert r.index_state is None


async def test_redis_gsc_only_upsert_preserves_prior_ga4(redis_store):
    """P8 dirty-state on the production store: a later GSC-only write must not
    wipe GA4 already in the hash."""
    await redis_store.save_performance_records([PerformanceRecord(
        url="https://example.org/c", period="2026-07",
        ga4_sessions_mo=200, ga4_conversions_mo=4,
    )])
    await redis_store.save_performance_records([PerformanceRecord(
        url="https://example.org/c", period="2026-07",
        gsc_clicks_mo=12, gsc_impressions_mo=300,
    )])
    recs = await redis_store.get_performance_records(url="https://example.org/c")
    assert len(recs) == 1
    r = recs[0]
    assert r.gsc_clicks_mo == 12
    assert r.ga4_sessions_mo == 200   # preserved
    assert r.ga4_conversions_mo == 4
