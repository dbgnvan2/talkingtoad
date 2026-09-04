# Micro-spec — P5.2: a stored count beside a scored score

**Date:** 2026-09-04
**TODO item:** Phase 5, P5.2
**Class:** One population counted two ways on one screen (P13), and a disclosure field that
reports the wrong number rather than none (P12/P24). LEARNINGS open risk (3) of the
2026-09-01 `info_detail` change, written down at the time and now cashed in.

---

## 1. Verified, not inferred

Ran against the `tests/test_info_tiers_integration.py` fixture (5 rows on one page: one
warning, four info at impacts 3/2/1/0) at `info_detail="key"`:

```
summary.by_category  = {'heading': 1, 'metadata': 2, 'image': 1, 'redirect': 1}
health_score         = 93   (info_scored 1 / excluded 3)

tile metadata  says 2  ->  drill-down lists 0
tile redirect  says 1  ->  drill-down lists 0
tile heading   says 1  ->  drill-down lists 1
tile image     says 1  ->  drill-down lists 1

PDF path     (no info_detail): {'total': 5, 'warning': 1, 'info': 4, 'info_excluded': 0}
By Page path (scoped)        : {'total': 2, 'warning': 1, 'info': 1, 'info_excluded': 3}
```

Two things this makes concrete, one of them worse than the TODO describes.

**1.1 A category tile is a button that lies about what is behind it.** `metadata` reads
**2** and opens an **empty list**. This is not a subtle numeric disagreement an operator
might not notice — it is a promise of findings followed by a blank page. The tile reads
`summary.by_category` (`sqlite_store.py:591-599`, a plain `GROUP BY category` over every
stored row); the drill-down `/results/{category}` filters by the job's level
(`crawl.py:1526-1532`). Two paths, one question, and only one of them knows the setting.

**1.2 The PDF does not merely show the stored count — it prints a false disclosure.**
`crawl.py:3057` calls `get_pages_with_issue_counts(job_id, page=1, limit=10)` **without
`info_detail`**, so the parameter defaults to `"all"`. The row comes back
`info_excluded: 0`. That field exists to say what the level left out, and on this path it
positively asserts *nothing was left out* when three rows were. A missing disclosure is a
gap; a disclosure reporting zero is a claim. The same store method, called correctly by
`/pages` twelve hundred lines earlier, returns `info_excluded: 3`.

Three of the four callers of `get_pages_with_issue_counts` omit the argument. Only
`crawl.py:1561` (By Page) passes it.

## 2. Every surface, and what each shows today

| # | Surface | Source | Today | Sits beside |
|---|---|---|---|---|
| S1 | Category tiles | `summary.by_category` | **stored** | the health score, on the same panel |
| S2 | PDF "Pages with Most Issues" | `get_pages_with_issue_counts` (no level) | **stored**, `info_excluded: 0` | the PDF health score |
| S3 | Excel category sheet | `summary.by_category` | **stored** | the Excel health score |
| S4 | Advisor page picker | `get_pages_with_issue_counts` (no level) | **stored**, and it *ranks* by it | — |
| S5 | PDF "Total Issues Found" | `summary.total_issues` | **stored**, unlabelled | "Health Score", two rows above |

S5 is the P16 shape: the frontend already solved it. `SummaryPanel.jsx:232` renders
`Total Issues` with `found · N scored` beneath. The PDF prints the bare stored number
directly under Health Score and says nothing. One front end got the fix.

Already correct and **not** to be touched: `by_severity` stays the stored count — the
Info Notices card (`SummaryPanel.jsx:246`) shows `info_scored` with `+N excluded`
beneath it, the PDF's `_info_notices_figure` does the same, and
`test_summary_stored_counts_unchanged` pins it. That pairing is the pattern this spec
copies rather than replaces.

## 3. Change

### 3.1 The summary carries both populations, named

`get_summary` gains two maps beside the existing `by_category`:

```python
"by_category":          {...},   # stored — unchanged, still every row
"by_category_scored":   {...},   # what the health score charged
"by_category_excluded": {...},   # the difference, per category
```

`by_category_scored[c] + by_category_excluded[c] == by_category[c]` for every category,
which is the same invariant `info_scored + info_excluded == by_severity.info` already
carries and the same one a test will pin. Computed with the SQL predicate already used by
`get_pages_with_issue_counts` (`INFO_DETAIL_MIN_IMPACT` floor), so there is one rule
expressed once per storage layer, not a second Python re-implementation.

**Additive on purpose.** Redefining `by_category` to mean the scored count would be a
smaller diff and the wrong shape: `by_severity` would then be stored while `by_category`
was scored, two adjacent fields in one response disagreeing about what a count means. The
codebase already answers this question — `info_scored`/`info_excluded` beside a stored
`by_severity` — and consistency with that beats brevity.

### 3.2 The tile shows what is behind it, and says what it is not showing

`SummaryPanel` renders `by_category_scored[cat]`, falling back to `by_category[cat]` for a
summary from before this change. When `by_category_excluded[cat] > 0`, the tile carries a
muted `+N not scored` beneath the label — the same disclosure shape as the Info Notices
card, per tile, because the whole point is knowing *which* tile moved.

Showing the scored count **without** that line would be its own P31: at
`info_detail="none"` a site's tiles would read all-zero, and zero is what a clean site
looks like. The count and the caveat ship together or neither ships.

