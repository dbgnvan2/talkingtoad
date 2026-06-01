"""
Tests for M6.2 — Performance Ledger.

Covers PerformanceRecord model, CrawledPage lifecycle date fields,
and SQLite store save/get/upsert for performance_ledger table.
"""

import pytest
from api.models.performance import PerformanceRecord
from api.models.page import CrawledPage


@pytest.mark.asyncio
async def test_save_and_get(store):
    rec = PerformanceRecord(
        url="https://example.com/page-a",
        period="2026-05",
        created_at="2026-05-01T00:00:00",
        gsc_clicks_mo=100,
        gsc_impressions_mo=5000,
        gsc_ctr_mo=0.02,
        gsc_avg_position_mo=15.3,
    )
    await store.save_performance_records([rec])
    results = await store.get_performance_records(url="https://example.com/page-a")
    assert len(results) == 1
    assert results[0].url == "https://example.com/page-a"
    assert results[0].period == "2026-05"
    assert results[0].gsc_clicks_mo == 100
    assert results[0].gsc_impressions_mo == 5000
    assert results[0].gsc_ctr_mo == 0.02
    assert results[0].gsc_avg_position_mo == 15.3
    assert results[0].created_at == "2026-05-01T00:00:00"
    assert results[0].recorded_at is not None


@pytest.mark.asyncio
async def test_upsert_no_duplicate(store):
    rec1 = PerformanceRecord(
        url="https://x/a", period="2026-05", gsc_clicks_mo=100
    )
    rec2 = PerformanceRecord(
        url="https://x/a", period="2026-05", gsc_clicks_mo=200
    )
    await store.save_performance_records([rec1])
    await store.save_performance_records([rec2])
    results = await store.get_performance_records(url="https://x/a")
    assert len(results) == 1
    assert results[0].gsc_clicks_mo == 200


@pytest.mark.asyncio
async def test_multiple_periods(store):
    recs = [
        PerformanceRecord(url="https://x/a", period="2026-05", gsc_clicks_mo=100),
        PerformanceRecord(url="https://x/a", period="2026-06", gsc_clicks_mo=150),
    ]
    await store.save_performance_records(recs)
    results = await store.get_performance_records(url="https://x/a")
    assert len(results) == 2
    assert results[0].period == "2026-05"
    assert results[1].period == "2026-06"


@pytest.mark.asyncio
async def test_domain_filter(store):
    recs = [
        PerformanceRecord(url="https://example.com/a", period="2026-05"),
        PerformanceRecord(url="https://example.com/b", period="2026-05"),
        PerformanceRecord(url="https://other.org/c", period="2026-05"),
    ]
    await store.save_performance_records(recs)
    results = await store.get_performance_records(domain="https://example.com")
    assert len(results) == 2
    assert all(r.url.startswith("https://example.com") for r in results)


@pytest.mark.asyncio
async def test_crawledpage_date_fields():
    page = CrawledPage(
        url="https://example.com/p",
        job_id="test-job",
        status_code=200,
        page_created_at="2026-01-15T10:00:00",
        last_technical_improvement_at="2026-06-01T12:00:00",
    )
    assert page.page_created_at == "2026-01-15T10:00:00"
    assert page.last_technical_improvement_at == "2026-06-01T12:00:00"
    d = page.model_dump()
    assert d["page_created_at"] == "2026-01-15T10:00:00"
    assert d["last_technical_improvement_at"] == "2026-06-01T12:00:00"


@pytest.mark.asyncio
async def test_empty_list_noop(store):
    await store.save_performance_records([])  # no crash


@pytest.mark.asyncio
async def test_get_nonexistent_url(store):
    results = await store.get_performance_records(url="https://no-such-url.com/x")
    assert results == []


@pytest.mark.asyncio
async def test_upsert_preserves_created_at_when_null(store):
    """COALESCE in upsert: if a re-save has created_at=None, the original is kept."""
    rec1 = PerformanceRecord(
        url="https://x/b", period="2026-05", created_at="2026-01-01T00:00:00",
        gsc_clicks_mo=10,
    )
    rec2 = PerformanceRecord(
        url="https://x/b", period="2026-05", created_at=None,
        gsc_clicks_mo=20,
    )
    await store.save_performance_records([rec1])
    await store.save_performance_records([rec2])
    results = await store.get_performance_records(url="https://x/b")
    assert len(results) == 1
    assert results[0].gsc_clicks_mo == 20
    assert results[0].created_at == "2026-01-01T00:00:00"


@pytest.mark.asyncio
async def test_get_all_no_filter(store):
    """get_performance_records() with no filters returns all records."""
    recs = [
        PerformanceRecord(url="https://a.com/1", period="2026-05"),
        PerformanceRecord(url="https://b.com/2", period="2026-05"),
    ]
    await store.save_performance_records(recs)
    results = await store.get_performance_records()
    assert len(results) == 2
