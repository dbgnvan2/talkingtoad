# Micro-spec E3: Put the Performance Ledger and Page Priority into the PDF and Excel exports

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: new `api/services/page_priority.py`; `api/services/report_generator.py`,
`api/services/excel_generator.py`, `api/routers/crawl.py`
Related shipped spec: `docs/functional-specification.md` §6.9 (Page-priority work queue)

## Problem (verified on job `05cd2496`, 2026-08-29)

`performance_ledger` holds **555 rows** for livingsystems.ca — per-URL GSC clicks,
impressions, CTR and average position, plus GA4 sessions, engagement rate, conversions and
AI-referral sessions, for periods `2026-07` and `2026-08`.

`grep -n "performance_ledger\|gsc\|impressions" api/services/report_generator.py` returns
**nothing**. The client-facing PDF uses none of it.

The consequence is visible on page 3 of the generated report. **"Top 10 Pages to Fix First"**
is ordered by `ORDER BY total DESC` on raw issue count (`sqlite_store.py:621`), so it lists
ten podcast-episode pages. The ledger's top earners do not appear at all:

```
emotional-pain-and-suffering/        15,216 impressions   55 clicks   0.36% CTR
bowen-theory/                        14,997 impressions   37 clicks   0.25% CTR
…/Newsletter-14-Sibling-Position.pdf 11,423 impressions   33 clicks
what-kind-of-help-is-helpful/         3,947 impressions    5 clicks   0.13% CTR
```

An independent audit of the same site led with exactly these pages, because a page with
15,000 impressions at 0.36% CTR is where the next hour of work pays. "The page with the most
info notices" is not.

This is **P25**: the ranking is *built* — §6.9's Authority Matrix, `rank_pages`, PW ordering
by clicks then conversions, all shipped and tested — and it is reachable only from the GUI
panel and `GET /api/crawl/{job_id}/page-priority`. The artifact the client actually receives
never asks for it.

## Change

### E3.1 — Extract the assembly once, so it cannot drift again

`get_page_priority` (`routers/crawl.py:1505`) currently assembles the ranked rows inline:
per-page health via `compute_page_health`, citability via `compute_citability_grade`,
ledger lookup via `get_performance_records`, flag via `evaluate_refresh`, order via
`rank_pages`. Move that body verbatim into:

```python
# api/services/page_priority.py
async def build_page_priority(store, job_id: str, *, today=None) -> list[dict]:
    """Ranked work queue for a job. Spec: docs/functional-specification.md#6.9"""
```

The router becomes a thin caller. The PDF and Excel generators call the same function.
Behaviour is unchanged by construction; a contract test pins the endpoint's response shape
before and after (below).

### E3.2 — Two new PDF sections

Inserted after **Dashboard Summary**, before **Top 10 Pages to Fix First**:

