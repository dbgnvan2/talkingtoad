---
status: pending
proposed: 2026-05-29
revised: 2026-05-29 (audit findings + scoping questions surfaced)
author: System Architect (QA hardened) + Claude (audit + reconciliation)
source: PLAN-V3.0.md M2.6 + Cycle DD seam
---

# Cycle EE: M2.6 — Usage aggregation API (review + scoping)

## What's in place (audit findings)

| Item | State |
|---|---|
| `ai_usage` table populated on every AIRouter call | ✅ Cycle DD |
| `get_ai_usage(customer_id=, from_ts=, to_ts=, provider=, job_id=, limit=)` seam | ✅ already exists in `SQLiteJobStore` |
| Pydantic BaseModel pattern for request/response | ✅ used in `api/routers/ai.py` for request models; no precedent for response DTOs yet |
| Existing aggregation endpoint pattern | ❌ no precedent — every "summary" endpoint today returns row dicts, not aggregated stats |
| EXPLAIN QUERY PLAN usage | ❌ no precedent — Test 4 is novel territory |
| Customer identity model | ❌ still doesn't exist; every write uses `SYSTEM_CONTEXT_ID` |
| Router pattern | ✅ `advisor.py`, `ai.py`, `geo.py` are precedents for dedicated routers with router-level `dependencies=[Depends(require_auth)]` |

## Spec review — what the QA spec gets right

| Item | Status |
|---|---|
| DB-level aggregation (SQL SUM/GROUP BY, no Python-memory summation) | ✅ correct constraint |
| `require_auth` at router level | ✅ matches existing pattern |
| Aggregated DTO only, no raw rows / no PII | ✅ |
| Time-bounded queries (max 90-day range) | ✅ correct concern |
| Test 4 (EXPLAIN QUERY PLAN) catches index regressions | ✅ valuable — currently no such test exists in the codebase |

## Spec review — five places needing sharpening

### 1. Scope mismatch with PLAN-V3.0.md M2.6 — 1 endpoint vs 5

QA spec defines **one endpoint** (`GET /api/ai/usage/stats`). PLAN-V3.0.md M2.6 lists **five**:

| PLAN.md endpoint | What it does |
|---|---|
| `GET /api/customer/usage/summary?period=month` | Cumulative tokens + cost across providers, by task_type |
| `GET /api/customer/usage/by-job?from=...&to=...` | Per-crawl cost breakdown |
| `GET /api/customer/usage/by-provider?period=month` | Provider/model split |
| `GET /api/customer/usage/timeseries?period=month&granularity=day` | Chart data |
| `GET /api/customer/usage/for-job/{job_id}` | Total AI cost for one crawl |

**Recommendation:** ship the QA-spec scope (1 endpoint, `GET /api/ai/usage/stats`) this cycle. It includes nested breakdowns by provider and model — covers ~70% of the PLAN.md surface in a single endpoint with sub-objects. The 4 specialized endpoints become a follow-up cycle (cheap to add — same aggregation patterns, different SQL filters).

### 2. URL path mismatch

QA spec: `/api/ai/usage/stats`. PLAN.md: `/api/customer/usage/*`. The `/api/customer/` prefix implies a customer identity model that doesn't exist (every request today is `SYSTEM_CONTEXT_ID`).

**Recommendation:** use QA spec's path. `/api/ai/usage/stats` keeps the URL honest with the current identity reality. When customer identity lands (M2.3+), we can add `/api/customer/usage/*` as a parallel namespace, or alias.

### 3. "Same require_auth as AI routes" — pick the auth posture for missing customer_id

QA spec says: "If a `customer_id` is passed, the query MUST filter by `customer_id`. Unauthenticated/system-only calls should only be permitted for authorized service accounts."

But:
- No service-account concept exists in the codebase
- Today every authenticated caller is the same actor (single bearer token)
- Writes always use `SYSTEM_CONTEXT_ID`

**Recommendation:** treat the bearer-token holder as effectively a system admin for now. When `customer_id` is omitted on read, return all records. When `customer_id` is passed, filter by it. Add an explicit `# TODO(M2.3)` comment so when customer identity lands we tighten this to "callers can only query their own customer_id unless service-account".

