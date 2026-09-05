# QA Gate — the 2026-09-05 deferral sweep (P6.3c, P5.2b, P5.3b, P5.4b, dimension floor, P8.5 close-out)

**Gate date:** 2026-09-04 (local) / sweep dated 2026-09-05
**Range:** `858841c..5906119` = `origin/main..HEAD` (6 commits, clean tree):
  `858841c` docs(spec) · `c33262d` fix(ledger re-key migration) · `b36cf17` refactor(registry: derived categories) ·
  `0823c93` test(severity parity + measurable floor) · `e73d6b5` chore(frontend: unused React import ×23) ·
  `5906119` docs(fold + LEARNINGS 27–30)
**Gate type:** independent (Hermes, fresh context — no agent verifies its own work)
**Verdict: APPROVED** — no blocking findings. All nine spec-table rows have real tests (several adversarial);
both suites green at HEAD; the applied-to-dev-store claim verified against the live database, not taken from the
commit message; fold-step compliance complete (pending file deleted, spec folded, thresholds updated because
numeric bounds genuinely changed, TODO/LEARNINGS updated).

## Paste-ready verdict block for Claude Code

```
QA GATE — 2026-09-05 deferral sweep (858841c..HEAD, 6 commits): APPROVED,
no blocking findings. Nothing to fix before pushing; the fold commit
(5906119) is already in the range and complete.

Evidence (all re-run at HEAD, not taken from commit messages):
- backend (dev pin 3.14): ./venv/bin/python -m pytest tests/
  -p no:cacheprovider -q -> 5552 passed, 1 skipped, 2 deselected
  (integration deselected by marker), 183.28s. New/changed modules re-run
  alone: 49 passed in 3.04s (test_migrate_rekey_performance_ledger.py,
  test_r5_severity.py, test_image_dimensions.py).
- frontend: npx vitest run -> 396 passed / 50 files (matches e73d6b5's
  "396 green"). eslint on all 23 changed files: 0 errors, 3 warnings —
  all three pre-existing at origin/main (hasIssues in AIReadinessPanel,
  originalScore in GEOReportPanel, DEFAULT_SETTINGS in SettingsPanel);
  the known SummaryPanel.jsx:1 React-import warning is GONE.
- spec table: rows 3.1-3.5 in TestWhatItTouches/TestRunningItAgain
  (re-keyed-not-deleted, collision-merges-via-shipped-fold, unmatched
  left-alone, idempotent, dry-run-writes-nothing — the last asserted on
  file bytes); 3.6/3.7 in TestTheCategorySetTracksTheCatalogue (both
  parity directions + not-vacuously-consistent adversarial); 3.8 in
  test_r5_severity.py (all 170 pinned + adversarial half using a
  dataclasses.replace copy so a self-comparing derivation fails); 3.9 in
  TestTheMeasurableFloorFollowsFromTheConstants (6 x floor(45/8) = 30
  vs cap 150, plus thresholds.md-vs-constants readback, no clock).
- dev store (read-only queries on talkingtoad.db): 445 ledger rows on an
  exact crawled-page key — matches c33262d's "readable rows 60 -> 445"
  exactly; 65 unmatched distinct urls LEFT ALONE (269 exact + 65 = 334
  distinct, consistent with the spec's 37/242/65 pre-migration split).
  Clicks/impressions conservation was asserted by the migration's own
  tests, not re-derived here.
- static scan over added lines: no secrets, no os.system/shell=True/
  eval/exec/pickle. Two SQL f-strings interpolate column lists taken
  from PerformanceRecord.model_fields (fixed Python identifiers), all
  values parameterised — not an injection vector.
- workflow: docs/pending/2026-09-05_deferral-sweep.md DELETED in
  5906119; fold landed in functional-specification.md incl. correction
  of the "invisible rather than wrong" sentence; thresholds.md gained
  only the derived-floor rows (spec §2's own numeric bounds — the
  sanctioned completion-time write); TODO.md closes P5.2b/P5.3b/P5.4b/
  P6.3c + the floor, records the CSV `phase`-column contract question;
  LEARNINGS 27-30 appended. issueHelp/issue-codes untouched (no
  registry code/category drift: derivation is from _CATALOGUE itself).
- no circular import: api/models/issue.py imports registry at module
  level; registry imports only stdlib at top level.

Non-blocking (see gate file body): the promised .pre-rekey backup is
absent from the repo dir today; a dead first-sort line in _merge; the
--apply backup-refusal branch has no direct test; 3 pre-existing eslint
warnings untouched by the import-only change.
```

