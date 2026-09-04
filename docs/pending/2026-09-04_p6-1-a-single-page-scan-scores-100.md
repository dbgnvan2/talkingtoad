# Micro-spec — P6.1: a single-page scan scores 100 and calls itself comparable

**Date:** 2026-09-04
**TODO item:** Phase 6, P6.1
**Class:** P25 (a fact computed and never rendered), P31 (a narrowed population read as a
clean result), P12 (a default reaching a surface and reading as a measurement).

---

## 1. Verified, not inferred

`/scan-page` creates a real job and its own docstring says "the caller can navigate straight
to `/results/{job_id}`". So a one-page audit lands on the same Results page as a full crawl.
Probed with a single-page job (`settings.single_page=True`, one page, no findings):

```
health_score       = 100        total_issues = 0
analysis_coverage  = None
health_score_basis = {'mode': 'all', 'categories_unscored': [], 'comparable': True, ...}
orphan_detection   = {'status': 'skipped_single_page'}
'checks_not_run' in summary        : False
'checks_not_run' in /results body  : False
```

**1.1 The 24 codes reach no UI beyond the re-check banner.** `checks_not_run` is returned by
four endpoints (`crawl.py:1839, 1975, 2200, 2478`) and rendered in exactly one place —
`Results.jsx:423`, the Page Audit re-check banner, and even there it is the *reason* sentence
keyed off `carried_over_codes`, not the list. The summary a reader actually looks at carries
neither. One of the 24 is disclosed (`ORPHAN_PAGE`, via `orphan_detection`); the other 23 are
not.

**1.2 `health_score_basis` does not merely omit the fact — it asserts the opposite.**
`categories_unscored: []` and `comparable: True` on a job where 24 checks could not run. The
field's own docstring says it exists because *"'we did not look' is arithmetically identical
to 'we found nothing'"*, and that a partial scan's score *"is not worse, it is NOT COMPARABLE,
and this record is what says so"*. It reasons about analysis **categories**; a single-page
scan runs every category over one page, so by its own terms nothing is unscored. The page
scope never enters it.

**1.3 The consequence: a fabricated improvement.** A full 10-page crawl with ten
`H1_MISSING` findings, then a single-page scan of one of those pages:

```
GET /comparison?previous_job_id=full
  comparable = True     reasons = None
  current = 100   previous = 96   delta health_score = +4
```

The report says the site improved by four points. It did not: one page was looked at instead
of ten, and 24 checks never ran. `comparable` is the mechanism this codebase built to prevent
exactly this, and it has no idea about page scope — it checks `info_detail`, the emission
version, and the category basis, and a one-page scan passes all three.

## 2. Change

### 2.1 The scan's scope travels on the basis

`health_score_basis` gains two fields:

```python
"page_scope":   "single_page" | "site",   # from settings.single_page
"pages_scored": int,                       # job.pages_crawled
```

`comparable` keeps its current meaning — *the category sets match* — because widening it
would make the existing reason strings wrong and would refuse the one comparison a
single-page scan legitimately supports (§2.3). The new fields are what `/comparison` reads.

### 2.2 The summary states what could not run

`get_summary` gains, for a single-page job only:

```python
"checks_not_run": [...24 codes...],
"checks_not_run_reason": _CHECKS_NOT_RUN_REASON,
```

Derived from the registry through the existing `_checks_a_single_page_scan_cannot_run()` —
never a second list. Absent (not `[]`) on a full crawl, because an empty list is a claim that
nothing was skipped and this must not be one more field asserting a clean bill (P12).

### 2.3 `/comparison` refuses across scopes

A fourth reason beside the three already there, in the same shape:

- scopes differ (`single_page` vs `site`) → `comparable: False`,
  `"a single-page scan is not comparable with a site crawl"`.
- both `single_page` but different `target_url` → `comparable: False`. Two one-page scans of
  *different* pages are two different measurements.
