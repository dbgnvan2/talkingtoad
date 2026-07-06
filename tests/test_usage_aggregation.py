"""Tests for usage aggregation API (v2.6 M2.6 / Cycle EE).

Per docs/pending/2026-05-29_m2_usage_aggregation_api.md (locked +
3 critique-driven amendments: integer-cents SQL aggregation,
UsageReader as independent class, customer_id auth-derived only).

8 tests: 4 QA evaluator + 4 supporting (per locked plan).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from api.schemas.usage import UsageReport
from api.services.sqlite_store import SQLiteJobStore
from api.services.usage_logger import (
    PeriodTooLargeError,
    UsageReader,
    usage_reader,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def store():
    """Isolated in-memory SQLite store per test."""
    s = SQLiteJobStore(":memory:")
    await s.init()
    yield s
    await s.close()


async def _seed(store: SQLiteJobStore, *records: dict) -> None:
    """Convenience: write several records with sensible defaults."""
    for rec in records:
        full = {
            "customer_id": "alice",
            "provider": "openai",
            "model": "gpt-4o",
            "input_token_count": 100,
            "output_token_count": 50,
            "cost_estimate_usd": 0.01,
            "success": True,
            # Stamp seeded rows inside the fixed May–June 2026 query window
            # used by the aggregation tests. Without this, record_ai_usage
            # defaults the timestamp to now(), so once wall-clock time passes
            # 2026-06-30 the seeded rows fall outside the window and the
            # aggregation returns empty (stale-date test rot, P4).
            "timestamp": "2026-05-15T00:00:00+00:00",
        }
        full.update(rec)
        await store.record_ai_usage(full)


# ---------------------------------------------------------------------------
# QA Evaluator Test 1 — Aggregation accuracy
# ---------------------------------------------------------------------------

class TestAggregationAccuracy:
    """Insert diverse usage data (varying costs, models, success-states);
    assert the returned sums + breakdowns match expectations.

    Critical: tests the integer-cents aggregation chain. If costs were
    summed as floats, 1.25 + 2.50 + 0.75 might come back as
    4.499999999... — this test would catch that."""

    @pytest.mark.asyncio
    async def test_aggregation_sums_exactly_to_cents(self, store):
        await _seed(
            store,
            {"provider": "openai", "model": "gpt-4o", "cost_estimate_usd": 1.25, "success": True},
            {"provider": "openai", "model": "gpt-4o", "cost_estimate_usd": 2.50, "success": True},
            {"provider": "gemini", "model": "gemini-2.0-flash", "cost_estimate_usd": 0.75, "success": False},
        )

        async def fake_get_store():
            return store

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            report = await usage_reader.get_usage_report(
                start_date="2026-05-01T00:00:00+00:00",
                end_date="2026-06-30T00:00:00+00:00",
                customer_id="alice",
            )

        assert report.total_calls == 3
        assert report.successful_calls == 2
        assert report.failed_calls == 1
        # Exact cent reconciliation — the integer-cents SQL must
        # produce exactly 4.50, not 4.4999...
        assert report.total_cost_usd == 4.50, (
            f"Expected exactly 4.50 (= 1.25 + 2.50 + 0.75); "
            f"got {report.total_cost_usd!r}. Integer-cents aggregation broken."
        )
        assert report.total_input_tokens == 300
        assert report.total_output_tokens == 150
        # Provider breakdown
        by_provider = {b.provider: b for b in report.by_provider}
        assert by_provider["openai"].total_cost_usd == 3.75
        assert by_provider["openai"].call_count == 2
        assert by_provider["openai"].failed_count == 0
        assert by_provider["gemini"].total_cost_usd == 0.75
        assert by_provider["gemini"].failed_count == 1
        # Model breakdown
        by_model = {(b.provider, b.model): b for b in report.by_model}
        assert by_model[("openai", "gpt-4o")].call_count == 2


# ---------------------------------------------------------------------------
# QA Evaluator Test 2 — Date guard (PERIOD_TOO_LARGE)
# ---------------------------------------------------------------------------

class TestDateGuard:
    """91-day query → PeriodTooLargeError at service layer,
    HTTP 400 PERIOD_TOO_LARGE at router layer."""

    @pytest.mark.asyncio
    async def test_91_day_range_raises_at_service_layer(self):
        with pytest.raises(PeriodTooLargeError) as excinfo:
            await usage_reader.get_usage_report(
                start_date="2026-01-01T00:00:00+00:00",
                end_date="2026-04-02T00:00:00+00:00",  # 91 days
                customer_id="alice",
            )
        assert "90-day" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_endpoint_returns_400_period_too_large(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/ai/usage/stats",
            params={
                "start_date": "2026-01-01T00:00:00+00:00",
                "end_date": "2026-04-02T00:00:00+00:00",  # 91 days
            },
            headers=auth_headers,
        )
        assert r.status_code == 400
        body = r.json()
        # The codebase has a global exception handler that unwraps the
        # "detail" wrapper FastAPI normally adds — error envelope appears
        # at the top level under "error", matching the existing
        # test_advisor_auth.py pattern.
        assert body["error"]["code"] == "PERIOD_TOO_LARGE", (
            f"Expected error envelope at top-level 'error'; got body: {body}"
        )


# ---------------------------------------------------------------------------
# QA Evaluator Test 3 — Tenancy isolation
# ---------------------------------------------------------------------------

class TestTenancyIsolation:
    """Customer A's data must never appear in Customer B's aggregation.
    Tests at the service layer — the router always uses
    SYSTEM_CONTEXT_ID today; the service-layer isolation is what makes
    M2.3 (real per-customer identity) safe to land later without
    re-auditing the SQL."""

    @pytest.mark.asyncio
    async def test_customer_a_query_excludes_customer_b_data(self, store):
        await _seed(
            store,
            {"customer_id": "alice", "cost_estimate_usd": 1.00},
            {"customer_id": "alice", "cost_estimate_usd": 2.00},
            {"customer_id": "bob", "cost_estimate_usd": 5.00},
            {"customer_id": "bob", "cost_estimate_usd": 10.00},
        )

        async def fake_get_store():
            return store

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            alice_report = await usage_reader.get_usage_report(
                start_date="2026-05-01T00:00:00+00:00",
                end_date="2026-06-30T00:00:00+00:00",
                customer_id="alice",
            )

        # Alice's total is exactly her sum (1.00 + 2.00 = 3.00), NOT
        # the global total of 18.00 — even though both customers' rows
        # are in the same table.
        assert alice_report.total_cost_usd == 3.00, (
            f"Alice's report contains data from other customers — "
            f"got {alice_report.total_cost_usd} (expected 3.00). "
            f"Tenancy isolation breach at the SQL layer."
        )
        assert alice_report.total_calls == 2
        assert alice_report.customer_id == "alice"


# ---------------------------------------------------------------------------
# QA Evaluator Test 4 — Structure (index utilization via EXPLAIN QUERY PLAN)
# ---------------------------------------------------------------------------

class TestIndexUtilization:
    """The Cycle DD ai_usage table indexes are billing-critical — a
    customer-id-filtered aggregation that table-scans instead of using
    idx_ai_usage_customer_ts would become slow as the table grows.
    SQLite's EXPLAIN QUERY PLAN catches this on day 0."""

    @pytest.mark.asyncio
    async def test_customer_filtered_aggregation_uses_index(self, store):
        # Run the same aggregation SQL the service uses, with EXPLAIN
        # QUERY PLAN prefixed. SQLite returns rows like
        # "SEARCH ai_usage USING INDEX idx_ai_usage_customer_ts (...)".
        sql = """
            EXPLAIN QUERY PLAN
            SELECT
                COUNT(*) AS total_calls,
                SUM(input_tokens) AS in_tok,
                SUM(output_tokens) AS out_tok,
                SUM(CAST(ROUND(cost_estimate_usd * 100) AS INTEGER)) AS cents
            FROM ai_usage
            WHERE customer_id = ?
              AND timestamp >= ?
              AND timestamp <= ?
        """
        cursor = await store._db.execute(
            sql, ("alice", "2026-05-01T00:00:00", "2026-06-30T00:00:00")
        )
        rows = await cursor.fetchall()
        # SQLite's EXPLAIN QUERY PLAN returns rows with column "detail"
        # that contains strings like "SEARCH ai_usage USING INDEX
        # idx_ai_usage_customer_ts (...)". Join all detail strings so
        # we catch the index reference regardless of step ordering.
        plan = " | ".join(r["detail"] for r in rows)

        assert "idx_ai_usage_customer_ts" in plan, (
            f"Customer-filtered aggregation is NOT using "
            f"idx_ai_usage_customer_ts — billing queries will table-scan "
            f"as ai_usage grows. EXPLAIN QUERY PLAN output:\n{plan}"
        )


