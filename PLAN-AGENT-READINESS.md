---
status: draft
created: 2026-06-21
author: planning assistant (for review by Dave)
depends_on: v2.6 baseline (registry.py catalogue + issueHelp.js + report generator stable)
references_readonly: [docs/functional-specification.md, docs/thresholds.md]
implements: agent-friendly-web-checks-spec-v1.md + roadmap items from docs/TalkingToad-Feature-Ideas
---

# Implementation Plan — Agent-Readiness & Roadmap Checks

> **For the coding agent:** This is a *plan*, not approval to write code. TalkingToad's
> CLAUDE.md mandates a **micro-spec → `docs/pending/` → STOP for human approval →
> implement+test** cycle for every feature. Each work package below tells you what to put
> in the micro-spec, but you must save the pending spec and get explicit approval before
> touching source. Do **not** edit `docs/functional-specification.md` or `docs/thresholds.md`
> directly — they are READ-ONLY (the Gemini Compiler is the only sanctioned writer).

This plan covers three bodies of work, in priority order:

1. **Agent-Readiness checks** — implements `agent-friendly-web-checks-spec-v1.md` (already authored).
2. **Technical-SEO gap checks** — the high-value Screaming Frog checks TalkingToad lacks.
3. **Platform features** — scoring, monitoring, measurement, fix-loop extensions (larger; scope-flagged).

Appendix A is the requested **CLAUDE.md review**. Appendix B is a consolidated **edge-case catalogue**.

---

## Document model & naming (the chain this plan sits in)

Recommended four-layer chain, mapped to where each lives in this repo. The goal is one
owner per question, with no duplicated state:

| Layer | Answers | Lives in | Status |
|---|---|---|---|
| **Feature brief** (the "menu") | *What & why* — value, audience, scope | `docs/TalkingToad-Feature-Ideas.md` (+ this tracker) | exists |
| **Functional + Technical spec** (per feature) | *What it does* (pass/fail, acceptance) **and** *how it's built* (files, codes, thresholds) | `docs/pending/YYYY-MM-DD_<feature>.md` → folded by the Gemini compiler into the master `docs/functional-specification.md` | per-feature |
| **Implementation plan** | *In what order, with which tests* | this file (`PLAN-AGENT-READINESS.md`) | exists |
| **Tracker** | *What's done* | the table below | live |

> **Naming recommendation.** Your instinct (Features → Functional Spec → Technical Spec →
> Implementation Plan) is the standard chain and is correct. One adjustment for this repo:
> **keep functional and technical in a single per-feature spec file** (two clearly-labelled
> sections — "Functional specification" and "Technical design"), not two files. Reasons:
> (1) your master is already `functional-specification.md`, and the compiler folds *one*
> pending file per feature into it; (2) two separate spec files per feature doubles the
> documents that can drift, which your parity/compiler discipline is specifically built to
> avoid. So: **Feature brief → one combined spec (`docs/pending/…`) → implementation plan →
> tracker.** If you later want a standalone technical/design doc for a *large* feature
> (e.g. continuous monitoring), promote it to `docs/specs/<domain>/` — the repo already uses
> that folder for domain specs.

---

## Status tracker (ALL features, all phases)

Legend: ☐ not started · ◐ in progress · ☑ done · — n/a. "Spec" = an approved
`docs/pending/` micro-spec exists. Tick cells as work lands; this table is the single
check-off surface for the coding agent.

### Phase 1 — Agent-readiness (spec authored → `docs/pending/2026-06-21_agent-readiness-checks.md`)

| ID | Feature | Spec | Tests | Code | Docs | Shipped |
|---|---|---|---|---|---|---|
| WP0 | Issue-code reconciliation (reuse vs new) | ☑ | ☑ | ☑ | ☑ | ☑ |
| WP1 | Named AI-crawler access in robots parsing | ☑ | ☑ | ☑ | ☑ | ☑ |
| WP2 | JS-dependency / client-side-render detection | ☑ | ☑ | ☑ | ☑ | ☑ |
| WP3 | Semantic-HTML & interactive-element correctness | ☑ | ☑ | ☑ | ☑ | ☑ |
| WP4 | Placeholder / dead-link detection | ☑ | ☑ | ☑ | ☑ | ☑ |
| WP5 | Structured-data presence + FAQPage gap | ☑ | ☑ | ☑ | ☑ | ☑ |
| WP6 | Agent-Readiness Score + surfacing | ☑ | ☑ | ☑ | ☑ | ☑ |

