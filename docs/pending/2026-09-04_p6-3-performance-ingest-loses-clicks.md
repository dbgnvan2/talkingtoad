# Micro-spec — P6.3: the performance ingest loses clicks and says it ingested them

**Date:** 2026-09-04
**TODO item:** Phase 6, P6.3 (the last)
**Class:** P16 (a capability added at one front end only), P2 (a partial failure that leaves
no trace), P31 (a narrowed result rendered as a complete one).

---

## 1. Verified, on both ingest paths

One crawled page (`https://e.com/about`), three GSC rows: two URL variants that fold onto
that page (100 clicks and 50), and one URL no crawl contains.

**1.1 `/api/gsc/ingest` — orphans stored, and the count says nothing went wrong**

```
POST /api/gsc/ingest -> 200 {'ingested': 3, 'period': '2026-09'}
  ledger[https://e.com/about]         = [(50, 500)]
  ledger[https://e.com/never-crawled] = [(9, 90)]
```

- `ingested: 3` on a job where **one** page matched. An ingest where *nothing* matched
  returns the same shape, so "the GSC property is a different domain from the crawl" and "the
  join worked" are indistinguishable from the response (P2).
- The unmatched row is **persisted under its raw URL** — a key no consumer reads, because
  page-priority looks rows up by the crawled page's exact url.
- The two folded rows became `(50, 500)`. **100 clicks and 1000 impressions vanished.** The
  page actually earned 150 and 1500.

**1.2 `/api/performance/ingest` — half right, and its comment says why**

```
POST /api/performance/ingest -> 200
  {'ingested': 1, 'unmatched_urls': ['https://e.com/never-crawled'], 'invalid_urls': [], ...}
  ledger[/about] = [(50, 500)]
```

The unmatched half is **correct and documented**: *"Bundle URLs that match no crawled page are
held out (surfaced in `unmatched_urls`) rather than persisted under an orphan key the consumer
would never read."* The GSC path violates exactly that reasoning, in the same repo, on the
same ledger — P16.

The fold half is **wrong on both paths, identically**: `(50, 500)`, and nothing in either
response says two URLs collapsed into one row.

## 2. Two defects, two shapes

| | `/api/gsc/ingest` | `/api/performance/ingest` |
|---|---|---|
| unmatched URL | stored as an orphan, counted as ingested | held out, reported ✓ |
| two URLs folding onto one page | last-wins, data lost, silent | last-wins, data lost, silent |

The first is a missing capability on one of two siblings. The second is a shared arithmetic
error, and it is the more expensive: a nonprofit reading "50 clicks" for a page that earned
150 will deprioritise it.

## 3. Change

### 3.1 One fold, used by both paths

A `fold_performance_rows` helper in `api/services/perf_join.py` — beside `match_key` and
`build_crawled_key_map`, the two functions this join already shares — taking rows already
resolved to a storage key and returning one record per key, plus the list of keys that more
than one source URL resolved to.

**The arithmetic is per field kind, not one rule:**

- **Counts add.** `gsc_clicks_mo`, `gsc_impressions_mo`, `ga4_sessions_mo`,
  `ga4_engaged_sessions_mo`, `ga4_conversions_mo`, `ga4_ai_referral_sessions_mo`. Two URL
  variants of one page are two slices of that page's traffic; the page's clicks are their sum.
  This is the half that recovers the lost 100.
- **Rates are recomputed, never averaged.** `gsc_ctr_mo = clicks / impressions`,
  `ga4_engagement_rate_mo = engaged / sessions`, from the summed numerator and denominator.
  Averaging two CTRs weights a 10-impression row equally with a 10,000-impression one.
- **Position is impression-weighted.** `Σ(position × impressions) / Σ(impressions)`. A plain
  mean says a page ranking 5th for its main query and 90th for one stray impression averages
  47.5.
- **Zero denominators** fall back to `None`, not `0.0` — a rate with no impressions is
  unmeasured, and this repo has now shipped `info_excluded: 0` and `categories_unscored: []`
  as cautionary tales about writing 0 for "no data".

### 3.2 The GSC path adopts its sibling's contract

`/api/gsc/ingest` holds unmatched URLs out instead of persisting them, and its response
becomes the same shape as `IngestResult`:

