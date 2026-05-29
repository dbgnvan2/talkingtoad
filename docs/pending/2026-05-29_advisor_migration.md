---
status: pending
proposed: 2026-05-29
revised: 2026-05-29 (QA spec hardening + audit findings folded in)
author: System Architect (QA hardened) + Claude (audit + reconciliation)
source: Cycle BB closing-note (advisor.py is the last direct-to-provider holdout)
---

# Cycle CC: Advisor service migration through AIRouter

> **Naming note.** The QA spec labelled this "Milestone 2.3", but PLAN-V3.0.md M2.3 is "Per-customer credentials (encrypted at rest)" — different work. To avoid the collision this cycle is named **Cycle CC** in the cycle log, and "Advisor migration" elsewhere. PLAN-V3.0.md M2.3 (customer credentials) is still blocked on the "where does customer_id come from" identity-model decision flagged at the end of Cycle Z/BB.

## Goal

Migrate the last remaining direct-to-provider LLM call sites
(`_call_openai_critic`, `_call_gemini_critic` in
`api/services/advisor.py`) through AIRouter. After this cycle, the
`TestNoDirectProviderHTTPInServices` architecture guard's allow-list
drops from 2 entries to 0 — closing the "Provider Migration" era of
v3.0.

## Scope of THIS cycle

In scope:
- Refactor `evaluate_page()` to call `ai_router.call_text(...)` for the
  critic LLM call. Remove `_call_openai_critic`, `_call_gemini_critic`,
  `_get_model`, and the module-level `_OPENAI_API_KEY` / `_GEMINI_API_KEY`
  / `_OPENAI_ENDPOINT` / `_GEMINI_ENDPOINT` / `_TIMEOUT` constants.
- Preserve `_fetch_page()` and its `httpx.Client` usage — it's for HTML
  fetching, not LLM calls, and is SSRF-guarded. See §Reconciliation #1.
- Drop the `advisor.py` allow-list entry in
  `tests/test_ai_pricing.py::TestNoDirectProviderHTTPInServices._ALLOWED_VIOLATIONS_PER_FILE`.
- Decide and implement the JSON-mode handling — see §Pending decision.
- Update any tests that mock `_call_*_critic` (none found per audit but
  re-verify after the refactor).

Explicitly OUT of scope:
- `_fetch_page` itself — it's already SSRF-guarded and serves a non-LLM
  purpose. Could be moved to a shared utility later but that's a tidying
  cycle, not blocking.
- `_html_to_markdown` placeholder — comment in code says "in production,
  use html2text or similar". That's its own follow-up (M-something).
- All non-LLM logic in advisor.py (response parsing, markdown rendering,
  AdvisorReport construction) — preserved unchanged.

## Audit findings (verified against advisor.py @ HEAD c0a9cc2)

| Item | Reality |
|---|---|
| LLM call sites | **2** — `_call_openai_critic` (line 95), `_call_gemini_critic` (line 172) |
| Other `httpx` use | **1** — `_fetch_page` (line 56), legitimate HTML fetch, NOT a provider call |
| `httpx.Client` sync use inside async `evaluate_page` | **Yes, pre-migration anti-pattern** — blocking sync HTTP inside an async function blocks the event loop. The AIRouter migration **incidentally fixes this** by making the LLM call truly async. |
| `response_format: {"type": "json_object"}` (OpenAI-only) | **Yes** at line 156 — see §Pending decision |
| Public functions | **Only `evaluate_page()`** is public; everything else is `_private` |
| Existing test coverage | `tests/test_advisor.py` (model + rendering tests), `tests/test_advisor_calibration.py` (uses `evaluate_page` real-call). Per audit grep, NO tests mock the `_call_*_critic` private functions directly. |
| Allow-list entry today | `advisor.py: 2` in `_ALLOWED_VIOLATIONS_PER_FILE` (`openai.com` URL + `generativelanguage.googleapis` URL) |

## Reconciliation of the QA spec with reality

### 1. "No Direct HTTPX in advisor.py" — refined to "no direct PROVIDER calls"

The QA spec's Test 4 wording ("Attempt to import openai or httpx (for
external URLs)") would break `_fetch_page` if applied literally. The
right invariant is **"no direct provider URL literals in advisor.py"**
— which the existing `TestNoDirectProviderHTTPInServices` architecture
guard from Cycle BB already enforces. This cycle drops the allow-list
exception, no new test needed.

The `httpx` import stays — `_fetch_page` continues to use it.

### 2. "advisor.py must import only from ai_router" — refined

The QA spec's wording would forbid `from api.models.advisor import ...`
which is obviously needed. The real constraint is:
**For LLM calls, advisor.py uses only `ai_router.call_text(...)`. Other
imports (models, SSRF guards, logging, json, regex) are unchanged.**

The architecture guard `TestNoProviderSDKImports` (Cycle Z) plus
`TestNoDirectProviderHTTPInServices` (Cycle BB) together enforce this
exactly — no new test needed.

### 3. Pending decision — JSON-mode handling

`_call_openai_critic` uses `"response_format": {"type": "json_object"}` —
OpenAI's structured-output mode. `ModelConfig` is intentionally sparse
(3 fields per Cycle Z approval) and does NOT expose this. Three options:

- **(a) Drop the hint.** Prompt already says "Return valid JSON only".
  Failures caught by existing `json.loads()` try/except.
- **(b) Add `json_mode: bool` to ModelConfig.** Provider-agnostic flag —
  OpenAI maps to `response_format`, Gemini ignores. Mild abstraction leak.
- **(c) Wrap response parsing in single-retry logic** so malformed-JSON
  triggers one retry with a more-emphatic prompt. Robust regardless.