> **WP0–WP6 implemented 2026-06-22.** Reconciliation outcome (see the pending
> spec's §2): WP1 reuses the shipped `AI_BOT_*` family (`check_ai_bot_access`);
> WP2 reuses `RAW_HTML_JS_DEPENDENT` and adds new `JS_DEPENDENT_NAVIGATION`;
> WP5 reuses `FAQ_SCHEMA_MISSING` + `DATE_PUBLISHED_MISSING` and adds new
> `SCHEMA_ORG_MISSING` (homepage Organization) + `CONTACT_INFO_NOT_IN_HTML`.
> 9 new codes total; new categories `rendering`, `semantic_html`. The existing
> `AI_BOT_*` codes are **not** recategorised into `crawler_access` — doing so
> would strip their confidence labels (an architecture-test invariant); WP1's
> crawler-access concept stays served by the shipped `ai_readiness` codes.
> Agent Health score reuses the v1.5 impact-weighted Health-Score model over
> agent-relevant issues. Tests: `tests/test_agent_readiness_checks.py` +
> `tests/test_crawl_router_contracts.py::TestAgentReadinessContract`.

### Phase 2 — Technical-SEO gap checks (each needs its own micro-spec)

| ID | Feature | Spec | Tests | Code | Docs | Shipped |
|---|---|---|---|---|---|---|
| 2.1 | Image missing width/height (CLS) | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2.2 | Soft 404 detection | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2.3 | Canonical robustness suite | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2.4 | Structured-data validation | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2.5 | Pagination (rel=next/prev) | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2.6 | Mobile usability (font/tap-target) | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2.7 | PageSpeed / Core Web Vitals (PSI API) | ☐ | ☐ | ☐ | ☐ | ☐ |

### Phase 3 — Platform & GEO-growth features (each needs its own micro-spec; scope-flagged)

| ID | Feature | Spec | Tests | Code | Docs | Shipped |
|---|---|---|---|---|---|---|
| 3.1 | Fix-loop extensions (schema/H1/alt/CTA injection) | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.2 | "See your site as an agent" view | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.3 | Continuous monitoring + alerts | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.4 | Competitor benchmarking | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.5 | Business-outcome measurement (GA4 + AI-referral) | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.6 | AI visibility / citation tracking across LLMs | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.7 | Content-opportunity / gap audit (comparison, original-data, buyer-guide formats) | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.8 | Author / E-E-A-T signal audit | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.9 | Off-site entity (sameAs) footprint audit | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3.10 | Conversion-readiness audit (CTA / trust / tools) | ☐ | ☐ | ☐ | ☐ | ☐ |

### Phase 4 — V4 explanation layer (per `PLAN-V4.0.md`)

| ID | Feature | Spec | Tests | Code | Docs | Shipped |
|---|---|---|---|---|---|---|
| 4.1 | Every new code ships V4-complete (good_vs_bad + how_it_can_mislead) | ☑ | — | ☐ | ☐ | ☐ |
| 4.2 | Backfill ~120 legacy codes to the 6-part explainer | ☐ | ☐ | ☐ | ☐ | ☐ |

> **Coverage note:** Phase 1 is the only batch with an authored spec today. Phases 2–4 are
> *mapped* here but each still needs its own `docs/pending/` micro-spec + approval before
> code (CLAUDE.md rule). The detail for Phase 1 is in §1; Phase 2 in §2; Phase 3 in §3;
> Phase 4 in §4.

---

## 0. Ground rules baked into every work package

These come straight from CLAUDE.md. Treat them as the Definition of Done; a package is not
complete until every box is checked.

### 0.1 Definition of Done (per work package)

- [ ] **Micro-spec** written to `docs/pending/YYYY-MM-DD_<feature>.md`; approved by the user.
- [ ] **Issue codes** added to the single source of truth — `api/crawler/checkers/registry.py`
      (`_CATALOGUE`, `_ISSUE_SCORING`, and `_AI_READINESS_CONFIDENCE` if the code is an
      ai_readiness code). *Do not* add codes in `issue_checker.py` — it is now a thin facade
      over the `checkers/` package.
- [ ] **Parity kept green:** `frontend/src/data/issueHelp.js` and the auto-generated
      `docs/issue-codes.md` regenerated/updated so the catalogue↔help↔scoring↔confidence
      parity tests pass.
- [ ] **V4 explainer** for every new code: `definition`, `impact` (with evidence tier),
      `fix`, **plus** `good_vs_bad` and `how_it_can_mislead` (the mandatory honesty fields —
      see `PLAN-V4.0.md`; `SCHEMA_VISIBLE_MISMATCH` is the field template).
- [ ] **Tests** (see 0.2) including at least one **adversarial** case per text/scoring function.
- [ ] **Docs** updated: relevant `docs/specs/...` file and `docs/thresholds.md` entries
      (via the compiler, not by hand) if any numeric bound was added.
- [ ] **Per-item completion:** run `./scripts/run_compiler.sh`, update `PLAN-V4.0.md`
      worked-examples tally, `git push origin main`.

### 0.2 Required tests (CLAUDE.md test taxonomy)

| Test type | File pattern | What it proves |
|---|---|---|
| Unit | `test_<feature>.py` | Detection / scoring logic, incl. ≥1 adversarial "passes for the wrong reason" case |
| Integration / API contract | `test_<component>_integration.py` | Endpoint request→response→side-effects; **written before** any frontend code |
| Architecture constraint | add to `test_architecture_constraints.py` | Design rules (e.g. "a scan must never call the WP API"; catalogue↔help parity) |
| Serialization | add to `test_api_serialization.py` | Every model field the frontend reads is present in the response |

### 0.3 Cross-cutting invariants (do not break)

- **SSRF:** every outbound fetch goes through `api/crawler/fetcher.py:is_ssrf_safe()` — including
  any new fetch (PageSpeed API, render comparison, competitor crawl).
- **Auth:** new routers under `/api/*` require `AUTH_TOKEN` bearer auth via `require_auth`
  (fail-closed in prod). Only `/api/health` is public.
- **WordPress safety:** no URL/slug/permalink changes via the WP API; no automated in-post
  image-link rewrites; every WP-touching endpoint calls `_validate_wp_domain_for_job` /
  `_validate_wp_domain_for_url` (403 `DOMAIN_MISMATCH` on mismatch).
- **XSS:** any helper injecting user text into HTML must HTML-escape first.
- **Crawl politeness:** do not weaken the rate-limit / crawl-delay / robots.txt respect in
  `engine.py` when adding new per-page work.
- **Reuse before you invent codes.** Several spec items already have codes — map to them,
  don't duplicate (see 1.0).

---

## 1. Phase 1 — Agent-Readiness checks

Implements `agent-friendly-web-checks-spec-v1.md`. This is the priority phase: it is already
specced, it differentiates the product, and most checks are static-HTML (no rendering).

### 1.0 Reconcile new vs existing codes first (do this before WP1)

The spec lists codes that **already exist** — reuse them, do not recreate:

| Spec code | Already in catalogue as | Action |
|---|---|---|
| `NOINDEX_META`, `NOINDEX_HEADER` | same names | Reuse; ensure surfaced in the agent view |
| `H1_MISSING`, `H1_MULTIPLE`, `HEADING_SKIP` | same names | Reuse |
| `IMG_ALT_MISSING` | same name | Reuse |
| `META_DESC_MISSING`, `META_DESC_TOO_LONG`, `META_DESC_DUPLICATE` | same names | Reuse |
| `OG_TITLE_MISSING`, `OG_DESC_MISSING` | same names | Reuse |
| `BROKEN_LINK_404`, `BROKEN_LINK_5XX` | same names | Reuse |
| `AI_CRAWLER_BLOCKED` | overlaps existing `AI_BOT_*` table (`AI_BOT_SEARCH_BLOCKED`, `AI_BOT_TRAINING_DISALLOWED`, …) | **Decide:** extend the existing AI-bot codes rather than add a parallel one. Document the mapping in the micro-spec. |
| `SCHEMA_*` | schema typing + `SCHEMA_VISIBLE_MISMATCH` exist | `SCHEMA_MISSING`/`SCHEMA_FAQ_MISSING` are likely new; build on the existing `schema_blocks` extractor |

**Genuinely new codes** introduced in Phase 1: `JS_DEPENDENT_CONTENT`, `JS_DEPENDENT_NAVIGATION`,
`NON_SEMANTIC_BUTTON` (+ optional `LANDMARK_MAIN_MISSING`, `LANDMARK_NAV_MISSING`,
`INTERACTIVE_NO_ACCESSIBLE_NAME`), `PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK`,
`SCHEMA_MISSING`, `SCHEMA_FAQ_MISSING`, `CONTACT_INFO_NOT_IN_HTML`, `NO_DATE_ON_CONTENT`.
`FACTUAL_INCONSISTENCY` is **out of scope for automation** — flag for manual review only.

---

### WP1 — Named AI-crawler access in robots parsing

- **Goal:** Per-crawl checks that AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)
  are not blocked, robots.txt is reachable, and no blanket `Disallow: /` applies to them.
