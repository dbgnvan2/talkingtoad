# PLAN — "Search Everywhere" GEO enhancements

**Initiative owner tracker.** Durable backlog + status ledger for the GEO/AI-citability
work derived from the *"From 'SEO' to 'Search Everywhere'"* source doc (Neil Patel /
NP Digital). This is the **master tracker** — nothing in this initiative ships without
a row here. Per-phase implementation detail lives in `docs/pending/<date>_<phase>.md`
micro-specs (authored one phase at a time), then folds into
`docs/functional-specification.md` at completion.

Critical review that produced this backlog: see §"Critical review" below (promoted here
from the approved pending plan).

---

## Locked decisions (2026-07-22, owner)

- **A. Build sooner, accept rework.** New issue codes may be built **before** the
  R3→R5 scoring refactor lands. Each new code is hand-scored provisionally now and
  **MUST be re-derived into the R5 `(confidence, effect_size, fatal_override)` +
  `scope` matrix** when R5 lands. Every new code below carries a **`R5-REWORK`** flag
  as a standing reminder.
- **B. TalkingToad-only.** The 8 serp-discover ideas and the SERP-similarity commodity
  score are **out of scope** (serp-discover owns them). Not tracked here.
- **C. Lead with E1 + E2** (brand-entity consistency + body near-duplicate) — the two
  genuinely-new, crawl-only, highest-strategic-fit items.
- **D. Per-phase micro-specs**, one phase at a time, each with full V4 explainer
  content and approved before code.

---

## Status ledger (the "don't miss anything" list)

Status values: `backlog` → `spec` (micro-spec in `docs/pending/`, awaiting approval)
→ `building` → `shipped`. R5-REWORK = must be re-scored when R5 lands.

> **Update 2026-07-22:** the R3→R5 scoring refactor is **already landed** (audit vs
> `talkingtoad-scoring-change-spec.md` — see `docs/functional-specification.md` §4.0.1).
> The E1/E2 codes were built directly on the R5 model (`_CALIBRATION` (confidence,
> effect_size) → `derive_impact`, `scope`), so their R5-REWORK debt is **cleared** —
> the flag was a precaution from when R5 was assumed in-flight. NEAR_DUPLICATE_BODY and
> BOILERPLATE_RATIO_HIGH are kept **independent** (distinct failure modes — duplication
> vs. thinness; word-count gates make them mutually exclusive with the `CONTENT_THIN`
> parent, so no §6 suppression wiring is needed). E3/E4 remain to be scored when built.

| ID | Item | Source idea | New codes | Scope | Phase | Status | R5-REWORK |
|---|---|---|---|---|---|---|---|
| **P0** | AI-bot **strategic framing** copy (block-to-protect vs allow-to-cite) | #3 | none (copy only) | — | P0 | ✅ `shipped` 2026-07-22 — `AI_BOT_TRAINING_DISALLOWED` how_it_can_mislead (block-training ≠ block-citation) | no |
| **E1** | Brand-entity consistency | #5 | `ENTITY_NAME_INCONSISTENT` (site), `ENTITY_SAMEAS_MISSING` (page), `AUTHOR_IDENTITY_INCONSISTENT` (site) | cross-page | **P1** | ✅ `shipped` 2026-07-22 — functional-spec §4.10; `test_entity_consistency.py` | ✅ cleared 2026-07-22 |
| **E2** | Body near-duplicate + boilerplate | #7 | `NEAR_DUPLICATE_BODY` (site), `BOILERPLATE_RATIO_HIGH` (page) | cross-page | **P1** | ✅ `shipped` 2026-07-22 — functional-spec §4.10; `test_near_duplicate_body.py` | ✅ cleared 2026-07-22 |
| **E3** | Schema extraction completeness | #4 | `HOWTO_SCHEMA_INCOMPLETE`, `PRODUCT_REVIEW_SCHEMA_MISSING` (page, type-gated) | page | P2 | ✅ `shipped` 2026-07-22 — `ai_readiness.py`; `test_schema_completeness_eeat.py` | ✅ born into R5 |
| **E4** | Author E-E-A-T | #6 | `AUTHOR_CREDENTIALS_MISSING` (page); first-hand experience left to existing `geo_llm` (no new keyword code) | page | P2 | ✅ `shipped` 2026-07-22 — `ai_readiness.py`; `test_schema_completeness_eeat.py` | ✅ born into R5 |
| **E5** | **Citability grade** (rollup) | #2, #1 | none — derived per-page grade from `ai_readiness` issues | page | P3 | ✅ `shipped` 2026-07-22 — `compute_citability_grade`; returned on `/page-priority` **and** `/pages`; UI badge (owner-approved) on Page Priority queue + By-Page view (`CitabilityBadge`). Originality-lens label still not built (optional). | ✅ born into R5 |