- both `single_page`, same URL → **comparable**. This is the before/after a rescan produces
  and the one comparison this scope genuinely supports; refusing it would break a working
  feature to fix a broken one.

The delta is still returned, as it is for the existing reasons — the guard labels, it does not
withhold.

### 2.4 Results says so on the page the reader is on

`SummaryPanel` renders a banner for a single-page job, in the shape the partial-scan banner
already uses (`analysis_coverage.mode === 'partial'`): one sentence naming the count, and the
codes on demand behind a disclosure toggle rather than 24 names in the reader's face. The
score is captioned with the same fact, because the number and its basis must not be separable.

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_single_page_summary_names_the_checks_that_could_not_run` | §2.2 regresses |
| 3.2 | `test_full_crawl_summary_has_no_checks_not_run_key` | the key becomes `[]` on a full crawl |
| 3.3 | `test_checks_not_run_is_derived_from_the_registry` | a second hand-kept list appears |
| 3.4 | `test_single_page_scan_is_not_comparable_with_a_site_crawl` | §2.3 regresses — the +4 returns |
| 3.5 | `test_two_scans_of_the_same_page_stay_comparable` | §2.3 is written too broadly |
| 3.6 | `test_two_single_page_scans_of_different_pages_are_not_comparable` | the URL half of §2.3 is dropped |
| 3.7 | `test_basis_carries_the_page_scope_both_ways` | §2.1 regresses |
| vitest | the banner names the count, lists on demand, and is absent on a full crawl | §2.4 regresses |

**Adversarial cases:**

- **3.4 asserts the delta is labelled, not that it is absent.** The plausible wrong fix is to
  suppress the comparison entirely; the established behaviour is to return the numbers with
  `comparable: false` and a reason, and three existing reasons already work that way.
- **3.5 is the other direction and the one that matters most** — a blanket "single-page scans
  are never comparable" passes 3.4 and 3.6 and silently breaks the rescan before/after, which
  is a shipped feature. It is written first for that reason.
- **3.2 exists because `[]` is the failure mode this repo keeps hitting** — `info_excluded: 0`
  in P5.2, `categories_unscored: []` here. A disclosure field that reports "nothing" is a
  claim, and on a full crawl the honest encoding is *absent*.
- **3.3 reads the summary's list against
  `{c for c, s in _CATALOGUE.items() if s.needs_full_crawl}` computed in the test**, so a
  hand-maintained copy that happens to match today still fails when the registry moves.

Every test verified red by deleting the code it guards, and both named wrong fixes verified by
writing them.

## 4. Considered and rejected

- **Deduct points for the checks that did not run.** Rejected, and `health_score_basis`'s own
  docstring rejects it in advance: *"inventing a penalty for a check that did not run is
  fabricating a finding."* A single-page score is not worse, it is not comparable.
- **Set `comparable: False` on the basis for every single-page job.** Rejected: it breaks the
  rescan before/after (§2.3) and overloads a field that currently means one specific thing.
- **Render all 24 codes in the summary.** Rejected: 24 code names above a one-page report is
  the "wall of text nobody reads" that makes the next disclosure easier to ignore. Count in
  the sentence, names on demand — which is what the TODO's "names them on demand" asks for.
- **Re-use `analysis_coverage` by writing `mode: "partial"` on single-page jobs.** Rejected:
  that field means *which analysis groups ran*, and a single-page scan runs all of them. Two
  different narrowings sharing one field is the P13 shape, and the partial-scan banner's
  wording ("these categories were not checked") would be false.

## 5. Not in scope

- The other two Phase-6 items (`rechecked`, GSC ingest) are separate.
- Whether a single-page job should appear in job history alongside full crawls at all is a
  product question, not a disclosure one.

## 6. Done when

- A single-page job's Results summary states how many checks could not run and names them on
  demand.
- No surface claims `categories_unscored: []` / `comparable: true` for a scan that could not
  run 24 checks.
- `/comparison` between a one-page scan and a site crawl returns `comparable: false` with a
  reason — and two scans of the same page still compare.