- **Files:** `api/crawler/robots.py` (parser already groups user-agent directives),
  `api/crawler/checkers/crawlability.py` (emit codes), `registry.py` (codes/scoring).
- **Scope note:** job-level, not per-page (see spec §6.2). Reconcile with the existing AI-bot table.
- **Tests:** `test_ai_bots.py` already exists — extend it. Cases: explicit `Disallow: /` under
  `User-agent: GPTBot`; `Allow:` overriding a broader `Disallow`; wildcard `User-agent: *` block;
  robots.txt returns 5xx (treat as blocked) vs 404 (treat as allow-all).
- **Edge cases:** see B.1.
- **Docs:** `docs/specs/core-crawler/`.

### WP2 — JS-dependency / client-side-render detection

- **Goal:** Flag pages whose core content/nav is absent from server-rendered HTML — the cheap
  proxy for "AI crawlers see nothing" (no headless renderer required).
- **New codes:** `JS_DEPENDENT_CONTENT` (critical), `JS_DEPENDENT_NAVIGATION` (warning).
- **Files:** `api/crawler/parser.py` (compute signal: visible-text length, script-byte ratio,
  empty-root-container detection), `api/crawler/checkers/crawlability.py`, `registry.py`.
- **Heuristic (put exact thresholds in `thresholds.md` via compiler):** flag when extractable
  main-text words < N **and** script bytes / HTML bytes > R **and** a known empty mount point
  (`<div id="root">`/`#app` empty) is present. Tunable; ship conservative to avoid false positives.
