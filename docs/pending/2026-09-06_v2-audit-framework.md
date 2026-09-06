# Micro-spec: v2 Audit Framework — performance, accessibility, entity depth, and the Decisions surface

**Date:** 2026-09-06
**Status:** PENDING OWNER APPROVAL — no source code touched until this is reviewed.
**Spec IDs:** V2-PERF, V2-A11Y, V2-ENTITY, V2-LINK, V2-DECIDE (P0); V2-AEO, V2-ANALYTICS (P1); V2-TYPO, V2-MOBILE (P2).
**Extends:** the crawler checkers (`api/crawler/checkers/`), the issue registry
(`api/crawler/checkers/registry.py`), the entity/schema logic in `AI_READINESS`, and the
WordPress audit's read-only opt-in pattern (`api/services/wp_audit.py`).
**Relates to:** `V2-RESEARCH.md` (the strategic note this implements). The repo's own
`IssueCategory` design reserved `performance`, `mobile`, `schema` as "Phase 2 — unbuilt"; this spec
is that phase, grounded in an external audit + industry sources rather than re-invented.

> **⚠ Superseded in part by the implementation spec's Revision r1 (2026-09-06).**
> This document is the approved *strategy*. The tables below are the pre-review draft and
> several of their per-code details were corrected against the code:
> `ORG_LOGO_MISSING` was **withdrawn** (already emitted as `ENTITY_NAP_INCOMPLETE`);
> `ORG_LEGAL_NAME_INCONSISTENT` became `ORG_LEGAL_NAME_MISSING` with the casing rule dropped;
> `IMG_MISSING_DIMENSIONS` is **info**, not warning, and fires when *either* dimension is
> undeclared (not both); and `LOW_INBOUND_LINKS` is gated on a complete link graph.
> **Implement from `docs/pending/2026-09-06_v2-audit-implementation.md`, not from this file.**

---

## Problem & context

TalkingToad has 170 checks and is strong on the crawl/on-page core (crawlability, linking,
metadata, security). The Living Systems audit — and the research in `V2-RESEARCH.md` — shows a
great nonprofit audit also covers, and TalkingToad currently misses:

1. **Performance** — `RENDERING` has 4 codes that only fire on external CWV data a plain crawl
   never has. No static CLS/lazy-load/dimension checks, so a crawl reports "no performance
   problems" when it simply did not look.
2. **Accessibility** — 4 semantic-HTML codes; a nonprofit audit must check form labels, contrast,
   focus, and error announcement (audiences skew older / include disabilities; legally relevant).
3. **Entity depth** — `ENTITY_*` covers NAP/hours well, but not logo, `legalName`, `areaServed`/
   `priceRange`/geo.
4. **Weak internal linking** — `ORPHAN_PAGE` fires at zero inbound links; the audit found
   "54 pages with exactly one." That tier is invisible.
5. **Decisions** — a consultant hands back a list of things *only the org can decide* (legal name,
   address type, hours, archive indexability). TalkingToad reports only defects, so those are lost.

And one positioning correction (V2-AEO): the `AI_READINESS` category labels `llms.txt`/chunking
as universal "AI-ready" signals, but Google explicitly does not use them. The product must say
which engine each signal moves.

---

## Architecture decisions

- **DA1 — performance split by evidence tier.** Static checks (`IMG_MISSING_DIMENSIONS`, lazy-load
  attributes) are scored in the crawl. Lab CWV (`CWV_LCP/INP/CLS_POOR`) stays as-is but gains a
  lab path through `js_renderer.py`/`web_vitals.py` — a heuristic **never** stands in for a metric.
  No fabricated numbers; a metric that could not be measured renders as *not checked* (the P2 shape
  this repo already enforces).
- **DA2 — one new category, two already reserved.** `performance` and `mobile` **already exist** as
  `IssueCategory` members (v1.4 reserved them for "Phase 2"; they are just unbuilt). Only
  `accessibility` is a new member. New emitted categories must be added to `CATEGORY_DISPLAY`
  (parity-tested). Entity depth stays inside `AI_READINESS` (it already owns `ENTITY_*`).
  `PHASE_1_CATEGORIES` is derived from the catalogue, so no hand-kept set to drift (the P5.2b rule).
  See the implementation spec for the exact registration mechanics.
