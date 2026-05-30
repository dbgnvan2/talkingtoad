---
status: deferred
proposed: 2026-05-29
revised: 2026-05-29 (technical mechanism kept; strategic identity model added)
deferred: 2026-05-29 (per user — multi-tenant work paused until paid-customer launch is imminent)
author: System Architect (QA) + Claude (audit + strategic gap)
source: Strategic blocker noted in Cycles Y/Z/BB/CC/DD/EE closeouts
---

> **Deferred 2026-05-29.** User decision: TalkingToad currently runs as a
> single-tenant nonprofit deployment. `SYSTEM_CONTEXT_ID` as a single-tenant
> identifier is fine for now. M2.3 (customer credentials), M2.4 (per-task
> routing), and M2.7 (Customer Settings UI) remain blocked on this work,
> but those milestones are not required for the current nonprofit feature
> set. Revisit when paid-customer launch is imminent.
>
> The spec below is preserved verbatim so the audit + scoping work doesn't
> need to be redone. To revive: flip `status` back to `pending`, re-verify
> the audit findings against then-current `main`, and proceed from the
> "Pending decisions for user approval" section.

# Cycle FF: Identity Model design (M2.3/M2.4 prerequisite) — DEFERRED

## What the QA spec gets right (technical mechanism)

The QA recommendation's technical pattern is sound — keep it:

| QA proposal | Status |
|---|---|
| `contextvars` for async-safe identity propagation | ✅ correct primitive — FastAPI's standard approach |
| `IdentityContext` as immutable dataclass | ✅ |
| Middleware-based resolution (vs threading args through every function) | ✅ |
| `customer_id` only in context, never API keys / secrets | ✅ correct privacy boundary |
| No manual customer_id construction in services | ✅ |
| Impersonation explicitly gated + logged | ✅ |
| Test 1 (concurrent isolation), Test 2 (middleware enforcement), Test 3 (downstream consumption) | ✅ all the right behavioural tests |

## What the QA spec under-scopes (the strategic gap)

The QA spec describes *how* identity propagates but not *what identity is*. Five decisions remain unmade:

### Strategic question 1 — What is a "customer"?

The product is currently nonprofit-oriented (single-org users), but PLAN-V3.0.md targets paid customers with per-customer AI billing. The identity model depends on which:

- **(a) One-org-one-customer.** Each customer is a single organisation with a single user. Simplest. Matches the nonprofit reality. No "user accounts within a customer" needed.
- **(b) Customer + users.** Customer can have multiple users (agency model). Needs a `users` table, login/session UI.
- **(c) Full SaaS.** Signup, password reset, email verification, billing. Big surface.

**Recommendation: (a)** for v3.0 launch. Defer (b)/(c) to v4.

### Strategic question 2 — Authentication mechanism?

- **(α) API keys per customer** — long-lived bearer tokens; one row per (customer, key). Simplest. Used by Stripe, OpenAI, Anthropic. Programmatic-friendly.
- **(β) JWT / session cookies** — short-lived signed tokens; requires login flow. Needed if a customer-facing web UI is on the roadmap (M2.7 implies yes).
- **(γ) Both** — API keys for programmatic + sessions for UI.

**Recommendation: (α) only** for this cycle. (β) is a follow-up when M2.7 (Customer Settings UI) actually needs login. Don't build login infrastructure today for UI that doesn't exist yet.

### Strategic question 3 — Where do the AUTH_TOKEN env var and SYSTEM_CONTEXT_ID fit?

Currently `AUTH_TOKEN` is a single shared bearer. Two paths:

- **(i) Deprecate AUTH_TOKEN.** Every request needs an api_key row. AUTH_TOKEN becomes "system admin api_key" — a special row in the table, set via env var on first run.
- **(ii) Keep AUTH_TOKEN as system admin, add api_keys table for customers.** Both auth paths coexist. AUTH_TOKEN → system_account, api_key → matching customer_id.

