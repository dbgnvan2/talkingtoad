# Learnings — TalkingToad (failure patterns & fix log)

> **What this is:** institutional memory of how *this* codebase has failed, so the same
> **class** of bug is caught in review instead of production. After fixing any real bug,
> add a **Fix log** entry and, if it's a new generic pattern, fold it into the global
> catalogue (below).
>
> **Generic pattern catalogue + full review checklist live globally** at
> `~/.claude/standards/learnings.md` (auto-loaded by Claude Code for every repo). This file
> keeps the **TalkingToad-specific** open risks and fix log, plus an inline copy of the
> checklist for convenience. Read the checklist before reviewing or writing any
> **checker, fetch, scoring, or report** code.

---

## Review checklist (run before merging checker / fetch / scoring / report changes)

1. **External calls (P5):** does every outbound call (`fetcher.py`, robots, sitemap, external-link
   check, image check, AI/LLM via `AIRouter`, future PageSpeed API) go through `is_ssrf_safe()`
   and have timeout + retry/backoff? Are *all siblings* hardened, not just the one in scope?
2. **Failure visibility (P2):** on partial failure, is anything logged/counted, or does data
   silently vanish? Can "found nothing" be told apart from "the call failed"?
3. **Transient vs terminal (P1):** is a retryable failure (429, timeout, bot-block) being written
   as a permanent negative (`is_broken`, `not_available`)? Keep the "unverified" path for
   bot-blocked hosts (LinkedIn/FB/IG).
4. **Scope completeness (P3):** have all sources/locations been enumerated? (JSON-LD in `<body>`
   not just `<head>`; `@graph` nesting; nested/gzip sitemaps; all heading sources; every page type)
5. **Hardcoded assumptions (P4):** any literal year/date/threshold/topic-word in logic that belongs
   in `docs/thresholds.md` / config? (The catalogue's `_ISSUE_SCORING` and thresholds are the home
   for numbers — not inline magic.)
6. **Ground-truth check (P6):** is a status trusted without verifying the artifact? A WP fix marked
   "applied" must be re-verified against the live page (re-scan), not assumed.
7. **Scoring adversarial test (P7):** what input scores high for the *wrong* reason? Does the Health
   Score / Agent-Readiness Score move monotonically (more failures ⇒ never a higher score)?
8. **Dirty-state / second-run (P8):** does this read state that persists between crawls (prior job
   rows, Performance Ledger, cached results, re-applied fixes)? Is there a test that pre-populates
   that state and asserts the feature ignores prior-run content / is idempotent?
9. **Input starvation / size caps (P9):** for every cap in a data path (500-page crawl, 50
   ext-links/page, 500/job, 200 images/job, 50 query-variants/path, 300 KB HTML, the 1500-word GEO
   window, AI token/excerpt budgets): on a *real, large* site, what fraction of input survives? Is
   the drop announced ("N of M")? Are test fixtures big enough to make the cap actually bite?
10. **Fix→test map (P10):** does each fix in the change map to a test? Is the *highest-impact /
    most-likely-to-regress* fix tested FIRST, not just the easy constant-membership ones? Are
    genuine integration paths (live HTTP, WP API, LLM) flagged as untested rather than implied covered?
11. **Architecture constraints:** a scan must never call the WP API; catalogue ↔ `issueHelp.js` ↔
    scoring ↔ confidence-label parity holds for every new code; serialization includes every field
    the frontend reads.

> Pattern definitions (P1–P10) and the reasoning behind each item: `~/.claude/standards/learnings.md`.

---

## Open risks (found by review, not yet bitten)

- **New fetches must route through `is_ssrf_safe()`.** Any Phase-2/3 outbound call (PageSpeed
  Insights, render-comparison, competitor crawl, GA4) is a fresh chance to bypass SSRF — wire it in.
- **Silent display/computation caps.** Several caps protect the crawler but can starve a check or hide
  rows on large sites. Audit each against real-scale data and announce "N of M" rather than truncating
  silently (P9). The GEO 1500-word window and any AI excerpt budget are the highest-risk.
- **Transient external failures.** 429/timeout on external-link or image checks must not persist as
  permanent "broken"; keep them retryable / "unverified" (P1).
- **Schema parsing robustness.** `@graph` flattening, multiple JSON-LD blocks, and malformed JSON must
  not silently drop a page's structured data (P2/P3) — relevant to the new `SCHEMA_*` checks.
- **Score monotonicity.** Health Score and the Agent Health score must never increase when
  more issues are found; a monotonicity test guards the agent score
  (`tests/test_agent_readiness_checks.py::TestAgentHealthScore::test_agent_score_monotonic_non_increasing`).
  Holds because all impacts are ≥ 0 — re-check if any check is ever given a negative/bonus impact (P7).
- **WP4 placeholder-link false positives (highest live FP risk).** `PLACEHOLDER_LINK` /
  `WRONG_PLACEHOLDER_LINK` run on real HTML where `href="#"` legitimately drives accordions/tabs and
  links to `example.com`/`google.com` can be real references. Detection is deliberately conservative
  (CTA class/text gating, `role`/`aria-expanded`/`data-toggle` exclusion, known-host + empty-path
  gating) but the first production crawls should be eyeballed. If FPs appear, tighten — do not loosen
  to "flag any `#` link" (P7).
- **Agent-readiness signals are parser-precomputed.** Like the GEO checks, the WP2–WP5 signals are
  computed in `parser.py` while `soup` is in scope and stored as `ParsedPage` flags; checkers only read
  them. New agent checks must follow this pattern (no re-parsing in the checker, no raw HTML on the
  model) and wrap computation defensively so a parse quirk never aborts the crawl (P2).

---

## Fix log

Newest first. Format: **Issue → Root cause → What would have caught it → Fix → Pattern.**

- **2026-06-22 — Agent-readiness spec's "new" codes collided with already-shipped codes.**
  - *Issue:* The approved micro-spec (written against a v2.6 baseline) listed `SCHEMA_FAQ_MISSING`,
    `JS_DEPENDENT_CONTENT`, `SCHEMA_MISSING`, and `NO_DATE_ON_CONTENT` as **new** codes, but the repo had
    since shipped `FAQ_SCHEMA_MISSING`, `RAW_HTML_JS_DEPENDENT`, a page-level `SCHEMA_MISSING`, and
    `DATE_PUBLISHED_MISSING` covering the same intent. Building the spec verbatim would have created
    duplicate, parallel catalogue entries.
  - *Root cause:* Spec authored against a stale snapshot of `_CATALOGUE`; no reconciliation step had run
    against the live registry before "approved".
  - *What would have caught it:* WP0 — grepping the live `_CATALOGUE` for each proposed code before
    writing any. (Did this; the collisions surfaced immediately.)
  - *Fix:* Reused shipped codes; added only the 9 genuinely-new ones; added a new `SCHEMA_ORG_MISSING`
    for the distinct homepage-Organization gap (the existing `SCHEMA_MISSING` name was taken). Did **not**
    recategorise `AI_BOT_*` into a `crawler_access` category — that would have stripped their confidence
    labels (an architecture-test invariant = lost functionality). Recorded in
    `docs/functional-specification.md` §4.9 and `PLAN-AGENT-READINESS.md`.
  - *Pattern:* P3/P4-adjacent — "reuse before you invent"; always reconcile a spec's catalogue claims
    against the live source of truth (the repo meta-rule: grep the whole catalogue for the class before
    adding a code).
