# Micro-spec — P8.4: the query was supplied, and thrown away

**Date:** 2026-09-04
**TODO item:** Phase 8, P8.4 (the last)
**Class:** P25 with a twist — not a field computed and never rendered, but a field *received
from the producer*, acknowledged, and discarded, while the surface that needs it reports
nothing.

---

## 1. Verified

Striking distance reads target queries from **one** place: `job.priority_seed`, the CSV
uploaded when the scan was started (`striking_distance.py:48-53`, whose comment says so —
*"Target queries live only in the GSC priority seed the job was started with (the ledger
carries none)"*).

Meanwhile `/api/performance/ingest` accepts `top_queries` on every bundle page and drops them:

```python
if any(p.gsc and p.gsc.top_queries for p in bundle.pages):
    deferred.append("top_queries")
```

Measured end to end — a bundle carrying a real query for a page that then lands in the
striking-distance band:

```
ingest -> 200   deferred=['top_queries']
striking-distance rows=1
  target_query=None   other_queries=[]
  rewrite_brief="Rewrite the title and meta description of … to target its main search query…"
```

The page is found. The query was **supplied by the producer**, acknowledged as received, and
discarded — and the rewrite brief then tells the operator to target "its main search query"
without being able to name it. A scan that never uploaded a priority seed can never have a
target query, however much performance data it ingests.

`performance_ledger` has no query column (`job_store_base.py:833-851`), and the store already
has an additive `ALTER TABLE performance_ledger ADD COLUMN` migration path
(`sqlite_store.py:208`), so this is a column plus a read, not a schema project.

## 2. Change

### 2.1 The ledger stores the queries it is given

A `gsc_top_queries TEXT` column (JSON), written by `ingest_bundle` alongside the metrics it
already stores, as a list of `{query, impressions}` ordered by impressions descending. The
full `BundleQuery` carries clicks/ctr/position too; only the query and its impressions are
kept, because impressions are what orders them and nothing consumes the rest.

### 2.2 Folding follows P6.3's rule, not a new one

Two source URLs can fold onto one page (P6.3), and both may carry queries. **Impressions per
query add**, and the list is re-sorted — the same arithmetic P6.3 established for counts, so
this is consistent rather than a second convention. Two slices reporting the same query for
one page are two slices of that query's traffic.

### 2.3 `deferred` stops saying it dropped them

`deferred` tells a producer what was accepted but not stored. Once stored, `top_queries` must
leave that list, or the response lies in the other direction — a producer reading it would
keep re-sending data it thinks was lost. The **site-level** query report
(`bundle.site.ga4_site_search_terms`) is genuinely still not stored and stays deferred.

### 2.4 Striking distance prefers the ledger, falls back to the seed

Ledger queries first (they are per-period and move with the data), then `priority_seed` for a
job whose bundle carried none. The comment claiming the ledger carries none goes with it.

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_an_ingested_query_reaches_striking_distance` | the measured `target_query=None` returns |
| 3.2 | `test_top_queries_is_no_longer_reported_as_deferred` | §2.3 regresses |
| 3.3 | `test_the_site_level_query_report_is_still_deferred` | §2.3 over-applied |
| 3.4 | `test_folded_urls_sum_impressions_per_query` | a second folding convention appears |
| 3.5 | `test_the_priority_seed_still_supplies_queries_when_the_ledger_has_none` | the fallback is dropped |
| 3.6 | `test_the_ledger_wins_over_a_stale_seed` | precedence is the wrong way round |
| 3.7 | `test_a_page_with_no_queries_anywhere_reports_none_not_empty_string` | "unknown" becomes "" |

**Adversarial cases:**

- **3.5 is the one the obvious implementation breaks.** Replacing the seed lookup with a
  ledger lookup satisfies 3.1 and silently removes target queries from every job that got
  them the old way — a regression on the only path that works today.
- **3.6 fixes the precedence deliberately.** With both present they will disagree eventually;
  the ledger is per-period and moves with the data, the seed is frozen at scan start, so the
  ledger wins. Asserted rather than left to whichever lookup runs first — which is the P8.2
  mistake in a different file.
- **3.4 reuses P6.3's fixture shape** so the two folds cannot drift apart. A query present in
  both folded slices must end with the summed impressions, not one slice's.
- **3.7** guards the P12 shape this repo keeps hitting: `""` is a query, `None` is "we do not
  have one", and the rewrite brief reads differently for each.

## 4. Considered and rejected

- **Store the full `BundleQuery`.** Rejected: clicks, ctr and position per query have no
  consumer, and a column of unread data is what P6.2 just deleted. Adding the fields when
  something needs them is cheaper than carrying them now.
- **Keep reading only the seed, and document it.** Rejected: the producer is already sending
  the data and being told it was received. Documenting that we discard it does not make the
  brief able to name a query.
- **Also implement PB4/PB5/PB7/PB9.** Rejected as scope. The TODO lists them as *remaining*,
  not as part of this item; they are separate bundle sections with their own contracts.
- **Also pin the dimension-pass concurrency floor** (the "~33 images" note carried alongside
  P8.4). Rejected here: it is a different subsystem and a test-coverage question, not a
  data-flow one. Recorded so it is not lost with the item that carried it.

## 5. Not in scope

- Query-level *reporting* (a "queries for this page" panel). This item makes one query
  available where one is already asked for.
- Backfilling queries for jobs ingested before the column existed — they have none, and their
  `target_query` stays `None`, which is honest.

## 6. Done when

- A bundle-supplied query reaches the striking-distance row and its rewrite brief.
- `deferred` no longer claims `top_queries` was dropped, while the site-level report still is.
- A job that gets its queries from the priority seed still gets them.
- Folded URLs sum impressions per query, by the same rule as every other count.