- **DA3 — the Decisions surface is NOT an issue code.** It is a first-class output, like Fix Focus:
  generated from crawl facts + a small question bank, never scored into the health score (a
  decision is not a defect).
- **DA4 — honest AEO labels.** Rename/annotate `LLMS_TXT_*`, `CHUNKS_NOT_SELF_CONTAINED`, and the
  answer-engine-pattern codes with their engine scope ("ChatGPT/Perplexity/agents — not a Google
  AI Overviews factor"). Code names stay; explainers and the PDF say which engine.

---

## P0 — the checks (concrete)

### V2-PERF — performance (new category `PERFORMANCE`)

| Code | Severity | Detects | Evidence | Effort |
|---|---|---|---|---|
| `IMG_MISSING_DIMENSIONS` | 🟡 warning | `<img>` lacking `width` **and** `height` (CLS driver) | the `<img>` tag | 1 |
| `IMG_LAZYLOAD_MISSING` | 🔵 info | non-first-viewport `<img>` without `loading="lazy"` | element position in doc order (heuristic) | 2 |
| `LCP_ELEMENT_LAZY_LOADED` | 🔵 info | hero/logo/first image marked `loading="lazy"` (hurts LCP) | first `<img>` above the fold | 2 |
| `RENDER_BLOCKING_JS` | 🔵 info | synchronous `<script>` (no `defer`/`async`) in `<head>` | script tag | 2 |

- `IMG_MISSING_DIMENSIONS` is the reliable, high-value one (audit item 43). The lazy-load codes are
  heuristics and are labeled as such; they never claim a metric they did not measure.

### V2-A11Y — accessibility (new category `ACCESSIBILITY`)

| Code | Severity | Detects | Evidence | Effort |
|---|---|---|---|---|
| `FORM_FIELD_NO_LABEL` | 🟡 warning | `<input>/<select>/<textarea>` without `<label for>`, `aria-label`, or `aria-labelledby` | the field element | 1 |
| `FORM_ERROR_NO_ANNOUNCE` | 🔵 info | form with client-side validation lacking `aria-describedby`/`role=alert` (heuristic) | form + input attributes | 2 |
| `FOCUS_INDICATOR_REMOVED` | 🔵 info | `outline:none`/`outline:0` without a replacement focus style (heuristic) | inline/style CSS | 3 |
| `CONTRAST_RATIO_LOW` | 🟡 warning | text/background contrast < WCAG 4.5:1 (computed styles; post-crawl opt-in) | computed color | 3 |

- `FORM_FIELD_NO_LABEL` is the reliable one (extends the existing `INTERACTIVE_NO_ACCESSIBLE_NAME`
  pattern to form fields). `CONTRAST_RATIO_LOW` needs computed styles and is post-crawl/opt-in, like
  the WordPress audit — never silently skipped.

### V2-ENTITY — entity depth (inside `AI_READINESS`)

| Code | Severity | Detects | Evidence | Effort |
|---|---|---|---|---|
| `ORG_LOGO_MISSING` | 🔵 info | `Organization`/`LocalBusiness` without `logo`/`image` | JSON-LD node | 1 |
| `ORG_LEGAL_NAME_INCONSISTENT` | 🔵 info | `legalName` absent, or `name` casing/canonicalization mismatch | JSON-LD node | 2 |
| `LOCAL_BUSINESS_FIELD_INCOMPLETE` | 🔵 info | missing `areaServed`, `priceRange`, or `geo` when `LocalBusiness` is declared | JSON-LD node | 1 |

- Audit items 30–32, 68. Static and reliable. `ENTITY_NAP_INCOMPLETE`/`ENTITY_HOURS_DEFAULT`/
  `ENTITY_FIELD_EMPTY` already cover the rest.

### V2-LINK — weak-link tier (inside `CRAWLABILITY`)

| Code | Severity | Detects | Evidence | Effort |
|---|---|---|---|---|
| `LOW_INBOUND_LINKS` | 🔵 info | page with exactly **one** inbound internal link (`ORPHAN_PAGE` = zero) | link graph | 1 |

- Audit item 16. Reuses the existing link graph; one new predicate.

---

## P0 — the Decisions surface (V2-DECIDE)

A read-only, per-site checklist generated after a crawl, enumerating facts only the org can decide.
Each entry: the decision, why it matters (one sentence), and which crawl facts it is derived from.
Not scored, never a defect.

Question bank (seed, from the Living Systems audit §12–§13):
legal organization name + public name · address type (customer-facing vs administrative vs mailing)
· verified public hours vs suppress · which archives should rank · which forms/platforms represent a
completed inquiry/registration/donation · named content reviewers · legacy backlinks/listings to
remap · hosting backup/cache/WAF confirmation.

Rendered as its own panel; exported in the PDF/Excel; each item can be marked resolved without
affecting the health score.

---

## P1 — honest AEO + analytics (summarized)

- **V2-AEO:** rewrite explainers + PDF for `LLMS_TXT_*`, `CHUNKS_NOT_SELF_CONTAINED`, and
  answer-engine codes to name the engine they serve; add the GSC "Generative AI performance" report
  as the visibility source of truth (not a third-party proxy).
- **V2-ANALYTICS:** an opt-in, read-only "Analytics configuration audit" — conversion events,
  cross-domain/outbound measurement, 404 event — mirroring `wp_audit.py`'s capability-probe and
  `not_inspected` boundary.

## P2 — higher false-positive risk (summarized)

- **V2-TYPO:** `TYPO_SUSPECTED` over slugs/headings/schema values; default off, `info`/low, explicit
  "may be a name or loanword" caveat.
- **V2-MOBILE:** tap-target size + mobile-usability via the render path; needs measurement.

---

## Acceptance criteria

1. Every P0 code has: a catalogue entry with severity/impact/effort/fixability, a seven-part
   explainer (`frontend/src/data/issueHelp.json` **and** the generated Python copy), and
   `docs/issue-codes.md` regenerated (parity tests green).
2. `IMG_MISSING_DIMENSIONS`, `FORM_FIELD_NO_LABEL`, `ORG_LOGO_MISSING`, `LOW_INBOUND_LINKS` each
   ship with an adversarial test — an input that *looks* like a hit but is not (the repo's
   self-review rule), plus a monotonicity/scope test where a score is involved.
3. New categories are derived into `PHASE_1_CATEGORIES` without a hand-kept set; the structural
   parity tests pass on both interpreters (3.11 and 3.14).
4. The Decisions surface ships with an API-contract integration test **before** any frontend code
   (the repo's non-negotiable rule), covering the response schema, empty-site case, and auth.
5. Heuristic codes (lazy-load, render-blocking, focus, contrast) declare their evidence tier on
   screen and in the PDF; an unmeasured metric renders *not checked*, never clean.
6. V2-AEO explainers name the engine each signal serves; the PDF and the AI-Readiness panel carry
   the same wording (one source, not two phrasings).

## Explicit non-goals

- No off-site authority (local listings, backlinks, outreach) — paid third-party data, declined.
- No crawl-budget/log analysis — needs server logs a public crawler can't reach.
- No WordPress-specific checks in the crawl — platform-agnostic only; WP stays in the opt-in audit.
- No content-*quality* scoring beyond the existing LLM advisory (E-E-A-T depth is not a reliable
  crawl code).
- No URL-changing or image-link-updating automation (standing WP safety constraints unchanged).

## Test mapping (to be written at implementation)

| Spec | Test |
|---|---|
| V2-PERF | `test_perf_static_checks.py` — dimensions/lazy-load/render-blocking, incl. adversarial `width`-but-no-`height` |
| V2-A11Y | `test_accessibility_checks.py` — label variants (`for`, `aria-label`, `aria-labelledby`), contrast not-run disclosure |
| V2-ENTITY | `test_entity_depth.py` — logo/legalName/field presence + adversarial `image`-but-not-`logo` |
| V2-LINK | `test_low_inbound_links.py` — 0 vs 1 vs 2 inbound boundaries |
| V2-DECIDE | `test_decisions_surface.py` — schema, empty site, auth, resolved-state persistence |
| V2-AEO | `test_aeo_scope_labels.py` — every relabeled code's explainer names its engine |