**Recommendation: (ii)** — preserves backward compat (existing deployments don't break), distinguishes "ops/admin" from "tenant" cleanly.

### Strategic question 4 — Schema additions?

Minimum viable tables for the recommended model:

```sql
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,    -- short slug, e.g. "acme-nonprofit"
    name TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',  -- free | basic | premium (M2.8)
    created_at TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE api_keys (
    api_key_hash TEXT PRIMARY KEY,   -- SHA-256 of the key; never the raw value
    customer_id TEXT NOT NULL,
    label TEXT,                       -- human-readable, "Production / Alice's laptop"
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,                  -- nullable; soft delete
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE INDEX idx_api_keys_customer ON api_keys(customer_id);
```

Note: api_keys stores the **hash** of the key, never the raw value. The raw key is returned exactly once at creation time (a la AWS / GitHub). This is the same pattern as `customer_ai_credentials` will use in M2.3.

### Strategic question 5 — What about existing data?

Current `ai_usage` / `crawl_jobs` rows have no customer_id linkage. On migration:

- **(α) Backfill to SYSTEM_CONTEXT_ID.** Pretend they're all system account. Loses zero data; the existing rows just appear in the system-admin's usage report.
- **(β) Backfill to a synthetic "legacy" customer.** Clean separation; needs migration script.
- **(γ) Mark a clean break.** v3.0 ai_usage rows start fresh; v2.x data is archived/ignored.

**Recommendation: (α)** — `SYSTEM_CONTEXT_ID` is already the placeholder customer_id on every existing row (per Cycle DD's write contract). No backfill needed; the rows are already consistent with the new model.

## Cycle FF — proposed scope (with recommendations applied)

**In scope:**

1. **Schema additions** in `api/services/job_store_base.py` SCHEMA: `customers` table + `api_keys` table + indexes. Idempotent (`CREATE IF NOT EXISTS`). Bootstrap a `system_account` customer row at `init()` time.
2. **`api/services/identity.py`** new module:
   - `IdentityContext` (immutable `@dataclass(frozen=True)`): `customer_id: str`, `is_system_admin: bool`, `auth_source: str` (one of `"api_key"`, `"system_token"`, `"none"`).
   - `_current_identity: ContextVar[IdentityContext | None]` — async-safe per-request state.
   - `get_identity() -> IdentityContext` — fail-fast accessor (raises if context not set).
   - `set_identity(ctx)` — context-managed setter used by middleware only.
3. **`api/services/auth.py` refactor**:
   - `require_auth()` is **augmented**, not replaced. It still rejects bad tokens, but now also resolves the bearer token → `IdentityContext` and sets the contextvar.
   - Token resolution order:
     1. If bearer matches `AUTH_TOKEN` env → `IdentityContext(SYSTEM_CONTEXT_ID, is_system_admin=True, auth_source="system_token")`
     2. Else SHA-256-hash the bearer, look up in `api_keys` table → `IdentityContext(customer_id, is_system_admin=False, auth_source="api_key")`
     3. Else raise 401.
4. **Wire `_resolve_customer_id_from_auth()`** in `api/routers/usage.py` to call `get_identity().customer_id` instead of returning `SYSTEM_CONTEXT_ID` constant. **This is the one M2.3 prerequisite that closes today.**
5. **AIRouter integration**: `_log_usage` and `_call()` already pass `customer_id` as an arg; no change. Callers will gradually shift from passing the `SYSTEM_CONTEXT_ID` constant to passing `get_identity().customer_id`. **Not in scope this cycle** — callers stay on the constant until they're individually migrated.

**Explicitly OUT of scope (deferred):**

- User accounts (multiple users per customer)
- Login UI / session cookies / JWT
- API-key management endpoints (`POST /api/customer/api-keys` etc.) — these would need an admin UI. Today, keys are provisioned via direct DB insert by ops.
- Per-tenant filesystem isolation
- The actual M2.3 work (customer_ai_credentials table + Fernet) — separate cycle once FF lands
- Migration of every caller to use `get_identity()` — incremental work post-FF

## Negative constraints (per QA spec, expanded)

- `IdentityContext` is `frozen=True` — immutable.
- `set_identity()` is called ONLY from the auth middleware. No other call site allowed (enforced by an architecture test: grep `set_identity` outside `auth.py` returns 0).
- `IdentityContext` stores `customer_id` only — never the API key itself, never any credential.
- `get_identity()` raises explicitly if no context is set — never returns a default. This is the privacy boundary: a caller that forgets to be inside an authenticated request can't silently get "system account" data.
- Architecture test: grep for `SYSTEM_CONTEXT_ID` usage in service files; document the migration plan from constant → `get_identity()`.

## Tests (3 evaluator from QA + 4 supporting)

| # | Test | Verifies |
|---|---|---|
| 1 | **Concurrent context isolation** (QA #1) | Spawn 2 concurrent async requests with different bearer tokens; assert each sees its own `IdentityContext` (`contextvars` isolation is correct under asyncio) |
| 2 | **Middleware enforcement** (QA #2) | Call any router endpoint without bearer → 401 BEFORE any router code runs; verify the context never gets set |
| 3 | **Downstream consumption** (QA #3) | Mock a service that calls `get_identity()`; verify it receives the right `IdentityContext` without `customer_id` being passed as a parameter |
| 4 | **AUTH_TOKEN → system_admin** | Bearer = `AUTH_TOKEN` env value → `is_system_admin=True`, `auth_source="system_token"`, `customer_id=SYSTEM_CONTEXT_ID` |
| 5 | **API key → tenant identity** | Bearer = valid api_key hash row → `is_system_admin=False`, `auth_source="api_key"`, `customer_id=` the FK row |
| 6 | **`set_identity` callable from only one place** | Architecture test: grep `set_identity(` returns matches only in `api/services/auth.py` |
| 7 | **`get_identity()` raises if no context set** | Calling outside a request raises `LookupError` (or custom `NoIdentityError`); never returns silent default |

## Risks + mitigations

- **Existing tests using AUTH_TOKEN break.** Mitigation: the AUTH_TOKEN → system_admin path preserves bearer-token-equals-AUTH_TOKEN semantics exactly. Existing tests should pass unchanged. Verify with full suite.
- **api_keys table doesn't have any rows on first run, locking out non-admin clients.** Mitigation: documented seeding via direct DB insert. Or auto-seed a "default-customer" row + a dev api_key in dev mode only.
- **`get_identity()` called outside a request crashes prod.** Mitigation: tests cover the raise behaviour explicitly; any service calling `get_identity()` outside a request context is a code bug and should crash loudly.
- **Tests get verbose**: every test that hits an authenticated endpoint now has to set up identity context. Mitigation: pytest fixture `as_system_admin` / `as_customer(customer_id)` that handles setup.

## Pending decisions for user approval

1. **Approve the strategic scope** — recommendation set: one-org-one-customer (a), API keys only (α), keep AUTH_TOKEN as system admin (ii), backfill via SYSTEM_CONTEXT_ID (α)?
2. **Schema additions** — confirm the `customers` + `api_keys` schema as above?
3. **Defer caller migration** — confirm: this cycle wires `identity.py` + auth middleware + ONE caller (`api/routers/usage.py` `_resolve_customer_id_from_auth`). All other services keep using SYSTEM_CONTEXT_ID constant until individually migrated in follow-up cycles?
4. **Test count** — confirm 3 evaluator + 4 supporting = 7 tests?
5. **Estimate**: ~6 hours wall-time. ~250 lines of code (schema + identity module + auth refactor + the one router migration) + 7 tests. **Do you want me to proceed once approved, or split this into TWO cycles (FF.1: schema+identity; FF.2: auth refactor)?**

Alternative path worth considering: **defer the whole thing.** TalkingToad's current single-tenant nonprofit deployment doesn't NEED multi-tenancy. The M2.x billing infrastructure works fine with SYSTEM_CONTEXT_ID as a single-tenant identifier. If paid-customer launch is not imminent, this cycle can be deferred until it's actually needed. Worth flagging as an option.