**Done already (no work — recorded so we don't re-open):**
- Idea **#3 detection** — `api/services/ai_bots.py` + 7 `AI_BOT_*` codes (GPTBot,
  ClaudeBot, CCBot, Google-Extended, PerplexityBot, Bytespider, Applebot, Amazonbot,
  OAI-SearchBot). Only the P0 framing copy remains.
- Idea **#2 detection** — ~12 GEO/extractability codes already emit; only the E5
  rollup is missing.
- Idea **#4** Article/FAQ/Org/date/JSON-LD-validity — shipped; only HowTo/Product-Review
  gap (E3).
- Idea **#7 freshness** — `CONTENT_STALE`, `CONTENT_DATE_STALE_VISIBLE`,
  `CONTENT_STAT_OUTDATED` shipped; only body near-dup (E2) missing.

**Explicitly declined / out of scope (recorded so we don't re-litigate):**
- All 8 serp-discover ideas; SERP-similarity commodity score; off-platform trackers;
  branded-demand / AIO-exposure / share-of-voice (need SERP/competitor/off-platform data).

---

## Sequencing

1. **P0** (copy-only) — can land anytime, independent of everything.
2. **P1 = E1 + E2** — micro-spec approved → build → review → ship. *(current step)*
3. **P2 = E3, E4** — after P1.
4. **P3 = E5** — after P1/P2 (E5 Originality lens consumes E2's near-dup result); grade
   weights come from the R5 matrix, so E5 is the natural point to also do the R5 rework
   pass on E1–E4.
5. **R5 rework pass** — when R3→R5 lands, re-derive impact/severity for every `R5-REWORK`
   code from the live matrix; delete provisional hand-scores. Tracked as its own row when R5 is scheduled.

---

## Critical review (promoted from the approved pending plan)

Verified against the shipped 152-code catalogue (`docs/feature-inventory.yaml`),
`api/services/ai_bots.py`, `api/crawler/checkers/ai_readiness.py`, `cross_page.py`,
and `api/routers/geo.py`.

| # | Idea | Already built? | Verdict |
|---|---|---|---|
| 3 | AI-crawler access check | **Yes — comprehensive** | Ship P0 copy only |
| 2 | GEO / AI-extractability | **Yes — as signals**, no grade | E5 rollup |
| 4 | Structured-data coverage | **Mostly** | E3 (HowTo/Product-Review) |
| 7 | Freshness & differentiation | **Freshness yes; near-dup title+meta only** | E2 (body near-dup) |
| 6 | Evidence / expertise | **Partial** | E4 (credentials) |
| 5 | Brand-entity consistency | **No — sameAs only in generation, never checked** | **E1 — new, top fit** |
| 1 | Uniqueness / fingerprint | **Signals partial; commodity score needs SERP** | E5 lens (crawler half only) |

Evidence notes: `topic_jaccard` is a JS-render-vs-raw diff (`js_renderer.py`), **not**
cross-page body similarity. Existing health score (`_compute_v15_health_score`) is
**site-level severity-weighted**, not a per-page GEO grade. `AUTHOR_BYLINE_MISSING`
(`ai_readiness.py:118`) is **presence-only**, no credentials check. `sameAs` appears
only in `geo.py` schema **generation**, with no crawl-time **check**.
