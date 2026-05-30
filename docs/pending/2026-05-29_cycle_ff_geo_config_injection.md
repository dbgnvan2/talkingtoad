---
status: historical
proposed: 2026-05-29
revised: 2026-05-29 (audit findings + prompt design + scoping questions)
shipped: 2026-05-30
author: System Architect (QA) + Claude (audit + reconciliation)
source: User pivot away from deferred-Identity-Model Cycle FF
---

> **Shipped 2026-05-30.** All 5 acceptance tests pass; full suite at
> 1,380 passed / 12 skipped / 0 failed (matches predicted target of
> 1,375 baseline + 5 new). All Cycle CC `test_advisor_routing.py` tests
> still green (zero regression in AIRouter call shape). Implementation:
>
> 1. `api/models/advisor.py`: added `geo_config: GeoConfig | None = None`
>    to `AdvisorRequest`; GeoConfig import wired in.
> 2. `api/services/advisor.py`: added `_GEO_CONTEXT_PREFIX` constant and
>    `_build_geo_context()` helper (whitelisted to the 4 entity fields);
>    `_run_critic` signature extended with `geo_config` kwarg; system_prompt
>    construction prepends interpolated context when provided, empty
>    string when None (fallback parity).
> 3. `evaluate_page` threads `request.geo_config` through to `_run_critic`.
> 4. `tests/test_advisor_geo_injection.py`: 5 tests covering interpolation,
>    fallback parity (semantic contract, not exact-string), end-to-end
>    threading, all-four-fields, and the no-leak privacy boundary.

# Cycle FF (revised): GeoConfig injection into advisor.py

> **Cycle name note.** The previously-saved Cycle FF (`2026-05-29_identity_model.md`) is `status: deferred` — that slot is free for this new work. The deferred Identity Model spec stays preserved at its own filename for future revival.

## What the QA spec gets right

| QA proposal | Status |
|---|---|
| Wire existing `GeoConfig` into `advisor.py`, not redesign | ✅ correct — leverages already-shipped infra |
| Modify `AdvisorRequest` to accept optional `GeoConfig` | ✅ |
| Fallback to current generic prompt when `geo_config` is None | ✅ critical for backward compat with all the Cycle CC tests |
| No changes to AIRouter call shape | ✅ |
| No changes to AdvisorReport JSON schema | ✅ — entity findings flow through existing AuthoritySignals/FactualGrounding |
| No hardcoded "Living Systems" / "Vancouver" in advisor.py | ✅ |

## Audit findings (verified against current `main`)

| Item | State |
|---|---|
| `GeoConfig` dataclass (existing) | `domain`, `org_name`, `topic_entities` (list), `primary_location`, `location_pool` (list), plus model-config + report fields |
| `AdvisorRequest` dataclass (existing) | `url`, `content`, `original_content`, `job_id`. Has `__post_init__` validation requiring url OR content. |
| Existing GeoConfig server-side lookup pattern | `api/routers/ai.py:251` fetches by domain from `store.get_geo_config(domain)` for the **image-analysis** path |
| Existing `analyze_image_with_geo` takes `geo_config: dict[str, Any]` | not `GeoConfig` directly — service interface uses dict for serialisability |
| Current `_run_critic` prompt (post-Cycle-CC) | Pure generic 6-property GEO review — no entity-specific guidance |
| Cycle CC `test_advisor_routing.py` tests | Verify AIRouter call shape; the planned change keeps the call shape intact (only prompt text changes) so these should pass unmodified |

## Spec review — five places needing sharpening

### 1. Where does GeoConfig come from?

QA spec: "Modify `AdvisorRequest` to accept `geo_config: GeoConfig | None`" — i.e., **client-side delivery**.

Existing image-AI pattern: **server-side lookup by domain** (`store.get_geo_config(domain)`).

Three paths:
- **(a) Client-side only.** Client fetches GeoConfig (it has the GET /api/geo/settings endpoint) and passes it along in the AdvisorRequest. Simple, matches the QA spec, no router changes.
- **(b) Server-side auto-lookup.** Router extracts domain from URL and fetches GeoConfig automatically. Matches the image-AI pattern. But breaks for content-only requests (no URL → no domain).
- **(c) Hybrid.** Accept geo_config in request; if absent and URL is provided, fall back to server-side lookup by domain.

**Recommendation: (a) for this cycle.** Honors the QA spec literally; defers (c) to a follow-up if user-experience demands less client work. (a) is also the only path that works uniformly for both URL and content-only requests.

