---
status: pending
proposed: 2026-05-29
author: System Architect
source: PLAN-V3.0.md M2.2
---

# Milestone 2.2: Pricing Table

## The Signature

- **Input:** `provider` (str), `model` (str), `input_tokens` (int), `output_tokens` (int).
- **Output:** `Decimal` (calculated USD cost).
- **Objective:** Implement a centralized `PriceLookup` service that maps provider/model combinations to unit prices, decoupling pricing logic from driver calculations.

## Data Isolation

- **Pricing Registry:** price definitions MUST be isolated in a dedicated config or JSON schema (`api/services/pricing_table.json`).
- **Currency Safety:** calculations MUST be performed using `decimal.Decimal` to avoid floating-point errors common in financial arithmetic.
- **Immutability:** pricing definitions MUST be immutable at runtime.

## Negative Constraints

- **No Hardcoded Math:** forbidden to hardcode pricing constants inside driver logic (e.g. `input_tokens * 0.000003`). All calculations must flow through the `PriceLookup` service.
- **No Network Calls:** the price registry must be local/in-memory. It cannot trigger an API call to the provider to fetch current pricing.
- **No Null Costs:** `AIRouter` must raise an `UnknownModelError` if a model is passed for which no pricing entry exists, rather than returning `0.0`.

## The Evaluator

- **Unit Test 1 (Calculation Accuracy):** assert that 1,000 input tokens and 1,000 output tokens for `gpt-4o` result in the exact USD cost defined in the table.
- **Unit Test 2 (Safety):** verify that requesting a non-existent model (e.g. `gemini-9.9-beta`) raises `UnknownModelError`.
- **Unit Test 3 (Contract Update):** verify that the AIRouter correctly calls the `PriceLookup` service and populates the `cost_estimate_usd` field in the `AIResponse`.

---

## Audit findings & scoping questions (Cycle AA pre-execution)

### Current state (verified)

| Item | State |
|---|---|
| `cost_estimate_usd` in AIResponse | **Exists as `float`** (Cycle Z); currently hardcoded to `0.0` in both drivers with `# TODO(M2.2)` markers |
| `_SAFE_METADATA_KEYS` includes `cost_estimate_usd` | yes — log_usage already plumbs it through |
| `decimal.Decimal` used anywhere | no |
| `UnknownModelError` | does not exist |
| `pricing_table.json` or `ai_pricing.py` | does not exist |
| Models currently called | `gpt-4o` (OpenAI rewriter), `gemini-2.0-flash` (Gemini rewriter), `gpt-4o` (ai_analyzer default), `gemini-1.5-flash` (ai_analyzer default), other Gemini variants in `_AI_READINESS_CONFIDENCE` references |

### Discrepancies vs the spec / PLAN-V3.0.md M2.2

1. **`Decimal` output vs current `float` field.** The spec's signature returns `Decimal`, but `AIResponse.cost_estimate_usd` is typed `float`. Three options:
   - (a) Change `AIResponse.cost_estimate_usd` from `float` to `Decimal` (strict — but every downstream consumer that does JSON-serialise the field needs a `Decimal` encoder, and `log_usage` records become `Decimal` instances)
   - (b) Compute as `Decimal` internally, convert to `float` at the AIResponse boundary (pragmatic — keeps the JSON-friendly type but loses the precision-correctness story at the field)
   - (c) Compute as `Decimal`, expose both: `cost_estimate_usd_decimal: Decimal` and keep `cost_estimate_usd: float` derived from it (belt-and-braces — adds field surface)

2. **JSON vs Python module.** The spec says `api/services/pricing_table.json`. PLAN-V3.0.md M2.2 says `api/services/ai_pricing.py` with a Python `PRICING` dict. Tradeoffs:
   - **JSON pro:** edit without Python knowledge; portable; clearly "config" not "code"
   - **JSON con:** needs a parser + schema validation; can't use `Decimal` literals (JSON has no Decimal type — strings would be needed and parsed); mutable after load unless wrapped in `MappingProxyType`; loses type-checking
   - **Python pro:** native `Decimal` literals; trivially immutable via `frozenset` of tuples; type-checked; matches `ai_router.py` pattern (all constants in code today)
   - **Python con:** changing pricing requires a code deploy (not a config-only update)

3. **Pricing unit ambiguity.** Spec says "unit prices" without naming the unit. Industry convention + PLAN-V3.0.md M2.2 use **per-1M-tokens** (e.g. OpenAI gpt-4o: $2.50 input / $10.00 output per 1M). Need explicit confirmation so the table values match the math.

4. **`LAST_REVIEWED` constant from PLAN.md M2.2 not in the new spec.** PLAN.md proposed a `LAST_REVIEWED = "2026-05-27"` constant alongside the table so admins can see how stale prices are. Worth keeping — pricing drifts every few months as providers cut prices.

5. **Where does cost computation happen?** The spec says "AIRouter must call PriceLookup". Two implementations:
   - (a) **Drivers compute cost themselves.** Pro: cost lives next to where tokens are extracted. Con: drivers now depend on the pricing service (coupling).
   - (b) **AIRouter wraps the driver call and patches cost in.** Pro: drivers stay simple (current Cycle Z shape). Con: AIRouter does post-processing on the dataclass (which is `frozen=True` — needs `dataclasses.replace`).
   - The "no hardcoded math in driver logic" constraint argues for (b). Drivers would only know about tokens; they'd never compute money.

### Negative-constraint nuance

The spec says **"AIRouter must raise UnknownModelError if no pricing entry exists, rather than returning 0.0."** This means **every model called must be in the pricing table** — there's no fallback. Implication for this cycle:

