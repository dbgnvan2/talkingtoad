---
status: pending
proposed: 2026-05-29
author: Claude (post-AA review + advisory)
source: Cycle Z explicit deferral + post-M2.2 architecture audit
---

# Cycle BB candidate: ai_analyzer.py migration through AIRouter

## Why this is the right next work

After Cycle Z (M2.1 AIRouter) and Cycle AA (M2.2 PriceLookup), the
AIRouter abstraction handles ~30% of LLM calls in the codebase
(only `api/services/rewriter.py` was migrated). The other ~70% are
still direct-to-httpx in two files:

| File | Direct call sites | Consequence |
|---|---|---|
| `api/services/ai_analyzer.py` | 4 | No cost tracking, no usage log, no per-customer fallback for the AI page-analysis path or any image-vision analysis. Architecture guard scan finds these as "still using SDK-shaped HTTP" violations. |
| `api/services/advisor.py` (service) | 2 endpoint constants | Same — the advisor's `evaluate_page()` function. |

**Per the post-M2.2 architecture-guard scan**, `ai_analyzer.py` accounts
for 4 of 6 remaining direct provider URL references in `api/services/`.
Migrating it through AIRouter:

1. Removes the bulk of remaining direct-to-provider plumbing.
2. **Validates `AIRouter.call_vision()` end-to-end** — currently exercised
   only by unit tests in `test_ai_router.py`, never by a real caller.
   The ai_analyzer image-analysis path is the first real consumer.
3. Brings cost tracking, sanitised usage log, and (future M2.3) per-customer
   credentials to the AI page-analysis and image-vision flows automatically.
4. Sets up `advisor.py` service migration as a clean follow-up cycle
   (smaller scope, same pattern).

**It does NOT depend on M2.3 (customer credentials), M2.4 (per-task
routing), or any other deferred infrastructure** — pure refactor with
no new architecture decisions.

## Scope — what exactly migrates

### Text path (2 call sites)

`api/services/ai_analyzer.py:126` → `analyze_with_ai(prompt_key, context) -> str`:
- Currently reads `OPENAI_API_KEY` / `GEMINI_API_KEY`, picks provider by
  key availability (OpenAI preferred), formats the prompt from
  `PROMPT_LIBRARY[prompt_key]`, and delegates to `_call_openai` or
  `_call_gemini`.
- **After migration:** keeps the prompt-library formatting; replaces the
  key-resolution + dispatch with one `ai_router.call_text(...)` call
  passing `customer_id=SYSTEM_CONTEXT_ID`. Returns the `AIResponse.content`
  string (preserves the existing `str` return type — no caller-visible
  contract change).
- Removes `_call_openai` and `_call_gemini` (~40 lines each).

### Vision path (2 call sites)

`api/services/ai_analyzer.py:195` → `analyze_image_with_ai(image_url, current_alt) -> dict`:
- Currently fetches the image bytes inline inside `_call_openai_vision`
  and `_call_gemini_vision` (each driver does its own fetch + format).
- **After migration:** caller (this function) fetches once via
  `httpx.AsyncClient` (the SSRF-safe path already in use), then passes
  `image_bytes` + `image_mime` to `ai_router.call_vision(...)`.
- Returns the existing `dict` shape (description, suggested_alt, scores).
  AIRouter returns `AIResponse.content` as a string — we parse it the
  same way the inline drivers do today (JSON extraction with fallback).
- Removes `_call_openai_vision` and `_call_gemini_vision` (~50 lines each).

### Module-level state cleanup

- Remove module-level `OPENAI_API_KEY` / `GEMINI_API_KEY` env reads at
  the top of the file (lines ~24-25 of pre-migration form). AIRouter
  reads env per call.
- Remove `import httpx` from this module (drivers handle HTTP). The
  vision-path image fetch is the one exception — for that, `httpx` is
  fine since image-bytes fetching is not "provider HTTP".
- Architecture guard expansion: `tests/test_ai_pricing.py::TestNoMoneyMathInDrivers`
  fixture currently scans only `api/services/providers/`. After this
  cycle, add a sibling architecture test that scans `api/services/`
  (excluding `providers/` and `ai_router.py`/`ai_pricing.py`) for any
  remaining `openai.com` / `generativelanguage.googleapis` / `anthropic.com`
  literals. **Expected matches after migration:** 2 (in `advisor.py`,
  to be cleaned in a follow-up cycle). Test must allow that gap
  explicitly so it doesn't fail incorrectly.

## Out of scope (deferred)

- `api/services/advisor.py` service migration — same pattern, smaller.
  Its own follow-up cycle.
- M2.3 (customer credentials) — independent. The `customer_id` flowing
  through ai_analyzer is still `SYSTEM_CONTEXT_ID` after this migration.
- M2.5 (ai_usage persistence) — independent. `_log_usage()` still
  INFO-logs only after this migration; persistence lands separately.
