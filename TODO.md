---
status: current
last_reviewed: 2026-09-03
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
## Phase 5 — the numbers on screen disagree with each other (4 — ALL DONE)

Every item here is a contradiction the operator can see: two figures about the same thing that
do not match. That is the most expensive kind of defect this app has, because it costs trust in
the figures that *are* right. Do these first.

- [x] **P5.1 — the inline fix path could not succeed for any code** (2026-09-03). The item as
  written was stale: `8d96b6d` (2026-08-10) had already put `TITLE_H1_MISMATCH` in the backend
  map and removed the parity exclusion. The conclusion was right and understated. `apply-one`
  handed `apply_fix` a record with no `field` and no `wp_post_id`, so **all ten** codes the panel
  offers returned `No fix spec for field ''`; and `/wp-value` returned `value` while both
  consumers read `current_value`, so the editor opened blank. Both suites were green throughout —
  no success-path pytest existed, and every vitest mock was written from the component, so it
  agreed with the component about a key the server never sent (P27). Fixed: the backend derives
  the field from `_CODE_TO_FIELD` and ignores any body `field`, resolves the post, and returns
  400 `CODE_NOT_FIXABLE` / 404 `POST_NOT_FOUND` / 400 `UNKNOWN_FIELD`; `wp-value` returns
  `current_value`; vitest mocks come from one fixture pinned to the live endpoint.
  `tests/test_inline_fix_contract.py` (14 tests), every guard verified red by deleting the code
  it guards.
  - [x] **P5.1b** (folded in on owner approval) — `NOT_IN_SITEMAP` and `JSON_LD_MISSING` never
    reached their one-click branch, because it was gated on a `predefinedValue` prop that
    `Results.jsx` (the only call site) never passed. `wp-value` now publishes
    `predefined_value` from `PREDEFINED_FIX_VALUES` and the panel switches mode on it;
    `apply_fix` fills a blank proposal from that constant **keyed on the field**, so it can
    never rescue a blank `seo_title` from the guard that stops an empty write clearing live
    content.
  - *Cold sweep found 8 further findings in the fix itself — all fixed and mutation-verified,
    logged in `LEARNINGS.md`.* The two worth remembering: the blank→constant substitution had
    been put in the **shared** `apply_fix`, which silently changed the batch path (a stored fix
    whose value an operator deliberately cleared would have started applying the default); and
    the predefined-value tests read `PREDEFINED_FIX_VALUES` for their oracle, so flipping
    `sitemap_include` to `"never"` — which would make the one-click fix *exclude* the page from
    the sitemap — left all 4997 tests green.
  - **Deliberately not fixed:** `FixInlinePanel.jsx`'s fallback description
    `` `This will set the value to "${predefined}"…` `` is unreachable today, because
    `PREDEFINED_DESCRIPTIONS` covers both fields that can produce a non-null `predefined_value`.
    Kept as the defensive default for a third predetermined field; it is not claimed as tested.
- [x] **P5.2 — stored counts beside a scored score** (2026-09-04). Five surfaces, not two, and the
  symptom was worse than "two figures disagree": a category **tile is a button**, and at
  `info_detail="key"` the `metadata` tile read **2** and opened an **empty list**. Measured, not
  inferred. The PDF was worse still — `get_pages_with_issue_counts` defaults to `"all"` and three
  of its four callers omitted the argument, so the per-page row reported `info_excluded: 0` on a
  job that excluded three rows: a disclosure field asserting the opposite of the truth rather than
  staying silent (P12/P24). Fixed: `by_category_scored` / `by_category_excluded` beside the stored
  `by_category` (reconciling per category); tiles render the scored count **with** a "+N not
  scored" line, because a bare 0 is what a clean category looks like (P31); every caller passes
  the level, pinned by a structural test; the PDF prints per-page `(+N excluded)` and
  `5 (2 scored)` for its total, the phrasing the Results panel already used (P16); Excel counts
  the scored map. One SQL predicate (`_kept_info_sql`) for every count query in the store.
  13 mutations verified red — including the two wrong fixes: redefining `by_category` as scored,
  and showing the scored count with no disclosure.
  - *Caught by mutation, not review:* the first version of the PDF test asserted the **count** and
    the store's disclosure field, so deleting the rendered "(+N excluded)" line left it green. It
    now seeds a second page whose per-page figures differ from the site total, so the assertion
    cannot be satisfied by the dashboard's line.
  - *Cold sweep found 7 more, all real, all fixed.* The serious one: `_kept_info_sql` — the SQL
    restatement of `info_row_excluded` — **omitted the Python's `impact >= 4` clause**, so the fix
    re-created the very defect it was closing for the 4,860 live rows that are `severity='info'`
    with impact ≥ 4. Its docstring claimed it mirrored the Python and cited a test that did not
    exist; there is now a grid test executing both through SQLite. The By Page half had shipped
    with the same hole on 2026-09-01. Also: a **sixth** surface (the PDF's own category table),
    found by grepping the field rather than re-reading this ticket; and passing the level into the
    advisor's membership check moved a `limit=50` window, so a URL that validated before the change
    400'd after — a P9 underneath (membership was answered over the top 50 pages of a 500-page
    crawl), now fixed and tested.
