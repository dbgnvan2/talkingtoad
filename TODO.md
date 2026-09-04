---
status: current
last_reviewed: 2026-09-02
---
# TalkingToad — TODO (the live plan)

Four phases, agreed 2026-09-02 ("I want this to be a great app"). Per-sweep deferrals and the
completed-features ledger live in [`docs/TODO-ARCHIVE.md`](docs/TODO-ARCHIVE.md); items from
there that the plan schedules are restated below under their phase.

## ⚠️ CRITICAL CONSTRAINTS

**DO NOT IMPLEMENT URL CHANGES VIA WP API:** the WordPress REST API is not reliable for
operations that change URLs (slugs, permalinks, redirects). Any URL-related fix is manual.

**DO NOT AUTOMATE IMAGE LINK UPDATES IN POSTS/PAGES:** optimisation uploads a new file; the
user replaces the old image in the post by hand.

## Phase 1 — close the two holes that undercut trust

- [x] **Rate limits are real bounds** (2026-09-02). Limiter keyed on the bearer token's hash, not
  the client-controlled forwarded address; limit strings are constants; first 429 tests in the
  repo (`tests/test_rate_limits.py`).
- [x] **The rulebook no longer points at files that do not exist** (2026-09-02). `CLAUDE.md` and
  `LEARNINGS.md` carried their own rules and a pattern index.
- [x] **TODO.md is the live plan** (2026-09-02). Deferrals archived.

## Phase 2 — the education layer (V4)

- [x] **Style guide** — `docs/explanation-style-guide.md` (2026-09-02).
- [x] **Every issue code carries the seven-part explainer** — all 170, in
  `frontend/src/data/issueHelp.json` (authored) with the Python copy generated (2026-09-02).
- [x] **Completeness + substance guards** — `tests/test_issue_help_completeness.py` (2026-09-02).
- [x] **Rendered** in `IssueHelpPanel` and the PDF help box (2026-09-02).
- [x] **Retired confidence vocabulary gone**; `LEGACY_VOCABULARY` is empty (2026-09-02).
- [x] **Owner read-through** — done 2026-09-03. Owner: "I'm happy with the explanations." The V4 content pass is closed; the ~120 pre-2026-05 codes it was
  scoped to backfill were completed in Phase 2.
> **Panel explainers** for the non-issue features are Phase 7 below — verified
> 2026-09-03 that four of the six panels have none.

## Phase 3 — reliability of the happy path

- [x] **Playwright happy path** in CI (`frontend/e2e/happy-path.spec.js`, job `e2e`) — 2026-09-02.
- [x] **CI builds the Docker image** (job `docker`) — 2026-09-02.
- [x] **Concurrent-crawl politeness guard** — 409 `CRAWL_IN_PROGRESS_FOR_DOMAIN` — 2026-09-02.
- [x] **Four auth-only routes** have contract tests — 2026-09-02.
- [x] **Placeholder constraints** are real tests (`tests/test_scan_constraints.py`) — 2026-09-02.
- [x] **Persistent PDF export options** — 2026-09-02.

## Phase 4 — three features with real user value

- [x] **Striking-distance pages** (PB3; band 5–15, floor 50, per the original spec) — 2026-09-02.
- [x] **Compare card** with struck-through delta and reason — 2026-09-02.
- [x] **Re-check all pages in place** and the **WordPress audit** button — 2026-09-02.
- [x] **Fix Focus third state** `not_checked` — 2026-09-02.
## Phase 5 — the numbers on screen disagree with each other (4)

Every item here is a contradiction the operator can see: two figures about the same thing that
do not match. That is the most expensive kind of defect this app has, because it costs trust in
the figures that *are* right. Do these first.

- [ ] **P5.1 — `FixInlinePanel` maps `TITLE_H1_MISMATCH → seo_title`, the backend fix map does
  not.** The inline fix for that code likely fails server-side, and the parity test *excludes*
  the code rather than failing. Decide which side is right, wire it, delete the exclusion.
  **Done when:** the parity test covers every code with no exclusion list, and an inline fix for
  `TITLE_H1_MISMATCH` either applies or is not offered. **Size:** small — the test hook exists.