**Recommendation:** **(a) drop the hint** in this cycle. The prompt is
already explicit; OpenAI compliance is near-100% on `gpt-4o` even
without the flag. If we observe parse failures in production after
migration, escalate to (c) — never (b), which violates the sparse
ModelConfig constraint the user explicitly approved.

This is the single open decision blocking implementation. Acceptance
criteria assume (a).

## Implementation order (when authorized)

1. **Identify the right model.** Like rewriter.py, advisor.py pre-flights
   credential resolution to pick the right model per provider:
   `gpt-4o` (OpenAI) or `gemini-2.0-flash` (Gemini). Both already in
   `PRICING` table. Pattern matches `rewriter.py:_pick_model()`.
2. **Refactor `evaluate_page()`** to call
   `ai_router.call_text(customer_id=SYSTEM_CONTEXT_ID, system_prompt=..., user_prompt=..., model_config=...)`.
   The critic's system prompt (lines 104-111 / 181-188) becomes
   `system_prompt`; the content + comparison_note becomes `user_prompt`.
3. **Add the explicit JSON-mode handling decision.** Per §Pending
   decision recommendation: drop the hint, rely on prompt + post-parse
   error handling. Add a single try/except around `json.loads()` (already
   present in `_parse_critic_response`).
4. **Delete `_call_openai_critic`, `_call_gemini_critic`, `_get_model`**,
   and the module-level provider-key / endpoint / timeout constants.
5. **Map AIRouter exceptions** to the existing error surface:
   - `ProviderAuthError` → re-raise (the advisor router maps to 402)
   - `ProviderAPIError` → re-raise (advisor router maps to 5xx; preserves
     observability via the AIRouter `_log_usage` `success=False` path)
6. **Drop the advisor.py allow-list entry** in
   `tests/test_ai_pricing.py::TestNoDirectProviderHTTPInServices._ALLOWED_VIOLATIONS_PER_FILE`.
   With the migration done, the count must be 0.
7. **Verify existing tests:**
   - `tests/test_advisor.py` — no `_call_*_critic` mocks per audit. Tests
     focus on model construction and report rendering. Should pass
     unchanged.
   - `tests/test_advisor_calibration.py` — calls `evaluate_page` directly.
     Per its existing pattern (calibration test) it may make a real API
     call; if so, behaviour unchanged after migration.
8. **Run full suite.** Target: 1,341 + 0 net new tests (the architecture
   test count stays the same, just the allow-list shrinks).
9. **Commit + push.**

## Acceptance criteria (finalized)

1. `_call_openai_critic`, `_call_gemini_critic`, `_get_model` removed
   from `api/services/advisor.py`.
2. Module-level constants removed: `_OPENAI_API_KEY`, `_GEMINI_API_KEY`,
   `_OPENAI_ENDPOINT`, `_GEMINI_ENDPOINT`, `_TIMEOUT`.
3. `_fetch_page` preserved with `httpx.Client` intact.
4. `evaluate_page()` calls `ai_router.call_text(...)` exactly once per
   request (no fallback chain — AIRouter handles provider selection).
5. The `advisor.py` entry in `_ALLOWED_VIOLATIONS_PER_FILE` is removed
   (count goes 2 → 0). The architecture test will assert this
   automatically via its "got cleaner than expected" check.
6. Full suite: 1,341 passed (no net change in test count; the existing
   guard updates instead of adding a new test), 12 skipped, 0 failed.
7. `TestNoDirectProviderHTTPInServices` passes with advisor.py at 0
   provider-URL matches.
8. **Observability check (the QA spec's Test 3):** add one new contract
   test that calls `evaluate_page` with a mocked `ai_router.call_text`,
   asserts that the `_log_usage` was invoked with `customer_id=SYSTEM_CONTEXT_ID`,
   `provider` in `{"openai", "gemini"}`, and `success=True`. This is the
   migration's positive proof — the call goes through AIRouter and gets
   logged. Without this test, we have no positive assertion that the
   migration actually routes through AIRouter (only the architecture
   guard which is negative — "no URLs").

## Risks + mitigations

- **JSON parse failures after dropping `response_format`.** Mitigation:
  the existing post-parse try/except in `_parse_critic_response` keeps
  working; if observed failure rate exceeds baseline, escalate to
  option (c) retry logic in a follow-up.
- **AsyncIO behaviour change.** The pre-migration code used sync
  `httpx.Client` inside async `evaluate_page` (event-loop-blocking
  anti-pattern). Post-migration is fully async. This is an
  *improvement*, but slot-timing-sensitive tests could in theory be
  affected. Run the full suite to verify.
- **`tests/test_advisor_calibration.py` may call real API.** Verify
  during execution whether the test is marked `@pytest.mark.live` or
  similar; if so the real call still happens through AIRouter and
  ideally is a quarantined live test like the GEO apply one. If not,
  it's a hidden network-dependent test that should be quarantined.

## Out of scope (deferred — same as Cycle Z/AA/BB closeouts)

- M2.3 (customer_ai_credentials + Fernet encryption) — still blocked
  on identity-model decision
- M2.4 (per-task-type model routing) — same blocker
- M2.5 (ai_usage table persistence) — independent; could go in parallel
- M2.9 (DeepSeek driver) — independent; net-new code
- Per-customer identity-model decision cycle — strategic blocker for
  M2.3/M2.4/M2.7

## Decisions still pending user approval

1. Approve / reject the revised spec as a whole.
2. Confirm the JSON-mode handling recommendation: **option (a) drop the
   hint**?
3. Confirm scope: ONLY the LLM call migration in advisor.py — explicitly
   leave `_fetch_page` and `_html_to_markdown` alone for now?
4. Confirm the new observability test (acceptance criterion #8) is
   wanted — it's beyond the original QA spec but addresses the gap
   between "no URLs" (negative) and "actually went through AIRouter"
   (positive).
