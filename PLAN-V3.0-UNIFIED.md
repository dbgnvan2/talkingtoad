---
status: active-roadmap
last_reviewed: 2026-05-31
supersedes_for_planning: none
references_readonly: [PLAN-V3.0.md, docs/functional-specification.md, docs/thresholds.md]
---

# TalkingToad v3.0 — Unified Roadmap (orche guiding spec)

> **What this file is.** The single, *editable* roadmap orche works from for v3.0.
> It merges two sources:
> 1. The existing milestone plan in **`PLAN-V3.0.md`** (which is `status: current` →
>    **READ-ONLY**; reproduced here only as a status table, never edited in place), and
> 2. The **Gemini "GEO Authority Engineering Roadmap"** (4 granular milestones),
>    reconciled against the code already on `main`.
>
> **Why a new file.** `PLAN-V3.0.md` is frozen (`status: current`). This file is the
> live working surface; update *this* as cycles land.
>
> **Authoritative, read-only references** (never edit): `docs/functional-specification.md`,
> `docs/thresholds.md`, `PLAN-V3.0.md`, and any file with `status: current`.

---

## How orche consumes this document

orche's loop is **micro-spec → approval → implement+test → commit**, one cycle per
deliverable. This umbrella does **not** replace the per-cycle micro-spec — for each
unstarted item below, the architect emits a `docs/pending/YYYY-MM-DD_<feature>.md`
micro-spec, **stops for user approval**, then the developer/QA cycle runs.

**Trigger pattern (from the Gemini spec, mapped to orche roles):**

| Role | Instruction template |
|---|---|
| **Orchestrator** | "Execute `<Item ID>` from `PLAN-V3.0-UNIFIED.md`." |
| **Architect** | "Write the `docs/pending/` micro-spec for `<Item ID>`. List exact files, signatures, test plan, security check. Stop for approval." |
| **Senior Dev** | "Review `<Item ID>` against `<files>`. Audit dependencies + constraints. Approve or bounce." |
| **Developer** | "Implement `<Item ID>`. Write code + Evaluator test(s). Run suite. Commit." |
| **QA** | "Adversarially audit `<Item ID>`. 'What would a correct-looking but wrong result look like?' Add the failing case." |

**Self-checking gates every cycle must pass** (from `CLAUDE.md` + `.orche/architect_directives.md`):
- Every frontend-called endpoint has a **contract test asserting each field the frontend reads** *before* the frontend code.
- Every text-processing / scoring function has **≥1 adversarial test**.
- Issue-code changes keep `_CATALOGUE` ↔ `issueHelp.js` ↔ `docs/issue-codes.md` **in parity**.
- Security check is explicit: **SSRF / auth / WordPress / XSS** — yes/no each.
- No new files outside the `api/` · `frontend/src/` · `tests/` · `docs/` layout.

---

## Part A — Milestone status (M0–M11, from PLAN-V3.0.md)

Reference only. Full detail lives in the read-only `PLAN-V3.0.md`. This table is the
truth-of-record for *where each milestone stands* as of 2026-05-31.

| Milestone | Title | Status | Notes |
|---|---|---|---|
| **M0** | Foundation, security, docs cleanup | ✅ **Done** | SSRF audit, advisor auth, containerize (Railway), prod hardening, fix-domain routers restored |
| **M1** | Complete AI-readiness v2.0 gaps | ✅ **Substantially done** | Confidence labels, chrome-aware paragraph counting (Cycle W); spot-verify remaining §gaps |
| **M2** | AI multi-provider + usage tracking | 🟡 **In progress / partly blocked** | AIRouter, pricing, usage persistence + aggregation shipped (Cycles Z–EE). **M2.3 (per-customer creds), M2.4 (per-task routing UI), M2.7 (Settings UI) are BLOCKED** on the deferred Identity Model (`docs/pending/2026-05-29_identity_model.md`, `status: deferred` — user paused multi-tenant until paid-customer launch) |
| **M3** | Google-validated GEO **audit** extensions | ⬜ **Pending** | `SCHEMA_VISIBLE_MISMATCH`, `X-Robots-Tag`/`AI_PREVIEW_SUPPRESSED`, `AI_NO_VISUAL_COMPANION`, `AI_MAIN_CONTENT_LOW_RATIO`, + M3.6 scoring-scope fixes. **Distinct from Workstream GA below** (audit vs generation) |
| **M4** | Content Freshness suite | ⬜ **Pending** | `CONTENT_DATE_STALE_VISIBLE`, `CONTENT_STAT_OUTDATED`, page-type cadence |
| **M5** | Citation ingestion (sibling tool) | ⬜ **Pending** | `POST /api/jobs/{id}/ai-citations`, `AI_CITED_PAGE`, `AI_HIGH_VALUE_UNCITED` |
| **M6** | GSC OAuth (opt-in) | ⬜ **Pending** | Strictly opt-in; tool runs identically without it |
| **M7** | Reporting & confidence surfacing | ⬜ **Pending** | PDF/Excel AI-readiness + freshness + citations sections |
| **M8** | Endpoint contract backfill | ✅ **Done** | Backfill + CI endpoint-coverage guard shipped in v2.5 |
| **M9** | Refactor hotspots | ⬜ **Pending / partial** | `issue_checker.py` partially split (`checkers/`); `Results.jsx`, `crawl.py` outstanding |
| **M10** | Frontend infrastructure | ⬜ **Pending** | Toast system, a11y baseline, code-splitting |
| **M11** | Docs sync & v3.0 release | ⬜ **Pending** | Final version bump + doc sync |

