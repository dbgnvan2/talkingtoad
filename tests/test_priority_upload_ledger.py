"""U3 — GSC priority upload → Performance Ledger join.

build_ledger_records joins the seed's per-page metrics onto crawled pages using
the same key machinery as /api/performance/ingest, mapping the file's fields to
PerformanceRecord (ctr derived, avg_position→position, inquiries→ga4_conversions).
"""

from __future__ import annotations

from datetime import datetime, timezone

from api.models.page import CrawledPage
from api.services.gsc_priority import build_ledger_records, parse_priority_upload

TARGET = "https://livingsystems.ca"
NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def _crawled(url):
    return CrawledPage(job_id="j1", url=url, status_code=200,
                       crawled_at=NOW)


def test_u3_join_maps_fields_and_derives_ctr():
    seed = parse_priority_upload({"pages": [
        {"url": "https://livingsystems.ca/", "clicks": 138, "impressions": 1494,
         "avg_position": 23.5, "inquiries": 1},
    ]}, TARGET)
    pages = [_crawled("https://livingsystems.ca/")]
    recs = build_ledger_records(seed, pages, period="2026-08", recorded_at=NOW.isoformat())
    assert len(recs) == 1
    r = recs[0]
    assert r.url == "https://livingsystems.ca/"
    assert r.period == "2026-08"
    assert r.gsc_clicks_mo == 138 and r.gsc_impressions_mo == 1494
    assert abs(r.gsc_ctr_mo - 138 / 1494) < 1e-9      # derived
    assert r.gsc_avg_position_mo == 23.5               # avg_position → position
    assert r.ga4_conversions_mo == 1                   # inquiries → GA4 conversions


def test_u3_www_scheme_slash_tolerant_join():
    """A seed https URL joins a crawled http/www/trailing-slash variant."""
    seed = parse_priority_upload({"pages": [
        {"url": "https://livingsystems.ca/counselling", "clicks": 5, "impressions": 50},
    ]}, TARGET)
    pages = [_crawled("https://www.livingsystems.ca/counselling/")]
    recs = build_ledger_records(seed, pages, period="2026-08", recorded_at=NOW.isoformat())
    assert len(recs) == 1
    assert recs[0].url == "https://www.livingsystems.ca/counselling/"


def test_u3_absent_inquiries_stays_none_in_ledger():
    """Sweep #1 (P2): a page with no inquiries writes ga4_conversions_mo=None,
    not 0 — so ranking can't mistake 'unknown' for 'proven zero'."""
    seed = parse_priority_upload({"pages": [
        {"url": "https://livingsystems.ca/", "clicks": 5, "impressions": 50},  # no inquiries
    ]}, TARGET)
    pages = [_crawled("https://livingsystems.ca/")]
    recs = build_ledger_records(seed, pages, period="2026-08", recorded_at=NOW.isoformat())
    assert recs[0].ga4_conversions_mo is None


def test_u3_seed_page_not_crawled_is_skipped():
    """A seed URL with no matching crawled page contributes no ledger row (P2 —
    no phantom record for a page that wasn't scanned)."""
    seed = parse_priority_upload({"pages": [
        {"url": "https://livingsystems.ca/crawled", "clicks": 1, "impressions": 2},
        {"url": "https://livingsystems.ca/not-crawled", "clicks": 9, "impressions": 9},
    ]}, TARGET)
    pages = [_crawled("https://livingsystems.ca/crawled")]
    recs = build_ledger_records(seed, pages, period="2026-08", recorded_at=NOW.isoformat())
    assert [r.url for r in recs] == ["https://livingsystems.ca/crawled"]