- [x] **P5.2b — `PHASE_1_CATEGORIES` contained `duplicate`** (closed 2026-09-05). Now derived:
  `frozenset(spec.category for spec in _CATALOGUE.values())`. Two parity tests assert both
  directions plus a third against a vacuously-empty derivation. Noted while doing it: because
  every emitted category is in the set, the CSV export's `phase` column is constant `"1"` —
  true before this change, and a contract question of its own (below).
- [x] **P5.3 — the filter agreed with the score and never said so** (2026-09-04). The premise was
  stale for the third item running: the store has filtered on the kept info count since
  2026-09-01. What it did instead was quieter and, by this repo's own rule, worse — at `key` a
  page with two findings **vanished from a filtered list** and the response carried no
  `info_detail`, no `hidden`, no count (P31). Three defects behind it: `/pages` was the one list
  endpoint with no `info_filtered` and no reveal override; `issue_counts.info_excluded` had been
  on every row since 2026-09-01 with **no component reading it** (P25), so a fully-excluded page
  rendered identically to a clean one; and `?min_severity=bogus` returned 200 meaning
  "everything" (P14). Fixed with `info_filtered {hidden, by_tier, info_detail, pages_hidden}`,
  the reveal-only `?info_detail=`, 422 `INVALID_SEVERITY`, and By Page / Top 10 disclosures.
  11 mutations verified red.
  - The structural test (no allowlist) also caught **`/page-priority`** rendering per-page
    `health_score` without naming the level — LEARNINGS open risk (1) arriving verbatim, now
    **CLOSED** there.
  - *First cycle gated by an external reviewer, and it earned it:* the gate caught me
    **overwriting `ByPagePanel.test.jsx`** and silently deleting its two E5/P8 citability tests
    (a green suite cannot tell you a test was removed — restored); a **contradiction inside my own
    approved spec** (§3.4 asked Top10Pages to disclose on `pages_hidden > 0`, which §3.1 of the
    same document fixes at 0 in exactly that case — reimplemented against `hidden` and the spec
    amended at the fold); and a **false claim in a commit message** ("recorded in TODO" for
    something never recorded — this bullet is that record).
- [x] **P5.3b — the unused `React` import** (closed 2026-09-05). The item named one file; the
  pattern was **23**, against 27 components that already shipped without it. Removed from all 23
  — the class, not the instance — verified by `vitest` (396 green) and a real `npm run build`.