**Single biggest open decision (gates M2 completion):** whether to revive the
**Identity Model** (un-defer multi-tenant) or hold. Until then, M2's multi-tenant
sub-items stay parked and the AIRouter runs single-tenant.

---

## Part B — Workstream GA: GEO Authority Engineering

The Gemini roadmap's four "Milestone 3.x" items, **renumbered GA1–GA4** to avoid
collision with the existing PLAN-V3.0 Milestone 3. GA is a *generation/authority*
track; PLAN-V3.0 M3 is an *audit* track. They are complementary and both ship in v3.0.

**Reconciliation summary (verified against `main`, 2026-05-31):**

| Gemini ID | This ID | Verdict | Evidence |
|---|---|---|---|
| 3.1 Structural Tree-Walking Auditor | **GA1** | ✅ **Fixed + verified (2026-05-31)** | Was *count-based* (flagged verbose sections, missed `<h3>`). Rewritten to **positional depth (threshold 3) + `<h2>`/`<h3>` + wrapper-transparent walk**; `<ol>`/`<table>` count as content; field renamed `is_h2_answer_buried`→`is_answer_buried` (back-compat retained). 11 positional tests incl. the verbose-section false-positive guard + `<h3>` case. Full suite **1393 passed, 0 fail**. Spec: `docs/pending/2026-05-31_ga1_positional_answerability.md`. |
| 3.2 Dynamic Entity-Prompt Injection | **GA2** | ✅ **Verified complete (2026-05-31)** | `advisor._build_geo_context()` interpolates 4-field GeoConfig whitelist with legacy fallback when `geo_config is None` (Cycle FF / FF.1). Both Gemini evaluator tests present + passing (7 tests total). No delta. |
| 3.3 Complexity-Moat FAQ Generator | **GA3** | 🆕 **Net-new** | `api/services/geo_faq.py` absent |
| 3.4 Authoritative Entity Schema Factory | **GA4** | 🆕 **Net-new** | No schema factory; needs new GeoConfig field `entity_wikipedia_url` |

**Cross-cutting decisions for GA3 + GA4 (locked with user 2026-05-31):**
- **Generate-and-suggest only.** Output is returned for the user to copy/paste or
  download. **No WordPress writes** of any kind. → Not WP-touching, so no
  `_validate_wp_domain_*` needed; explicitly call this out as "no WP surface".
- **No outbound fetch.** `entity_wikipedia_url` and any URL is *embedded as a string*,
  never fetched. → **No SSRF surface.**
- **Auth required.** New endpoints live in `api/routers/ai.py` (GA3) and
  `api/routers/geo.py` (GA4) — both already gated by `require_auth`.
- **XSS:** generated JSON-LD is returned as a JSON string and must be rendered in the
  frontend as **text in a copy box** (never `dangerouslySetInnerHTML`).
- **GUI:** surface as a **new card** inside an existing GEO panel — no navigation
  restructure.

---

### GA1 — Structural Tree-Walking Auditor  ·  ✅ Fixed + verified (2026-05-31)

