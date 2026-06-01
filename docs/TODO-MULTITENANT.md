# Multi-Tenant / Identity Model — PARKED TODO

> **Status: deliberately deferred by the user (2026-05-31).**
> Multi-tenant is **NOT happening until the user explicitly needs it** (paid-customer
> launch). Do not start any of this without a direct instruction. Stored here so it's
> out of the active roadmap but not lost.

## Why it's parked
TalkingToad currently runs single-tenant (one nonprofit org). The AIRouter already works
single-tenant via `SYSTEM_CONTEXT_ID`. None of the multi-tenant work is needed for the
current feature set or the nonprofit deployment.

## What's blocked on this (from PLAN-V3.0 M2)
- **M2.3** — Per-customer encrypted AI credentials (`customer_ai_credentials` table, Fernet).
- **M2.4** — Per-task-type model routing UI (`customer_model_preferences`).
- **M2.7** — Customer Settings UI (API keys, model prefs, usage widget, tier badge).
- The **Identity Model** itself (the prerequisite): `docs/pending/2026-05-29_identity_model.md`
  (`status: deferred`). Decisions still open there: what a "customer" is, auth mechanism
  (API keys vs JWT/session), where `AUTH_TOKEN`/`SYSTEM_CONTEXT_ID` fit.

## What already shipped that does NOT need multi-tenancy (so it's done)
AIRouter, pricing table, usage persistence + aggregation (Cycles Z–EE) — all run
single-tenant today.

## To revive (when the user says so)
1. Flip `docs/pending/2026-05-29_identity_model.md` `status: deferred` → `pending`.
2. Re-verify its audit findings against then-current `main`.
3. Resolve the open identity questions, then proceed M2.3 → M2.4 → M2.7.

*Parked 2026-05-31 per user instruction #4 ("Multi Tenant is NOT happening until I need
it — store that away in a separate todo").*
