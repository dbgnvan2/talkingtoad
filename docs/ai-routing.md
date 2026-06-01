---
title: AI Routing
status: draft
last_updated: 2026-06-01
---

# AI Routing

## Overview

The AIRouter (`api/services/ai_router.py`) selects the appropriate AI model for each task type. It supports multiple providers (OpenAI, Google Gemini) with configurable routing via `ModelConfig` objects.

The router exposes two call methods:
- `call_text()` — text-only LLM calls.
- `call_vision()` — multimodal vision + text calls.

Both return an `AIResponse` with the model output and a `cost_estimate_usd` computed by `PriceLookup`.

## System Context

### Single-Tenant (Current)

- `SYSTEM_CONTEXT_ID` is hardcoded to a single value.
- All AI requests use the same API keys from environment variables.
- Usage tracking is aggregated, not per-customer.

### Multi-Tenant (Parked)

- Per-customer AI key management is **not shipped**.
- See [`TODO-MULTITENANT.md`](TODO-MULTITENANT.md) for the planned design.
- The routing table supports per-customer overrides in the data model, but the UI and provisioning flow are not implemented.

## Cost and Pricing

### Reference

- Current pricing is tracked in `api/services/ai_pricing.py` via the `PriceLookup` class.
- Prices use `Decimal` precision and are updated manually when provider pricing changes.
- **LAST_REVIEWED**: Check the file header for the last review date.

### Usage Persistence

- Usage records are stored in the `ai_usage` table (SQLite) or `ai_usage:*` keys (Redis).
- Records include: `timestamp`, `task_type`, `model`, `input_tokens`, `output_tokens`, `cost_estimate`.
- Aggregation queries are available via the admin endpoints (single-tenant only).

## Provider Notes

### OpenAI

- Default provider for most task types.
- Requires `OPENAI_API_KEY` environment variable.

### Google Gemini

- Supported as an alternative provider.
- Requires `GEMINI_API_KEY` environment variable.
- Available for GEO analysis via the model selector (`/api/geo/ai-model`).

### DeepSeek

- **Not wired** in the current release. No DeepSeek integration exists.

## Related

- AI-readiness labels: [`ai-readiness.md`](ai-readiness.md)
- Security model: [`security-model.md`](security-model.md)
- API reference: [`api.md`](api.md)
