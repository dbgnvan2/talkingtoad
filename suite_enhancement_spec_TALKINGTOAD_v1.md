# TalkingToad — Suite Enhancement Spec (v1, self-contained)

Origin: this slice was split from the cross-tool master
`suite_enhancement_spec_v1.md` (in the serp-discover repo), itself derived from
`three_tool_audit_review_20260721.md`. **This file is self-contained** — the
full requirements and acceptance criteria for TalkingToad's items are inlined
below; you do not need the master to implement them. The master is referenced
only for cross-tool context.

Commits MUST carry `Spec: suite_enhancement_spec_v1.md#<item>`.

## Decisions applied (2026-07-21, from the owner)

- **Apps stay independent.** TalkingToad keeps its **own config** — it does NOT
  read a shared client-profile file. The cross-tool coupling items (X-1 shared
  profile / orchestration) are **dropped** as shared features.
- **TT-1 page selection = sample the site's primary navigation-menu pages**, not
  every page and not a traffic-ranked top-N. PSI key will be supplied by the owner.

## Build status & sequencing (2026-07-21) — DECISION B: HOLD

**All new-issue-code work here (TT-3, TT-2, TT-1, TT-4) is deferred until the
in-flight R3→R5 scoring refactor lands**, so new codes are born into the final
derived-scoring schema and do not need reworking. Only **X-4** (docs) shipped.

| Item | Status |
|---|---|
| X-4 (backlink-exclusion note in `docs/overview.md`) | ✅ **Done** (2026-07-21) |
| TT-3 (crawl-time response speed) | ⏸ Held — unblock when scoring refactor lands |
| TT-2 (keyword cannibalization via GSC) | ⏸ Held — same, + needs the GSC change below |
| TT-1 (Core Web Vitals via PSI) | ⏸ Held — later, owner supplies `PSI_API_KEY` |
| TT-4 (rendered mobile-usability) | ⏸ Held — optional stretch |

**Unblock condition:** the R3→R5 model is stable — the
`(confidence, effect_size, fatal_override)` derivation matrix, `scope: page|site`,
and `suppresses` are the live source of truth for new codes (see
`talkingtoad-scoring-change-spec.md` + `LEARNINGS.md` R5 entries).

### Implementation intel (gathered 2026-07-21 — use when unblocked)