### 2. GeoConfig dataclass vs dict at the service boundary

The existing `analyze_image_with_geo(... geo_config: dict[str, Any])` takes a dict. AdvisorRequest is itself a dataclass. Two paths:

- **(α) AdvisorRequest gets `geo_config: GeoConfig | None`** — typed end-to-end. Need to import GeoConfig into `api/models/advisor.py`.
- **(β) AdvisorRequest gets `geo_config: dict | None`** — matches the image-AI service interface. Less type safety.

**Recommendation: (α)**. The cost (one import) is trivial; the benefit (Pydantic + type checking + ergonomic field access) is real. The image-AI mismatch is a pre-existing inconsistency we can clean up later; no need to propagate it.

### 3. Which GeoConfig fields go into the prompt?

GeoConfig has ~12 fields. The QA spec mentions `org_name`, `topic_entities`, `primary_location`. Need to be explicit about the others:

| Field | Include in prompt? | Rationale |
|---|---|---|
| `org_name` | ✅ | The entity the page should authoritatively mention |
| `primary_location` | ✅ | Primary geographic anchor |
| `location_pool` | ✅ | Secondary geo entities for distribution |
| `topic_entities` | ✅ | Domain topics the page should engage with |
| `domain` | ❌ | Internal lookup key; not LLM-relevant |
| `model` / `temperature` / `max_tokens` | ❌ | Advisor uses its own model selection via `_pick_critic_model()`; GeoConfig's are for image-AI only |
| `client_name` / `prepared_by` | ❌ | Report-rendering metadata, not entity-validation context |
| `created_at` / `updated_at` | ❌ | Internal metadata |

### 4. Test 2 (Fallback Parity) is too brittle

QA spec wording: "Assert that the generated prompt **exactly matches** the legacy static prompt."

This breaks if anyone ever fixes a typo or clarifies the legacy prompt. The real contract is: **when geo_config is None, the prompt must NOT contain any GeoConfig-derived strings.**

Revised Test 2: pass `geo_config=None`; assert the prompt does NOT contain `"TestCorp"`, `"Springfield"`, or any other test-fixture entity. Optionally also assert that key phrases from the legacy prompt are still present (semantic contract, not exact-string).

### 5. The QA spec doesn't show the new prompt design

This is the single biggest gap. The behavioural change rides entirely on the prompt content. I propose:

```python
# When geo_config is provided, prepend this block to the generic prompt:
GEO_CONTEXT_PREFIX = """ENTITY VALIDATION CONTEXT:
The page under evaluation should authoritatively represent the following entities:
- Organization: {org_name}
- Primary location: {primary_location}
- Service locations: {location_pool_csv}
- Topic entities: {topic_entities_csv}

When evaluating, surface findings in the existing six properties:
- factual_grounding: flag missing or mismatched mentions of the entities above
  as 'generalities' (with issue='entity not present') or absent specific_facts.
- authority_signals: list specific entity mentions found on the page in
  citations_present; list expected entity mentions absent in citations_missing
  (with claim='[entity name]' and why_needed='domain authority').

DO NOT add new JSON keys for this — use the existing schema.
"""
```

