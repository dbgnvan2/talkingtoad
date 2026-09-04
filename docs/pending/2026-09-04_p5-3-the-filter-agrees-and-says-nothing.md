# Micro-spec — P5.3: the filter agrees with the score, and says nothing about it

**Date:** 2026-09-04
**TODO item:** Phase 5, P5.3
**Class:** P31 (a narrowed population rendered as a clean result), P25 (a field computed,
shipped on every row, and read by nothing), P14 (an invalid input treated as a valid one).

---

## 1. The premise is stale; the item is not

TODO P5.3 reads:

> **`/pages?min_severity=info` is level-blind.** The filter does not know about
> `info_detail`, so it returns rows the score excluded.

**It knows.** `get_pages_with_issue_counts` filters on `r["info"]`
(`sqlite_store.py:836`), which has been the *kept* count since the 2026-09-01 SQL
predicate landed and is correct at every level since P5.2 fixed
`_kept_info_sql`. Probed on a job at `info_detail="key"` with three pages —
`/warn` (one warning), `/lowinfo` (two info rows at impact 1 and 0, both below the
level's floor), `/clean` (nothing):

```
/pages?min_severity=info at key:
  https://e.com/warn  {'total': 1, 'critical': 0, 'warning': 1, 'info': 0, 'info_excluded': 0}
  keys in response  : ['job_id', 'pages', 'pagination']
  info_filtered?    : False

/pages (unfiltered)  : [('warn', 0, 0), ('clean', 0, 0), ('lowinfo', 0, 2)]
/pages?min_severity=bogus -> 200 ['warn']

drawer for /lowinfo  : 0 issues, info_filtered {'hidden': 2, 'by_tier': {'low': 2}, ...}
```

The filter did not return a row the score excluded. It did something the TODO did not
anticipate and which is worse under this codebase's own rules: **it dropped a page with two
findings out of a filtered list, and returned nothing that says so.**

An operator asking "show me the pages with info issues" is handed a list whose only
omissions are precisely the pages whose info issues were excluded. The response carries no
`info_detail`, no `hidden`, no count. This is the P31 shape LEARNINGS states as a standing
rule — *report the suppressed state as "skipped, covered N of M", never as zero, which
every surface renders as a clean bill of health* — and P5.3 is the third Phase-5 item whose
written premise no longer holds while its instinct does.

## 2. What is actually wrong

### 2.1 `/pages` is the one list endpoint with no `info_filtered` (P16)

`/results` (`crawl.py:1499`), `/results/{category}` (`:1544`) and `/pages/issues` (`:1694`)
all return `info_filtered: {hidden, by_tier, info_detail}`. `/pages` returns
`{job_id, pages, pagination}`. `docs/functional-specification.md:591` says "every list
response carries `info_filtered`" — false, and false for the one list where the filtering
removes whole *pages* rather than rows inside a page.

`/pages` also has no reveal-only `?info_detail=` override, which the other three do. So the
By Page view is the only list an operator cannot widen to see what was dropped.

### 2.2 `info_excluded` is on every row and no component reads it (P25)

The store has returned `issue_counts.info_excluded` since 2026-09-01. Neither consumer
renders it:

- `ByPagePanel.jsx:30-32` renders a badge per severity `> 0`. The `/lowinfo` row is
  `{total: 0, critical: 0, warning: 0, info: 0, info_excluded: 2}` — every badge is
  suppressed and the page renders **with no badges at all**, identical to `/clean`.
- `Top10Pages.jsx:29` filters `critical + warning + info > 0`, so the same page is removed
  from the list outright.

The docstring on `get_pages_with_issue_counts` says the field exists "so By Page can never
list a page as '3 issues' whose drawer shows none". It prevents that. It does not prevent
the inverse, which is what shipped: By Page lists a page as **clean** whose drawer says
`hidden: 2`.

### 2.3 An unknown `min_severity` is silently a filter (P14)

`_SEVERITY_RANK.get(min_severity, 4)` (`sqlite_store.py:799`) maps any unrecognised string
to rank 4, which admits every severity — so `?min_severity=bogus` returns **200** and
behaves as "any issue", and `?min_severity=Critical` (capitalised) silently stops filtering.
`/results/{category}` already refuses an unknown category with **422 `INVALID_CATEGORY`**;
this is the same class of input on a sibling endpoint, answered differently.

## 3. Change

### 3.1 `/pages` discloses what the level removed — rows *and* pages

The response gains `info_filtered`, matching its three siblings, with one field they do not
need:

```python
"info_filtered": {
    "hidden": int,          # excluded info ROWS across the job's pages
    "by_tier": {...},
    "info_detail": level,
    "pages_hidden": int,    # pages that qualify for this min_severity at `all` and not at `level`
}
```

`pages_hidden` is the disclosure this endpoint specifically needs and the others do not: on
`/results` the level removes rows from a list, and the shorter list is itself visible; here
it removes whole rows from the *page* list, and a page that is not listed leaves no trace at
all. It is `0` whenever `min_severity` is unset (an unfiltered By Page lists every crawled
page regardless of level) and whenever the level is `all`.

### 3.2 `/pages` accepts the reveal-only override

`?info_detail=` on `/pages`, through the same `resolve_info_detail` as the others — it may
loosen the job's level, never tighten it. Without it the By Page view is the only list whose
omissions cannot be inspected.

### 3.3 An unknown `min_severity` is refused

**422 `INVALID_SEVERITY`**, naming the valid values, in the router beside the existing
`INVALID_CATEGORY` guard — not in the store, because the store's rank default is also used
for "no filter" and the router is where the other input validation lives.

### 3.4 By Page shows what it is not counting

- `ByPagePanel` renders a muted `+N not scored` chip when `info_excluded > 0`, so a page
  with only excluded rows is not visually identical to a clean one, and shows the panel-level
  `info_filtered` sentence when anything was hidden.
- `Top10Pages` keeps ranking by the scored count — a page with nothing chargeable does not
  belong in "pages with the most issues" — but carries the same one-line disclosure when
  `pages_hidden > 0`, so the omission is stated once rather than per row.

## 4. Tests

| # | Test | Goes red when |
|---|---|---|
| 4.1 | `test_pages_filtered_by_info_declares_the_pages_it_dropped` | `pages_hidden` is absent or 0 when pages were dropped |
| 4.2 | `test_pages_hidden_is_zero_when_nothing_was_dropped` | `pages_hidden` becomes a count of something else |
| 4.3 | `test_pages_carries_info_filtered_like_its_siblings` | the block is dropped |
| 4.4 | `test_every_list_endpoint_carries_info_filtered` | a *fourth* list endpoint ships without it |
| 4.5 | `test_pages_reveal_shows_the_pages_the_level_dropped` | §3.2 regresses |
| 4.6 | `test_pages_reveal_cannot_tighten` | reveal becomes a real filter |
| 4.7 | `test_unknown_min_severity_is_422_not_a_silent_pass` | §3.3 regresses |
| 4.8 | `test_every_valid_min_severity_is_accepted` | the guard is too broad |
| vitest | `ByPagePanel` shows the not-scored chip; a fully-excluded page is not rendered as clean | §3.4 regresses |

**Adversarial cases:**

- **4.1 asserts the dropped page's URL is recoverable**, not merely that a number is
  non-zero. A `pages_hidden` computed as "any page with `info_excluded > 0`" would be
  non-zero here and wrong — it must count pages that *changed qualification*, not pages that
  lost a row. 4.2 pins the other side with a job where every page qualifies anyway.
- **4.4 is structural, over the router**: it enumerates the `/api/crawl/{job_id}` GET routes
  that return a `pages` or `issues` list and asserts each response carries `info_filtered`.
  The three siblings were consistent and `/pages` was not, and nothing noticed for three
  days; a behavioural test per endpoint would not have caught the *fourth*.
- **4.7 asserts the status AND that no rows come back** — a 422 that still executed the query
  would pass a status-only check, and the point is that an unrecognised filter never silently
  becomes "everything".
- **vitest** asserts a fully-excluded page renders *differently* from a clean one, which is
  the actual defect. Asserting only that the chip appears would pass an implementation that
  also puts it on clean pages.

Every test verified red by deleting the code it guards, and both "wrong fix" variants above
verified by writing them.

## 5. Considered and rejected

- **Make `min_severity=info` return pages whose info rows were excluded** (i.e. genuinely
  make the filter level-blind, matching the TODO's literal words). Rejected: it would put
  the filter back in disagreement with the score, which is the defect Phase 5 exists to
  remove. The filter is right; its silence is the bug.
- **Drop `info_excluded` from the row** since nothing reads it. Rejected: it is the correct
  disclosure and the fix is to render it (P25 is closed by wiring, not by deleting).
- **Have `Top10Pages` list pages with only excluded findings.** Rejected: it ranks by issue
  count and a page with nothing chargeable is not a top-issue page. The omission is disclosed
  once at panel level instead.
- **Validate `min_severity` in the store.** Rejected: the store's rank default also encodes
  "no filter", and the router is where `INVALID_CATEGORY` already lives.

## 6. Not in scope

- `pagination.total_pages_crawled` reports the job's crawl total while `total_pages`
  paginates the *filtered* set. Differently named, not contradictory; left alone.
- The `min_severity` semantics themselves (rank 3 = "any issue") are unchanged.

## 7. Done when

- The filter and the score agree on what "info" means for that job — **already true**, and
  now pinned by a test that says so rather than left as an accident.
- A By Page list narrowed by the level says so, names how many pages it dropped, and can be
  widened to show them.
- A page whose findings were all excluded does not render identically to a page with none.
- An unrecognised `min_severity` is refused rather than silently meaning "everything".