- Adding a vision pricing path. `gemini-1.5-flash` (the model
  ai_analyzer currently uses for vision) is already in the pricing
  table with `vision: True`. Cost tracking will Just Work.
- Adding non-OpenAI/non-Gemini providers — DeepSeek/Anthropic drivers
  are M2.9+.

## Acceptance criteria

1. `api/services/ai_analyzer.py`:
   - `analyze_with_ai(prompt_key, context) -> str` delegates to
     `ai_router.call_text(...)` with `customer_id=SYSTEM_CONTEXT_ID`.
   - `analyze_image_with_ai(image_url, current_alt) -> dict` fetches the
     image bytes via `httpx.AsyncClient` (SSRF guard preserved), then
     delegates to `ai_router.call_vision(...)`. Result-dict shape
     unchanged (description, suggested_alt, accuracy_score, etc.).
   - No more `_call_openai*` / `_call_gemini*` private functions.
   - No more module-level `OPENAI_API_KEY` / `GEMINI_API_KEY` reads.
   - File LOC reduces from 527 to ≤ ~250 (the 4 driver methods and
     their HTTP plumbing are ~280 lines; counts may differ slightly).

2. `tests/test_ai_pricing.py::TestNoMoneyMathInDrivers` fixture
   extended OR new test `TestNoDirectProviderHTTPInServices` added that:
   - Scans `api/services/` for `openai.com` / `generativelanguage.googleapis` /
     `anthropic.com` / `deepseek.com` URL literals.
   - Excludes `api/services/providers/`, `api/services/ai_router.py`,
     `api/services/ai_pricing.py`.
   - Allows known exceptions in `advisor.py` (2 lines) with explicit
     comment marker so the count is locked but not zero. When advisor
     migrates in a follow-up cycle, the test gets a 2-line removal.

3. Existing AI-readiness / image-analysis tests pass. ai_analyzer has
   coverage in:
   - `tests/test_ai_readiness.py` — analyze_with_ai uses
   - `tests/test_geo_image_ai.py` — image analysis uses
   - any test mocking `_call_openai` / `_call_gemini` private symbols
     needs to be updated to mock at the `ai_router.call_text` /
     `call_vision` boundary (same pattern as Cycle Z rewriter test fix).

4. Full suite stays green. Current baseline: 1,340 passed, 12 skipped,
   0 failed. New baseline target: 1,340+ passing (some tests may be
   replaced; net should be ≥ existing count).

5. Architecture-guard `test_no_sdk_imports_under_api_services` from
   Cycle Z continues to pass (no new SDK imports introduced).

## Implementation order (when authorized)

1. Identify every test that mocks `_call_openai` / `_call_gemini` /
   `_call_openai_vision` / `_call_gemini_vision` — list them up-front
   so the migration unblocks all at once.
2. Refactor `analyze_with_ai()` to use `ai_router.call_text(...)`.
   Run the text-path tests; iterate until green.
3. Refactor `analyze_image_with_ai()`:
   - Extract image fetching into a small helper (uses existing
     SSRF-safe `fetch_image` from `api/crawler/fetcher.py` if available,
     or a minimal local httpx call mirroring the current pattern).
   - Replace the per-driver vision dispatch with one
     `ai_router.call_vision(...)` call.
   - Run vision-path tests; iterate.
4. Delete `_call_openai`, `_call_gemini`, `_call_openai_vision`,
   `_call_gemini_vision`, the module-level env-var reads, and the
   top-level `import httpx` (replace with a targeted import in the
   image-fetch helper).
5. Add the architecture-guard test for "no direct provider URLs in
   `api/services/` outside the allow-list".
6. Run full suite. Verify zero regression.
7. Commit + push.

Estimated cycle size: ~6 hours wall-time (the test refactors are the
slow part — vision tests have non-trivial fixture setup).

## Advisory — what else I'd recommend, not part of this cycle

1. **Tidy `docs/pending/`** — five completed specs are accumulating.
   Cycle U did a consolidation pass into `functional-specification.md` §8.6;
   a sibling §8.7 should fold in Cycles V/W/X/Z/AA and clear `pending/`.
   This is a small standalone tidying cycle (~30 minutes) — not blocking.
2. **The advisor.py service migration** (same pattern, ~2 sites)
   should be its own cycle immediately after this one. Together,
   ai_analyzer + advisor close every direct-to-httpx provider call in
   `api/services/` and the architecture-guard's "expected matches"
   count drops to 0.
3. **The "customer_id from where?" question** remains the strategic
   blocker for everything in M2.3 / M2.4 / M2.7. Worth a focused
   architectural-decision cycle before attempting any of those.
4. **PLAN-V3.0.md M2.5 (ai_usage table)** could go in parallel with
   ai_analyzer migration since they touch different code. If you'd
   rather have persisted usage data than the bigger refactor, swap
   the order.