This preserves the LLM output schema (per the QA spec's "No Schema Changes Yet" constraint) while giving the LLM concrete entity context to evaluate against.

## Scope of THIS cycle (with recommendations applied)

In scope:
1. **`api/models/advisor.py`**: add `geo_config: GeoConfig | None = None` field to `AdvisorRequest`. Import GeoConfig at top.
2. **`api/services/advisor.py` `_run_critic`**: when `request.geo_config` is provided, prepend the `GEO_CONTEXT_PREFIX` (interpolated with the relevant fields) to `system_prompt`. When None, system_prompt is the unchanged legacy generic prompt.
3. **Threading**: `evaluate_page` passes `request.geo_config` through to `_run_critic` (current signature is `_run_critic(content, original)` — add `geo_config` arg).
4. **Tests**: 3 evaluator + 2 supporting (see below).

Explicitly OUT of scope:
- Server-side auto-lookup of GeoConfig by domain (deferred per recommendation #1).
- Changes to the JSON output schema (per QA constraint).
- Changes to AIRouter / `_pick_critic_model` / AdvisorReport.
- Migration of frontend to send GeoConfig — that's a frontend cycle.
- `analyze_image_with_geo` consistency cleanup (the dict-vs-dataclass mismatch noted in audit) — separate small cycle.

## Implementation order

1. Add `geo_config: GeoConfig | None = None` to `AdvisorRequest` in `api/models/advisor.py`. Add the import. Don't break `__post_init__`.
2. In `api/services/advisor.py`:
   - Define `_GEO_CONTEXT_PREFIX` constant near the prompts.
   - Add a helper `_build_geo_context(geo_config: GeoConfig | None) -> str` that returns either the interpolated prefix or empty string.
   - Update `_run_critic(content, original, geo_config=None)` to prepend the geo context to `system_prompt`.
   - Update `evaluate_page` to thread `request.geo_config` through.
3. Write the 5 tests in a new file `tests/test_advisor_geo_injection.py`.
4. Run targeted tests; iterate.
5. Run full suite. Verify zero regressions on existing Cycle CC `test_advisor_routing.py` tests.
6. Commit + push.

## Tests (3 evaluator + 2 supporting)

| # | Test | Verifies |
|---|---|---|
| 1 | **Prompt Interpolation** (QA #1) | Pass GeoConfig with `org_name="TestCorp"`, `primary_location="Springfield"`. Mock AIRouter. Assert `system_prompt` passed to `call_text` contains both "TestCorp" and "Springfield". |
| 2 | **Fallback Parity** (QA #2, revised) | Pass `geo_config=None`. Mock AIRouter. Assert `system_prompt` does NOT contain "ENTITY VALIDATION CONTEXT" header. Also assert the legacy core phrase ("content quality reviewer for Generative Engine Optimization") IS present (semantic continuity). |
| 3 | **End-to-End with GeoConfig** (QA #3) | Run `evaluate_page` with a full GeoConfig and mocked AIRouter returning the minimal valid critic JSON. Assert no exceptions and the returned markdown is non-empty. |
| 4 | **All four entity fields interpolated** (supporting) | Pass GeoConfig with all four entity fields populated. Assert each field's value appears in `system_prompt`. Catches a refactor that drops one field by accident. |
| 5 | **No leak of non-entity fields** (supporting) | Pass GeoConfig with `client_name="ConfidentialCo"`, `model="gemini-2.0-pro"`. Assert NEITHER value appears in the prompt. Privacy/correctness boundary — those fields aren't for the LLM. |

## Acceptance criteria

1. `AdvisorRequest.geo_config` field exists, type `GeoConfig | None`, default `None`.
2. `_run_critic` accepts `geo_config` arg; threads through from `evaluate_page`.
3. When provided, the prompt contains `org_name`, `primary_location`, `location_pool` items, `topic_entities` items.
4. When None, the prompt is the legacy generic prompt (no ENTITY VALIDATION CONTEXT block).
5. All 5 tests above pass.
6. All Cycle CC `test_advisor_routing.py` tests still pass (no regression in AIRouter call shape).
7. Full suite stays green: 1,375 baseline + 5 net new = **1,380 passed, 12 skipped, 0 failed**.

## Risks + mitigations

- **`AdvisorRequest` is a Pydantic-adjacent dataclass; adding a nested GeoConfig may trip serialization.** Mitigation: GeoConfig is already a dataclass; nesting works with `dataclasses.asdict()` and FastAPI's Pydantic-via-dataclass auto-conversion. If issues, fall back to dict at the request boundary and reconstruct in the service.
- **Risk of breaking the Cycle CC API contract tests.** Mitigation: keep `_run_critic`'s call to `ai_router.call_text` unchanged — only the contents of system_prompt change. Cycle CC tests assert call structure (4 kwargs), not prompt content.
- **Frontend doesn't yet send GeoConfig.** Acceptable — `geo_config` defaults to None, advisor behaves as it does today. The new entity-evaluation behaviour activates only when frontend (or any client) opts in.

## Decisions still pending user approval

1. **Confirm path (a) for GeoConfig delivery** — client-side only, no server-side auto-lookup this cycle?
2. **Confirm path (α) for type** — `geo_config: GeoConfig | None` (typed) vs dict?
3. **Confirm the field whitelist** in §3 of the review (only the 4 entity fields go into the prompt; reporting / model-config fields stay out)?
4. **Confirm the proposed `GEO_CONTEXT_PREFIX` prompt design** (or do you want different wording)?
5. **Confirm Test 2's revised contract** (assert absence of GeoConfig strings + presence of legacy core phrase) over the brittle "exactly matches legacy" assertion?

Estimated scope after approvals: ~3 hours. ~80 lines of changed code (small) + 5 tests.