**"Search Performance"** — rendered only when the ledger has rows for this domain.
- Period(s) covered, stated explicitly, and the source ("Google Search Console + GA4,
  supplied via the Performance Bundle"), so the reader knows this is first-party data.
- Site totals: impressions, clicks, CTR, average position; GA4 sessions, engagement rate,
  conversions, AI-referral sessions.
- **Top 15 pages by impressions**, each with clicks, CTR, average position, and the page's
  TalkingToad health score beside it. This is the join that neither a crawler alone nor an
  analytics export alone can produce, and it is the section's reason to exist.
- **High-impression / low-CTR** callout: pages above the impressions median whose CTR is
  below the site average — the snippet-rewrite worklist.

**"Priority Pages"** — the §6.9 queue, top 15, with columns: rank, URL, bucket
(Vulnerable Star / Traffic Decay / Hidden Gem / …), health, citability grade, clicks,
impressions, conversions, and the review-flag reasons.

### E3.3 — Re-order "Top 10 Pages to Fix First", honestly

When the ledger has rows for the domain, this section is ordered by `build_page_priority`
instead of raw issue count, and its subtitle changes to name the ordering
("ranked by traffic, conversions and page health"). When the ledger has **no** rows the
ordering and subtitle are exactly as today — matching §6.9's stated behaviour that the queue
"works with **or without** GSC data" and collapses to health-only ordering.

The section must never imply traffic weighting it did not apply. The subtitle is the
mechanism that keeps that honest, and it is asserted by test.

### E3.4 — Excel parity

A **Performance** tab and a **Priority Pages** tab, same data, uncapped.

### E3.5 — Staleness guard (P6)

Ledger rows carry `recorded_at` / `source_generated_at`. When the newest row for the domain
is older than `TT_PERF_STALE_DAYS` (env, default 60), both PDF sections render with a dated
banner — "Performance data as at 2026-08-01, 92 days old" — rather than presenting stale
numbers as current. When the ledger is empty the sections are omitted entirely, and the
Scope-and-Caveats section (E7) records that performance data was not supplied.

## API contract table (required before code, per CLAUDE.md)

| Endpoint | Consumer expects | Test name | Status |
|---|---|---|---|
| `GET /api/crawl/{job_id}/page-priority` | response shape byte-identical after the E3.1 extraction: `{pages:[{url,health_score,citability_grade,gsc:{clicks,impressions,ctr,position,conversions},review_flag:{flagged,reasons},bucket,priority_rank}],total}` | `tests/test_page_priority.py::test_e3_1_endpoint_contract_unchanged_after_extraction` | Pending |
| `GET /api/crawl/{job_id}/export/pdf` | Performance + Priority Pages sections present when ledger non-empty | `tests/test_report_integration.py::test_e3_2_pdf_has_performance_when_ledger_present` | Pending |
| `GET /api/crawl/{job_id}/export/pdf` | both sections **absent**, no crash, when ledger empty | `…::test_e3_2_pdf_omits_performance_when_ledger_empty` | Pending |
| `GET /api/crawl/{job_id}/export/excel` | Performance + Priority Pages tabs | `tests/test_excel_generator.py::test_e3_4_excel_has_performance_tabs` | Pending |

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E3.1a | `build_page_priority` returns the same rows, same order, as the pre-extraction router body on a fixture job | `tests/test_page_priority.py::test_e3_1a_extraction_is_behaviour_preserving` |
| E3.1b | **P25 guard:** router, PDF and Excel all call `build_page_priority`; removing any call fails a test | `tests/test_architecture_constraints.py::test_e3_1b_all_surfaces_call_page_priority` |
| E3.2a | With the real 555-row ledger fixture, PDF text contains `emotional-pain-and-suffering` in the top-15-by-impressions table | `tests/test_report_integration.py::test_e3_2a_top_impressions_lists_real_top_page` |
| E3.2b | Health score is joined onto each performance row (the join is the point) | `…::test_e3_2b_performance_rows_carry_health` |
| E3.2c | High-impression/low-CTR callout selects `what-kind-of-help-is-helpful` (3,947 imp, 0.13% CTR) and not the homepage (2,042 imp, 7.5% CTR) | `…::test_e3_2c_low_ctr_callout_selects_underperformers` |
| E3.3a | Ledger present → Top-10 order equals `build_page_priority` order, subtitle names the weighting | `…::test_e3_3a_top10_uses_priority_order_with_ledger` |
| E3.3b | Ledger absent → Top-10 order and subtitle identical to today (no regression) | `…::test_e3_3b_top10_unchanged_without_ledger` |
| E3.3c | **Adversarial (P7):** a zero-traffic page with 40 info notices must NOT outrank a 15,000-impression page with 3 | `…::test_e3_3c_issue_count_does_not_beat_traffic` |
| E3.5a | Ledger older than `TT_PERF_STALE_DAYS` renders the dated banner | `…::test_e3_5a_stale_ledger_banner` |
| E3.5b | **Dirty-state (P8):** a job re-exported after new ledger rows land uses the new period, not the cached one | `…::test_e3_5b_reexport_picks_up_new_period` |

Fix→test map (P10): **E3.3c first.** It is the adversarial case that states the whole point of
the change — and the one a naive implementation silently fails.

## Fixture

`tests/fixtures/performance/livingsystems_ledger.json` — the real 555 ledger rows exported
from `talkingtoad.db`, URLs preserved, checked in. Real-scale by construction (P9).

## Adjacent issues found, not fixed (rule 10)

- The AI executive summary (`routers/crawl.py:1641`) is built from `top_3` issue descriptions
  and health score only. It has the ledger available and does not use it, so the narrative and
  the new sections can disagree. Worth a follow-up spec; not changed here.
- `get_pages_with_issue_counts` sorts by raw `total` for every caller, not just the PDF. The
  Results "By Page" view has the same weakness. Flagged, not changed.

## Out of scope

Fetching GSC/GA4 directly. Acquisition stays with the producer app per
`2026-08-11_performance-bundle-producer-contract.md`; E3 is consumption only.
