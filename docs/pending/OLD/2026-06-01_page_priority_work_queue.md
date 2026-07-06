---
status: draft-future
proposed: 2026-06-01
author: Architect (post-v3.0 shakedown, TalkingToad session)
type: feature
source: User insight during v3.0 shakedown — "should we score pages and present a list of top candidates?"
---

# Page Priority Work Queue + Per-Page GEO Workflow

> **Status: draft-future.** Specced during the v3.0 shakedown to capture the idea while
> fresh. Build AFTER v3.0 testing is complete. Not yet approved for implementation.

## The problem (observed in real use)
The GEO Analysis panel only ever analyses **one page — the crawl's target URL** (homepage).
The user cannot choose another page, and nothing tells them *which* pages most need work.
They're left guessing. Meanwhile TalkingToad already computes three per-page signals but
never ranks pages by them in one actionable place.

## The insight: we already built the ranking engine
Three signals exist per page but aren't combined into a "what to work on next" list:
1. **Health score** — per-page issue impact (`max(0, 100 - sum(issue impacts))`, as M5/M6 use).
2. **GSC performance** — clicks/impressions/CTR/position (M6.1 ingest → Performance Ledger).
3. **Refresh/Authority signals** — `api/services/refresh_trigger.py:evaluate_refresh()` already
   classifies pages: **Vulnerable Star** (high impressions + low health → fix first),
   **Hidden Gem** (healthy + no traffic → re-target), **Staleness**, **Traffic Decay**.

**M6.3's `evaluate_refresh` IS the "top candidates" engine.** This feature surfaces it.

## Goal
A **Page Priority Work Queue**: list all crawled pages, rank them by the Authority Matrix
(Vulnerable Stars first), and let the user click any page to run GEO analysis + rewrite on
THAT page. Turns M6's matrix from data into a workflow.

## Scope — three parts

### Part 1 — Backend: page priority ranking endpoint
- **New** `GET /api/crawl/{job_id}/page-priority` (in crawl.py, auth via existing router dep).
- For each crawled page, assemble: `url`, `health_score` (from issue impacts), GSC metrics
  (from Performance Ledger if present, else null), and the `ReviewFlag` from
  `evaluate_refresh(records, health_score, today=...)`.
- **Rank** by a priority key:
  - Vulnerable Star (high impressions + health < threshold) → highest
  - Traffic Decay / Staleness flagged → next
  - then by `health_score` ascending (worst health first) as the GSC-less fallback
    (so it's useful even without GSC connected)
  - Hidden Gems surfaced as a separate "opportunity" bucket
- Response: `{ pages: [{url, health_score, gsc:{clicks,impressions,ctr,position}|null,
  review_flag:{flagged, reasons}, priority_rank, bucket}] }`.
- **Deterministic:** pass `today` from request time into `evaluate_refresh` (per the M4/M5/M6 pattern).

### Part 2 — Backend: per-page GEO analysis (already supported — just wire it)
- The advisor already supports multi-page via `POST /api/ai/geo-report` with `page_urls`
  (see `advisor.py:generate_geo_report_legacy`, the `page_urls` branch — validates URLs
  belong to the job, analyses each, labels sections via `_wrap_page_section`).
- And `POST /api/ai/rewrite-url` already rewrites ANY url.
- **No new analysis backend needed** — Part 3 just calls these with a chosen page URL
  instead of the target_url.

### Part 3 — Frontend: the Work Queue UI + per-page actions
- **New** `PagePriorityPanel.jsx` (additive card on Results; lazy-loaded per M10.3): a
  sortable/filterable table of pages with health, GSC metrics, and a colored
  priority/Review-flag badge (Vulnerable Star / Hidden Gem / Stale / Decay). Render as text;
  no nav restructure (CLAUDE.md GUI rule).
- **Per-row action:** "Analyse GEO" → opens/feeds the GEO panel for THAT url
  (pass the selected url into `GEOReportPanel`, which calls `geo-report` with
  `page_urls:[url]` instead of defaulting to target_url). Then the existing rewrite flow
  works on the chosen page.
- **GEOReportPanel change:** accept an optional `pageUrl` prop; when set, send
  `page_urls:[pageUrl]` and show "Analysing this page: <pageUrl>" (the target-URL surfacing
  already added during shakedown generalises to this). Default (no prop) = legacy target_url.
- **V4 explainer** (standing rule): what the priority buckets mean — Vulnerable Star = "earns
  traffic but structurally weak, fix first"; Hidden Gem = "healthy but not found, re-target";
  Stale/Decay = "refresh due". How it can mislead: GSC lag, low-traffic sites show thin data.

## Files (when built)
| File | Change |
|---|---|
| `api/routers/crawl.py` | NEW `GET /api/crawl/{job_id}/page-priority` |
| `api/services/refresh_trigger.py` | reuse `evaluate_refresh` (maybe add a `rank_pages()` helper) |
| `frontend/src/components/PagePriorityPanel.jsx` | NEW work-queue table |
| `frontend/src/components/GEOReportPanel.jsx` | optional `pageUrl` prop → `page_urls:[url]` |
| `frontend/src/api.js` | `getPagePriority(jobId)` client fn |
| `frontend/src/pages/Results.jsx` | mount PagePriorityPanel (additive, lazy) |

## Tests
- Backend: page-priority ranks Vulnerable Stars first; works with NO GSC data (health-only
  fallback); deterministic `today`; contract test for the response shape.
- Adversarial: page with no ledger records → null GSC, ranked by health only, no crash;
  empty job → empty list.
- Frontend: PagePriorityPanel renders ranked rows; clicking "Analyse GEO" passes the right
  url; GEOReportPanel with `pageUrl` prop sends `page_urls:[pageUrl]`.

## Security check
SSRF: No (analysis uses existing guarded fetch; GSC via Google only) · Auth: yes (existing
router deps) · WordPress: No (generate-and-suggest; rewrite is copy-paste, never auto-published)
· XSS: No (render as text).

## Why this is the right next feature
- Makes M6's Authority Matrix **actionable** (it's currently data with no workflow).
- Unlocks **multi-page GEO** (the parked `feature/multi-page-geo` need) via the existing
  `page_urls` backend — minimal new backend.
- Directly answers the user's two questions: "how do I work on another page" + "show me the
  top candidates."

## Open decisions for approval (when scheduled)
- Exact priority formula / thresholds (reuse M6.3 constants vs new tunables).
- Does "Analyse GEO" reuse the existing GEOReportPanel inline, or open a focused modal?
- Show the queue always, or only after a crawl completes / GSC connected?
