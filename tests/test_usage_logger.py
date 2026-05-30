"""Tests for AI usage persistence (v2.6 M2.5 / Cycle DD).

Per docs/pending/2026-05-29_m2_usage_persistence.md (approved
2026-05-29 with all five recommendations).

Three QA evaluator tests + four supporting tests:
    1. Persistence (round-trip) — QA evaluator #1
    2. Latency (γ: structural + behavioural) — QA evaluator #2
    3. success=False on provider errors — QA evaluator #3
    4. Whitelist enforcement at persistence layer
    5. await_pending() actually awaits
    6. Parse-failure path (Cycle CC TODO closure)
    7. Schema column + index presence

The store fixture uses :memory: SQLite so tests are fast and isolated.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from unittest.mock import AsyncMock, patch

import pytest

from api.services.ai_router import (
    AIResponse,
    AIRouter,
    ModelConfig,
    ProviderAPIError,
    SYSTEM_CONTEXT_ID,
    _log_usage,
    _SAFE_METADATA_KEYS,
)
from api.services.sqlite_store import SQLiteJobStore
from api.services.usage_logger import UsageLogger, usage_logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
async def store():
    """Isolated in-memory SQLite store per test."""
    s = SQLiteJobStore(":memory:")
    await s.init()
    yield s
    await s.close()


def _ai_response(content: str = "ok") -> AIResponse:
    return AIResponse(
        content=content,
        provider_id="openai",
        model="gpt-4o",
        input_token_count=100,
        output_token_count=50,
        cost_estimate_usd=0.0,  # AIRouter post-processes
        truncated=False,
    )


# ---------------------------------------------------------------------------
# QA Evaluator Test 1 — Persistence round-trip
# ---------------------------------------------------------------------------

class TestPersistenceRoundTrip:
    """Per QA spec Test 1: trigger record, query, verify."""

    @pytest.mark.asyncio
    async def test_record_then_query_finds_row(self, store):
        await store.record_ai_usage({
            "customer_id": SYSTEM_CONTEXT_ID,
            "provider": "openai",
            "model": "gpt-4o",
            "input_token_count": 100,
            "output_token_count": 50,
            "cost_estimate_usd": 0.0025,
            "success": True,
        })

        rows = await store.get_ai_usage(customer_id=SYSTEM_CONTEXT_ID)
        assert len(rows) == 1
        row = rows[0]
        assert row["customer_id"] == SYSTEM_CONTEXT_ID
        assert row["provider"] == "openai"
        assert row["model"] == "gpt-4o"
        assert row["input_tokens"] == 100
        assert row["output_tokens"] == 50
        assert row["cost_estimate_usd"] == 0.0025
        assert row["success"] == 1
        assert row["timestamp"]  # auto-supplied
        assert row["error_message"] is None

    @pytest.mark.asyncio
    async def test_required_fields_validated(self, store):
        """customer_id, provider, model are NOT NULL — record_ai_usage
        must reject calls missing any of them. Catches caller bugs
        where the metadata dict was assembled incorrectly."""
        with pytest.raises(ValueError, match="customer_id, provider, model"):
            await store.record_ai_usage({"provider": "openai", "model": "gpt-4o"})

    @pytest.mark.asyncio
    async def test_get_ai_usage_filters(self, store):
        """The get_ai_usage filters are the seam M2.6 will use for
        aggregation queries. Lock the filter semantics in now so M2.6
        doesn't have to rediscover them."""
        for cust in ("alice", "bob"):
            for prov in ("openai", "gemini"):
                await store.record_ai_usage({
                    "customer_id": cust, "provider": prov,
                    "model": "gpt-4o" if prov == "openai" else "gemini-2.0-flash",
                    "input_token_count": 10,
                })

        assert len(await store.get_ai_usage()) == 4
        assert len(await store.get_ai_usage(customer_id="alice")) == 2
        assert len(await store.get_ai_usage(provider="openai")) == 2
        assert len(
            await store.get_ai_usage(customer_id="alice", provider="openai")
        ) == 1


# ---------------------------------------------------------------------------
# QA Evaluator Test 2 — Latency (γ: structural + behavioural)
# ---------------------------------------------------------------------------