- [x] **P5.4 — prevalence judged an old job by today's catalogue** (2026-09-04). `compute_prevalence`
  took `(code, url)` pairs, so the stored impact and severity were **discarded at the boundary**
  and everything was re-derived from `_CATALOGUE`/`derive_impact` while the lists, the counts and
  the health score used the stored value. Both recalibration directions measured; the upward one
  is worse — prevalence *names a code that appears in no list*, the "quick win you cannot find"
  that `_prevalence_for_display` was written to prevent. And it was **already firing on live
  data**: six §7-deleted codes hold 4,559 rows (`OG_IMAGE_MISSING` 1474, `OG_DESC_MISSING` 1188,
  `SCHEMA_MISSING` 1025, …) that the lists show, `by_severity` counts and the score charges, and
  prevalence dropped on `_CATALOGUE.get(code) is None`. **Decision: the stored value wins** — the
  principle `scoring_model_version` and `ISSUE_EMISSION_VERSION` already encode. 6 mutations
  verified red, plus one the gate ran itself.
  - *Superseded, not quietly flipped:* `test_e4_1b_unknown_code_ignored_not_crashed` asserted
    `prev == []` for an unknown code. That expectation **was** the defect; rewritten in place with
    the reason and the live row counts, keeping its "must not crash" half.
  - *One mutation survived the first pass:* `severity=spec.severity if spec else severity` —
    keeping the catalogue for known codes — passed all 28 tests, because the only severity
    assertion used a code the catalogue had *forgotten* and so exercised just the `else` branch.
    Test 4.5c now covers a known code whose stored severity differs.
