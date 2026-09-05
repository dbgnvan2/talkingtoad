# Micro-spec — the deferral sweep, and one deferral whose premise was wrong

**Date:** 2026-09-05
**TODO items:** P6.3c, P5.2b, P5.3b, P5.4b, the dimension-pass concurrency floor, P8.5
**Class:** mostly hygiene — except the first, which is P8 (a decision made on state nobody
measured) and turns out to be user-facing.

---

## 1. P6.3c is not closeable. 242 pages' performance data is misfiled.

I deferred this on 2026-09-04 with the words *"invisible rather than wrong"*, and never
measured it. Measured now, against `talkingtoad.db`:

```
distinct ledger urls:                        344
  stored under the crawled-page key already:  37
  would match a crawled page via match_key:  242   <- read by nothing
  genuinely match no crawled page:            65
```

The 242 are not orphans. They are **GSC data for pages that exist in the crawl**, stored
under the raw form (`https://livingsystems.ca/about/`) while the pages are keyed without the
trailing slash. Striking distance, page-priority and the Authority Matrix all look rows up by
the crawled page's exact url, so for 242 of 279 matchable pages the app holds performance data
and shows none.

That is the opposite of the reasoning I recorded. "Invisible" was true; "rather than wrong"
was not — the operator ingested this data and the app behaves as if it never arrived.

### 1.1 Change: re-key, do not delete

A migration that re-points each recoverable row from its raw url to the crawled-page key,
**merging** where a row for that key already exists in the same period rather than
overwriting — using P6.3's arithmetic (counts add, rates recomputed, position
impression-weighted), because two rows for one page in one period are two slices of it.

The 65 genuinely unmatched rows are left alone: nothing establishes they belong to a crawled
page, and inventing a key for them is the fabrication this repo keeps refusing.

### 1.2 The 2026-09-03 lesson applies literally

That migration's near-miss was a delete rule that *sounded* right and proposed 553 deletions
where 73 were correct, caught only because someone looked at the number. So:

- the script runs **dry-run by default**, printing counts and a sample of before/after keys;
- the counts are reported here before anything is applied;
- it is **idempotent** — re-running finds nothing to move, and a test asserts that;
- it never deletes: a row is re-keyed or left.

## 2. The mechanical items

- **P5.2b — `PHASE_1_CATEGORIES` still contains `duplicate`.** A hand-kept frozenset in
  `api/models/issue.py`, read by three modules, holding a category CLN1 established no checker
  emits. Derived from the registry instead (`{spec.category for spec in _CATALOGUE.values()}`),
  which is CLN2's treatment and deletes the drift rather than the symptom.
- **P5.3b — `SummaryPanel.jsx:1` imports `React` unused.** Zero `React.` references in the
  file. One word.
- **P5.4b — `_CATALOGUE[code].severity` is a hand-kept literal.** All 170 agree with
  `severity_from_impact(derive_impact(code))` today, by convention alone;
  `test_issue_help_completeness` pins *issueHelp* to the derived value, so the catalogue's own
  field is the third copy and the only untested one. One assertion.
- **The dimension-pass concurrency floor.** The archive records the derivation: with
  `CONCURRENCY=6`, `TIMEOUT_S=8`, `BUDGET_S=45`, worst-case measurable images ≈ `6 × 45/8 ≈ 33`
  against up to 150 unbounded. Pinned as **arithmetic over the three constants**, not a
  wall-clock test — yesterday's flaky-timing lesson is one day old and this is the same shape.
  The test asserts the floor the constants imply and that `images_measured` discloses the
  shortfall.
- **P8.5 — closed.** CI is green on all four jobs and the guard shipped.

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_recoverable_rows_are_re_keyed_not_deleted` | the migration deletes |
| 3.2 | `test_a_collision_merges_by_the_same_rule_as_the_fold` | it overwrites instead |
| 3.3 | `test_rows_matching_no_crawled_page_are_left_alone` | it invents a key |
| 3.4 | `test_the_migration_is_idempotent` | re-running double-counts |
| 3.5 | `test_dry_run_writes_nothing` | the default is destructive |
| 3.6 | `test_phase_1_categories_is_derived_from_the_catalogue` | the hand list returns |
| 3.7 | `test_no_category_in_the_set_is_unemitted` | `duplicate` (or a successor) creeps back |
| 3.8 | `test_catalogue_severity_matches_the_derived_value` | P5.4b's third copy drifts |
| 3.9 | `test_the_measurable_floor_follows_from_the_constants` | a constant moves without the floor |

**Adversarial cases:**

- **3.2 is the one that can lose data.** A re-key onto an occupied `(url, period)` is the
  collision P6.3 already reasoned about; taking either row wholesale discards the other's
  clicks. It asserts the summed total, not "a row exists".
- **3.4 exists because a re-keying migration is exactly the kind that is run twice** — once in
  dry-run, once for real, and later by someone unsure whether it ran. The second pass must find
  nothing, or impressions double.
- **3.7 is the point of 3.6.** Deriving the set makes `duplicate` disappear *today*; the test
  asserts every member is emitted by some spec, so the next dead category fails rather than
  riding along.
- **3.9 is deliberately not a timing test.** A wall-clock assertion of concurrency is what
  turned CI red intermittently yesterday; this pins the relationship the archive documented,
  which is what "unpinned" actually meant.

## 4. Deliberately not in this sweep

- **P6.2b** (per-row "last evaluated" state) and **P6.3b** (widening `gsc_ctr_mo` /
  `gsc_avg_position_mo` to express "unmeasured"). Both are schema/contract changes across the
  model, the ledger and every reader. Each needs its own spec; folding them into a hygiene
  sweep is how a sweep becomes a rewrite.
- **PB4/PB5/PB7/PB9.** These are unbuilt bundle sections, not deferred fixes. They are on the
  list because PB3 shipped, and calling them "deferrals to clear" would misrepresent a feature
  backlog as debt.
- **The two Parked items** (SSRF resolve-then-fetch TOCTOU, the Playwright render budget). The
  standing instruction is that these need a design decision rather than a fix, and nothing has
  changed that.

## 5. Done when

- The 242 misfiled rows are readable by the consumers that were built to read them, with the
  dry-run numbers reported before anything was written.
- `PHASE_1_CATEGORIES` has no member no checker emits, and cannot regain one.
- The catalogue's severity, the derived value and `issueHelp` are pinned to each other.
- The measurable-images floor is a consequence of the constants, asserted without a clock.
