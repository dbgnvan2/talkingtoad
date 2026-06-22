---
status: proposed
created: 2026-06-21
feature: Agent-readiness checks (Phase 1)
supersedes: agent-friendly-web-checks-spec-v1.md (root research spec → operationalised here)
references_readonly: [docs/functional-specification.md, docs/thresholds.md]
plan: PLAN-AGENT-READINESS.md (Phase 1, WP0–WP6)
note: |
  This is a micro-spec awaiting approval per CLAUDE.md. Do NOT write code until approved.
  Combines Functional spec (observable behaviour / acceptance) and Technical design
  (files, codes, thresholds) in one file per the repo's document model.
---

# Micro-spec — Agent-readiness checks (Phase 1)

## 1. Summary

Add a coherent set of "agent-readiness" checks so TalkingToad can tell a site owner how
findable, parseable and operable their site is to AI crawlers (citation agents) and, at a
basic level, task-executing agents. Operationalises `agent-friendly-web-checks-spec-v1.md`
into the repo's catalogue + checker architecture, and adds a headline **Agent-Readiness
Score** alongside the existing Health Score.

Scope = Phase 1 only (WP0–WP6 in the plan). Phases 2–4 get their own micro-specs.

## 2. Issue-code reconciliation (WP0 — do first)

Reuse existing catalogue codes; do **not** create parallels:

| Spec concept | Reuse existing code | New code? |
|---|---|---|
| noindex meta / header | `NOINDEX_META`, `NOINDEX_HEADER` | no |
| H1 missing / multiple / skip | `H1_MISSING`, `H1_MULTIPLE`, `HEADING_SKIP` | no |
| Image alt missing | `IMG_ALT_MISSING` | no |
| Meta description present/length/dup | `META_DESC_MISSING`, `META_DESC_TOO_LONG`, `META_DESC_DUPLICATE` | no |
| Open Graph | `OG_TITLE_MISSING`, `OG_DESC_MISSING` | no |
| Broken links | `BROKEN_LINK_404`, `BROKEN_LINK_5XX` | no |
| AI crawler blocked | map to existing `AI_BOT_*` table (`AI_BOT_SEARCH_BLOCKED`, `AI_BOT_TRAINING_DISALLOWED`, …) | extend, don't fork |

**New codes introduced here:** `JS_DEPENDENT_CONTENT`, `JS_DEPENDENT_NAVIGATION`,
`NON_SEMANTIC_BUTTON`, `LANDMARK_MAIN_MISSING`, `LANDMARK_NAV_MISSING`,
`INTERACTIVE_NO_ACCESSIBLE_NAME`, `PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK`,
`SCHEMA_MISSING`, `SCHEMA_FAQ_MISSING`, `NO_DATE_ON_CONTENT`, `CONTACT_INFO_NOT_IN_HTML`.
`FACTUAL_INCONSISTENCY` is **out of scope** (manual review only).

## 3. Functional specification (observable behaviour + acceptance)

Severity tiers per `agent-friendly-web-checks-spec-v1.md` §5. Scope column: J = job-level
(once per crawl), H = homepage only, P = every page.

| Code | Scope | Fires when | Severity | Acceptance test idea |
|---|---|---|---|---|
| `AI_BOT_*` (reuse) | J | robots.txt blocks GPTBot/ClaudeBot/PerplexityBot/Google-Extended, or is 5xx, or blanket `Disallow: /` applies to them | Critical | robots with `Disallow: /` under `User-agent: GPTBot` ⇒ fires; `Allow:` override ⇒ does not |
| `JS_DEPENDENT_CONTENT` | P | main text largely absent from server HTML while heavy JS + empty mount present | Critical | empty `#root` + bundle + no body text ⇒ fires; short server-rendered page ⇒ does not |
| `JS_DEPENDENT_NAVIGATION` | P | nav links absent from raw HTML | Warning | nav present in HTML ⇒ no fire |
| `NON_SEMANTIC_BUTTON` | P | `div`/`span` used as a clickable control with no `role`/accessible name | Warning | `div role=button aria-label=…` ⇒ no fire |
| `LANDMARK_MAIN_MISSING` / `LANDMARK_NAV_MISSING` | P/H | no `<main>` / no `<nav>` landmark | Info | present ⇒ no fire |
| `INTERACTIVE_NO_ACCESSIBLE_NAME` | P | button/link/field with no text, `aria-label`, or `title` | Warning | icon-only `<button aria-label>` ⇒ no fire |
| `PLACEHOLDER_LINK` | P | navigational CTA whose href is `#` / `javascript:void(0)` | Critical | in-page `#section` anchor ⇒ no fire |
| `WRONG_PLACEHOLDER_LINK` | P | link to a placeholder domain (example.com, stray google.com, localhost) | Critical | legitimate reference link ⇒ no fire (use text/position to disambiguate) |
| `SCHEMA_MISSING` | H | homepage has no JSON-LD `Organization` schema | Warning | present ⇒ no fire |
| `SCHEMA_FAQ_MISSING` | P | FAQ-shaped content present but no `FAQPage` JSON-LD | Warning | real FAQ marked up ⇒ no fire |
| `NO_DATE_ON_CONTENT` | P | article/post with no visible publish/update date | Info | dated post ⇒ no fire |
| `CONTACT_INFO_NOT_IN_HTML` | H | address/phone/email only in images or JS, not raw HTML | Warning | footer text contact ⇒ no fire |