- [x] **P5.4b — `_CATALOGUE[code].severity` was a hand-kept literal** (surfaced 2026-09-04 by the
  P5.4 spec §6, recorded here at the gate's request). Nothing pins it to
  `severity_from_impact(derive_impact(code))`; all 170 agree today by convention alone.
  `test_issue_help_completeness` pins *issueHelp* to the derived value, so the catalogue's own
  field is the third copy of one rule and the only untested one (P13, and LEARNINGS checklist 17).
  **Closed 2026-09-05:** `test_r5_severity.py` now pins all 170, with an adversarial half that
  fails if the comparison ever becomes the derivation against itself. `test_r5_severity.py`'s own
  docstring claimed such a parity test already existed — it did not, and the claim is corrected.

## Phase 6 — things the app knows and does not say (3 — ALL DONE)

Disclosure gaps. Each is a fact already computed and then dropped — the P25 shape this codebase
keeps hitting, and the reason four separate bugs this week were invisible until someone looked
in SQLite.

- [x] **P6.1 — a single-page scan scored 100 and called itself comparable** (2026-09-04). The
  item was right and stopped one step short. `checks_not_run` reached one UI — the Page Audit
  re-check banner, and even there only its *reason* sentence. Worse, `health_score_basis` did not
  omit the fact but **asserted the opposite**: `categories_unscored: []`, `comparable: true` on a
  job where 24 checks could not run, because it reasons about analysis *categories* and a
  single-page scan runs every category over one page. Measured consequence: a one-page scan
  reported a **+4 health improvement** against a ten-page crawl of the same site — the exact false
  comparison `comparable` exists to prevent. Fixed: `page_scope`/`pages_scored` on the basis, a
  fourth `/comparison` refusal, `checks_not_run` in the summary (absent — not `[]` — on a full
  crawl), and a Results banner with the count and names on demand. 11 mutations verified red,
  including the blanket "single-page never compares" ban, which passes the cross-scope test and
  silently kills the rescan before/after.
  - *The gate's non-blocking finding, fixed rather than commented:* the first implementation
    re-derived the code list inside `sqlite_store` and wrote a **differently worded** reason
    sentence, so one fact reached two surfaces in two phrasings. The registry's own comment beside
    `needs_full_crawl` already said "do not mirror the list anywhere else". Both now live in the
    registry, pinned by a behavioural test and a structural one.
- [x] **P6.2 — `rechecked` was a field no consumer read** (2026-09-04). Two fields share the
  name: `fix_focus.py`'s **string** `"not_checked"`, which `FixFocusPanel` genuinely renders,
  and the rescan response's **boolean** on issue rows, which nothing has ever read — that
  response reaches the UI through a banner rendering four *code lists*, never per-issue rows.
  It was also derivable on every row: carry-over is defined as "code in `needs_full_crawl`"
  and an unrunnable code can never be newly found, so the flag was a per-row copy of a
  code-level fact. Deleted, with its `docs/api.md` and functional-spec lines. A test asserted
  it *for* the missing consumer — its message read "so the panel cannot distinguish a
  re-checked finding from a carried-over one", a dependency that never held; it keeps the real
  assertion (presence) and loses the claim. 4 mutations verified red, including the
  `grep -r rechecked` sweep that would delete the live Fix Focus string.
- [ ] **P6.2b — the persistent Page Audit drawer cannot distinguish a carried-over finding
  from a re-checked one** (surfaced 2026-09-04 by P6.2; transcribed here at the gate's
  request). Measured: after a rescan, `/pages/issues` returns
  `H1_MISSING -> {'scored': True}` and `ORPHAN_PAGE -> {'scored': True}` — identical keys,
  though only one was re-evaluated. The re-check banner says so but is **transient**: dismiss
  it or reopen the drawer and the disclosure is gone. Deliberately NOT fixed in P6.2: the
  drawer also serves full-crawl jobs, where `needs_full_crawl` codes *were* checked, so "when
  was this row last evaluated, and by what kind of scan" is genuine per-row state stored
  nowhere. Adding it is a schema change to the `issues` table — the same reasoning
  `docs/TODO-ARCHIVE.md` applied to the Fix Focus third state. **Done when:** a finding the
  last scan could not evaluate is distinguishable in the drawer, or the decision not to store
  that is recorded with its reason.

- [x] **P6.3 — the performance ingest lost clicks and said it ingested them** (2026-09-04).
  Measured: one crawled page, three GSC rows (two folding onto it with 100 and 50 clicks, one
  matching nothing) → `ingested: 3`, the unmatched row stored under a key page-priority never
  reads, and the folded rows written as `(50, 500)` on a page that earned 150 and 1500. The
  sibling `/api/performance/ingest` already held unmatched URLs out — its comment states the
  exact reasoning the GSC path violated (P16) — but probing showed **the fold is wrong on both
  paths identically**, so one shared `fold_performance_rows` serves both. Arithmetic per field
  kind: counts add, rates recompute from the summed parts, position is impression-weighted, a
  field no source carried stays `None`. `/api/gsc/ingest` now returns `received`/`matched`/
  `ingested`/`unmatched_urls`/`invalid_urls`/`folded_urls`. 8 mutations verified red.
  - *The riskiest part was the read-merge, not the fold.* The bundle path's carry-forward for
    omitted sections ran per page, before folding, so a carried GA4 value would be summed once
    per folding URL (40 → 80, reproduced). It now runs once per folded row.
  - *Two pre-existing tests were passing **because** of the orphan write* — they seeded no
    crawled pages, so the test named "writes records to the ledger" was exercising the raw-URL
    fallback rather than the join it claims to test. Seeded, with the reason.
- [ ] **P6.3b — `gsc_ctr_mo` and `gsc_avg_position_mo` cannot express "no denominator"**
  (deferred 2026-09-04 from P6.3 §3.1; transcribed here at the gate's request). They are bare
  `float`s defaulting to `0.0`, and every consumer does arithmetic on them, so a fold with zero
  impressions writes `0.0` — "measured, and it was zero" — where `ga4_engagement_rate_mo`
  (`float | None`) can say `None`. Widening them is a contract change across the model, the
  ledger schema and the readers. Pinned meanwhile by
  `test_gsc_ctr_with_no_impressions_stays_zero_deliberately`, so it reads as a decision.
  **Done when:** the two fields can express "unmeasured", or the 0.0 is documented as the
  contract with its reason.
- [x] **P6.3c — the misfiled ledger rows are re-keyed** (closed 2026-09-05). **The deferral's
  premise was wrong and I never measured it.** "Invisible" was true; "rather than wrong" was not.
  Of 344 distinct ledger URLs, 242 were GSC data for pages that DO exist in the crawl, stored
  under the raw spelling — the app held that data and showed none of it.
  `scripts/migrate_rekey_performance_ledger.py` re-keys, never deletes, merges collisions through
  the shipped `fold_performance_rows`, and is dry-run by default. Applied: 395 rows onto 394 keys,
  9 merges, clicks and impressions conserved exactly, readable rows **60 → 445**.
  Two things the dry run caught that review had not: the target among several crawled spellings
  was being chosen by cursor order (it had picked a 3-job spelling over a 65-job one), and the
  hand-rolled merge took `gsc_top_queries` from one slice instead of folding them.

## Phase 7 — the V4 second half (1 — ALL DONE)

- [x] **P7.1 — panel explainers for the non-issue features** (2026-09-04). Verified by counting,
  not by trusting: `GEOReportPanel` 2, `GSCInsightsPanel` 1, and **zero** on the four named.
  The structural guard then found two the item had not listed — `PagePriorityPanel` and
  `FixFocusPanel` also hand-wrote the block. So there were **five** copies, and their labels had
  **already drifted** ("Why it matters" / "Good vs. bad" / "How to use it" in FixFocusPanel),
  which is a better argument for a shared component than the one the spec made. One home for the
  labels (`PanelExplainer.jsx`) and one for the copy (`panelHelp.json`), nine panels registered.
  The spec also had an error I corrected while implementing: it registered a `geo-report` panel
  that does not exist — `GEOReportPanel` has two distinct sub-tools (a GEO FAQ generator working
  from your settings, and an entity-schema factory), both different from `FaqSchemaModal`, which
  works only from answers already in the page HTML.
  - *The line that matters most:* batch optimisation uploads NEW files and your pages keep
    serving the old ones until you swap each by hand. Without it an operator watching a green
    progress bar reasonably concludes the site got faster. The vitest asserts that sentence.
  - *Gate finding acted on:* the id check ran one way only, so an entry no panel renders would
    have passed everything. Both directions now, mutation-verified.

## Phase 8 — engineering debt with no user symptom (4 — ALL DONE)

Real, worth doing, and nothing breaks tomorrow if they wait.

- [x] **P8.1 — a second writer silently un-did the first one's ticks** (2026-09-04). Measured:
  two panels each un-ticking a different item left `{'H1_MISSING': 'checked'}` — tab B's stale
  write restored what tab A had cleared. The likelier trigger needs one person: `verify-page`
  held the snapshot across a live re-crawl. Fixed with `store.mutate_fix_focus` (read-modify-write
  inside `BEGIN IMMEDIATE`) **and** by moving the rescan outside the lock — that half is about
  ordering, and a correct lock around a stale read still loses the tick.
  - *Gate finding, fixed:* `regenerate` still merged the copy it read at request start. My
    structural guard could not see it because the write lived inside the exempt builder, and the
    exemption's reason ("a first build has nothing to lose") does not cover a rebuild that merges
    state.
- [x] **P8.2 — the walk stopped at the first card, not the right one** (2026-09-04). Two anchors
  to one href split across nested cards reported **`[]`** — the finding disappeared. The choice
  was made by `break`, not by a rule. Now the container is the innermost card that *contains* the
  group, so `non_card_classes` — an editorial list the module says "the next theme will always
  defeat" — stops being what makes the check correct.
- [x] **P8.3 — one home for the page-size limit, and a pin chosen on evidence** (2026-09-04).
  The number had **four** homes, not two. `default_factory`, because `= _DEFAULT_PAGE_SIZE_LIMIT_KB`
  looks right and still bakes in a copy. `cryptography` 48→50.0.1, accepted on behaviour: a green
  suite plus a real Fernet round-trip, since the helpers no-op without a key. The gate verified it
  on a **fresh 3.11 venv from requirements.txt alone** — the leg that ships.
- [x] **P8.4 — the query was supplied, and thrown away** (2026-09-04). The bundle sent
  `top_queries`, the ingest reported them `deferred`, and striking distance showed
  `target_query=None` with a brief telling a nonprofit to target "its main search query" without
  naming one. Now persisted in the ledger (`gsc_top_queries`), folded by P6.3's arithmetic, read
  ahead of the scan-time seed, and no longer reported as deferred.
- [ ] **Three pre-existing eslint warnings** on files the 2026-09-05 sweep touched only at the
  import line — unused `hasIssues`, `originalScore`, `DEFAULT_SETTINGS`. Raised by the QA gate as
  non-blocking and verified identical at `origin/main`, so they predate the sweep and are not its
  doing. Not fixed with it: the sweep changed one line per file, and deleting live bindings is a
  different change needing its own look at whether each is genuinely dead.
- [ ] **The CSV export's `phase` column can only say `"1"`** (surfaced 2026-09-05 while deriving
  `PHASE_1_CATEGORIES`; pre-existing). `phase` is `"1" if issue.category in PHASE_1_CATEGORIES
  else "2"`, and every emitted category is in that set because Phase 2 (performance, mobile,
  schema) is unbuilt — so the column is a constant presented as a classification (P12). Left
  alone deliberately: removing or changing a column is a contract change for anything parsing the
  export, which is not a hygiene-sweep decision. **Done when:** the column is retired with a note
  in `docs/api.md`, or Phase 2 categories exist and it starts meaning something.
- [ ] **Performance Bundle PB4/PB5/PB7/PB9** remain after PB3 — separate bundle sections with
  their own contracts, explicitly out of P8.4's scope.
- [x] **The dimension-pass concurrency floor is pinned** (closed 2026-09-05). As arithmetic over
  the constants — `6 x floor(45/8)` = 30 against a cap of 150 — plus a test that reads the four
  values out of `docs/thresholds.md` and compares them to the live constants. No clock: a timing
  assertion is what turned CI intermittently red on 2026-09-03. The archive's "~33" was the
  unrounded `6 x 45/8`; the guaranteed floor is 30.
- [x] **P8.5 — CI had been red for every push, and nothing said so.** Closed 2026-09-05: all
  four jobs green, and `tests/test_declared_dependencies.py` now fails the build if `api/` or a
  test needs anything `requirements.txt` does not provide (it immediately found `pyyaml`, which
  was arriving only as a transitive of `uvicorn[standard]`). Found by the Phase 8 gate,
  2026-09-04. Two causes, one mine: `tests/test_performance_fold.py` (new in P6.3) patched
  `google.oauth2.credentials`, which is **not** in `requirements.txt`, so four tests failed on
  every CI run while passing locally. The rest were older: `tests/test_wp_domain_validation.py`
  patched `_CREDS_PATH` on two modules while six routers bind their own copy, so those tests
  passed only because a real `wp-credentials.json` sits in a dev machine's repo root. Both fixed;
  the suite now passes with that file removed.
  - **Verified after the fix (run 33933…):** `pytest 3.14 — development` ✅,
    `pytest 3.11 — ships` ✅, `docker build` ✅. Both test legs are green for the first time in
    this session's history.
  - **Still red, and NOT from this work: the `e2e` job has never passed since it was added**
    (`63ab034`, 2026-09-02). `npm ci` refuses because `frontend/package-lock.json` has no
    `esbuild` entry while CI resolves `vite@^5.2.0` to a build requiring `esbuild@0.28.2`;
    locally `esbuild@0.21.5` is installed and `npm install --package-lock-only` changes nothing,
    so the lock and the resolution disagree only in CI. Deliberately not fixed here: it needs a
    vite/esbuild version decision, and the build plus 396 vitest tests depend on the answer —
    not a change to make at the end of an unrelated phase. **Done when:** `npm ci` succeeds in
    CI and the e2e job runs.
  - **Done (2026-09-05):** `tests/test_declared_dependencies.py` checks the reverse direction —
    that the code needs only what `requirements.txt` declares, resolving "would this install in
    CI" through the dependency closure with declared extras honoured. It scans `patch("a.b.c")`
    strings as well as imports, because the outage arrived as a patch target. `api/` must declare
    its **module-level** imports (an ImportError at startup); a lazy import inside an
    optional feature, or a `try: import … except ImportError:` block, is allowed — that is how
    `gsc.py` and `js_renderer.py` are legitimately written. A test may use an undeclared package
    only if the same file skips on **that module name**; guarding a sibling is what let this
    through the first time. Verified by reproducing the original outage.
  - *It found one thing immediately:* `authority.py` imports `yaml` at module level and every
    provider of PyYAML in the tree is extras-gated — it arrived only through
    `uvicorn[standard]`. Now declared, for the reason the file already gives for pydantic.

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
