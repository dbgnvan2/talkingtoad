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
- [ ] **Owner read-through.** The copy was written and cold-reviewed by Claude against the
  checkers; the reading level for your clients is your call. Read a category tab's explanations
  end to end and edit `issueHelp.json` directly (then `python scripts/generate_issue_help_py.py`).
- [ ] **Panel explainers** for the non-issue features (FAQ generator, schema factory, image
  optimizer, GEO report) — the V4 plan's second half; not part of Phase 2.

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
- [ ] **Striking-distance queries** come only from the GSC priority seed; persisting `top_queries`
  in the ledger (PB3's original intent) would give every scan a target query.

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
- [ ] **`WpAuditPanel` renders none of Site Health, plugin overlaps, or inactive themes** — the
  panel shows plugins total/active/inactive, pending updates, inactive plugins and the
  `not_inspected` boundary; `site_health`, `overlaps` and `inactive_themes` reach the payload
  and only the PDF prints them (P25/P16). WA2's whole payoff — the first real Site Health row
  this feature has produced, a `critical` on livingsystems.ca — is invisible in the app. Not
  done here because CLAUDE.md requires explicit instruction before changing what a panel
  displays, and the approved WA spec did not cover it. There is also no `WpAuditPanel.test.jsx`
  at all. (Cold sweep, 2026-09-02.)
- [ ] **`users/me` capabilities are `allcaps`, not `current_user_can()`** — the raw role map,
  unfiltered by `map_meta_cap`, so a role plugin or a multisite subsite that filters
  `activate_plugins` at the meta layer still reports it true and `can_run_wp_audit` will
  promise an audit that 403s. The REST API exposes no effective-capability check; closing it
  properly means probing `plugins` with a HEAD/OPTIONS rather than inferring. (Cold sweep,
  2026-09-02.)
- [ ] **`NEAR_DUPLICATE_BODY` stores its cluster twice, O(N²) across a cluster** — ND1 keeps
  `members` (N urls) beside `near_identical_to` (N−1) on each of N rows, and `_issue_dict`
  serialises `extra` whole and uncapped, so a 50-page doorway cluster carries ~5,000 urls.
  Kept because the approved micro-spec specifies both keys, and `members` is now what every
  pre-ND1 stored row renders from. Nothing in `api/` or `frontend/src` reads `members` on a
  NEW row: once historical rows no longer matter, drop it from the emitter and keep the
  renderer's supersede rule for the old ones. (Cold sweep, 2026-09-02.)
- [ ] **`/comparison` will report a one-off delta across the ND1/ND3 deploy** — the first crawl
  after it shows +(N−1) warnings per near-duplicate cluster and, on a bare-origin site, one
  fewer page, with nothing changed on the site. `comparable` only knows about `info_detail`
  and partial analysis. `SCORING_MODEL_VERSION` was not bumped: the R5.1 tiebreak change
  restores the pre-ND1 site score for `NEAR_DUPLICATE_BODY`, and measured over all 149
  complete jobs in the development store it moves the elected representative on 2 (both
  `MISSING_HSTS`) and changes the site score on **0**. It is not score-neutral by
  construction for the other eleven site-scoped codes, though — their impacts are constant
  per code, so the tiebreak always decides the election; it happens not to bite on this
  corpus. What definitely changed across the deploy is the row COUNT. Either teach
  `comparable` about the issue-emission shape or stamp an emission version. No frontend
  consumer today. (Cold sweep, 2026-09-02.)
- [ ] **`perf_join.match_key` collides on pre-ND3 jobs that stored both home-page spellings** —
  both fold to `//site.ca/` and `build_crawled_key_map` is last-wins, so GSC/GA4 data attaches
  to only one of the two duplicate rows in those old jobs. Going forward the duplicate cannot
  exist. Harmless unless someone re-reads an old job's ledger join. (Cold sweep, 2026-09-02.)
- [ ] `page_size_limit_kb` defined twice; `cryptography` pinned by venv match, not audit.
- [ ] GSC ingest: unmatched rows stored as silent orphans; fold-collision last-wins.
- [ ] Resolve-then-fetch TOCTOU in `is_ssrf_safe` (needs IP pinning — a design change).
- [ ] Playwright render budget vs the per-request guard (not measurable without Playwright).

## Dropped (and why)

- **TypeScript migration / CSS refactor of `Results.jsx`** — high cost, nothing user-visible.
- **Real-time crawl console** — the progress view answers the operator's question.
- **E5 "Originality lens" label** — the citability grade and near-duplicate codes cover it.
- **Multi-tenant** — parked by owner decision; see `docs/TODO-MULTITENANT.md`.