- The current rewriter calls `gpt-4o` (OpenAI) and `gemini-2.0-flash` (Gemini) → both must be in the table from day one.
- `api/services/ai_analyzer.py` has its own caller paths and calls `gemini-1.5-flash` and `gpt-4o` → if we strictly enforce, ai_analyzer breaks on day one unless we either (a) refactor it through AIRouter in this cycle (which we deferred from Cycle Z) or (b) pricing table includes models that ai_analyzer uses today even though ai_analyzer doesn't go through AIRouter yet.
- **Recommendation:** ship the pricing table with all currently-referenced models (gpt-4o, gpt-4o-mini, gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-flash-8b, claude-3-5-sonnet, claude-3-5-haiku, deepseek-chat per PLAN-V3.0.md). Strict-raise behaviour activates only at the AIRouter boundary today; legacy callers (ai_analyzer.py, advisor service) are unaffected until they migrate.

## Scoping decisions (approved 2026-05-29 via AskUserQuestion)

1. **Decimal vs float at AIResponse boundary** → option (a): compute as `Decimal` internally, convert to `float` at the `AIResponse` boundary. `AIResponse.cost_estimate_usd` stays `float`. The precision-correct math happens inside `PriceLookup`; the field-assignment cast to float loses sub-cent precision only at the very end, which is acceptable for an *estimate* surfaced as a single decimal field.
2. **File format** → Python module: `api/services/ai_pricing.py` with `Decimal` literals. NOT JSON. Matches PLAN-V3.0.md M2.2 and the existing pattern of `ai_router.py` keeping constants in code.
3. **Pricing unit** → per-1M-tokens (matches PLAN-V3.0.md M2.2 and provider documentation conventions). Confirmed via the spec's source-of-truth pointer to PLAN-V3.0.md.
4. **`LAST_REVIEWED` constant** → included.
5. **Cost computation site** → option (b): AIRouter post-processes the driver's `AIResponse` via `dataclasses.replace`. Drivers stay simple — they only know about tokens, never about money. Honors "no hardcoded math in drivers" cleanly.
6. **Initial table contents** → all PLAN-V3.0.md M2.2 models (8 entries):
   - `("openai", "gpt-4o")` — $2.50 / $10.00 per 1M (vision)
   - `("openai", "gpt-4o-mini")` — $0.15 / $0.60 per 1M (vision)
   - `("gemini", "gemini-2.0-flash")` — $0.075 / $0.30 per 1M (vision)
   - `("gemini", "gemini-1.5-flash-8b")` — $0.04 / $0.15 per 1M (no vision)
   - `("anthropic", "claude-3-5-sonnet")` — $3.00 / $15.00 per 1M (vision)
   - `("anthropic", "claude-3-5-haiku")` — $0.80 / $4.00 per 1M (vision)
   - `("deepseek", "deepseek-chat")` — $0.27 / $1.10 per 1M (no vision)

   Plus `("gemini", "gemini-1.5-flash")` because `ai_analyzer.py` still references it directly — needed when ai_analyzer migrates. Price per Google's published rate: $0.075 / $0.30 per 1M (vision-capable).

## Acceptance criteria (finalized)

1. `api/services/ai_pricing.py` exists with:
   - `LAST_REVIEWED: str = "2026-05-27"` constant (per PLAN-V3.0.md M2.2 freshness reference)
   - `PRICING: Mapping[tuple[str, str], dict]` immutable mapping of `(provider, model)` → `{"input_per_1m": Decimal, "output_per_1m": Decimal, "vision": bool}`
   - Wrapped in `types.MappingProxyType` to be runtime-immutable
   - `class PriceLookup` exposing `calculate_cost(provider, model, input_tokens, output_tokens) -> Decimal`
   - Class-level (or module-level) singleton — same pattern as `ai_router` (module-level instance)
2. `UnknownModelError(AIRouterError)` added to `api/services/ai_router.py` exception hierarchy.
3. `PriceLookup.calculate_cost(...)` raises `UnknownModelError` for `(provider, model)` not in the table.
4. AIRouter wraps `_call()` to look up cost and patch it via `dataclasses.replace(response, cost_estimate_usd=float(decimal_cost))`. Driver-emitted `cost_estimate_usd=0.0` is silently overwritten.
5. The three QA-evaluator tests pass:
   - **Test 1 (Calculation Accuracy):** 1000 input + 1000 output tokens × gpt-4o → `Decimal('0.0125')` (= 1000/1_000_000 × 2.50 + 1000/1_000_000 × 10.00).
   - **Test 2 (Safety):** `PriceLookup.calculate_cost("gemini", "gemini-9.9-beta", 1, 1)` raises `UnknownModelError`.
   - **Test 3 (Contract Update):** `AIRouter.call_text(...)` with mocked driver returns an `AIResponse` whose `cost_estimate_usd` is the float of the table-computed cost, not the driver's `0.0`.
6. The existing 1,318 / 12 skipped baseline holds. No regression in the Cycle Z tests (especially `TestUnifiedResponseContract` which asserts response shape).
7. Architecture test: assert no provider-driver file contains arithmetic of the form `* 0.00...` or `/ 1_000_000` — confirms drivers don't compute money. (Implemented as a focused grep similar to the SDK-import guard.)

## Implementation order (when authorized)

1. Add `UnknownModelError` to `ai_router.py`.
2. Write `api/services/ai_pricing.py` with the 8 + 1 entries, `LAST_REVIEWED`, `PriceLookup` class.
3. Write 3 unit tests for `PriceLookup` itself (calculation, unknown model, immutability).
4. Modify AIRouter `_call()` to post-process via `dataclasses.replace`.
5. Write the contract test (Test 3) at the AIRouter level.
6. Write the architecture guard (no math in driver files).
7. Run targeted tests, then full suite.
8. Commit + push.

Estimated: 1 cycle, ~200 lines of new code + ~6 new tests.