- **Goal:** Enforce node-depth constraints so the core answer is extractable.
- **Status:** Shipped in Cycle GG (count-based); **corrected to positional + `<h3>` in the GA1
  fix cycle** (`docs/pending/2026-05-31_ga1_positional_answerability.md`). Full suite green.
- **Existing signature:** `assess_extractability(parsed_page: ParsedPage) -> dict`
  (`{score: 0-100, is_extractable: bool, ...}`) and
  `audit_answerability(parsed_page, soup=None) -> str | None` (returns
  `"GEO_SUMMARY_BURIED"` or `None`). `ContentNodeAuditor` walks the local DOM.
- **Files (read to verify, do not rebuild):** `api/services/extractability.py`,
  `api/crawler/issue_checker.py` (emit site ~L496), `api/crawler/checkers/registry.py`
  (catalogue L1201, scoring L235, confidence L1381), `api/crawler/parser.py` (pre-computed signal).
- **Data isolation:** Local DOM tree only — **no external API / LLM**. ✔ confirmed.
- **Verify-only acceptance:**
  - [x] Confirm the constraint matches the implemented depth logic; document any delta. → **done, 3 deltas below.**
  - [x] Confirm an adversarial test pins the burial threshold and asserts `GEO_SUMMARY_BURIED`
        fires. → added `test_burial_threshold_boundary_exactly_four` (3↔4 edge);
        `tests/test_extractability.py::TestContentNodeAuditor` green (5 tests).
- **✅ Deltas resolved (2026-05-31 — user classified the original behaviour a bug, fixed now):**
  1. **Semantic model → positional.** Now measures *where* the first content node sits
     (push-down depth), not *how many* follow. A leading answer is depth 1 regardless of length;
     only answers pushed below media/preamble are flagged. Threshold **3**.
  2. **Scope → `<h2>` and `<h3>`.** Walker iterates both; FAQ answers under `<h3>` are covered.
  3. **Walk → document-order, wrapper-transparent.** A content node wrapped in a `<div>` under
     the heading is found at depth 1 (the old direct-siblings-only walk missed it).
  4. **Content tags → `+<ol>`, `+<table>`** (decisions B, C). Field renamed
     `is_h2_answer_buried`→`is_answer_buried`, back-compat retained.
- **Security check:** SSRF no · auth n/a (crawl-time) · WordPress no · XSS no.
- **Docs impact:** none beyond confirming `docs/issue-codes.md` parity for `GEO_SUMMARY_BURIED`.

---

### GA2 — Dynamic Entity-Prompt Injection  ·  ✅ Shipped (verify-only)

- **Goal:** Contextualize the advisor critic using runtime `GeoConfig`.
- **Status:** Implemented in Cycles FF / FF.1. **Verification cycle.**
- **Existing signature:** `advisor._build_geo_context(geo_config: GeoConfig | None) -> str`,
  prepended to `system_prompt`. Whitelist = `org_name`, `topic_entities`,
  `primary_location`, `location_pool`. `AdvisorRequest.geo_config` is wired and exposed on
  `POST /api/ai/advisor`.
- **Files (verify):** `api/services/advisor.py`, `api/routers/ai.py`, `api/models/geo_config.py`.
- **Data isolation:** prompt built from whitelisted GeoConfig fields only; **no hardcoded
  entity strings**; legacy static prompt when `geo_config is None`. ✔ confirmed.
- **Verify-only acceptance:**
  - [x] Test 1: `org_name` appears in the built system prompt. →
        `test_prompt_includes_org_and_primary_location_when_geoconfig_provided` (green).
  - [x] Test 2: legacy parity when `geo_config is None`. →
        `test_fallback_prompt_when_geoconfig_is_none` (green — asserts no `ENTITY VALIDATION
        CONTEXT` block, legacy core phrase preserved).
  - **Bonus coverage already present:** all-four-fields-land, HTTP-endpoint threading,
    and a non-whitelisted-fields-don't-leak guard (7 tests total, all passing). **No delta.**
- **Security check:** SSRF no · auth **yes** (`require_auth` on `/api/ai/*`) · WordPress no · XSS no.
- **Docs impact:** none.

---

### GA3 — Complexity-Moat FAQ Generator  ·  🆕 Net-new

- **Goal:** Generate long-tail, high-intent FAQ anchors as JSON-LD `FAQPage` objects,
  for the user to paste into their site (no WP write).