- **Tests:** adversarial is essential here. Must-not-flag: a legitimately short but
  server-rendered page; a page with `<noscript>` fallback content; lazy-loaded images that
  still have real `<img>` tags; server-rendered-then-hydrated pages. Must-flag: empty `#root`
  + bundled JS + no body text.
- **Edge cases:** see B.2.

### WP3 — Semantic-HTML & interactive-element correctness

- **Goal:** Detect `div`/`span` used as buttons/links, missing `<main>`/`<nav>` landmarks, and
  interactive elements with no accessible name (the accessibility-tree channel agents read).
- **New codes:** `NON_SEMANTIC_BUTTON` (warning); optional `LANDMARK_MAIN_MISSING`,
  `LANDMARK_NAV_MISSING` (info), `INTERACTIVE_NO_ACCESSIBLE_NAME` (warning).
- **Files:** new `api/crawler/checkers/semantic_html.py` (register it in `checkers/__init__.py`
  and the orchestration in `issue_checker.py` facade), `registry.py`.
- **Tests:** must-not-flag a `div role="button"` with `aria-label` (has a role and a name);
  must-flag a bare `<div class="btn" onclick=...>` with no role/label. Icon-only `<button>`
  with `aria-label` passes; icon-only with nothing fails.
- **Edge cases:** see B.3. **Note:** overlaps WCAG/axe-core (Phase 3 accessibility) — keep this
  a small heuristic now; don't duplicate a full axe ruleset.

