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

- [ ] **Style guide** for explanation copy: reading level, no-jargon rule, show-don't-assert for
  good/bad examples. `docs/explanation-style-guide.md`.
- [ ] **Every issue code carries the 6-part explainer** in `frontend/src/data/issueHelp.js`:
  definition · impact · fix · good_vs_bad · how_it_can_mislead · confidence. 37 of 170 have
  `how_it_can_mislead` today, 35 have `good_vs_bad`. Order: critical + warning (47), then
  Key and Notable info, then Low.
- [ ] **Parity test** fails on an incomplete entry (extends `test_confidence_help_parity.py`).
- [ ] **Render it**: `IssueHelpPanel` shows good/bad and "how this can mislead"; the PDF's
  help section prints them so the client's copy teaches offline.
- [ ] **25 help entries use the superseded confidence vocabulary** (`Mechanistic` /
  `Empirical` / `Conventional`); reconcile with `authority.yaml` `basis` during the pass.

## Phase 3 — reliability of the happy path

- [ ] **Playwright happy path** in CI: start crawl → results → export PDF.
- [ ] **CI builds the Docker image**, so the Playwright/JS-render install is exercised.
- [ ] **Concurrent-crawl politeness guard** in `_launch_crawl`: two crawls of one domain at
  once halve `crawl_delay_ms` against a nonprofit's server.
- [ ] **Four routes have auth-only coverage** (`tests/test_auth_matrix.py::_AUTH_ONLY_COVERAGE`):
  one behavioural contract test each.
- [ ] **Placeholder constraints that still need a real test:** image scan uses HEAD not GET;
  scan never triggers fetch; GEO analysis refuses without configuration; `LLMS_TXT_MISSING`
  end to end.
- [ ] **Persistent PDF export options** in localStorage.

## Phase 4 — three features with real user value

- [ ] **Striking-distance pages into the rewriter** (Performance Bundle PB3): pages ranking
  8–20 from the ledger, one click to the Content Rewriter with the target query.
- [ ] **Compare view**: render `/comparison`, strike the Health delta through with `reason`
  when `comparable` is false (different `info_detail`, partial scan).
- [ ] **Rescan all pages in place** (re-check stored pages without a fresh crawl) and a button
  for the WordPress configuration audit (`POST /api/wp-audit/{job_id}` has no caller today).
- [ ] **Fix Focus third state** `not_checked` for codes the re-check could not evaluate
  (schema change to the persisted snapshot).

## Adjacent, when touched

- [ ] **`FixInlinePanel` maps `TITLE_H1_MISMATCH → seo_title` but the backend fix map does not** —
  the inline fix for that code likely fails server-side; the parity test excludes it. Decide
  which side is right and drop the exclusion. (Promoted from the archive 2026-09-02.)
- [ ] `checks_not_run` from `/scan-page` reaches no UI beyond the Page Audit note; the Results
  summary for a single-page job does not say which 24 checks could not run.
- [ ] Fix Focus mutations are read-modify-write on one blob (last writer wins); Performance
  Bundle PB4/PB5/PB7/PB9 remain after PB3; dimension-pass concurrency floor (~33 images) unpinned.
- [ ] Category tiles / PDF per-page rows show stored counts beside a scored score (`info_detail`).
- [ ] Prevalence tiers by today's catalogue, lists by stored impact (P8).
- [ ] `/pages?min_severity=info` is level-blind.
- [ ] Nested card containers (E6): choose between nested candidates deliberately.
- [ ] `rechecked` is a field no consumer reads — wire or delete.
- [ ] `page_size_limit_kb` defined twice; `cryptography` pinned by venv match, not audit.
- [ ] GSC ingest: unmatched rows stored as silent orphans; fold-collision last-wins.
- [ ] Resolve-then-fetch TOCTOU in `is_ssrf_safe` (needs IP pinning — a design change).
- [ ] Playwright render budget vs the per-request guard (not measurable without Playwright).

## Dropped (and why)

- **TypeScript migration / CSS refactor of `Results.jsx`** — high cost, nothing user-visible.
- **Real-time crawl console** — the progress view answers the operator's question.
- **E5 "Originality lens" label** — the citability grade and near-duplicate codes cover it.
- **Multi-tenant** — parked by owner decision; see `docs/TODO-MULTITENANT.md`.