```python
ingested: int          # rows persisted — matched only
matched: int           # source URLs that resolved to a crawled page
received: int          # source URLs the GSC API returned
unmatched_urls: [...]  # held out, not stored
invalid_urls: [...]    # unparseable, skipped
folded_urls: {...}     # storage key -> the source URLs that collapsed onto it
```

`received` and `matched` together are the "matched N of M" the TODO asks for. `ingested`
keeps its name and its meaning — rows written — and is no longer mistakable for M.

### 3.3 Both responses report the fold

`folded_urls` is added to `IngestResult` too. A fold is not an error — it is the normal shape
of a GSC domain property — but it changes a number the operator reads, so it is stated. Empty
dict when nothing folded, and **absent keys rather than `{key: [url]}` for the single-URL
case**: a "fold" of one is not a fold.

### 3.4 Orphan rows already in the ledger

Not migrated. Existing orphan rows are keyed by URLs no consumer reads, so they are invisible
rather than wrong, and a destructive migration to tidy invisible rows is the trade the
2026-09-03 collapse warned about. Recorded in TODO with that reasoning.

## 4. Tests

| # | Test | Goes red when |
|---|---|---|
| 4.1 | `test_gsc_ingest_holds_out_urls_that_match_no_crawled_page` | the orphan write returns |
| 4.2 | `test_gsc_ingest_reports_matched_of_received` | the counts collapse back to one number |
| 4.3 | `test_folded_urls_sum_their_clicks_and_impressions` | last-wins returns (either path) |
| 4.4 | `test_folded_ctr_is_recomputed_not_averaged` | CTR is averaged |
| 4.5 | `test_folded_position_is_impression_weighted` | position is meaned |
| 4.6 | `test_a_rate_with_no_impressions_is_none_not_zero` | 0.0 is written for "unmeasured" |
| 4.7 | `test_both_ingest_paths_report_folded_urls` | one path keeps the disclosure and not the other |
| 4.8 | `test_a_single_url_is_not_reported_as_folded` | every row is reported as a fold |
| 4.9 | `test_ga4_counts_fold_without_disturbing_gsc` | the fold reaches only the fields it should |

**Adversarial cases:**

- **4.3 asserts 150, not "not 50".** The plausible wrong fix is first-wins, which changes the
  number, fixes nothing, and passes any test written as an inequality.
- **4.4 and 4.5 use inputs where the wrong arithmetic is close but not equal** — 100/1000 and
  50/500 both have CTR 0.1, so an *averaged* CTR is also 0.1 and a test using those rows
  cannot tell the two apart. The fixture deliberately uses different CTRs so the mean and the
  recomputation differ.
- **4.7 is the P16 guard**, and it is the reason this item is one change rather than a GSC
  patch: the unmatched capability existed on one path only for months, and the way that
  happens again is fixing the fold on the path that was in the ticket.
- **4.9** pins that summing GSC counts does not touch GA4 fields carried forward by the
  bundle path's read-merge (P8) — the two mechanisms meet here and the merge must still win
  for fields the source did not carry.

Every test verified red by reverting the code it guards, and each named wrong fix by writing
it.

## 5. Considered and rejected

- **Fix `/api/gsc/ingest` only.** Rejected: the fold defect is identical on both paths, and
  leaving it on the sibling is how the unmatched capability came to exist on one path only.
- **Last-writer-wins but log the collision.** Rejected: the TODO says "recorded rather than
  overwritten", and a log line beside a wrong number is a record of the loss, not a fix. The
  100 clicks are still gone.
- **Sum every numeric field.** Rejected: CTR, engagement rate and average position are not
  counts, and summing them produces numbers with no meaning (a CTR of 0.2, a position of 11).
- **Migrate the existing orphan rows.** Rejected (§3.4).
- **Make the GSC path call `ingest_bundle`.** Tempting — one implementation — but rejected:
  it would put a GSC API response through a producer-bundle contract with a version, sources
  and a `generated_at` it does not have, and the domain guard would need a synthetic
  `site_url`. The shared thing is the *fold*, and that is what gets extracted.

## 6. Done when

- `/api/gsc/ingest` reports `matched` of `received`, holds unmatched URLs out, and names them.
- Two source URLs folding onto one crawled page produce that page's real totals, on **both**
  ingest paths, with the fold named in the response.
- No rate is written as `0.0` when its denominator was zero.