# ---------------------------------------------------------------------------
# Supporting Test 5 — Empty period returns zero-valued report
# ---------------------------------------------------------------------------

class TestEmptyPeriod:
    """Date range with no rows must return a valid (zero-valued) report,
    not raise. Frontend would break on a null/missing payload."""

    @pytest.mark.asyncio
    async def test_empty_period_returns_zero_report(self, store):
        async def fake_get_store():
            return store

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            report = await usage_reader.get_usage_report(
                start_date="2020-01-01T00:00:00+00:00",
                end_date="2020-01-31T00:00:00+00:00",
                customer_id="nobody",
            )

        assert report.total_calls == 0
        assert report.successful_calls == 0
        assert report.failed_calls == 0
        assert report.total_input_tokens == 0
        assert report.total_output_tokens == 0
        assert report.total_cost_usd == 0.0
        assert report.by_provider == []
        assert report.by_model == []
        assert report.customer_id == "nobody"


# ---------------------------------------------------------------------------
# Supporting Test 6 — Failed calls counted correctly
# ---------------------------------------------------------------------------

class TestFailedCallsCounted:
    """Per provider AND per top-line, the success-bool must be summed
    correctly. ProviderBreakdown.failed_count + UsageReport.failed_calls."""

    @pytest.mark.asyncio
    async def test_4_success_1_failure(self, store):
        await _seed(
            store,
            {"success": True},
            {"success": True},
            {"success": True},
            {"success": True},
            {"success": False},
        )

        async def fake_get_store():
            return store

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            report = await usage_reader.get_usage_report(
                start_date="2026-05-01T00:00:00+00:00",
                end_date="2026-06-30T00:00:00+00:00",
                customer_id="alice",
            )

        assert report.total_calls == 5
        assert report.successful_calls == 4
        assert report.failed_calls == 1
        # Per-provider breakdown also tracks failures
        assert report.by_provider[0].failed_count == 1