## Evidence table

| Check | Command | Result |
|---|---|---|
| Range + tree state | `git log origin/main..HEAD --oneline`; `git status` | 6 commits as listed; clean tree; ahead 6 |
| Backend full suite (dev pin) | `./venv/bin/python -m pytest tests/ -p no:cacheprovider --tb=short -q` | **5552 passed, 1 skipped, 2 deselected**, 183.28s, exit 0 |
| New/changed modules alone | `pytest tests/test_migrate_rekey_performance_ledger.py tests/test_r5_severity.py tests/test_image_dimensions.py` | **49 passed** in 3.04s |
| Spec rows collected | `--collect-only` over the two test files | rows 3.1–3.5, 3.6–3.7, 3.8, 3.9 all present under the expected classes (see map below) |
| Frontend | `cd frontend && npx vitest run` | **396 passed / 50 files**, 5.88s |
| Lint changed files | `npx eslint <23 changed jsx/js>` | **0 errors, 3 warnings** — all pre-existing at origin/main (verified identical lines at the parent); SummaryPanel React warning resolved |
| Static scan | `git diff origin/main..HEAD` added lines grepped | no secrets / os.system / shell=True / eval / exec / pickle; 2 benign model-field SQL f-strings |
| Dev-store claim | `sqlite3 -readonly talkingtoad.db` | 445 readable rows (exact-key), 65 unmatched urls left alone; matches commit exactly |
| Import graph | `grep` on registry.py imports; issue.py read | registry top-level imports are stdlib-only → no circular import from `issue.py:15` |

## Spec table → test map (docs/pending/2026-09-05_deferral-sweep.md §3)

| Row | Spec name | Implemented as | Where |
|---|---|---|---|
| 3.1 | `test_recoverable_rows_are_re_keyed_not_deleted` | `test_recoverable_rows_are_re_keyed_not_deleted` | `TestWhatItTouches` |
| 3.2 | `test_a_collision_merges_by_the_same_rule_as_the_fold` | `test_a_collision_merges_by_the_same_rule_as_the_fold` | `TestWhatItTouches` (sums 150/5000, ctr 0.03, pos 17.0 — an overwrite/mean cannot pass) |
| 3.3 | `test_rows_matching_no_crawled_page_are_left_alone` | `test_rows_matching_no_crawled_page_are_left_alone` | `TestWhatItTouches` |
| 3.4 | `test_the_migration_is_idempotent` | `test_the_migration_is_idempotent` | `TestRunningItAgain` (runs twice; third-run plan must be empty) |
| 3.5 | `test_dry_run_writes_nothing` | `test_dry_run_writes_nothing` | `TestRunningItAgain` (asserted on `read_bytes()` before/after, not on reported output) |
| 3.6 | `test_phase_1_categories_is_derived_from_the_catalogue` | `test_every_category_in_the_set_is_emitted_by_some_code` + `test_every_emitted_category_is_in_the_set` | `TestTheCategorySetTracksTheCatalogue` |
| 3.7 | `test_no_category_in_the_set_is_unemitted` | `test_the_set_is_not_vacuously_consistent` (names `metadata`/`heading`/`broken_link`/`security` — an empty derivation satisfies both parity tests) | same class |
| 3.8 | `test_catalogue_severity_matches_the_derived_value` | `test_every_catalogue_severity_matches_the_derived_value` + `test_the_parity_check_would_notice_a_drifted_literal` | `tests/test_r5_severity.py` (P32 guard via `replace()` copy) |
| 3.9 | `test_the_measurable_floor_follows_from_the_constants` | `TestTheMeasurableFloorFollowsFromTheConstants` (4 parametrised thresholds.md↔constant readbacks + shortfall-unreachable adversarial + `images_measured`/`images_measurable` disclosure) | `tests/test_image_dimensions.py` |