### WP4 — Placeholder / dead-link detection

- **Goal:** Flag CTAs that go nowhere or to a placeholder domain.
- **New codes:** `PLACEHOLDER_LINK` (`href="#"`/`javascript:void(0)` on a navigational CTA),
  `WRONG_PLACEHOLDER_LINK` (href to `example.com`, a stray `google.com`, `localhost`, etc.).
- **Files:** `api/crawler/checkers/links.py`, `registry.py`. Reuse existing anchor/link extraction.
- **Tests:** adversarial — must-not-flag legitimate `href="#"` used by a JS accordion/tab, in-page
  anchors (`href="#section-2"`), `mailto:`/`tel:` links. Must-flag a styled button-CTA whose only
  href is `#`, and a "Contact us" link pointing at `google.com`.
- **Edge cases:** see B.4. This is the highest false-positive-risk check after WP2 — be conservative.

### WP5 — Structured-data presence + FAQPage gap

- **Goal:** Flag homepage missing Organization schema and FAQ-style content lacking FAQPage schema.
- **New codes:** `SCHEMA_MISSING` (warning, homepage-scoped), `SCHEMA_FAQ_MISSING` (warning).
- **Files:** `api/crawler/checkers/metadata.py` (reuse the existing `schema_blocks` extractor that
  already flattens `@graph`), `registry.py`. **Tie-in:** wire the "fix" path to the existing
  Entity Schema Factory (`/api/geo/entity-schema`) and FAQ generator (`/api/ai/geo-faq`).