Adding one issue code is a coordinated multi-surface change under a **parity
invariant** (catalogue ↔ `issueHelp.js` ↔ scoring ↔ confidence-label; enforced by
a parity test — see `LEARNINGS.md` checklist #11). For each new code touch:

1. `api/crawler/checkers/registry.py` — **three** structures: the `(impact,
   effort)` map, the R3 scoring map `(confidence, effect_size, fatal_override)`
   (e.g. `"PAGE_TIMEOUT": ("Reasonable proxy", "large", False)`), and the
   `_IssueSpec` catalogue (category / severity / description / recommendation /
   human_description / fixability). Impact & severity are **derived** from the R3
   matrix — do not hand-set them once the refactor is live.
2. Frontend `issueHelp.js` **and** `api/services/issue_help_data.py` — full V4
   explainer (definition / impact / fix / confidence + `good_vs_bad` +
   `how_it_can_mislead`).
3. `scripts/generate_issue_codes_doc.py` — regenerate `docs/issue-codes.md`.
4. Tests: detection boundary + the parity test.
5. New numeric thresholds → `docs/thresholds.md`, never inline.

**TT-3 specifics:** capture response time in `api/crawler/fetcher.py` → add a
field to `CrawledPage` (`api/models/page.py`, sibling to `response_size_bytes`) →
persist in `api/services/sqlite_store.py` → a `crawlability` checker reads it and
emits `PERF_SLOW_RESPONSE`. Confidence tier **Reasonable proxy**, `scope: page`.

**TT-2 specifics (the "#6" answer, confirmed in code):**
`api/services/gsc_client.py::fetch_page_performance` requests only
`dimensions=["page"]` — it never sees which *query* a URL ranks for. Cannibalization
therefore needs a **new** `dimensions=["query","page"]` fetch (reuse the existing
5-try backoff), then group client URLs per query. Emit a **site-scoped**
`KEYWORD_CANNIBALIZATION` once (thresholds ≥2 URLs / ≥10 impressions, in config).
GSC is one-time-OAuth and already wired (`api/routers/gsc.py`); the per-URL-per-month
`PerformanceRecord` ledger (`api/models/performance.py`) stores page-level only.

**TT-1 note:** a PageSpeed call is already anticipated (`LEARNINGS.md`: "future
PageSpeed API" + SSRF note) — route any new outbound call through `is_ssrf_safe()`
with timeout + retry, per the P5 checklist.

## Binding conventions for every new issue code (this repo)

Read first: `CLAUDE.md`; `docs/functional-specification.md`; `docs/thresholds.md`;
`PLAN-V4.0.md`; the catalogue-generation contract in `docs/issue-codes.md` header
(edit `api/crawler/issue_checker.py` `_CATALOGUE` / `_ISSUE_SCORING` /
`_AI_READINESS_CONFIDENCE`, then re-run `scripts/generate_issue_codes_doc.py`).

- **Full V4 explainer** (per `PLAN-V4.0.md`): `definition`, `impact`, `fix`,
  `confidence` tier (Established / Reasonable proxy / Heuristic), **plus**
  `good_vs_bad` and `how_it_can_mislead`. Missing the last two fails the
  help-parity test.
- Thresholds/token lists in config, never hardcoded.
- `data_available` handling so old crawls neither crash nor fabricate zeros.
- Trend: persist per-URL-per-run in `talkingtoad.db`; label single runs as snapshots.

*(verify in code)* markers below indicate structures confirmed only at
docs/catalogue level — if they differ, stop and report before improvising.

---

## TT-3 — Measured crawl-time response speed  · Phase 1 · no new dependency

**Problem.** Page speed is reported only via proxies (`PAGE_SIZE_LARGE`,
`PAGE_TIMEOUT`, image weight). The crawler already fetches every page but does not
record server response time, so there is no measured speed signal.

**Required change.**
1. During the existing crawl fetch, capture **time-to-first-byte / total response
   time** per URL (the async HTTP client already has the timing — expose it).
   *(verify in code — the fetch layer.)*
2. Persist `response_ms` on the page record and in `talkingtoad.db` so it trends
   across runs.
3. New code **`PERF_SLOW_RESPONSE`**. Threshold from config (`docs/thresholds.md`):
   default **warning ≥ 1500 ms**, info ≥ 800 ms. Confidence tier: **Reasonable
   proxy**.
4. Full V4 explainer, incl. `good_vs_bad` (300 ms vs 2500 ms) and
   `how_it_can_mislead` (a one-off slow response under load ≠ chronic; TTFB ≠ full
   render — that is TT-1).

**Acceptance criteria.**
- TT-3.1 Every crawled page record carries numeric `response_ms`, persisted; a
  fixture crawl asserts it.
- TT-3.2 `PERF_SLOW_RESPONSE` fires above / not below the configured threshold
  (boundary test); threshold read from config, not hardcoded.
- TT-3.3 Code in `_CATALOGUE` with a full V4 `issueHelp.js` entry; catalogue↔help
  parity green; `docs/issue-codes.md` regenerated.
- TT-3.4 Old crawl rows without `response_ms` do not crash reporting.

---

## TT-2 — Keyword cannibalization via GSC  · Phase 1 · no new dependency

**Problem.** Two of the client's own pages competing for one query is invisible.
TalkingToad already holds GSC data, making this a query, not a new integration.

**Threshold (owner-confirmed):** flag a query where **≥2 own URLs** receive
impressions and the query has **≥10 impressions** in the GSC window.

**Required change.**
1. Using the existing GSC link, for each query group the **client URLs** receiving
   impressions/clicks. *(verify in code — confirm the GSC layer exposes per-query
   → per-URL rows; if it returns query-only totals, add the `page` dimension to
   the GSC fetch. This is the "#6" check.)*
2. New **site-scoped** code **`KEYWORD_CANNIBALIZATION`** (one site-level
   deduction per the R5 scope model, not per page). Payload lists the competing
   URLs with impressions/clicks/avg position and which URL GSC favours.
3. Recommendation: consolidate into one canonical page + 301 the weaker URL(s),
   naming the winner. Confidence tier: **Reasonable proxy**.
4. Thresholds (`min_urls`=2, `min_impressions`=10, lookback) in config, not code.
5. Full V4 explainer; `how_it_can_mislead`: legitimately distinct pages (a service
   page vs a blog post) can share a query without true cannibalization — a prompt
   to review, not a verdict.

**Acceptance criteria.**
- TT-2.1 On a GSC fixture with one query → two client URLs above threshold, the
  code fires once, site-scoped, naming both URLs and the favoured one.
- TT-2.2 A single-URL query, or one below min-impressions, does not fire.
- TT-2.3 With GSC not connected, the check is skipped and the report says it
  requires a GSC connection (never guesses).
- TT-2.4 Thresholds config-driven (test overrides, sees change); parity green;
  docs regenerated.

---

## TT-1 — Core Web Vitals & measured performance  · Phase 3 · external dependency

**Problem.** No performance category exists. Blog steps 7–8 (page speed, LCP/INP/
CLS) are the clearest capability gap; closing them adds an external measurement
dependency — a deliberate, gated step.

**Owner decisions applied:** data source = **PageSpeed Insights API**; page set =
**the site's primary navigation-menu pages** (derive from the nav the crawler
already discovers), not full-site, not traffic top-N; per-run **cap** retained as
a safety limit; **owner supplies `PSI_API_KEY`**.

**Required change.**
1. New **PERFORMANCE category** with `CWV_LCP_SLOW`, `CWV_CLS_HIGH`,
   `CWV_INP_SLOW` (INP proxied by TBT when only lab data is available). `PERF_TTFB_SLOW`
   is TT-3.
2. Config `performance: {enabled: false, source: psi, page_set: nav_menu,
   page_cap: <safety limit>, psi_api_key_env: PSI_API_KEY, thresholds: {...}}`.
   Off by default; capped; run log prints "Performance: N PSI calls (cap M)".
3. **Page selection:** resolve the site's primary navigation-menu links from the
   crawl graph; that set (deduped, capped) is the CWV sample. Selection logic in
   code; `page_set` + `page_cap` in config.
4. Thresholds (config / `thresholds.md`): LCP good < 2.5 s / poor > 4 s; CLS good
   < 0.1 / poor > 0.25; INP good < 200 ms / poor > 500 ms. Confidence tier:
   **Established** for the vendor-defined values; the sampling + lab-vs-field
   caveat is the `how_it_can_mislead` content.
5. Trend: store CWV per URL per run; report change since last run; label single
   runs as snapshots.
6. Full V4 explainers for every new code (lab ≠ field; single PSI sample is noisy;
   **only the sampled nav pages are covered — state the sampled set, never imply
   full-site coverage**).
7. Missing/invalid `PSI_API_KEY` → feature skipped with a logged warning, never an
   abort.

**Acceptance criteria.**
- TT-1.1 With `performance.enabled: false` (default), **zero** PSI calls (mock
  call-count test).
- TT-1.2 With a mocked PSI client, LCP/CLS/INP parse into the fields; each code
  fires above / not below its configured threshold at boundaries.
- TT-1.3 Page selection resolves to the nav-menu set and respects `page_cap`
  (fixture: nav of 15 links, cap 10 → exactly 10 PSI calls); run log states count
  and cap.
- TT-1.4 CWV history persists; a second run reports change vs the first.
- TT-1.5 Missing `PSI_API_KEY` skips the feature with a warning, no abort.
- TT-1.6 Old crawls render with `data_available: false`; every new code has a full
  V4 explainer; parity green; docs regenerated.

---

## TT-4 — Rendered mobile-usability signal  · optional stretch

**Problem.** Mobile coverage stops at static `MISSING_VIEWPORT_META` +
`IMG_NO_SRCSET`. TalkingToad already runs a render pass a usability check can
reuse.

**Required change.**
1. On the existing render, at a mobile viewport width, detect horizontal overflow
   (content wider than viewport); optionally tap-target proximity. New code
   `MOBILE_CONTENT_OVERFLOW`, confidence tier **Heuristic**, full V4 explainer.
2. Reuse the existing render — do **not** add a second headless-browser pass.

**Acceptance criteria.**
- TT-4.1 A fixture with a fixed-width element wider than the mobile viewport
  fires; a responsive fixture does not.
- TT-4.2 No new render pass introduced; parity/doc criteria as for all new codes.

---

## X-4 — Backlink-exclusion note  · Phase 1 · docs only

Add a short **"Out of scope: backlink graph analysis"** note to
`docs/overview.md`: the suite uses Domain Authority as the sole authority proxy;
full backlink/toxic-link/disavow analysis needs a paid link-graph provider and is
judged low-ROI for one nonprofit; revisit only if scale or budget changes.

**Acceptance criteria.** X-4.1 The note exists in `docs/overview.md` with wording
consistent across the three repos' equivalent docs. No code/test change.

---

## Cross-tool item touching this repo (now optional, off by default)

**X-2 (AI-citation loop) — deferred, not Phase 1.** Because apps stay independent,
this is an **optional** bridge for owners who run both TalkingToad and
serp-discover. If built later: TalkingToad writes a schema-stable export of
observed client citations (`AI_CITED_PAGE` / `AI_HIGH_VALUE_UNCITED`) that
serp-discover may ingest. **Open code-check (#7):** what `AI_CITED_PAGE` is
sourced from and whether an export exists — resolve during a TalkingToad code
read before any wiring.

## Out of scope (this repo)

- **TT-5** cross-web plagiarism (Copyscape-style) — declined.
- **X-1** shared client profile / orchestration — dropped as a shared feature per
  the keep-apps-independent decision.