### 4. "Maximum 90-day range" — pick reject vs clip

QA spec says max 90-day range "to prevent DB performance degradation" but doesn't say what happens on violation.

**Recommendation:** **hard reject with HTTP 400** (`PERIOD_TOO_LARGE` error code). Explicit > silent — a caller asking for 6 months of data should know they're not getting it, not silently get 90 days back.

### 5. DTO shape — needs to be concrete

QA spec lists `total_cost`, `token_breakdown`, `model_usage_count` informally. The exact shape needs to lock down before frontend can consume.

**Proposed:**

```python
class ProviderBreakdown(BaseModel):
    provider: str
    call_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    failed_count: int

class ModelBreakdown(BaseModel):
    provider: str
    model: str
    call_count: int
    total_cost_usd: float

class UsageReport(BaseModel):
    period_start: str               # echoes the request param (ISO 8601 UTC)
    period_end: str
    customer_id: str | None         # null = "all customers"
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    by_provider: list[ProviderBreakdown]
    by_model: list[ModelBreakdown]
```

Why these fields:
- `total_*` covers the dashboard top-line summary
- `by_provider` enables "where is my spend going?" — the spec's "token_breakdown"
- `by_model` provides finer detail — the spec's "model_usage_count"
- `failed_count` per-provider lets ops surface provider-level reliability issues
- `period_start` / `period_end` echo back the request so frontend can render the title

## Scope of THIS cycle