class TestLatency:
    """Per QA spec Test 2 + my recommendation (option γ): structural
    AND behavioural. Without the structural test, a refactor could
    silently switch to synchronous writes — the behavioural test would
    catch it but only on a CI run, and it could be flaky."""

    def test_usage_logger_record_uses_create_task_structurally(self):
        """Structural: assert UsageLogger.record's source contains
        asyncio task scheduling. Brittle to refactor but catches the
        case where someone "simplifies" away the async pattern without
        noticing the latency contract.

        Note: in Cycle DD the actual scheduling moved from _log_usage
        (which now just awaits record) into UsageLogger.record itself.
        Either layer must contain create_task — checking record because
        that's where the actual fire-and-forget happens. _log_usage is
        thin; UsageLogger.record owns the latency contract."""
        source = inspect.getsource(UsageLogger.record)
        assert "create_task" in source, (
            "UsageLogger.record no longer schedules an async task — the "
            "latency contract for AIRouter calls is broken. Restore the "
            "asyncio.create_task pattern."
        )

    @pytest.mark.asyncio
    async def test_call_text_returns_before_slow_write_completes(
        self, monkeypatch
    ):
        """Behavioural: mock the DB write to sleep 500ms.
        AIRouter.call_text should still return in well under 100ms
        because the write is fire-and-forget."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()
        mock_driver = AsyncMock()
        mock_driver.provider_id = "openai"
        mock_driver.call_text = AsyncMock(return_value=_ai_response())
        router._drivers = {"openai": mock_driver}

        # Mock _persist to sleep 500ms — simulates a slow DB write.
        async def slow_persist(safe):
            await asyncio.sleep(0.5)

        with patch(
            "api.services.usage_logger.UsageLogger._persist",
            side_effect=slow_persist,
        ):
            start = time.monotonic()
            await router.call_text(
                customer_id=SYSTEM_CONTEXT_ID,
                system_prompt="sys",
                user_prompt="hello",
                model_config=ModelConfig(model="gpt-4o"),
            )
            elapsed = time.monotonic() - start

        # Generous margin: 500ms simulated DB latency vs 100ms response
        # budget gives 5x headroom. On slow CI 100ms can still be tight
        # so we use 200ms — still 2.5x faster than the simulated write.
        assert elapsed < 0.2, (
            f"AIRouter.call_text took {elapsed:.3f}s with a 500ms simulated "
            f"DB write — write is no longer fire-and-forget. Latency "
            f"contract broken."
        )


# ---------------------------------------------------------------------------
# QA Evaluator Test 3 — success=False on provider errors
# ---------------------------------------------------------------------------

class TestErrorPathRecordsFailure:
    """Per QA spec Test 3: provider HTTP errors must be recorded with
    success=False so billing rollups can distinguish "consumed tokens"
    from "failed before consuming"."""

    @pytest.mark.asyncio
    async def test_provider_api_error_logged_with_success_false(
        self, monkeypatch, store
    ):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()
        mock_driver = AsyncMock()
        mock_driver.provider_id = "openai"
        mock_driver.call_text = AsyncMock(
            side_effect=ProviderAPIError("openai HTTP 503")
        )
        router._drivers = {"openai": mock_driver}

        # Wire usage_logger to write to OUR isolated store.
        async def fake_get_store():
            return store

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            with pytest.raises(ProviderAPIError):
                await router.call_text(
                    customer_id=SYSTEM_CONTEXT_ID,
                    system_prompt="sys",
                    user_prompt="hello",
                    model_config=ModelConfig(model="gpt-4o"),
                )

            # Drain the fire-and-forget write.
            await usage_logger.await_pending()

        rows = await store.get_ai_usage(customer_id=SYSTEM_CONTEXT_ID)
        assert len(rows) == 1, (
            f"Expected exactly 1 ai_usage row from the error path; got {len(rows)}"
        )
        assert rows[0]["success"] == 0
        assert "503" in (rows[0]["error_message"] or "")


# ---------------------------------------------------------------------------
# Supporting Test 4 — Whitelist enforcement at persistence layer
# ---------------------------------------------------------------------------

class TestWhitelistAtPersistenceLayer:
    """Defence-in-depth: usage_logger.record() re-applies the
    _SAFE_METADATA_KEYS whitelist. Even if a future caller bypasses
    AIRouter._log_usage and calls usage_logger.record() with raw
    prompt text, the whitelist drops it."""

    @pytest.mark.asyncio
    async def test_forbidden_keys_silently_dropped(self, monkeypatch, store):
        async def fake_get_store():
            return store

        logger = UsageLogger()

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            await logger.record({
                "customer_id": "test",
                "provider": "openai",
                "model": "gpt-4o",
                # Forbidden — privacy risk
                "prompt": "raw prompt text with PII",
                "response": "raw model response",
                "user_email": "alice@example.com",
            })
            await logger.await_pending()

        rows = await store.get_ai_usage(customer_id="test")
        assert len(rows) == 1
        # The row schema doesn't even have columns for prompt/response —
        # this is the second line of defence. The first was the whitelist
        # dropping the keys. Confirm by inspecting the row dict has only
        # the schema columns.
        row = rows[0]
        # Forbidden keys must not be in the row dict
        for forbidden in ("prompt", "response", "user_email"):
            assert forbidden not in row, (
                f"{forbidden} leaked into ai_usage row — whitelist failed"
            )

    def test_safe_metadata_keys_is_locked(self):
        """If someone widens _SAFE_METADATA_KEYS, this test fails to
        force a review of the privacy impact."""
        expected = {
            "customer_id", "provider", "model",
            "input_token_count", "output_token_count", "cost_estimate_usd",
            "task_type", "success", "error_message", "timestamp",
        }
        assert _SAFE_METADATA_KEYS == frozenset(expected), (
            f"_SAFE_METADATA_KEYS changed — review privacy impact before "
            f"adding/removing keys. Got: {sorted(_SAFE_METADATA_KEYS)}"
        )


# ---------------------------------------------------------------------------
# Supporting Test 5 — await_pending() correctness
# ---------------------------------------------------------------------------

class TestAwaitPending:
    """The lifespan-shutdown hook depends on await_pending draining
    every in-flight write. If it returned early, writes would be
    cancelled and billing data lost."""

    @pytest.mark.asyncio
    async def test_drains_multiple_in_flight_writes(self, store):
        async def fake_get_store():
            return store

        logger = UsageLogger()

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            # Schedule 10 records without awaiting individually.
            for i in range(10):
                await logger.record({
                    "customer_id": f"cust-{i}",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_token_count": i,
                })

            # Immediately drain. After this, all 10 must be persisted.
            await logger.await_pending()

        rows = await store.get_ai_usage(limit=100)
        assert len(rows) == 10, (
            f"await_pending returned with {len(rows)}/10 rows persisted — "
            f"shutdown would lose {10 - len(rows)} writes."
        )

    @pytest.mark.asyncio
    async def test_await_pending_safe_when_no_writes_in_flight(self):
        """Re-entrant + safe on empty queue."""
        logger = UsageLogger()
        # No-op
        await logger.await_pending()
        # Still no-op on second call
        await logger.await_pending()


# ---------------------------------------------------------------------------
# Supporting Test 6 — Parse-failure path (Cycle CC TODO closure)
# ---------------------------------------------------------------------------

class TestParseFailurePath:
    """Closes the advisor.py Cycle CC TODOs by providing
    record_parse_failure(). Verifies the row shape — token counts 0,
    success=0, error_message truncated to 500 chars."""

    @pytest.mark.asyncio
    async def test_record_parse_failure_writes_correct_shape(self, store):
        async def fake_get_store():
            return store

        logger = UsageLogger()
        long_error = "x" * 700  # Will be truncated to 500

        with patch("api.routers.crawl.get_store", side_effect=fake_get_store):
            await logger.record_parse_failure(
                customer_id="test",
                provider="openai",
                model="gpt-4o",
                error_message=long_error,
            )
            await logger.await_pending()

        rows = await store.get_ai_usage(customer_id="test")
        assert len(rows) == 1
        row = rows[0]
        assert row["success"] == 0
        assert row["input_tokens"] == 0
        assert row["output_tokens"] == 0
        assert row["cost_estimate_usd"] == 0.0
        assert len(row["error_message"]) == 500


# ---------------------------------------------------------------------------
# Supporting Test 7 — Schema column + index presence
# ---------------------------------------------------------------------------

class TestSchemaPresence:
    """Per CLAUDE.md API contract test rule: assert the schema is
    what the rest of the code thinks it is. If a future migration
    drops a column or index, M2.6's aggregation queries break — this
    test catches the schema regression on day 0."""

    @pytest.mark.asyncio
    async def test_ai_usage_table_has_all_columns(self, store):
        cursor = await store._db.execute("PRAGMA table_info(ai_usage)")
        cols = await cursor.fetchall()
        col_names = {c[1] for c in cols}
        expected = {
            "id", "customer_id", "job_id", "session_id", "task_type",
            "provider", "model",
            "input_tokens", "output_tokens", "cost_estimate_usd",
            "timestamp", "success", "error_message",
        }
        assert col_names == expected, (
            f"ai_usage columns drifted from M2.5 spec. "
            f"Got: {sorted(col_names)}\nExpected: {sorted(expected)}"
        )

    @pytest.mark.asyncio
    async def test_ai_usage_required_indexes_exist(self, store):
        """Indexes are NOT optional — billing queries that scan
        millions of rows depend on them. Sentry-level performance
        regression if any of these are dropped."""
        cursor = await store._db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ai_usage'"
        )
        rows = await cursor.fetchall()
        index_names = {r[0] for r in rows}
        required = {
            "idx_ai_usage_customer_ts",
            "idx_ai_usage_job",
            "idx_ai_usage_provider",
        }
        missing = required - index_names
        assert not missing, (
            f"Required ai_usage indexes missing: {sorted(missing)}. "
            f"Aggregation queries will be table-scans without these."
        )
