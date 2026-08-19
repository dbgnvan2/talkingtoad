# Micro-spec: traffic + conversion-weighted Page Priority (PW)

**Date:** 2026-08-14
**Status:** APPROVED 2026-08-14. PW-D1 = **clicks first, then conversions** (below). Building.
**Builds on:** functional-spec §4.8 (Page Priority / Authority Matrix), §6.12 (GSC upload).
**Motivation:** the user observed the Page Priority queue "ranks by score and ignores clicks and
impressions." Confirmed: `rank_pages` sorts by `(bucket, health_score, url)` — raw traffic only
matters at *bucket thresholds*, and GA4 conversions (`ga4_conversions_mo`, from the GSC upload's
`inquiries`) are written to the ledger but **never read** (deferred PB4).

## Problem
Within a bucket, and across the OK/Low-Health buckets, pages are ordered by **health alone**. So a
page with 138 clicks and one with 5 clicks — same bucket — tie-break by health, ignoring traffic.
Conversions do nothing. The upload plumbs GSC data in but does not let it *drive* the order.

## Design — within-bucket value ordering (bucket stays primary)
Keep the Authority-Matrix **bucket as the primary key** — needs-work-first is intentional (a
healthy high-traffic page should NOT jump the queue; it doesn't need work). Add **conversions and
clicks as the within-bucket ordering**, before health:

`sort key: (bucket_weight, −clicks, −conversions, health_score, url)`

- **Clicks first** (PW-D1): a high-click page is high-value whether it's a journey **entry point**
  (traffic arrives here, conversion happens elsewhere → its own conversion count is low/zero) **or**
  an **underperformer** (lots of clicks, few conversions → needs work). Both deserve to rank high;
  conversions-first would bury both. Then **conversions** (higher first) as the tiebreak among
  equal-click pages, then health (worst first), then url.
- A **tiered sort, not a weighted sum** — no magic blend constant (avoids P4); each tier is a real,
  explainable quantity.
- **Backward-compatible / no-GSC fallback:** with no ledger records, `conversions` and `clicks` are
  `0` for every page → the key collapses to `(bucket, 0, 0, health, url)` = **today's behavior
  exactly**. So a scan with no upload / no GSC is unchanged.
- `conversions` for the sort coalesces `None → 0` (unknown ⇒ don't float it up); the stored
  `ga4_conversions_mo` keeps its None (the P2 distinction is preserved in data, only the sort
  coalesces).

### PW1 — `rank_pages` (`api/services/refresh_trigger.py`)
Read `clicks`/`conversions` defensively from each row's `gsc` sub-dict (`None`/missing → 0) and use
the 5-tuple key above. `classify_page_bucket` and all bucket thresholds are **unchanged**.

### PW2 — carry conversions through (`api/routers/crawl.py::get_page_priority`)
Add `conversions: latest.ga4_conversions_mo` to the per-page `gsc` dict (alongside
clicks/impressions/ctr/position) so (a) `rank_pages` can read it and (b) it reaches the frontend.

### PW3 — surface it (`frontend/src/components/PagePriorityPanel.jsx`)
Show a **Conversions** value per page next to the GSC clicks/impressions column (dash when
`conversions` is null — unknown, not zero).

## Acceptance criteria → tests
| ID | Criterion | Test |
|---|---|---|
| PW1a | Two pages, same bucket + same health, higher **clicks** ranks first (adversarial: traffic now matters) | `tests/test_refresh_trigger.py::test_pw1a_clicks_break_within_bucket` |
| PW1b | Same bucket, **equal clicks** → higher **conversions** ranks first (conversions tiebreak) | `…::test_pw1b_conversions_break_click_ties` |
| PW1f | A high-click, **low/zero-conversion** page still ranks above a low-click page in the same bucket (journey-entry / underperformer both surface) | `…::test_pw1f_high_clicks_low_conversions_ranks_high` |
| PW1c | **No GSC data** → ranking identical to health-order (backward-compat / dirty-state) | `…::test_pw1c_no_gsc_falls_back_to_health` |
| PW1d | **Bucket still primary** — a Vulnerable Star outranks an OK page even with far fewer clicks (Authority Matrix preserved) | `…::test_pw1d_bucket_beats_traffic` |
| PW1e | `conversions=None` sorts as 0 (unknown doesn't float up), stored value stays None | `…::test_pw1e_none_conversions_sort_as_zero` |
| PW2 | `/page-priority` returns `gsc.conversions` per page | `tests/test_page_priority.py::test_pw2_conversions_in_payload` |
| PW3 | Panel renders the conversions value (and a dash for null) | `frontend`: `PagePriorityPanel.test.jsx` |

## Non-goals
- No change to bucket **definitions or thresholds** (Vulnerable Star / Traffic Decay / Hidden Gem
  stay as-is) — only the *within-bucket* order changes.
- No magic weight constant — tiered sort only.
- No change to the crawl **seed** (ii) — that already orders by the file's rank.
- Not the rich `PerformanceBundle` (GA4 sessions / index / GTM) — still deferred.

## Decision (resolved)
- **PW-D1 = clicks then conversions.** A high-click page ranks high whether it's a journey entry
  point (conversion elsewhere) or an underperformer (clicks high, conversions low) — both warrant
  attention; conversions-first would miss them. Conversions are the tiebreak among equal clicks.

## Completion
Fold into functional-spec §4.8 (note the within-bucket value ordering) + §6.12; add no new
thresholds; delete this pending file; push.