In scope:
- **New DTO file:** `api/schemas/usage.py` (new directory `api/schemas/` if it doesn't exist; otherwise `api/models/usage.py`). See §Decision question below for the location choice.
- **New aggregation method:** add `aggregate_ai_usage(start_ts, end_ts, customer_id=None, provider=None) -> UsageReport` to `SQLiteJobStore`. Uses SQL `SUM` / `COUNT` / `GROUP BY` — never pulls raw rows into Python.
- **New service method:** `UsageReader.get_usage_report(start, end, customer_id=, provider=) -> UsageReport` in `api/services/usage_logger.py`. Validates the 90-day cap, calls into the store, returns the DTO.
- **New router:** `api/routers/usage.py` exposing `GET /api/ai/usage/stats` with router-level `dependencies=[Depends(require_auth)]`. Query params: `start_date`, `end_date`, optional `customer_id`, optional `provider`.
- **Wire into `api/main.py`:** add `app.include_router(usage_router.router)` alongside the existing AI router registrations.
- **Tests:** 4 evaluator tests + 4 supporting (see §Tests below).

Out of scope (per recommendation #1):
- The 4 specialized endpoints (`by-job`, `by-provider`, `timeseries`, `for-job/{job_id}`). Their aggregation patterns are subset of what `aggregate_ai_usage` does — adding them in a follow-up cycle is small.
- Redis parity for `aggregate_ai_usage`. Pre-prod gating; ships in the same Redis-parity cycle as `record_ai_usage` / `get_ai_usage`.
- Frontend UI consuming this endpoint — M2.7 work.

## Implementation order (when authorized)

1. Decide: `api/schemas/` (new) or `api/models/` (existing) for the DTO file.
2. Write `UsageReport`, `ProviderBreakdown`, `ModelBreakdown` Pydantic models.
3. Add `SQLiteJobStore.aggregate_ai_usage(start_ts, end_ts, customer_id=None, provider=None) -> dict`. Returns a dict matching the `UsageReport` shape (frame the SQL with `GROUP BY` for the breakdowns).
4. Add `UsageReader` class (or method on existing `UsageLogger`) in `api/services/usage_logger.py` with `get_usage_report(...)`. Validates `(end - start) <= 90 days` else raises `ValueError`.
5. Write `api/routers/usage.py` with the one endpoint. Returns 400 for date-range violations.
6. Register the router in `api/main.py`.
7. Write the 8 tests below; run; iterate.
8. Run full suite. Verify zero regressions.
9. Commit + push.

## Tests (4 evaluator + 4 supporting)

### Per QA spec evaluator

1. **Aggregation accuracy.** Insert 3 records with known costs (e.g., $0.001, $0.002, $0.003) for the same customer across 2 providers. Query the endpoint. Assert `total_cost_usd == 0.006`, `total_calls == 3`, `by_provider` has correct breakdown.
2. **Security.** Request without bearer token → assert HTTP 401.
3. **Isolation.** Insert records for `customer_A` and `customer_B`. Query with `customer_id=customer_A`. Assert response contains only A's data — verify the SQL filter is doing the work, not just the response shape.
4. **Efficiency.** Run `EXPLAIN QUERY PLAN` on the customer-filtered aggregation SQL. Assert the output mentions `idx_ai_usage_customer_ts` (the index from Cycle DD). Catches a future regression where someone drops the index or writes a query that can't use it.

### Supporting tests added per audit

5. **Date-range cap rejected.** Request with `(end - start) > 90 days` → assert HTTP 400 with error code `PERIOD_TOO_LARGE`.
6. **Empty period returns zero-valued report.** Date range with no rows → assert `total_calls == 0`, `total_cost_usd == 0.0`, `by_provider == []`, `by_model == []`. Catches the "divide by zero" / "empty list" edge case.
7. **Failed calls counted correctly.** Insert 5 records: 4 success + 1 failure. Assert `successful_calls == 4`, `failed_calls == 1`, `total_calls == 5`.
8. **DB-level aggregation (no Python-side summation).** Mock `aggregate_ai_usage` to assert the SQL string contains `SUM(` and `GROUP BY` — locks the constraint that aggregation happens in SQL.

## Acceptance criteria

1. `api/{schemas,models}/usage.py` exists with `UsageReport` Pydantic model.
2. `SQLiteJobStore.aggregate_ai_usage(...)` exists and uses SQL `SUM` / `GROUP BY` (verified by Test 8).
3. `UsageReader` (or method on existing class) in `api/services/usage_logger.py` exposes `get_usage_report(...)`. Enforces 90-day cap.
4. `api/routers/usage.py` exposes `GET /api/ai/usage/stats` with router-level `require_auth`.
5. `api/main.py` registers the router.
6. All 8 tests pass.
7. Full suite stays green: 1,362 baseline + 8 net new = 1,370 passed, 12 skipped, 0 failed.
8. Architecture: the new router file follows the Cycle X pattern — `dependencies=[Depends(require_auth)]` at construction, NOT on individual endpoints.

## Risks + mitigations

- **EXPLAIN QUERY PLAN output differs across SQLite versions.** Mitigation: match substring, not full text. Look for `INDEX idx_ai_usage_customer_ts` rather than exact format.
- **Provider/model `GROUP BY` returns empty list when no rows exist** — already handled by returning `[]` (not `None`). Test 6 covers this.
- **Date parsing of ISO 8601 strings.** SQLite stores timestamps as ISO 8601 strings; `start_ts <= timestamp AND timestamp <= end_ts` works on lexically-comparable ISO strings as long as we use UTC consistently (we do — Cycle DD enforces this).
- **`customer_id` from the request flowing through unchecked.** Today every authenticated caller is effectively system admin; no need to validate `customer_id` against the caller's identity. TODO(M2.3) marker added so the auth tightening lands when identity model does.

## Decisions (LOCKED per user 2026-05-29)

| # | Decision | Status |
|---|---|---|
| 1 | DTO file location: `api/schemas/usage.py` | **LOCKED** |
| 2 | Service location: new `UsageReader` class in `api/services/usage_logger.py`, distinct from `UsageLogger` (no shared base or state) | **LOCKED** |
| 3 | Scope: `GET /api/ai/usage/stats` only; 4 specialized endpoints deferred | **LOCKED** |
| 4 | Date-range violation: hard reject HTTP 400 with `PERIOD_TOO_LARGE` code | **LOCKED** |
| 5 | Tests: 4 evaluator + 4 supporting | **LOCKED** |

## Critique-driven amendments (2026-05-29)

User audit surfaced three technical concerns folded into the implementation:

### A. Float-safe cost aggregation
`cost_estimate_usd` is stored as REAL (float) per Cycle DD. SUM() over floats is non-associative — accumulation error possible at scale. Fix: aggregation SQL converts each row to integer-cents BEFORE summing:

```sql
ROUND(SUM(CAST(ROUND(cost_estimate_usd * 100) AS INTEGER)) / 100.0, 2)
    AS total_cost_usd
```

Per-row `ROUND(cost_estimate_usd * 100)` snaps to nearest cent; CAST to INTEGER guarantees exact sum; final `/100.0` converts back to dollars. Result is cent-precise regardless of input float jitter. The DTO field remains `float` (JSON-friendly) but is now reconciliation-grade for billing.

### B. UsageReader as independent class (no God Service)
`UsageReader` and `UsageLogger` are sibling classes in the same module — no shared base class, no shared state, no shared instance. Each has its own singleton. Co-located only for discoverability.

### C. Customer-ID is auth-derived, not query-derived
**Router signature changes:** `customer_id` is **NOT** a query parameter. The router derives it from the auth context. Today (no identity model), the derived value is always `SYSTEM_CONTEXT_ID`. Future M2.3 will derive from the bearer token / session.

**`UsageReader.get_usage_report()` requires `customer_id`** as a positional arg. Passing `None` is forbidden — `None`-default would silently return global data (privacy hole). The service layer enforces this with an `assert customer_id is not None`.

**`SQLiteJobStore.aggregate_ai_usage()`** also requires `customer_id`. WHERE clause always includes `customer_id = ?` — no escape hatch.

This is a STRONGER guarantee than the original spec, which had `customer_id` as optional with a "system admin sees all" fallback. The locked-down version: there is no "see all" path through any layer.

## Final endpoint surface (post-critique)

```
GET /api/ai/usage/stats
    ?start_date=2026-05-01T00:00:00Z
    &end_date=2026-05-31T23:59:59Z
    &provider=openai            # optional
```

`customer_id` is NOT a query param. Derived server-side from auth context.

## Updated implementation order

1. Add `api/schemas/__init__.py` + `api/schemas/usage.py` with `UsageReport`, `ProviderBreakdown`, `ModelBreakdown` Pydantic models.
2. Add `SQLiteJobStore.aggregate_ai_usage(start_ts, end_ts, customer_id, provider=None)` — REQUIRES customer_id; integer-cents aggregation SQL.
3. Add `UsageReader` class (independent of `UsageLogger`) in `api/services/usage_logger.py` with `get_usage_report(start, end, customer_id, provider=None)`. Validates customer_id is not None, 90-day cap, calls store. Module-level `usage_reader` singleton.
4. Create `api/routers/usage.py` — derives customer_id from auth context (= `SYSTEM_CONTEXT_ID` for now with explicit `TODO(M2.3)` comment), router-level `Depends(require_auth)`.
5. Register in `api/main.py`: `from api.routers import usage as usage_router; app.include_router(usage_router.router)`.
6. Tests (per locked plan):
   - **Test 1 (Aggregation accuracy):** insert diverse data (varying costs, models, success-states), assert sum.
   - **Test 2 (Date guard):** 91-day query → 400.
   - **Test 3 (Tenancy isolation):** test at service layer (router always uses SYSTEM_CONTEXT_ID today). Insert data for `customer_a` and `customer_b`; call `usage_reader.get_usage_report(..., customer_id="customer_a")`; assert no customer_b data.
   - **Test 4 (Structure):** `EXPLAIN QUERY PLAN` over the customer-filtered aggregation SQL contains `idx_ai_usage_customer_ts`.
   - **Test 5 (Empty period):** date range with no rows → zero-valued report (`total_calls=0`, `by_provider=[]`).
   - **Test 6 (Failed calls):** 4 success + 1 failure → `successful_calls=4`, `failed_calls=1`.
   - **Test 7 (DB-level aggregation):** structural — SQL string contains `SUM(` and `GROUP BY`.
   - **Test 8 (customer_id required):** call `get_usage_report(customer_id=None)` → raises (TypeError / AssertionError).
7. Run full suite. Verify zero regressions.
8. Commit + push.

Estimated: ~250 lines of code + 8 tests.
