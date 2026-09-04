# Micro-spec — P5.4: prevalence judges an old job by today's catalogue

**Date:** 2026-09-04
**TODO item:** Phase 5, P5.4 (the last)
**Class:** P8 (dirty state — reading what persists between runs as if it were this run's),
P13 (two implementations of one rule), P31 (a row dropped from a table with nothing saying so).

---

## 1. Verified, not inferred

`compute_prevalence` is handed `(issue_code, page_url)` pairs (`prevalence.py:200-206`) and
nothing else. **The stored `impact` and `severity` are discarded at the boundary**, so every
downstream property — the severity on the row, and whether the row survives the job's
`info_detail` — is re-derived from *today's* `_CATALOGUE` and `derive_impact`, while the
issue lists, the counts and the health score all use the value stored at crawl time.

Three probes, all run:

**1.1 A recalibration downward drops a code from prevalence that the list still shows.**
`IMG_ALT_MISSING` stored at impact 3, job at `info_detail="key"` (floor 3):

```
derive_now=3   BEFORE  list=True  prevalence=True    (agree)
RECAL 3->2     AFTER   list=True  prevalence=False   (disagree)
```

**1.2 A recalibration upward is worse — prevalence names a code that appears in no list.**
`META_DESC_MISSING` stored at impact 2 (below the `key` floor, so absent everywhere):

```
A) stored=2 recalibrated->3:  list=False   prevalence=True
```

`_prevalence_for_display`'s own docstring says this is what it exists to prevent — *"a code
that appears in the Prevalence sheet but nowhere else in the workbook is the 'quick win you
cannot find' problem in another costume."* The filter it added reads `derive_impact`, so it
produces the very thing it was written to stop.

**1.3 The same defect is already firing on live data, no recalibration needed.**
`prevalence.py:106` skips any code `_CATALOGUE.get(code)` does not know. Six codes deleted
in the §7 merge still have rows in `talkingtoad.db`:

| Code | Rows |
|---|---|
| `OG_IMAGE_MISSING` | 1474 |
| `OG_DESC_MISSING` | 1188 |
| `SCHEMA_MISSING` | 1025 |
| `TITLE_META_DUPLICATE_PAIR` | 570 |
| `OG_TITLE_MISSING` | 172 |
| `TWITTER_CARD_MISSING` | 130 |
| | **4559** |

Probed with a `SCHEMA_MISSING` row:

```
in issue list=True   in prevalence=False
counted in by_severity={'critical': 0, 'warning': 0, 'info': 2}   health_score=95
```

The rows are listed, counted, and **charge the health score** — and prevalence drops them
without a word. This is not the latent hazard the TODO describes; it is that hazard already
realised on 4,559 rows, because a code being *deleted* is a recalibration to impact "none".

## 2. Which side wins: the stored value

The TODO asks for one to be chosen deliberately. **Stored.**

1. **An audit is a record of what was found when it ran.** The lists, `by_severity`,
   `by_category*`, `compute_page_health`, the exports and the citability grade all read the
   stored impact. Prevalence is the only surface re-deriving, so it is the outlier, and
   making the others follow the catalogue would silently restate old jobs' scores.
2. **The codebase already decided this.** `scoring_model_version` and
   `ISSUE_EMISSION_VERSION` exist precisely so `/comparison` can refuse a delta across a
   model change rather than pretend old rows were emitted under today's rules. Re-deriving
   at read time is the assumption those two stamps were added to deny.
3. **It is checklist item 8 verbatim** — "does this read state that persists between crawls
   … and assert the feature ignores prior-run content". Prevalence reads prior-run rows and
   applies this-run rules to them.

## 3. Change

### 3.1 The stored values reach `compute_prevalence`

`build_prevalence` passes `(code, url, impact, severity)`; `compute_prevalence` takes rows of
that shape. `Prevalence.severity` becomes the stored severity, and a new
`Prevalence.impact` carries the stored impact so the display filter can stop calling
`derive_impact`.

`human_description` and `category` continue to come from `_CATALOGUE` — they are labels, not
judgements, and a stale label is a cosmetic problem where a stale impact is an arithmetic
one. Where the catalogue no longer has the code, the description falls back to the code
itself and the category to the stored category.

### 3.2 `_prevalence_for_display` filters on the stored impact

`crawl.py:868-871` drops `derive_impact(r.code)` for `r.impact`. This is the whole of
defects 1.1 and 1.2: the same predicate (`info_row_excluded`) applied to the same value the
lists use.

### 3.3 A code the catalogue has forgotten is still a finding

`prevalence.py:106` currently `continue`s on an unknown code. It keeps the row instead,
built from the stored values. The `scope == "site"` skip only applies when the catalogue
knows the code — an unknown code has page URLs, which is what page-scoped means, and
guessing "site" would silently drop it again.

### 3.4 Rows of one code with different stored impacts

A rescan under a new model can leave one job holding two impacts for one code. Prevalence
takes the **maximum**, because prevalence exists to escalate and taking the max can never
demote a code below a value some row in the job actually carries. Deterministic, and stated
here so it is a decision rather than an accident of iteration order.

## 4. Tests

| # | Test | Goes red when |
|---|---|---|
| 4.1 | `test_prevalence_survives_a_recalibration_downward` | §3.2 regresses (the 1.1 disagreement) |
| 4.2 | `test_prevalence_does_not_name_a_code_no_list_contains` | §3.2 regresses (the 1.2 disagreement) |
| 4.3 | `test_prevalence_and_the_list_agree_across_the_whole_impact_grid` | either side re-derives |
| 4.4 | `test_a_code_deleted_from_the_catalogue_still_appears_in_prevalence` | §3.3 regresses |
| 4.5 | `test_deleted_code_prevalence_row_uses_the_stored_severity` | §3.3 falls back to a guess |
| 4.6 | `test_mixed_stored_impacts_take_the_maximum` | §3.4 becomes iteration-order dependent |
| 4.7 | `test_catalogue_still_supplies_the_description_and_category` | §3.1's split is inverted |

**Adversarial cases:**

- **4.3 is the one that matters** and is written per LEARNINGS item 13: for every
  (stored impact 0–5 × level) pair it asserts *"this code is in the prevalence table"* equals
  *"this code is in `/results`"*, reading both from live responses rather than recomputing the
  predicate. A test that recomputed `info_row_excluded` on both sides would agree with itself
  forever — which is exactly how this shipped.
- **4.1 and 4.2 simulate the recalibration** by patching `_IMPACT_OVERRIDES` and assert in
  *both directions*. 4.1 alone would pass an implementation that dropped every prevalence row;
  4.2 alone would pass one that kept every row.
- **4.5** guards the plausible wrong fix for §3.3: keeping unknown codes but labelling them
  from `severity_from_impact(stored_impact)` rather than the stored severity. Those agree
  today (verified: 0 of 170 catalogue specs disagree) and would diverge under exactly the
  recalibration this item is about, so the test pins the stored value specifically.
- **4.6** seeds the two impacts in both orders, so an implementation that takes "the last one
  seen" fails on one of the two.

Every test verified red by deleting the code it guards, and each named wrong fix verified by
writing it.

## 5. Considered and rejected

- **Make the lists follow today's catalogue instead.** Rejected in §2: it restates old jobs'
  scores retroactively and contradicts the two model-version stamps.
- **Re-derive prevalence but disclose the mismatch.** Rejected: a disclosure explaining why
  two tables in one report disagree is worse than the tables agreeing. Disclosure is the right
  answer for a *scope* choice (`info_detail`), not for one surface using stale inputs.
- **Backfill `issues.impact` for the six deleted codes.** Rejected: it is a destructive
  migration to fix a read-time bug, and the 2026-09-03 migration is a fresh reminder that
  rewriting stored findings is where the expensive mistakes live.
- **Drop the deleted codes from the lists too, for consistency.** Rejected — that is
  consistency achieved by hiding 4,559 findings the health score already charged.

## 6. Not in scope, recorded

- `_CATALOGUE[code].severity` is a hand-kept literal, not computed from
  `severity_from_impact(derive_impact(code))`. All 170 agree today, and
  `test_issue_help_completeness` pins *issueHelp* to the derived value — but nothing pins the
  catalogue's own field. A third copy of one rule with no test (P13). Adjacent, one assertion,
  and a different file's concern — to TODO.
- The six deleted codes remain in the database. Whether an old job should still report them
  at all is a data-retention question, not a rendering one.

## 7. Done when

- Prevalence and the issue lists agree about every code, at every level, across a simulated
  recalibration in both directions — pinned by a test that reads one side and asserts against
  the other's live output.
- A code today's catalogue has forgotten appears in prevalence with its stored severity,
  rather than vanishing from a table whose findings the health score is still charging.