# ---------------------------------------------------------------------------
# Supporting Test 7 — DB-level aggregation (structural)
# ---------------------------------------------------------------------------

class TestDBLevelAggregation:
    """Locks the constraint that aggregation happens in SQL, not Python.
    A refactor that pulled rows into a list and Python-summed them would
    pass the accuracy test but blow up at scale — this structural test
    catches the regression on day 0."""

    def test_aggregate_sql_uses_sum_and_group_by(self):
        """Scan the aggregate_ai_usage source for SUM( and GROUP BY.
        Brittle to refactor but the only way to prove SQL-side
        aggregation without a perf benchmark."""
        import inspect

        source = inspect.getsource(SQLiteJobStore.aggregate_ai_usage)
        assert "SUM(" in source, (
            "aggregate_ai_usage no longer uses SQL SUM — Python-side "
            "summation is forbidden per the Cycle EE 'No raw exposure / "
            "DB-level aggregation' constraint."
        )
        assert "GROUP BY" in source, (
            "aggregate_ai_usage no longer uses SQL GROUP BY — the "
            "per-provider / per-model breakdowns must be DB-side."
        )
        # The integer-cents pattern must also be preserved.
        assert "CAST(ROUND(cost_estimate_usd * 100)" in source, (
            "Integer-cents aggregation pattern was removed — "
            "float-summation precision risk reintroduced."
        )


# ---------------------------------------------------------------------------
# Supporting Test 8 — customer_id required (no global queries)
# ---------------------------------------------------------------------------

class TestCustomerIdRequired:
    """Per the auth-derived customer-id critique: there is NO path
    through this layer that aggregates without specifying a customer.
    Service layer enforces; store layer enforces; both are tested."""

    @pytest.mark.asyncio
    async def test_service_layer_rejects_empty_customer_id(self):
        with pytest.raises(ValueError, match="customer_id is required"):
            await usage_reader.get_usage_report(
                start_date="2026-05-01T00:00:00+00:00",
                end_date="2026-05-31T00:00:00+00:00",
                customer_id="",
            )

    @pytest.mark.asyncio
    async def test_service_layer_rejects_none_customer_id(self):
        with pytest.raises(ValueError, match="customer_id is required"):
            await usage_reader.get_usage_report(
                start_date="2026-05-01T00:00:00+00:00",
                end_date="2026-05-31T00:00:00+00:00",
                customer_id=None,  # type: ignore[arg-type]
            )

    @pytest.mark.asyncio
    async def test_store_layer_also_enforces(self, store):
        """Defence in depth: even if the service layer were bypassed,
        the store layer raises on empty customer_id."""
        with pytest.raises(ValueError, match="non-empty customer_id"):
            await store.aggregate_ai_usage(
                start_ts="2026-05-01T00:00:00+00:00",
                end_ts="2026-05-31T00:00:00+00:00",
                customer_id="",
            )


# ---------------------------------------------------------------------------
# Bonus — Router auth + endpoint registration (security tests)
# ---------------------------------------------------------------------------

class TestEndpointAuth:
    """The router-level Depends(require_auth) must reject unauthenticated
    requests. Matches the Cycle X pattern for ai/geo routers."""

    @pytest.mark.asyncio
    async def test_endpoint_rejects_missing_auth(self, api_client):
        r = await api_client.get(
            "/api/ai/usage/stats",
            params={
                "start_date": "2026-05-01T00:00:00+00:00",
                "end_date": "2026-05-31T00:00:00+00:00",
            },
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_endpoint_rejects_wrong_token(self, api_client):
        r = await api_client.get(
            "/api/ai/usage/stats",
            params={
                "start_date": "2026-05-01T00:00:00+00:00",
                "end_date": "2026-05-31T00:00:00+00:00",
            },
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401
