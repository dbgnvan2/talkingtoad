"""PB1 (ledger GA4/index round-trip) + PB8 (freshness) unit tests.

Spec: docs/functional-specification.md §4.8 (Performance Bundle ingestion)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from api.models.performance import PerformanceRecord
from api.services.performance_freshness import (
    STALENESS_DAYS_DEFAULT,
    days_since,
    earlier,
    is_stale,
    parse_generated_at,
)
from api.services.sqlite_store import SQLiteJobStore


# ── PB1: ledger persists GA4 + index fields, keeps None distinct from 0 ──────


@pytest.fixture
async def store():
    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


async def test_pb1_ga4_and_index_fields_round_trip(store):
    rec = PerformanceRecord(
        url="https://example.org/a", period="2026-07",
        gsc_clicks_mo=40, gsc_impressions_mo=900, gsc_ctr_mo=0.044, gsc_avg_position_mo=8.1,
        ga4_sessions_mo=180, ga4_engaged_sessions_mo=120, ga4_engagement_rate_mo=0.67,
        ga4_conversions_mo=6, ga4_ai_referral_sessions_mo=9,
        index_state="indexed", source_generated_at="2026-08-01T00:00:00Z",
    )
    await store.save_performance_records([rec])
    got = await store.get_performance_records(url="https://example.org/a")
    assert len(got) == 1
    r = got[0]
    assert r.ga4_sessions_mo == 180
    assert r.ga4_engagement_rate_mo == pytest.approx(0.67)
    assert r.ga4_conversions_mo == 6
    assert r.ga4_ai_referral_sessions_mo == 9
    assert r.index_state == "indexed"
    assert r.source_generated_at == "2026-08-01T00:00:00Z"


async def test_pb1_absent_ga4_reads_back_as_none_not_zero(store):
    """P2: 'no GA4 source' must stay distinguishable from 'zero sessions'."""
    rec = PerformanceRecord(
        url="https://example.org/b", period="2026-07",
        gsc_clicks_mo=5, gsc_impressions_mo=50, gsc_ctr_mo=0.1, gsc_avg_position_mo=3.0,
    )
    await store.save_performance_records([rec])
    r = (await store.get_performance_records(url="https://example.org/b"))[0]
    assert r.ga4_sessions_mo is None
    assert r.ga4_conversions_mo is None
    assert r.index_state is None


async def test_pb1_gsc_only_upsert_preserves_prior_ga4(store):
    """Store-layer COALESCE: a later GSC-only write (e.g. legacy /api/gsc/ingest)
    must not wipe GA4 data already in the row (P8 dirty-state)."""
    await store.save_performance_records([PerformanceRecord(
        url="https://example.org/c", period="2026-07",
        ga4_sessions_mo=200, ga4_conversions_mo=4,
    )])
    # Second write for the same (url, period) carries GSC only, GA4 = None.
    await store.save_performance_records([PerformanceRecord(
        url="https://example.org/c", period="2026-07",
        gsc_clicks_mo=12, gsc_impressions_mo=300,
    )])
    got = await store.get_performance_records(url="https://example.org/c")
    assert len(got) == 1, "must upsert, not duplicate"
    r = got[0]
    assert r.gsc_clicks_mo == 12
    assert r.ga4_sessions_mo == 200, "prior GA4 must survive a GSC-only write"
    assert r.ga4_conversions_mo == 4


# ── PB8: freshness helper ────────────────────────────────────────────────────


def test_pb8_parse_generated_at_tolerates_z():
    assert parse_generated_at("2026-08-01T00:00:00Z") is not None
    assert parse_generated_at("not-a-date") is None
    assert parse_generated_at(None) is None


def test_pb8_days_since_and_is_stale():
    today = date(2026, 8, 7)
    assert days_since("2026-08-01T00:00:00Z", today) == 6
    assert is_stale("2026-08-01T00:00:00Z", today) is False           # 6d ago → fresh
    assert is_stale("2026-06-01T00:00:00Z", today) is True            # >35d ago → stale
    assert is_stale(None, today) is None                             # unknown
    # boundary: exactly the threshold is not yet stale
    boundary = date(2026, 8, 7)
    gen = f"{(boundary - timedelta(days=STALENESS_DAYS_DEFAULT)).isoformat()}T00:00:00Z"
    assert is_stale(gen, boundary) is False
    one_more = f"{(boundary - timedelta(days=STALENESS_DAYS_DEFAULT + 1)).isoformat()}T00:00:00Z"
    assert is_stale(one_more, boundary) is True


def test_pb8_earlier_picks_oldest_and_handles_unparseable():
    old, new = "2026-06-01T00:00:00Z", "2026-08-01T00:00:00Z"
    assert earlier(new, old) == old            # oldest wins regardless of arg order
    assert earlier(old, new) == old
    assert earlier("bad", new) == new          # one-sided failure → parseable side
    assert earlier(new, "bad") == new
    assert earlier("bad", "worse") == "bad"    # neither parses → first arg