### 3.3 The three callers that dropped the level pass it

`crawl.py:3057` (PDF), `advisor.py:287` (page picker) and `advisor.py:354` (URL
validation) pass `info_detail=job.settings.info_detail`. The third changes no behaviour —
it reads only `url`, and a page with nothing but excluded rows is still returned by the
`LEFT JOIN` — but it is changed anyway so that "every caller passes the level" is a rule
with no exceptions to remember. A test pins that there are none.

The PDF's per-page row then renders `N Info` from the scored count and appends
`(+N excluded)` when the row has any, matching `_info_notices_figure`'s existing phrasing.

### 3.4 The PDF labels its total the way the screen already does

"Total Issues Found" becomes `1240 (1150 scored)` when `info_excluded > 0`, and the bare
number otherwise — the wording `_info_notices_figure` established, applied one row up.

### 3.5 Excel reads the scored map

`excel_generator.py:99` iterates `by_category_scored`. The workbook already carries
`info_caveat_note` (`test_excel_export_caveat_when_info_excluded`), so the disclosure
sentence is present; only the number was wrong.

## 4. Tests

Extending `tests/test_info_tiers_integration.py`, whose fixture already produces the
disagreement above.

| # | Test | Goes red when |
|---|---|---|
| 4.1 | `test_category_tile_count_equals_the_list_it_opens` | any tile count stops matching `/results/{category}` |
| 4.2 | `test_scored_plus_excluded_equals_stored_per_category` | the two new maps stop reconciling |
| 4.3 | `test_by_category_stays_the_stored_count` | `by_category` is redefined under a consumer |
| 4.4 | `test_pdf_page_rows_use_the_jobs_level` | `crawl.py:3057` drops the argument again |
| 4.5 | `test_pdf_page_rows_never_claim_zero_excluded_when_rows_were` | the false `info_excluded: 0` returns |
| 4.6 | `test_every_caller_of_get_pages_with_issue_counts_passes_info_detail` | a fourth caller forgets |
| 4.7 | `test_pdf_total_issues_shows_scored_when_any_excluded` | S5 regresses |
| 4.8 | `test_excel_category_sheet_uses_the_scored_count` | S3 regresses |
| vitest | `renders the scored count and the not-scored hint on a tile` | S2/3.2 regresses |

**Adversarial cases — the point of each:**

- **4.1 is the only test that would have caught this at all**, and it is written the way
  LEARNINGS item 13 now requires: it reads the tile's number out of the summary and
  asserts it against the **live list endpoint's length**, not against a second computation
  of the same thing. Two tests that each describe one side would agree with each other
  forever, which is exactly how this shipped.
- **4.3 is the other direction of 4.2.** The obvious wrong fix is to redefine
  `by_category` as scored and let 4.1 pass; 4.3 fails on that, and pins the existing
  `by_severity` symmetry.
- **4.5 is the adversarial half of 4.4.** Passing the level fixes both the count and the
  disclosure, so 4.4 alone cannot tell which was fixed. A row that is scoped but still
  reports `info_excluded: 0` is a live possibility if someone later computes the counts
  and the disclosure from different queries.
- **4.6 is structural** — it reads `api/` for `get_pages_with_issue_counts(` call sites and
  asserts each passes `info_detail`. A behavioural test covers the callers that exist; the
  next caller is the one that will forget. Its docstring will say plainly that it proves
  the argument is passed, not that the value is right.
- **vitest** asserts the tile renders the **scored** number *and* the `+N not scored`
  hint. Asserting only the number would pass the P31 implementation that shows a bare `0`
  for a fully-excluded category.

Every one of these is verified by deleting the code it guards and confirming it goes red,
including both "wrong fix" mutations above.

## 5. Considered and rejected

- **Redefine `by_category` as the scored count.** Rejected in §3.1 — it makes two adjacent
  fields in one response mean different things.
- **Label the tile instead of changing it** ("2 found, 0 scored"). Rejected: a tile is a
  button, and its number is a promise about what opening it shows. A label explaining why
  the button lies is worse than a button that does not.
- **Filter `by_category` in the router rather than the store.** Rejected: the store already
  expresses this predicate in SQL for `get_pages_with_issue_counts`; a second Python
  implementation of the same rule is the P13 shape that produced this item.
- **Fix S5 (PDF total) in a later item.** Rejected: it is the same sentence of the same
  spec, already solved on the other front end, and leaving it is how S1–S4 came to exist.

## 6. Not in scope, recorded

- `PHASE_1_CATEGORIES` (`sqlite_store.py`) still contains `duplicate`, which CLN1 removed
  from `CATEGORY_DISPLAY` in August. Every summary therefore carries a `by_category`
  key no surface renders and no checker emits. Harmless, adjacent, and a separate change —
  to TODO.
- `by_severity` and `total_issues` stay stored (§2).

## 7. Done when

- A category tile's number equals the length of the list it opens, at every level, pinned
  by a test that reads one side and asserts against the other's live output.
- No surface reports `info_excluded: 0` for a job that excluded rows.
- Every caller of `get_pages_with_issue_counts` passes the job's level, with a structural
  test that fails on the next one that does not.
- The PDF states its total the way the screen already does.