- **Tests:** FAQ detection heuristic must have an adversarial case (a Q&A-shaped blog post that
  isn't really an FAQ → decide flag/no-flag and test it). Schema parse-error handling.
- **Edge cases:** see B.5.

### WP6 — Agent-Readiness Score + surfacing

- **Goal:** A second headline number alongside Health Score, composed from the citation-side
  ai_readiness codes (already shipped) plus Phase 1 task-side codes; surfaced in the dashboard
  and PDF/Excel.
- **Files:** scoring in `api/crawler/checkers/registry.py` or a new `scoring/agent_readiness.py`;
  serialization in `api/routers/crawl.py` summary; `frontend/src/pages/Results.jsx` +
  components; `api/services/report_generator.py` and `excel_generator.py`.
- **API contract tests (write FIRST — see 0.2 / table below).**
- **GUI constraint:** CLAUDE.md forbids changing nav/structure without explicit sign-off — the
  micro-spec must include the exact UI placement for approval before frontend work.
- **Tests:** serialization test asserting `summary.agent_readiness_score` and its sub-breakdown
  exist; monotonicity test (more failing agent checks ⇒ score never increases).

#### API contract test table (Phase 1)

| Endpoint | Frontend expects | Test name | Status |
|---|---|---|---|
| GET `/api/crawl/{job_id}/summary` | `agent_readiness_score` (int 0–100), `agent_readiness.breakdown[]` | `test_summary_has_agent_readiness` | Pending |
| GET `/api/crawl/{job_id}/pages` | per-page `agent_issues[]` with `code`, `severity`, `tier` | `test_pages_have_agent_issue_tiers` | Pending |
| GET `/api/crawl/{job_id}/results/{category}` | new categories `semantic_html`, `rendering`, `crawler_access` resolve | `test_agent_categories_resolve` | Pending |

---

## 2. Phase 2 — Technical-SEO gap checks (from Screaming Frog)

Each is an independent work package following the same DoD. Detail kept lighter; the patterns
mirror Phase 1 (add code to `registry.py`, checker module, parity, tests, edge cases, docs).

| # | Check | New code(s) | Primary file(s) | Key edge cases | Effort |
|---|---|---|---|---|---|
| 2.1 | Image missing `width`/`height` (CLS) | `IMG_MISSING_DIMENSIONS` | `checkers/images.py` | CSS-sized images; `srcset`; SVG; lazy-load | Low |
| 2.2 | Soft 404 | `SOFT_404` | `checkers/crawlability.py`, `parser.py` | legit "no results" pages; thin-but-valid pages | Medium |
| 2.3 | Canonical robustness | `CANONICAL_CONFLICTING`, `CANONICAL_NON_INDEXABLE`, `CANONICAL_RELATIVE` | `checkers/metadata.py` | cross-domain syndication canonicals (legit); self-ref | Low |
| 2.4 | Structured-data validation | `SCHEMA_INVALID`, `SCHEMA_RICHRESULT_WARNING` | `checkers/metadata.py` | `@graph` nesting; multiple blocks; required-field rules | Medium |
| 2.5 | Pagination rel=next/prev | `PAGINATION_*` | new `checkers/pagination.py` | infinite scroll; WP archive patterns; loops | Medium |
| 2.6 | Mobile usability (font/tap-target) | `MOBILE_FONT_TOO_SMALL`, `MOBILE_TAP_TARGET` | `checkers/crawlability.py` | needs computed sizes — keep heuristic without rendering | Medium |

**2.7 PageSpeed / Core Web Vitals (separate, integration-heavy):** new service calling the
PageSpeed Insights API through `is_ssrf_safe()`; cache results; surface LCP/CLS/render-blocking.
Codes `CWV_*`. This is the one Phase 2 item that needs an external API + auth/quota handling —
treat as its own micro-spec.

---

## 3. Phase 3 — Platform features (scope-flagged)

These move TalkingToad from an on-site WordPress auditor toward an agent-readiness platform.
Each is a **product decision**, not just a feature; the micro-spec should state the scope shift.

- **3.1 Fix-loop extensions (highest leverage, mostly within existing mechanisms).** One-click
  insertion of Organization/FAQPage/Person JSON-LD (reuse Entity Schema Factory + FAQ generator),
  add-missing-H1, AI alt-text write (exists), repair dead CTA (extend `fix_link.py`). *Auto-fix
  the schema/heading/alt/link items; audit-and-guide the semantic-HTML/form items (theme-dependent).*
  Respect all WordPress-safety constraints.
- **3.2 "See your site as an agent" view.** Render the text-only / extracted view beside the
  human view. Pairs with WP2; strong demo. Frontend + a serialized "extracted content" field.
- **3.3 Continuous monitoring + alerts.** Scheduled re-crawls with email/Slack alerts on score
  drop / regression / new critical issue. Builds on the Performance Ledger. Needs a scheduler +
  notification service + dedupe of alerts.
- **3.4 Competitor benchmarking.** Audit a competitor's public site; compare Health + Agent-Readiness.
  Read-side engine is already CMS-agnostic; gate nothing for audit. Mostly UI + a compare endpoint.
- **3.5 Business-outcome measurement.** Extend Authority Matrix beyond GSC clicks: GA4 conversions/
  revenue, AI-referral traffic segmentation (referrer detection: chatgpt.com, perplexity.ai,
  gemini.google.com, copilot, claude.ai), branded-search lift. Off-site/analytics scope.
- **3.6 AI visibility / citation tracking across LLMs.** Query a panel of LLMs for target
  questions; record whether the domain is cited; surface competitor citations missed. Activates
  the existing citation-ingestion endpoint + the parked SERP-Discovery work. Largest scope shift.
- **3.7 Content-opportunity / gap audit.** Detect presence/absence of high-citation content
  types (comparison / "X vs Y" / alternatives, original-research/statistics, bottom-funnel buyer
  guides) and flag the missing ones; offer to scaffold via the existing FAQ/entity generators.
- **3.8 Author / E-E-A-T signal audit.** Visible author byline, Person schema with credentials,
  sameAs to author profiles. Low effort, fully on-site; complements existing entity work.
- **3.9 Off-site entity (sameAs) footprint audit.** Audit on-site evidence of an off-site
  presence: Organization schema sameAs links to Wikipedia/LinkedIn/YouTube/G2/Trustpilot/Crunchbase;
  flag a thin footprint as a corroboration risk. (Fuller review-velocity/mention tracking = off-site.)
- **3.10 Conversion-readiness audit.** Visible CTA, trust signals (reviews/testimonials/badges),
  interactive tools; pairs with 2.7 (Core Web Vitals). The webinar's "AI-friendly conversion
  architecture."

---

## 4. Phase 4 — V4 explanation-layer alignment (ongoing, not a separate build)

Per `PLAN-V4.0.md`, every new code shipped above **must** carry the full 6-part explainer
(`definition`, `impact`+tier, `good_vs_bad`, `how_it_can_mislead`, `fix`). This is already the
per-cycle standard — so Phase 1–3 codes ship V4-complete by default, and no separate pass is
needed for them. The only standalone V4 work remains backfilling the ~120 older pre-2026-05 codes.

---

## 5. Suggested sequencing

1. **Phase 0 hygiene** (Appendix A fixes to CLAUDE.md; cheap, prevents agent misdirection).
2. **WP1 → WP2 → WP4 → WP3 → WP5** (crawler access and link checks are lowest-risk; WP2/WP3 need
   the most adversarial testing).
3. **WP6** (score) once the underlying codes exist.
4. **Phase 2.1, 2.3** (low effort, high value) → 2.2, 2.4, 2.5, 2.6 → 2.7 (PSI).
5. **Phase 3.1** (fix-loop) early if you want the differentiator live; 3.2–3.5 are larger bets.

Dependencies: WP6 depends on WP1–WP5. 3.1 schema-fix depends on WP5. 3.2 depends on WP2's
extracted-content field. Everything depends on Phase 0's registry/source-of-truth correction.

---

## Appendix A — CLAUDE.md review (bloat & missing best practices)

**Overall:** the local `CLAUDE.md` is above average — lean by intent, with strong, unusually good
rules (API-contract-test-first, the adversarial-test requirement, parity guards, SSRF/auth/WP
safety). It needs **accuracy fixes and a few additions**, not heavy trimming. *(The global
`~/.claude/CLAUDE.md` could not be read — it's outside the connected folders. Grant access or paste
it and I'll review it too.)*

### A.1 Fix — stale "source of truth" (most important)

CLAUDE.md's directory tree and Coding-Standards both name `api/crawler/issue_checker.py` as the
`_CATALOGUE` source of truth. The repo has since refactored to a `api/crawler/checkers/` package;
**`checkers/registry.py`** now holds `_CATALOGUE`/`_ISSUE_SCORING`/`_AI_READINESS_CONFIDENCE`, and
`issue_checker.py` is a 642-line facade. A coding agent following CLAUDE.md will edit the wrong
file. Update both references and add the `checkers/` package to the directory tree (registry +
the 11 modules: metadata, headings, links, images, security, crawlability, url_structure,
ai_readiness, cross_page, registry, __init__).

### A.2 Fix — version inconsistency

CLAUDE.md says **"Current version: 3.0.0 — v3.0 shipped"** and points to `PLAN-V3.0-UNIFIED.md`,
while `docs/functional-specification.md` (the master) says **v2.6.0**. Pick one source of truth for
the version string and reconcile. (This same discrepancy surfaced when comparing the README to the
spec.) Verify the referenced `PLAN-V3.0.md` / `PLAN-V3.0-UNIFIED.md` / `PLAN.md` paths too —
several plans were moved to `archive/`, so the "Key Documentation Pointers" table may be dangling.

### A.3 Trim — feature/version narrative violates the file's own contract

The header says "No version history, no feature descriptions" and points history to
`legacy_changelog.md`. Yet lines ~21–33 ("v3.0 shipped features" / "Still parked") are exactly that.
Move them to `legacy_changelog.md` or the PLAN ledger and keep CLAUDE.md to rules/paths. This is
genuine, self-defined bloat.

### A.4 Add — complete the secrets list

"Critical Local Files (DO NOT COMMIT)" lists `wp-credentials.json`, `.env`, `.env-ttoad`,
`talkingtoad.db` but **not** `client_secret*.json` — a real Google OAuth client-secret file is
sitting in the repo root. `.gitignore` *does* cover `client_secret*.json` / `*-secret*.json`
(good — it is not tracked), but CLAUDE.md's list should include it for consistency, and ideally the
file should live outside the working tree (a `secrets/` dir or env var) rather than the repo root.

### A.5 Add — secret-scanning hook (missing best practice)

Given how many secrets live in the tree (`.env`, `.env-ttoad`, `wp-credentials.json`, the OAuth
secret, a 59 MB `talkingtoad.db`), add a **pre-commit secret scan** (gitleaks or detect-secrets) and
note it in CLAUDE.md. `.gitignore` is the only current guard; one mis-named file would leak. A hook
is cheap insurance and the natural complement to the existing "treat any new secret file as
DO-NOT-COMMIT" rule.

### A.6 Add — a couple of standing invariants worth promoting to "Hard Constraints"

- **Crawl politeness** (rate limit, crawl-delay, robots.txt respect) is in the spec/thresholds but
  not a CLAUDE.md hard constraint — promote a one-liner so an agent editing `engine.py` won't
  weaken it.
- **Branch/commit policy:** CLAUDE.md says commits land on `main` and the bridge operates on `main`,
  but doesn't state a commit-message convention or whether an agent may push directly. State it
  explicitly (e.g. conventional-commit style; direct-to-main is intended).

### A.7 Optional — consolidate a single "Definition of Done"

The pieces (tests, docs, compiler, PLAN tally, push) are excellent but scattered across three
sections. A single DoD checklist (like section 0.1 of this plan) at the top of Coding Standards
would make the per-item loop unmissable.

**Net:** apply A.1 and A.2 before any coding-agent work (they cause wrong edits); A.3–A.5 are
quick hygiene/security wins; A.6–A.7 are polish. I can prepare these edits as a `docs/pending/`
micro-spec (CLAUDE.md isn't status-locked, but routing through your own workflow keeps it clean) —
say the word.

---

## Appendix B — Consolidated edge-case catalogue

**B.1 AI-crawler / robots (WP1):** `Allow:` overriding a broader `Disallow:`; case-insensitive
user-agent matching; multiple UA groups; `User-agent: *` vs named bots; robots.txt 5xx (=blocked)
vs 404 (=allow-all) vs redirect; `Crawl-delay`; BOM/encoding; very large robots files.

**B.2 JS-dependency (WP2):** SPA app-shell with empty `#root`; legitimately short server-rendered
page (don't flag); `<noscript>` fallback present; content server-rendered then hydrated (don't flag);
lazy-loaded `<img>` with real markup (don't flag) vs 1×1 SVG placeholders only (flag); large inline
JSON-LD inflating script ratio without hiding content; AMP pages.

**B.3 Semantic HTML (WP3):** `div role="button"` + `aria-label` (pass); `<a>` styled as a button
(pass); icon-only control with `aria-label`/`title` (pass) vs nothing (fail); framework-generated
wrappers; multiple `<nav>` landmarks; `<main>` provided by theme vs absent.

**B.4 Placeholder links (WP4):** `href="#"` driving a JS accordion/tab (don't flag — needs a
heuristic: is it a styled CTA vs a control?); in-page anchors `href="#id"` (pass); `mailto:`/`tel:`
(pass); `javascript:void(0)` toggles (context-dependent); links to `google.com` as a *legitimate*
reference vs a placeholder CTA (use link text + position to disambiguate; be conservative).

**B.5 Structured data (WP5/2.4):** `@graph` nesting; multiple `<script type="application/ld+json">`
blocks; JSON-LD in `<body>` vs `<head>`; malformed JSON (parse-error path, don't crash); microdata/RDFa
(out of scope — JSON-LD only?); FAQ-shaped content that isn't a real FAQ.

**B.6 Images (2.1):** image sized only via CSS (no attrs) — flag or not?; `srcset`/`sizes`; inline
SVG (no dimensions needed); decorative `alt=""` (don't demand dimensions for hidden images).

**B.7 Soft 404 (2.2):** custom 404 template returning HTTP 200 (flag); a real, thin page that says
"no results yet" (avoid false positive); search-results pages.

**B.8 Canonical (2.3):** cross-domain canonical for legitimate syndication (don't hard-fail);
relative canonical URL; self-referencing canonical (pass); canonical to a `noindex` page (flag).

---

*Plan v1 — 2026-06-21. Built on `agent-friendly-web-checks-spec-v1.md`, `PLAN-V4.0.md`, the
functional specification (v2.6.0), and the live `checkers/` package layout. Implement only via the
micro-spec → approval → test cycle defined in CLAUDE.md.*