- [ ] **P5.2 — category tiles and PDF per-page rows show STORED counts beside a SCORED score.**
  `info_detail` charges fewer rows than it stores, so a tile can read "12 info" beside a score
  computed from 4. LEARNINGS logs this as open risk (3) of the `info_detail` change. **Done
  when:** every surface showing a count beside a score shows the same population, or labels
  which it is showing.
- [ ] **P5.3 — `/pages?min_severity=info` is level-blind.** Same family: the filter does not know
  about `info_detail`, so it returns rows the score excluded. **Done when:** the filter and the
  score agree on what "info" means for that job.
- [ ] **P5.4 — prevalence tiers by today's catalogue, lists tier by stored impact (P8).** After a
  recalibration across an impact boundary, an old job's prevalence table and its own issue list
  disagree by a code. **Done when:** one of the two is chosen deliberately and the other follows,
  with a test that pins the agreement across a simulated recalibration.

## Phase 6 — things the app knows and does not say (3)

Disclosure gaps. Each is a fact already computed and then dropped — the P25 shape this codebase
keeps hitting, and the reason four separate bugs this week were invisible until someone looked
in SQLite.

- [ ] **P6.1 — `checks_not_run` reaches no UI beyond the Page Audit note.** A single-page job's
  Results summary does not say which 24 checks could not run, so a clean-looking summary is
  partly "not checked". **Done when:** the summary states the count and names them on demand.
- [ ] **P6.2 — `rechecked` is a field no consumer reads.** Wire it or delete it; a field that
  travels and is never read is a claim nobody can check. **Done when:** it is rendered somewhere
  or gone from the model.
- [ ] **P6.3 — GSC ingest stores unmatched rows as silent orphans, and a fold collision is
  last-wins.** Performance data that matched nothing is indistinguishable from performance data
  that did not exist. **Done when:** the ingest reports "matched N of M" and a collision is
  recorded rather than overwritten.

## Phase 7 — the V4 second half (1)

- [ ] **P7.1 — panel explainers for the non-issue features.** Verified 2026-09-03: `GEOReportPanel`
  and `GSCInsightsPanel` have them; **`FaqSchemaModal`, `GeoSettingsModal`, `ImageAnalysisPanel`
  and `BatchOptimizePanel` have none**. The 170 issue codes all carry the seven-part explainer;
  these four tools carry nothing, so the app teaches a nonprofit what `META_DESC_TOO_LONG` means
  and not what the FAQ generator is for. **Done when:** each of the four carries the tool shape
  from `PLAN-V4.0.md` (what it is · why it is useful · good vs bad · how it can mislead · how to
  use it). **Size:** medium, and it is writing, not engineering.

## Phase 8 — engineering debt with no user symptom (4)

Real, worth doing, and nothing breaks tomorrow if they wait.

- [ ] **P8.1 — Fix Focus mutations are read-modify-write on one blob** (last writer wins). Two
  browser tabs, or one operator and one background job, silently lose an edit.
- [ ] **P8.2 — nested card containers (E6):** choose between nested candidates deliberately
  rather than taking whichever the upward walk stops at first.
- [ ] **P8.3 — `page_size_limit_kb` is defined twice**, and `cryptography` is pinned by venv
  match rather than audit.
- [ ] **P8.4 — striking-distance queries come only from the GSC priority seed.** Persisting
  `top_queries` in the ledger (PB3's original intent) would give every scan a target query
  instead of only the seeded ones.
- [ ] Performance Bundle PB4/PB5/PB7/PB9 remain after PB3; the dimension-pass concurrency floor
  (~33 images) is unpinned. Carried with P8.4 as the same area.

## Parked — needs a decision, not a fix (2)

- [ ] **Resolve-then-fetch TOCTOU in `is_ssrf_safe`.** Closing it needs IP pinning, which is a
  design change to every outbound call, not a patch. Recorded so it is a choice rather than an
  oversight.
- [ ] **Playwright render budget vs the per-request guard** — not measurable without Playwright
  in the loop, so there is nothing to test against today.

## Dropped (and why)

- **TypeScript migration / CSS refactor of `Results.jsx`** — high cost, nothing user-visible.
- **Real-time crawl console** — the progress view answers the operator's question.
- **E5 "Originality lens" label** — the citability grade and near-duplicate codes cover it.
- **Multi-tenant** — parked by owner decision; see `docs/TODO-MULTITENANT.md`.
