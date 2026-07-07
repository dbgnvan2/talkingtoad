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

- **2026-07-06 — GSC ingest sent `sites/undefined/...` → HTTP 400.**
  - *Issue:* After connecting Search Console, "Ingest" queried `sites/undefined/searchAnalytics/query` and Google rejected `http://undefined` as an invalid site URL.
  - *Root cause:* `list_properties()` returns snake_case `{site_url, permission_level}` (the app's API convention), but `GSCInsightsPanel.jsx` read camelCase `p.siteUrl`/`permissionLevel` → `undefined`. The panel's own test masked it by mocking a fictional camelCase shape, so it stayed green.
  - *What would have caught it:* an API-contract test asserting the panel consumes the *real* `/api/gsc/status` field names, and a test that Ingest sends a real `site_url` (never `undefined`).
  - *Fix:* panel reads `site_url`/`permission_level`; test mocks corrected to the real snake_case contract + a regression asserting the ingest URL never contains `undefined`.
  - *Pattern:* P6/serialization — a frontend/backend field-name mismatch with the test mocking a shape the backend never returns. Sibling of the `/api/gsc/status` missing-`configured` bug.

- **2026-07-06 — `analyze_with_ai` returned provider errors as `str`, rendered as AI content.**
  - *Issue:* `api/services/ai_analyzer.py::analyze_with_ai` signalled failure by **returning a sentinel
    error string** (`"AI analysis skipped: …"`, `"Error calling AI: …"`) rather than raising. Because
    success and failure were both `str`, callers rendered the error as if it were AI output:
    `/api/ai/analyze` returned it directly as `suggestion` (no guard at all); `/page-advisor` and
    `/site-advisor` fed it into recommendations; and the `crawl.py` executive-summary path **cached the
    error string onto the job** and served it as the summary.
  - *Root cause:* A mixed-mode `str` interface — the same return type for content and for failure — with
    ad-hoc `str.startswith`/`_is_ai_error` sentinel checks that several callers simply never made.
  - *What would have caught it:* An adversarial test forcing a provider error and asserting it never
    appears as content in any response or on the job (P14 checklist item 15).
  - *Fix:* `analyze_with_ai` (and `geo_llm._call_llm`) now raise a typed `AIAnalysisError` on failure;
    every caller catches it and routes to its error channel (503 / `{error}` field / skip). Deleted all
    `startswith`-sentinel checks and `geo_llm._is_ai_error`/`_ERROR_PREFIXES`. Adversarial tests added.
    Spec: `docs/pending/OLD/2026-07-06_p14-ai-error-contract.md`.
  - *Pattern:* **P14** — error state returned as string, rendered as content. Resolves the standing
    "error-as-content" class for the AI path; new AI callsites must let `AIAnalysisError` propagate.

- **2026-07-06 — R5: three divergent page-health computations; only one was capped + suppressed.**
  - *Issue:* The category-cap (20) and cluster/noindex suppression logic lived in **one** of three
    health-score computations. `crawl.py` and `citations.py` each recomputed health from a **raw
    uncapped sum**, so the same crawl could report different scores depending on which endpoint served it,
    and suppression/cap never applied on those two paths.
  - *Root cause:* A scoring rule was added to one sibling and its siblings were left on the old raw-sum
    path (classic drift across duplicated computations).
  - *What would have caught it:* A parity test asserting all health-score entry points agree on the same
    fixture (`tests/test_scoring_paths_unified.py`).
  - *Fix:* Unified all three onto a single capped + suppressed path; `crawl.py`/`citations.py` no longer
    recompute a raw sum. Added `scope: page|site` (site-config codes deduct once per site), extended
    suppression clusters + noindex scope-reduction, a Quick-Wins list, runtime-derived severity, and a
    `scoring_model_version` stamp (legacy rows read null). Spec: functional-spec §4.0.1.
  - *Pattern:* **P3/P5** — enumerate all siblings; a scoring change must be applied class-wide, not to
    one of N parallel computations.

- **2026-07-06 — `SCHEMA_VISIBLE_MISMATCH` false-positive from a WP SEO-plugin author graph-node.**
  - *Issue:* WordPress SEO plugins inject the byline author as a sibling `/schema/person/<hash>` graph
    node. This slipped `_is_author_publisher_node`, so `SCHEMA_VISIBLE_MISMATCH` fired **site-wide** on
    every page — a looks-wrong-but-is-right input scored as a failure.
  - *Root cause:* The author/publisher-node guard didn't recognise the plugin's hashed-`@id` Person node
    shape, so a legitimate structural node was treated as a spurious schema mismatch.
  - *What would have caught it:* An adversarial fixture using the real WP `/schema/person/<hash>` node
    asserting no `SCHEMA_VISIBLE_MISMATCH`, alongside a true-positive-preserved test.
  - *Fix:* Extended the guard in `api/services/schema_typing.py` (weight unchanged); added both the
    adversarial and true-positive tests. Confirmed on a real crawl (livingsystems.ca) where site health
    rose 73→88 once the FP cleared. Spec: `docs/pending/2026-07-06_deploy-gate-validation.md` (V2).
  - *Pattern:* **P7** — a detector that false-positives on a valid input; add the adversarial case.

- **2026-07-06 — llms.txt validator was stricter than the llmstxt.org spec.**
  - *Issue:* `LLMS_TXT_INVALID` required a `>` blockquote summary and ≥1 URL, capped URLs at 20, and
    hard-required `text/plain` — none of which the llmstxt.org spec mandates (only the `# Title` H1 is
    required; summary, sections, and link count are optional, no cap). A standard Yoast-generated file
    (H1 + plain summary + 50 links, no blockquote, leading UTF-8 BOM) was wrongly flagged.
  - *Root cause:* Invented editorial validity rules hardcoded in the checker, plus a leading UTF-8 BOM
    that defeated the H1 detection so even the one real requirement mis-fired.
  - *What would have caught it:* A regression test using the exact Yoast shape (BOM + H1 + plain summary
    + sections + 50 links) asserting it validates clean, with soft-404 still flagged.
  - *Fix:* Strip a leading BOM, then flag `INVALID` only when there is no Markdown H1 title (soft-404 /
    non-Markdown body). Removed the blockquote, min-URL, 20-URL cap, and MIME requirements. Updated the
    `LLMS_TXT_INVALID` recommendation, `docs/thresholds.md`, and regenerated `docs/issue-codes.md`.
  - *Pattern:* **P7** (a check that fails a looks-right-**and-is-right** input) + **P4** (editorial rule
    hardcoded in logic; now aligned to the external spec).

- **2026-07-06 — `/api/gsc/status` omitted `configured`, giving a dead-end Connect UI.**
  - *Issue:* `gsc_status()` returned `{connected, properties}` but no `configured` field on its 200
    paths. The panel read `!status.configured` (which was `undefined`) as "not configured" and never
    rendered the **Connect** button in the configured-but-not-linked state — a permanent dead end.
  - *Root cause:* A response missing a field the frontend keys on; the serializer and the frontend
    contract had drifted (the 503 "not configured" path was distinct from the 200 "configured but
    unlinked" state the field was meant to express).
  - *What would have caught it:* An API-contract test asserting `/api/gsc/status` 200 responses include
    `configured: true` (now `tests/test_gsc_integration.py::TestGscStatus::test_status_response_contract_fields`).
  - *Fix:* Added `"configured": True` to all three 200 responses (no-creds, success, except-fallback);
    the `_require_gsc_configured()` 503 path (→ `configured:false` on the client) is unchanged.
  - *Pattern:* **P6/serialization** — a status response must carry every field the frontend keys on;
    verify the contract, don't assume the client can infer a missing field.

- **2026-07-06 — `fetch_page` dropped `text/plain` bodies, so llms.txt/ai.txt saw empty content.**
  - *Issue:* `fetch_page` only decoded HTML/PDF bodies. For a `text/plain` response (a real llms.txt),
    `.html` was `None`, so the llms.txt check saw an empty body and validated it as empty → `INVALID`.
  - *Root cause:* A narrow content-type scope — only two body types were ever decoded — silently
    discarded every other text body with no signal.
  - *What would have caught it:* A fetcher test decoding a `text/plain` response and asserting the body
    is preserved (plus a size bound); an llms.txt respx test using a real plain-text file.
  - *Fix:* Added a `text: str | None` field to `FetchResult`; non-HEAD `text/*` (non-HTML) bodies are now
    decoded into `.text`, and the llms.txt check reads it. Size-bounded like the HTML path.
  - *Pattern:* **P2/P3** — silent drop on a narrow-scope assumption; enumerate the content types a data
    path must handle rather than assuming one or two are complete.

- **2026-07-06 — usage-aggregation tests rotted as wall-clock time advanced (test-only).**
  - *Issue:* The `_seed` helper omitted a timestamp, so `record_ai_usage` stamped rows at `now()`. Once
    real time passed the tests' fixed `2026-05-01..06-30` query window, seeded rows fell outside it, the
    aggregation returned empty, and three assertions failed — with no production bug.
  - *Root cause:* A test fixture depending on wall-clock `now()` against a hardcoded date window; the two
    dates drifted apart as the calendar advanced (a P4/P8-flavoured testing smell).
  - *What would have caught it:* Running the suite after the window's end date — or, structurally, seeding
    rows at a timestamp explicitly inside the query window rather than at `now()`.
  - *Fix:* Stamp seeded rows inside the fixed window. Test-only; no production change.
  - *Pattern:* **P4/P8 (testing)** — a hardcoded date window plus `now()`-stamped fixtures is a
    time-bomb; pin fixture timestamps relative to the window under test.

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