**Agent-Readiness Score (WP6):** a 0–100 headline computed from the citation-side
ai_readiness codes (already shipped) + the task-side codes above, surfaced in the crawl
summary, the By-Page view, and PDF/Excel. Acceptance: more failing agent checks must never
*increase* the score (monotonicity).

## 4. Technical design (how it's built)

- **Catalogue:** add the new codes to `api/crawler/checkers/registry.py` — `_CATALOGUE`
  (severity/category/fixability), `_ISSUE_SCORING` (impact/effort), and
  `_AI_READINESS_CONFIDENCE` for any code classed ai_readiness (with evidence tier). New
  category names: `crawler_access`, `rendering`, `semantic_html`.
- **Checkers:**
  - WP1 → extend `api/crawler/robots.py` (named-bot directive resolution) + emit in
    `checkers/crawlability.py`. Reconcile with the existing AI-bot table.
  - WP2 → compute the render-risk signal in `parser.py` (visible-text words, script-byte
    ratio, empty-mount detection); emit in `checkers/crawlability.py`.
  - WP3 → new `checkers/semantic_html.py`; register in `checkers/__init__.py` and the
    `issue_checker.py` facade orchestration.
  - WP4 → `checkers/links.py` (reuse anchor extraction).
  - WP5 → `checkers/metadata.py` (reuse the `schema_blocks` extractor that flattens `@graph`).
- **Thresholds:** WP2's word/script-ratio bounds go in `docs/thresholds.md` **via the
  compiler**, not by hand. Ship conservative defaults to minimise false positives.
- **Score (WP6):** scoring helper in `registry.py` or a new `scoring/agent_readiness.py`;
  serialize in `api/routers/crawl.py` summary; surface in `frontend/src/pages/Results.jsx`
  (placement to be approved — GUI-change rule) and in `report_generator.py` / `excel_generator.py`.
- **Parity:** add every new code to `frontend/src/data/issueHelp.js` with the full 6-part V4
  explainer; regenerate `docs/issue-codes.md`. Parity tests must stay green.

## 5. API contract tests (write before any frontend — CLAUDE.md rule)

| Endpoint | Frontend expects | Test name | Status |
|---|---|---|---|
| GET `/api/crawl/{job_id}/summary` | `agent_readiness_score` (int 0–100), `agent_readiness.breakdown[]` | `test_summary_has_agent_readiness` | Pending |
| GET `/api/crawl/{job_id}/pages` | per-page `agent_issues[]` (`code`, `severity`, `tier`) | `test_pages_have_agent_issue_tiers` | Pending |
| GET `/api/crawl/{job_id}/results/{category}` | `crawler_access`, `rendering`, `semantic_html` resolve | `test_agent_categories_resolve` | Pending |

## 6. Tests & edge cases

- Unit + adversarial per check (the "passes for the wrong reason" case is mandatory).
  WP2 and WP4 are the highest false-positive risks — see plan Appendix B.2 / B.4 for the
  required must-not-flag cases.
- Architecture-constraint test: a scan must never call the WP API; catalogue↔help↔scoring
  parity for all new codes.
- Serialization test: every new summary/page field a frontend reads is present.
- Monotonicity test for the Agent-Readiness Score.
- Edge-case catalogue: see `PLAN-AGENT-READINESS.md` Appendix B (B.1–B.5).

## 7. Out of scope

`FACTUAL_INCONSISTENCY` (manual); full headless JS rendering (WP2 is a static-HTML proxy
only); WCAG/axe full ruleset (Phase 2 accessibility); emerging standards (llms.txt is
already shipped; NLWeb/MCP/WebMCP are monitor-only).

## 8. Open questions

1. Confirm `AI_CRAWLER_BLOCKED` is folded into the existing `AI_BOT_*` codes rather than added.
2. WP6 score weighting: equal-weight by severity, or reuse the Health-Score impact weights?
3. Exact UI placement for the Agent-Readiness Score (needs GUI sign-off before frontend work).
4. WP4 disambiguation heuristic for legitimate `#`/external links — confirm conservative default.