The migration file's extra tests (beyond the spec table) pin exactly the defects its commit message claims the dry
run caught: `recorded_at` survival, `gsc_top_queries` folded-not-taken, earliest `created_at`, and the target
spelling chosen by majority (both insertion orders via `@pytest.mark.parametrize("reverse", [False, True])`).

## Static scan result

Clean over added lines. The two SQL f-strings in the migration (`_read`, `apply_moves`) build column lists from
`PerformanceRecord.model_fields` — fixed Python identifiers from the model, with every value bound via `?` — the
same benign class as the codebase's existing parameterised-store patterns.

## Workflow compliance

- **Spec folded:** yes — `docs/functional-specification.md` gains the re-key narrative (correcting the
  "invisible rather than wrong" sentence in place) and the sweep summary; pending file **deleted** in 5906119.
- **thresholds.md:** updated only for the new derived-floor rows (`45 s` / `8 s` budget rows + the "30 against a
  cap of 150" prose) — a genuine numeric-bound addition from spec §2, now asserted against the live constants by
  test 3.9's parametrised readback. No ad-hoc edits.
- **TODO.md:** P5.2b, P5.3b, P5.4b, P6.3c, and the dimension floor marked closed with corrected premises; the
  CSV `phase`-column constant-`"1"` observation recorded as a deliberate non-fix (contract question).
- **LEARNINGS.md:** items 27–30 appended; all four match this cycle's actual failure modes.
- **Registry/help parity:** registry.py's `_CATALOGUE` is the *source* of the new derivation, not a consumer —
  no issue-code/issueHelp/issue-codes.md drift possible from this change; parity tests green in the full run.
- **GUI architecture / WP safety:** untouched (no GUI files beyond import lines; no WP calls anywhere in range).
- **Unpushed state:** 6 commits, all part of this reviewed cycle — none is an unapproved pending spec.

## Non-blocking observations

1. **No `.pre-rekey-*.bak` on disk.** The store verifiably carries the migration's result (445 readable rows,
   exactly the commit's claim), and `main()` writes a backup before `--apply` and refuses without one — yet no
   `talkingtoad.db.pre-rekey-*.bak` exists alongside the older `.pre-origin-collapse` backups. Either the backup
   was removed after verification, or the apply path did not go through `main()`. Not a code defect; the refusal
   branch fails safe. If the backup was deleted, the pre-apply state is unrecoverable from that file — the
   git-committed claim of conservation (968 / 128,097) is the remaining record.
2. **`--apply` branch under-tested.** All 12 migration tests exercise `plan()`/`apply_moves()` directly or the
   dry-run default; nothing asserts `--apply` creates a backup or returns 1 when `copy2` fails. The destructive
   path's guard rails are the least-tested part of a destructive script. Candidate for one future test.
3. **Dead first sort in `_merge`** (`scripts/migrate_rekey_performance_ledger.py:132-134`): the first
   `sorted(...)` result is immediately overwritten by the second sort. The surviving sort is correct (freshest
   `recorded_at` first, `None` last) — the earlier line is inert. Cosmetic.
4. **Dangling spec citations.** The migration script and its test module cite
   `docs/pending/2026-09-05_deferral-sweep.md §1`, which the fold deleted. Matches the pre-existing convention
   (`test_r5_severity.py` still cites the long-folded `2026-07-06_scoring-change-remainder.md`) — historical
   pointer, not a violation, but the citations now resolve to nothing either way.
5. **3 pre-existing eslint warnings** on files the sweep touched only at the import line (`hasIssues`,
   `originalScore`, `DEFAULT_SETTINGS`) — verified identical at origin/main; unrelated to this cycle. The
   skill's known non-blocking SummaryPanel warning is resolved by the sweep.

## State

- Tree clean at `5906119`; nothing committed by this gate. Gate file is the only write.
- Push is clear: `git push origin main` will publish the fold with it.