- **Signature:**
  `generate_faq_block(geo_config: GeoConfig, mode: Literal["template","ai"] = "template", *, limit: int = 8) -> list[dict]`
  → returns a `FAQBlock` (list of Schema.org `FAQPage`/`Question` JSON-LD dicts).
- **Mode design (hybrid — user decision 2026-05-31):**
  - `"template"` (**default**): deterministic. Build questions from `GeoConfig.topic_entities`
    × locations (`primary_location` + `location_pool`) via question templates
    (e.g. `"What is the role of {entity} in {location}-based therapy?"`). Free, no key needed.
  - `"ai"` (**opt-in**): route through the existing **AIRouter**, following the advisor
    pattern exactly — `ai_router.call_text(customer_id=SYSTEM_CONTEXT_ID, system_prompt=…,
    user_prompt=…, model_config=cfg)` — inheriting credential resolution, provider routing,
    and automatic `ai_usage` logging.
  - **Note (verified):** `call_text` has **no** `task_type` parameter today; per-task
    labelling (`task_type="geo_faq"`) is **deferred to M2.4**. Do not invent the arg — use a
    local default-model map like `advisor._pick_critic_model()`.
- **Shared ≥6-word validator (enforced in BOTH modes):**
  `_passes_longtail(query: str) -> bool` → `len(query.split()) >= 6`. Every generated
  question passes through this filter regardless of mode. **No short-tail keywords.**
- **Fallback chain:** `ai` mode → if no key (402), provider error, or **all** AI questions
  fail the ≥6-word filter → fall back to `template` mode and tag `mode_used: "template"`.
- **Files to add/modify:**
  - **add** `api/services/geo_faq.py` (generator + validator + templates)
  - **modify** `api/routers/ai.py` — `POST /api/ai/geo-faq` (`require_auth`); body
    `{job_id | domain, mode}`; response `{faq_block: [...], mode_used, token_usage?}`
  - **modify** `api/services/ai_router.py` — register `"geo_faq"` task-type default model
  - **modify** `frontend/src/components/GEOReportPanel.jsx` (or `GeoSettings.jsx`) — add a
    "FAQ Schema" card with a mode toggle + copy box (loading/error states required)
- **Data isolation:** template mode is pure-local; AI mode's only network egress is the
  provider call **through AIRouter** (which already guards keys). No site fetch.
- **Evaluator / test plan:**
  - *Unit (template):* every generated query has **≥6 words** — adversarial: assert a
    5-word candidate is rejected/expanded, never emitted.
  - *Unit (ai, mocked router):* router returns a 4-word question → output is filtered and
    falls back to template; `mode_used == "template"`.
  - *Unit (ai, mocked router):* router returns valid 7-word questions → emitted; a
    `ai_usage` row is written with token counts.
  - *Schema:* each FAQBlock item validates as Schema.org `Question`/`Answer` (`@type`,
    `name`, `acceptedAnswer.text` present).
  - *Contract:* `POST /api/ai/geo-faq` → 200 schema (`faq_block`, `questions`, `mode_used`);
    401 no auth; 422 unknown `domain` / empty `topic_entities`; `mode=ai` with no key →
    200 `mode_used:"template"` (graceful fallback, NOT 402 — template is the guaranteed floor).
  - *Adversarial:* empty `topic_entities` → returns `[]` (or 422 with clear message), never crashes.
- **Security check:** SSRF **no** (no site fetch) · auth **yes** (`/api/ai/*`) ·
  WordPress **no** (generate-and-suggest) · XSS **no** (render in copy box as text).
- **Docs impact:** `docs/api.md` (+endpoint), `docs/ai-routing.md` (geo_faq default model);
  no `_CATALOGUE` change (generator, not an issue code).

---

### GA4 — Authoritative Entity Schema Factory  ·  🆕 Net-new

- **Goal:** Generate a nested, Schema.org-compliant JSON-LD block
  (`Organization → Service → FAQPage`) linking the org to its authoritative entity via
  `sameAs` — for the user to paste (no WP write).
- **Signature:**
  `build_entity_schema(geo_config: GeoConfig) -> dict` → a single nested JSON-LD object;
  serialised to string at the router edge.
