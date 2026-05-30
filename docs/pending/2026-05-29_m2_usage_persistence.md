---
status: pending
proposed: 2026-05-29
revised: 2026-05-29 (audit findings + architectural questions surfaced)
author: System Architect (QA hardened) + Claude (audit + reconciliation)
source: PLAN-V3.0.md M2.5 + Cycle CC TODOs
---

# Milestone 2.5: ai_usage persistence

## Goal

Persist token-usage events to durable storage so M2.6 (usage aggregation
API) and eventual billing rollups have real data to query. Closes the
three `TODO(M2.5)` markers that landed in Cycles Z / BB / CC.

## What's already in place (audit findings)

| Item | State |
|---|---|
| Async SQLite driver | `aiosqlite~=0.20.0` already in requirements |
| Schema pattern | Monolithic `SCHEMA` constant in `api/services/job_store_base.py:213`, applied at `init()` via `executescript`, idempotent `_migrate()` adds columns later |
| Store singletons | `get_job_store()` returns `SQLiteJobStore \| RedisJobStore` based on env (deployment-railway.md M0.7) |
| Async-task patterns | `asyncio.create_task` used in `js_renderer.py:166`, `batch_optimizer.py:151`; FastAPI `BackgroundTasks` used in `crawl.py:448` — both proven |
| Current `_log_usage` | INFO-log only (`api/services/ai_router.py:223`) — safe-key filtering already in place via `_SAFE_METADATA_KEYS` |
| Cycle CC TODOs to close | `advisor.py:252`, `advisor.py:596`, `ai_router.py:223` |

## Spec review — what the QA spec gets right

| Item | Status |
|---|---|
| Schema with indices on customer_id + provider | ✅ direction; PLAN-V3.0.md M2.5 also wants (customer_id, timestamp) for billing and (job_id) for per-audit cost |
| `api/services/usage_logger.py` encapsulation | ✅ correct |
| AIRouter has no DB knowledge | ✅ correct — AIRouter calls usage_logger, usage_logger handles the DB |
| `_SAFE_METADATA_KEYS` enforcement | ✅ already done in Cycle Z; persistence layer must respect the same whitelist |
| Test 1 (round-trip) and Test 3 (success=False on errors) | ✅ both correct |

## Spec review — three places the QA spec needs sharpening

### 1. "Separate task or background job" — pick one pattern

The QA spec says "if possible", but the **"No Blocking IO"** negative
constraint is hard. We must pick a real async pattern. Three options:

- **(a) `asyncio.create_task` + module-level task registry.** Pattern
  used in `js_renderer.py`. Simple. Risk: tasks orphaned on shutdown
  lose their writes. Mitigation: track pending tasks in a `set`, expose
  `await_pending()` for FastAPI lifespan-shutdown.
- **(b) FastAPI `BackgroundTasks`.** Pattern used in `crawl.py:448`.
  Proper request-lifecycle integration. Risk: requires the
  `background_tasks: BackgroundTasks` parameter to be threaded down
  through AIRouter's signature — which would couple AIRouter to FastAPI
  and break the M2.x "router is transport-neutral" stance.
- **(c) Real async queue (asyncio.Queue + worker task started at app
  startup).** Cleanest decoupling. Most infrastructure to build.

**Recommendation: (a)**. Matches existing patterns. Tasks tracked in
a set so shutdown can `await asyncio.gather(*pending)`. Failure to
persist falls back to logging the event to stderr — never silently
lost.

### 2. Redis parity — defer or include?

`RedisJobStore` exists at `api/services/redis_store.py` and the
codebase has SQLite/Redis parity for job storage. M2.5 spec doesn't
mention Redis. Two paths:

- **(i) SQLite-only this cycle.** Defer Redis parity to a follow-up.
  Faster ship. But production uses Redis (Upstash) — billing data
  would be SQLite-only until the follow-up lands.
- **(ii) Include both this cycle.** Larger scope (~1.5x size). Matches
  the existing parity pattern. Avoids billing-data-store mismatch
  between dev and prod.

**Recommendation: (i) SQLite-only.** The billing data isn't user-
facing yet (no M2.6 aggregation API yet); shipping SQLite-only gets
the table and the writes wired so M2.6 can land cleanly, then a
small follow-up cycle adds Redis parity before going to production
with billing.

### 3. Test 2 (Latency) — needs a concrete shape

The QA spec says "verify database latency does not block the response
return". Hard to assert cleanly. Three test shapes:

- **(α) Structural assertion**: scan `_log_usage` source for the
  literal `asyncio.create_task` (or similar) call. Pro: fast, no
  timing. Con: brittle to refactor.
- **(β) Behavioural assertion**: mock the DB write to sleep N
  milliseconds; assert that `ai_router.call_text` returns in < (N/4)
  ms. Pro: tests the actual behaviour. Con: flaky on slow CI.
- **(γ) Both**: do (α) as the primary assertion + (β) with a
  generous timing margin (e.g. mock sleeps 500ms, response must
  return in < 100ms).

**Recommendation: (γ)**. Robust against both refactors and CI noise.

