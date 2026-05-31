---
status: pending
proposed: 2026-05-31
author: Architect (GA3 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0-UNIFIED.md Workstream GA → GA3 (Gemini "Complexity-Moat FAQ Generator", 3.3)
---

# GA3 — Complexity-Moat FAQ Generator

## Goal
Generate long-tail, high-intent FAQ anchors as Schema.org JSON-LD (`FAQPage`)
that the user copies/pastes into their site. **Generate-and-suggest only — no
WordPress write.** Hybrid engine: deterministic templates by default, optional AI
enrichment through the existing `AIRouter`.

## Locked decisions (user, 2026-05-31)
- **WP output mode:** generate-and-suggest only. No WP REST write. → Not
  WP-touching; no `_validate_wp_domain_*` needed.
- **Engine:** **hybrid.** `mode="template"` (default, deterministic, free) +
  `mode="ai"` (opt-in via `AIRouter`).
- **≥6-word rule enforced in BOTH modes** by a single shared validator.
- **AI is strictly additive:** on no key / provider error / output failing the
  ≥6-word filter, **fall back to template** (template is the guaranteed floor).
  *(Supersedes the "402 when no key" idea floated in the umbrella doc — fallback is
  friendlier and keeps the feature working out of the box.)*

## Signature
```python
# api/services/geo_faq.py  (NEW)
async def generate_faq_block(
    geo_config: GeoConfig,
    mode: Literal["template", "ai"] = "template",
    *,
    limit: int = 8,
) -> dict:
    """Return a Schema.org FAQPage dict:
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [ {Question}, ... ],
         "_meta": {"mode_used": "template"|"ai", "token_usage": {...}|None}}
    Async because mode="ai" awaits AIRouter; template mode does no I/O.
    """

def _build_template_questions(geo_config: GeoConfig, limit: int) -> list[str]: ...
def _passes_longtail(query: str) -> bool:
    return len(query.split()) >= 6   # the one rule, applied in both modes
```

### Template engine (`mode="template"`)
- **Input anchors:** `geo_config.topic_entities` × locations
  (`primary_location` + `location_pool`). *(Gemini's "CoreTopicClusters" maps to the
  existing `topic_entities` field — no GeoConfig migration in GA3.)*
- **Templates** (each guaranteed ≥6 words once interpolated; round-robin across
  entities so coverage is even up to `limit`):
  - `"What is {entity} and how does it help people in {location}?"`
  - `"How does {entity} support mental health care in {location}?"`
  - `"What should I expect from {entity} counselling in {location}?"`
  - `"Where can families access {entity} services near {location}?"`
- Each produced `name` is run through `_passes_longtail`; any that somehow falls
  short (degenerate entity/location) is dropped, never emitted.
- `acceptedAnswer.text` in template mode = a clearly-marked draft placeholder, e.g.
  `"[Draft: write a concise 1–2 sentence answer about {entity} in {location}.]"` —
  the user writes the real answer. (We generate the *anchors*, per Gemini's intent.)

### AI engine (`mode="ai"`) — follows the advisor pattern exactly
- Build a `ModelConfig` from a local default-model map resolved against the active
  provider, mirroring `advisor._pick_critic_model()`:
  ```python
  from api.services.ai_router import ai_router, ModelConfig, SYSTEM_CONTEXT_ID
  provider, _ = ai_router._resolve_credentials(SYSTEM_CONTEXT_ID)
  cfg = ModelConfig(model=_DEFAULT_FAQ_MODEL_BY_PROVIDER.get(provider, "gpt-4o-mini"),
                    max_tokens=1500, temperature=0.4)
  resp = await ai_router.call_text(
      customer_id=SYSTEM_CONTEXT_ID,
      system_prompt=_FAQ_SYSTEM_PROMPT,   # instructs: questions only, ≥6 words, JSON list
      user_prompt=_render_entities(geo_config),
      model_config=cfg,
  )
  ```
- **Usage tracking is automatic** — `AIRouter._call()` already logs the `ai_usage`
  event (same as advisor/rewriter). `call_text` takes **no** `task_type` arg today;
  per-task labelling (`task_type="geo_faq"`) is **deferred to M2.4** and noted as a
  follow-up. Do **not** invent a `task_type` parameter.
- Parse the model's questions, run **every** one through `_passes_longtail`, keep the
  survivors. If zero survive (or the call raised / no credentials) → fall back to
  `_build_template_questions` and set `mode_used="template"`.
- Surface tokens from `AIResponse`: `{"input": resp.input_token_count,
  "output": resp.output_token_count, "cost_usd": resp.cost_estimate_usd}`.

## Files to add / modify
| File | Change |
|---|---|
| `api/services/geo_faq.py` | **NEW** — generator, templates, validator, AI path |
| `api/routers/ai.py` | **NEW endpoint** `POST /api/ai/geo-faq` (router already `require_auth`) |
| `frontend/src/components/GEOReportPanel.jsx` | **NEW card** "FAQ Schema": mode toggle (Template/AI), Generate button, JSON-LD copy box, loading + error states. Render JSON-LD as **text** (never `dangerouslySetInnerHTML`). No nav restructure. |
| `frontend/src/data/issueHelp.js` *(or a feature-help location)* | Short V4-style explainer for the feature (see below) |

> **GeoConfig load:** the endpoint reads the domain's config via the same store
> accessor `geo.py` uses — `await store.get_geo_config(domain)`. Follow `geo.py`'s
> existing store-acquisition pattern; do not introduce a new store module.

## Endpoint contract
`POST /api/ai/geo-faq`  (auth required — ai.py router dependency)

Request: `{ "domain": str, "mode": "template"|"ai" = "template", "limit": int = 8 }`
Response 200:
```json
{ "faq_block": { "@context": "...", "@type": "FAQPage", "mainEntity": [ ... ] },
  "questions": ["<q1>", "..."],
  "mode_used": "template" | "ai",
  "token_usage": { "input": 0, "output": 0, "cost_usd": 0.0 } | null }
```
Errors: `401` no auth · `422` unknown `domain` or `topic_entities` empty (clear
message) · `422` malformed body.

## Test plan
**Unit — template (`tests/test_geo_faq.py`):**
- Every generated `name` has **≥6 words** (assert across a realistic GeoConfig).
- **Adversarial:** a one-word entity + one-word location still yields ≥6-word
  questions, OR any sub-6-word candidate is dropped — assert none emitted is < 6 words.
- `limit` is respected; round-robin gives multi-entity coverage (not all from entity #1).
- Empty `topic_entities` → `mainEntity == []` (service level); endpoint maps this to 422.

**Unit — AI (mocked `ai_router.call_text`):**
- Router returns valid ≥6-word questions → emitted; `mode_used="ai"`; `token_usage`
  populated from the mocked `AIResponse`.
- Router returns a 4-word question → filtered; falls back to template;
  `mode_used="template"`.
- Router raises / no credentials → falls back to template, no exception escapes.

**Schema (unit):**
- Output validates as a Schema.org `FAQPage`: `@context`, `@type=="FAQPage"`, and each
  `mainEntity[i]` is a `Question` with `name` + `acceptedAnswer.text`.

**Contract (`tests/test_ai_router_contracts.py` or `test_geo_faq_integration.py`)** —
written BEFORE the frontend card:
- `POST /api/ai/geo-faq` 200 → response has `faq_block`, `questions`, `mode_used`.
- 401 without auth; 422 unknown domain; 422 empty topic_entities; 422 malformed body.
- `mode="ai"` with no provider key → 200 with `mode_used="template"` (graceful fallback,
  **not** an error).

## Security check
- **SSRF:** No — no outbound site fetch; AI egress is via `AIRouter` (already guarded).
- **Auth:** Yes — `/api/ai/*` router carries `require_auth`.
- **WordPress:** No — generate-and-suggest; no WP REST call; no domain-validation needed.
- **XSS:** No — JSON-LD returned as data and rendered in a text/copy box, never injected
  as HTML.

## Documentation impact
- `docs/api.md` — add `POST /api/ai/geo-faq`.
- No `_CATALOGUE` change (generator, not an issue code) → no issue-code parity work.
- `PLAN-V3.0-UNIFIED.md` — flip GA3 to ✅ when merged.

## V4 explainer (apply the new standard to the first net-new feature)
Per `PLAN-V4.0.md`, ship a plain-language explainer with the FAQ card:
- **What it is:** generates ready-to-paste FAQ schema (JSON-LD) built from your
  organisation's topics and locations.
- **Why it's useful:** long-tail FAQ questions are exactly what AI engines and search
  match against; structured FAQ markup makes your answers eligible for rich results and
  AI citation.
- **Good vs bad:** a 6+-word, specific question ("What should I expect from grief
  counselling in Vancouver?") vs a short head term ("counselling") that everyone competes
  for and AI can't anchor to.
- **How it can mislead:** the tool generates *anchors*, not verified answers — you must
  write accurate answers; schema for content you can't honestly answer can hurt trust.
- **How to fix/use:** paste the JSON-LD into the page, replace the draft answers with real ones.

## Acceptance criteria
1. Template mode emits only ≥6-word questions; the adversarial sub-6-word guard passes.
2. AI mode routes through `AIRouter`, logs usage, and **falls back to template** on
   no-key/error/short-output (asserted).
3. Output validates as Schema.org `FAQPage`.
4. Endpoint contract tests (incl. 401/422/fallback) pass **before** the frontend card.
5. No WP write, no SSRF surface. Full suite green, 0 regressions.