- **GeoConfig additions required (model change — handle serialization):**
  - **add** `entity_wikipedia_url: str = ""` to `api/models/geo_config.py` (the `sameAs` target)
  - persist + round-trip in `api/services/geo_config_store.py` (SQLite + Redis); default `""`
  - *(GA3 reuses existing `topic_entities` — no migration needed there.)*
- **Constraints:**
  - Output must nest `Organization` → `hasOfferCatalog`/`Service` → `FAQPage`.
  - Must include `sameAs` populated from `entity_wikipedia_url` (omit `sameAs` cleanly when blank).
  - Deterministic — **no LLM**. Pure construction from GeoConfig.
- **Files to add/modify:**
  - **add** `api/services/geo_schema_factory.py`
  - **modify** `api/routers/geo.py` — `POST /api/ai/geo-schema` *(or `/api/geo/entity-schema`)*
    (`require_auth`); body `{job_id | domain}`; response `{jsonld: str, valid: bool, warnings: [...]}`
  - **modify** `api/models/geo_config.py` + `api/services/geo_config_store.py` (field above)
  - **modify** `frontend/src/components/GEOReportPanel.jsx` (or `GeoSettings.jsx`) — add an
    "Entity Schema" card + copy box; add `entity_wikipedia_url` input to GEO settings
- **Evaluator / test plan:**
  - *Schema validity:* pass output to a JSON-LD validator (or structural assertion) →
    assert mandatory `@context`, `@type`, and `sameAs` (when url present) exist and nesting is correct.
  - *Adversarial:* blank `entity_wikipedia_url` → `sameAs` omitted, `valid:true`, never emits
    `"sameAs": ""` or `null`.
  - *Adversarial:* `org_name`/`topic_entities` empty → graceful minimal object or 422 with
    clear message, never a crash or malformed JSON.
  - *Contract:* `POST` → 200 schema; 401 no auth; 422 missing identifier.
  - *Serialization:* GeoConfig round-trips `entity_wikipedia_url` through store (SQLite + Redis).
- **Security check:** SSRF **no** (url embedded, never fetched) · auth **yes** ·
  WordPress **no** · XSS **no** (text copy box).
- **Docs impact:** `docs/api.md` (+endpoint), `docs/thresholds.md` untouched (read-only);
  note new GeoConfig field in `docs/architecture.md` if a config schema section exists.

---

## Recommended sequencing for orche

1. **GA1, GA2 — verify-only** (fast). Confirms the Gemini 3.1/3.2 intent is satisfied and
   closes the loop on already-shipped work. One small cycle each (or a combined verify cycle).
2. **GA3 — FAQ generator** (no schema migration; hybrid template/AI). Ship template mode +
   AI mode behind the shared ≥6-word validator.
3. **GA4 — Entity Schema Factory** (adds a GeoConfig field; deterministic). Do after GA3 so the
   GEO settings UI card and config-field work land together.
4. Then resume the PLAN-V3.0 audit track per priority — **M3** (Google-validated audit codes)
   pairs naturally with this GA work, followed by **M4/M5** as desired.

**Parking note:** M2 multi-tenant (M2.3/2.4/2.7) stays blocked on the Identity Model until
you decide to revive it. GA3's AI mode does **not** require that work — it uses the
AIRouter's existing single-tenant key resolution.

---

## Constraints checklist (every GA cycle re-affirms)

- [ ] No WordPress write in GA3/GA4 (generate-and-suggest only).
- [ ] No outbound fetch of user/entity URLs (no SSRF surface); if that ever changes, route
      through `api/crawler/fetcher.py:is_ssrf_safe()` first.
- [ ] New endpoints depend on `require_auth` (they live in `ai.py` / `geo.py`).
- [ ] Generated JSON-LD rendered as **text**, never injected as HTML.
- [ ] Pydantic model changes use existing classes (`GeoConfig`) + `Field(default_factory=...)`
      for mutable defaults; serialize in `geo_config_store.py`.
- [ ] Each new service/scoring/text function ships with **≥1 adversarial test**.
- [ ] Each frontend-called endpoint has a contract test **before** the frontend code.
- [ ] If any GA item later adds an issue code, update `_CATALOGUE` + `issueHelp.js` +
      regenerate `docs/issue-codes.md` (parity tests).

---

*Unified 2026-05-31 from `PLAN-V3.0.md` (read-only) + Gemini "GEO Authority Engineering
Roadmap". Edit THIS file as cycles land; never edit `PLAN-V3.0.md`.*