## Scope of THIS cycle (with recommendations applied)

In scope:
- **Schema:** add `ai_usage` table to `SCHEMA` in
  `api/services/job_store_base.py` with columns from PLAN-V3.0.md M2.5
  + indexes on `(customer_id, timestamp)`, `(job_id)`, `(provider)`.
- **Storage methods:** add `record_ai_usage(record: dict) -> None` and
  `get_ai_usage(customer_id, from_ts=..., to_ts=...) -> list[dict]` to
  `SQLiteJobStore`. (Public `get_ai_usage` is for M2.6's eventual
  aggregation queries; we wire the read path so M2.6 doesn't need to
  touch the store again.)
- **Public API:** new `api/services/usage_logger.py` with:
  - `class UsageLogger` (singleton pattern matching AIRouter / PriceLookup)
  - `async def record(self, metadata: dict) -> None` — schedules the
    DB write via `asyncio.create_task`, tracks in a module-level set
  - `async def await_pending(self) -> None` — for app shutdown
  - `async def record_parse_failure(self, customer_id, provider, model, error_message) -> None`
    — closes the advisor.py Cycle CC TODOs by providing a `success=False`
    entry for downstream parse failures
  - Module-level `usage_logger` singleton
- **AIRouter refactor:** `_log_usage` continues to filter via
  `_SAFE_METADATA_KEYS` and INFO-log (for observability when SQLite is
  down). It additionally calls `usage_logger.record(safe_metadata)` —
  fire-and-forget via the task pattern.
- **Cycle CC TODO closure:**
  - `api/services/advisor.py:252` and `:596` — replace `TODO(M2.5)`
    comments with actual `await usage_logger.record_parse_failure(...)`
    calls.
  - `api/services/ai_router.py:223` — `TODO(M2.5)` docstring updated to
    reflect that persistence now happens via usage_logger.

Out of scope (deferred):
- Redis parity — separate follow-up cycle before production billing.
- M2.6 (usage aggregation API endpoints) — independent next cycle;
  `get_ai_usage` is the seam M2.6 will plug into.
- M2.5 spec's "Retention: keep raw events for 90 days, then aggregate
  into monthly summaries" — needs its own cron/job design.
- DeepSeek driver — independent.
- Per-customer identity model — still the strategic blocker for M2.3.

## Schema (SQL)

```sql
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    job_id TEXT,                     -- nullable; links to a crawl job
    session_id TEXT,                 -- correlation ID for grouping calls
    task_type TEXT,                  -- "advisor" / "rewriter" / etc (M2.4)
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_estimate_usd REAL NOT NULL DEFAULT 0.0,
    timestamp TEXT NOT NULL,         -- ISO 8601 UTC
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_customer_ts
    ON ai_usage (customer_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_usage_job
    ON ai_usage (job_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_provider
    ON ai_usage (provider);
```

## Public API

```python
# api/services/usage_logger.py

class UsageLogger:
    """Singleton — use the module-level `usage_logger` instance."""

    def __init__(self) -> None:
        self._pending: set[asyncio.Task] = set()

    async def record(self, metadata: dict) -> None:
        """Schedule an ai_usage write. Returns immediately; the write
        completes asynchronously via asyncio.create_task. Failure to
        persist is logged via the standard logger but does NOT raise
        (a failed write must never block a successful LLM call).
        """
        # Enforce whitelist defensively — duplicates AIRouter's filter
        # but guards against any caller that bypasses _log_usage.
        safe = {k: v for k, v in metadata.items() if k in _SAFE_METADATA_KEYS}
        task = asyncio.create_task(self._persist(safe))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def record_parse_failure(
        self,
        customer_id: str,
        provider: str,
        model: str,
        error_message: str,
    ) -> None:
        """Convenience for the Cycle CC advisor TODO. Records a
        success=False event for application-level parse failures
        (distinct from provider HTTP failures which the AIRouter
        already records via the error-path in _call())."""
        await self.record({
            "customer_id": customer_id,
            "provider": provider,
            "model": model,
            "input_token_count": 0,
            "output_token_count": 0,
            "cost_estimate_usd": 0.0,
            "success": False,
            "error_message": error_message[:500],
            "timestamp": _now_iso(),
        })

    async def await_pending(self) -> None:
        """For FastAPI lifespan shutdown — wait for in-flight writes
        to complete before the process exits. Without this, fire-and-
        forget tasks lose their writes on shutdown."""
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)

    async def _persist(self, safe: dict) -> None:
        """Internal: the actual DB write."""
        try:
            store = await get_store()
            await store.record_ai_usage(safe)
        except Exception as exc:
            logger.warning("ai_usage_persist_failed", extra={"error": str(exc)})
            # Do NOT re-raise — write failures must not block the
            # async task or affect anything else.

usage_logger = UsageLogger()
```

## AIRouter integration

`_log_usage` continues to filter + INFO-log (so observability survives
DB outages), and additionally calls `usage_logger.record(safe)`:

```python
def _log_usage(metadata: dict) -> None:
    safe = {k: v for k, v in metadata.items() if k in _SAFE_METADATA_KEYS}
    logger.info("ai_usage", extra=safe)
    # M2.5: schedule persistence. Fire-and-forget — write does NOT
    # block the AIRouter call's return.
    asyncio.create_task(usage_logger.record(safe))
```

Note: `_log_usage` is called from `_call()` which is async; `asyncio.create_task` inside a sync function works as long as an event loop is running (which it always is inside FastAPI). Worth a defensive runtime check for tests that invoke `_log_usage` outside an event loop.

## Tests (3 evaluator + 4 supporting)

### Per the QA spec evaluator

1. **Persistence (round-trip).** Call `usage_logger.record({...})`,
   `await usage_logger.await_pending()`, query via
   `store.get_ai_usage(...)`. Assert the record exists with correct
   token counts and cost.
2. **Latency (option γ — both structural + behavioural).**
   - **Structural:** assert `_log_usage` source contains
     `asyncio.create_task`.
   - **Behavioural:** mock `store.record_ai_usage` to sleep 500ms.
     Time `ai_router.call_text` with a fully-mocked driver. Assert
     response returns in < 100ms.
3. **success=False on errors.** Trigger `ProviderAPIError` in driver;
   verify the persisted record has `success=0` and the error message.

### Supporting (added per audit)

4. **Whitelist enforcement at persistence layer.** Call
   `usage_logger.record({"prompt": "secret", "customer_id": "x"})` —
   verify only `customer_id` is persisted (prompt was silently dropped
   per `_SAFE_METADATA_KEYS`).
5. **`await_pending()` actually awaits.** Schedule 10 records, immediately
   await_pending, query — assert all 10 are present.
6. **Parse-failure path (Cycle CC TODO closure).** Trigger
   `usage_logger.record_parse_failure(...)`. Verify the resulting row
   has `success=0` and `error_message` truncated to 500 chars.
7. **Schema column presence.** Open the test DB, query `PRAGMA
   table_info(ai_usage)`, verify all 13 columns + the 3 indexes exist.

## Acceptance criteria

1. `ai_usage` table exists in SQLite with the 13 columns + 3 indexes
   above. Idempotent — re-running `init()` does not error.
2. `api/services/usage_logger.py` exists with the public API above.
3. `SQLiteJobStore.record_ai_usage(record)` + `get_ai_usage(...)` work.
4. AIRouter `_log_usage` continues to INFO-log AND calls
   `usage_logger.record(safe)` via `asyncio.create_task`.
5. Three TODO(M2.5) markers closed:
   - `advisor.py:252` and `:596` — parse-failure path emits
     `usage_logger.record_parse_failure(...)`.
   - `ai_router.py:223` — docstring updated.
6. All 7 tests above pass.
7. Full suite: 1,349 baseline + 7 net new = 1,356 passed, 12 skipped, 0 failed.
8. App startup creates the table; existing test DB fixtures get the
   new table via the same `init()` call. No test-fixture cleanup needed
   beyond the existing `:memory:` per-test pattern.

## Risks + mitigations

- **Orphan tasks on shutdown.** Mitigation: `await_pending()` plus
  wiring it into the FastAPI lifespan handler. (Lifespan integration
  is a follow-up if not done in this cycle — note as additional TODO.)
- **SQLite WAL contention.** Mitigation: SQLite handles concurrent
  writes serially. For dev/single-user workloads this is fine; for
  production-scale concurrent writes, the Redis-parity follow-up
  cycle is the answer.
- **Test event-loop ergonomics.** `asyncio.create_task` outside an
  event loop raises `RuntimeError`. The `_log_usage` call site needs
  a defensive `try/except RuntimeError` for tests that invoke it
  synchronously, or a smarter check (e.g. `asyncio.get_running_loop()`
  check). Implementation must handle this cleanly.
- **Schema drift between dev and prod.** Mitigation: schema lives in
  one place (`job_store_base.py`); both env apply same SCHEMA at
  init. Redis follow-up adds Redis-side parity.

## Decisions still pending user approval

1. **Async pattern: confirm option (a)** — `asyncio.create_task` + module-
   level task registry + `await_pending()` for shutdown? (My recommendation.)
2. **Redis parity: confirm option (i)** — SQLite-only this cycle, Redis
   parity in a follow-up cycle before production billing? (My recommendation.)
3. **Test 2 shape: confirm option (γ)** — structural + behavioural,
   with generous timing margin (mock sleep 500ms, response < 100ms)?
4. **Cycle CC TODO closure scope** — close all 3 TODOs (advisor.py:252,
   advisor.py:596, ai_router.py:223) in this cycle, or only the two
   parse-failure ones in advisor.py? (My recommendation: all 3.)
5. **Lifespan integration** — wire `await_pending()` into FastAPI
   lifespan shutdown handler in this cycle, or as a follow-up TODO?
   (My recommendation: this cycle — it's one line of integration and
   prevents the orphan-task class of bugs from day one.)

Estimated scope after approvals: ~6 hours wall-time. ~250 lines of
new code (usage_logger.py + schema additions + store methods) + ~7
tests. The async-task lifecycle is the part that needs most care.
