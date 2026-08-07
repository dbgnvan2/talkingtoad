# Micro-spec: Performance Bundle ingestion — GA4 + GTM + query/index via a source-agnostic contract

**Date:** 2026-08-06
**Status:** **Phase 1 SHIPPED (2026-08-06)** — PB1/PB2/PB6/PB8 implemented, tested (2130-green), and folded into functional-specification §4.8. Phases 2–3 (PB3/PB4/PB5/PB7/PB9) remain pending; this doc stays in `pending/` until they land. Architecture **decided 2026-08-06: Option A** (sibling app pushes bundle — see PB-A).
**Spec IDs:** PB1–PB9
**Extends:** the existing Performance Ledger (`api/models/performance.py`, `PerformanceRecord`),
`api/routers/gsc.py` ingest, the Page Priority queue (`PagePriorityPanel`), and refresh flags
(`api/services/refresh_trigger.py`). **Does not rebuild any of them.**
**Relates to:** `2026-08-06_measurement-integrity-checks.md` (supplies the crawl-side half of PB7).

---

## Problem & context

TalkingToad already ingests **GSC page-level** metrics (clicks/impressions/CTR/position) and uses
them to rank pages and flag "Vulnerable Star / Hidden Gem". What it lacks:

1. **GA4 signals** — sessions, engagement, and **conversions** (donations, form fills, newsletter
   signups) — the outcomes a nonprofit actually cares about, currently invisible.
2. **GSC query-level & index status** — `gsc_client.py` only queries `dimensions=["page"]`. No top
   queries per URL (⇒ no striking-distance), no URL-Inspection index/coverage state.
3. **GTM container health** — paused tags, missing GA4 config tag, broken triggers.
4. **Cross-signal completeness** — GA4/GSC know URLs the crawl never reached; the crawl knows pages
   that earn nothing. Neither side reconciles today.

The owner already runs a **separate reporting app** with GSC + GA4 + GTM OAuth wired up. Rather than
re-build GA4/GTM OAuth inside TalkingToad — which would drag in the deliberately **parked
multi-tenant identity model** (`docs/TODO-MULTITENANT.md`) — TalkingToad should accept a **pushed,
source-agnostic performance bundle**. TalkingToad owns *consumption* (ledger, priority, flags); the
sibling app owns *acquisition* (OAuth, quota, reporting). The existing in-app `/api/gsc/ingest`
becomes just one producer of the same contract.

### PB-A — architecture decision — **DECIDED: Option A (owner, 2026-08-06)**

- **Option A (CHOSEN):** sibling app is the producer; TalkingToad only ingests a bundle over an
  authenticated, domain-validated endpoint. **No new Google OAuth in TalkingToad. No identity-model
  unpark.** Shippable single-tenant today.
- **Option B (not taken):** build GA4/GTM OAuth natively in TalkingToad (mirroring `gsc.py`). More
  surface, more quota to manage, and it pushes on the parked identity model.

The contract stays source-agnostic, so Option B — or the existing in-app GSC ingest — can populate the
same ledger later without a contract change if the owner ever reverses this.

---

## The contract — `PerformanceBundle` v1

A versioned JSON document. One bundle = one site + one date range. Producer-neutral.

```jsonc
{
  "bundle_version": 1,
  "site_url": "https://example.org/",      // registrable-domain must match the target job (PB6)
  "generated_at": "2026-08-06T12:00:00Z",  // for staleness display (PB8)
  "period": "2026-07",                      // YYYY-MM, aligns with the ledger's monthly rows
  "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
  "sources": ["gsc", "ga4", "gtm"],         // which of the three are present in THIS bundle
  "pages": [
    {
      "url": "https://example.org/services/",
      "gsc": {"clicks": 12, "impressions": 340, "ctr": 0.035, "position": 8.4,
              "top_queries": [{"query": "family counselling", "clicks": 7, "impressions": 210,
                               "ctr": 0.033, "position": 6.1}],
              "index_state": "indexed"},     // indexed | crawled_not_indexed | discovered_not_indexed |
                                             //  excluded_noindex | not_in_gsc | unknown
      "ga4": {"sessions": 210, "engaged_sessions": 150, "engagement_rate": 0.71,
              "conversions": 4, "source_breakdown": {"organic": 180, "ai_referral": 9}}
    }
  ],
  "site": {                                  // site-level, not per-URL
    "ga4_site_search_terms": [{"term": "sliding scale", "count": 22}],
    "gtm_audit": {"container_id": "GTM-XYZ", "paused_tags": ["Old UA"],
                  "ga4_config_present": true, "broken_triggers": []}
  }
}
```

**Every field except `bundle_version`, `site_url`, `generated_at`, `period`, and `pages[].url` is
optional** — a GSC-only producer omits `ga4`/`gtm`; a producer without URL Inspection omits
`index_state`. Consumers must treat absence as "unknown", never zero (P2 — "empty" ≠ "not supplied").

---

## Design & implementation

### PB1 — Ledger extension (backend model)

Extend `PerformanceRecord` (`api/models/performance.py`) with **optional** GA4 + index fields, all
defaulting to `None` (not `0`, so "no GA4 source" is distinguishable from "zero sessions"):

```python
ga4_sessions_mo: int | None = None
ga4_engaged_sessions_mo: int | None = None
ga4_engagement_rate_mo: float | None = None
ga4_conversions_mo: int | None = None
ga4_ai_referral_sessions_mo: int | None = None
index_state: str | None = None            # controlled vocab above
```

Update both stores (`sqlite_store.py`, `redis_store.py`) schema + (de)serialisation — **both**, in the
same change (P5: sibling calls hardened together). New columns are nullable; legacy rows read `None`.
Query-level data is high-cardinality → store `top_queries` in a **separate** table/keyed structure
keyed by (url, period), not inline on the record.

### PB2 — Ingestion endpoint

`POST /api/performance/ingest` (new router `api/routers/performance.py`, `prefix="/api/performance"`,
`dependencies=[Depends(require_auth)]`). Body = `PerformanceBundle`. Behaviour:

- **PB6 domain guard** — validate `bundle.site_url` registrable-domain matches the target job's
  domain via the existing `_validate_wp_domain_for_url`-style helper; mismatch → 403 `DOMAIN_MISMATCH`
  (mirror the WP-safety pattern). A bundle must never write performance rows for a domain the job
  isn't for.
- Upsert one `PerformanceRecord` per `pages[]` for `period`, merging GA4 + GSC fields; store
  `top_queries`, `ga4_site_search_terms`, and `gtm_audit` in their side structures.
- Return `{"ingested": N, "sources": [...], "period": "...", "unmatched_urls": [...]}` where
  `unmatched_urls` = bundle URLs whose normalised form matched no crawled page (surfaced, not dropped
  — P2). **URL join uses `normaliser.py`** on both sides so trailing-slash/www/scheme differences
  don't silently split rows (P11 — round-trip normalisation).

### PB3 — Striking-distance → AI rewriter

New derived read `GET /api/performance/striking-distance/{job_id}` → pages+queries where
`position` ∈ config band (default **5–15**) **and** `impressions ≥` config floor (default **50**).
These are the highest-leverage inputs to the **existing** AI title/meta rewriter — the response
includes the top query so the rewriter can target it. Bands live in `docs/thresholds.md` /config, not
literals (P4). Read-only; no auto-rewrite (user triggers the existing rewriter).

### PB4 — Conversion-weighted priority (opt-in)

The Page Priority queue currently ranks by GSC traffic × health. Add an **optional** weighting mode
that incorporates `ga4_conversions_mo` when present, so donation/signup pages float up. Must
**degrade gracefully**: when no GA4 data exists for a job, behaviour is byte-identical to today
(GSC-only). Weighting factors in config (P4). This is an additive mode, not a replacement — confirm
default (recommend: GSC-only default, GA4-weighted when a bundle with `ga4` has been ingested).

### PB5 — Index-status reconciliation

Join `index_state` against the crawl. Emit a report (and optionally issue codes — confirm scope):
crawled pages that GSC reports `crawled_not_indexed` / `discovered_not_indexed` / `excluded_noindex`.
This is a P6 ground-truth check: the crawler found the page; is Google actually indexing it?

### PB7 — Coverage / cross-signal diff

`GET /api/performance/coverage-diff/{job_id}` → three lists, each a completeness win:
- `uncrawled_earning` — URLs in the bundle (GA4 sessions or GSC impressions > 0) that the crawl never
  reached → **candidate crawl seeds** (P3 discovery completeness) + orphan-page signal.
- `zero_traffic_crawled` — crawled, indexable pages with zero sessions/impressions over the period →
  content-prune / consolidate candidates.
- `tag_missing_but_active` — pages flagged `ANALYTICS_TAG_MISSING` (from the measurement-integrity
  spec) that nonetheless show GA4 sessions in the bundle → a measurement contradiction (tag in a
  template we didn't parse, or data from another property). Surfaced for review, not auto-resolved.

### PB8 — Freshness

Store `generated_at`; every surface that shows bundle-derived numbers shows the date and warns when
older than a config staleness window (default 35 days). Never present stale performance data as
current (P6-adjacent).

### PB9 — GTM audit surface

Render `gtm_audit` (paused tags, missing GA4 config, broken triggers) in the Connections/GSC panel
area. Read-through only — TalkingToad displays what the producer computed; it does **not** call the
GTM API itself under Option A.

### Frontend

- `ConnectionsPanel` / a new "Performance data" card: show last-ingested bundle date, sources present,
  `unmatched_urls` count, GTM audit summary.
- `PagePriorityPanel`: optional conversions column when GA4 present.
- New small panels for striking-distance and coverage-diff (read-only tables), gated on data presence
  with explicit empty/loading/error states (React rule).

---

## API contract tests (write BEFORE any frontend code — repo rule)

| Endpoint | Frontend/consumer expects | Test name | Status |
|----------|---------------------------|-----------|--------|
| POST `/api/performance/ingest` | `{ingested, sources, period, unmatched_urls, stale, deferred}`; 403 on domain mismatch; GA4-absent bundle stores `None` not `0` | `test_performance_ingest.py::test_ingest_response_schema` · `::test_domain_mismatch_returns_403_and_writes_nothing` · `::test_ingest_ga4_only_page_keeps_gsc_null_not_zero` | ✅ done |
| POST `/api/performance/ingest` | unmatched bundle URLs are reported, not dropped | `test_performance_ingest.py::test_unmatched_urls_surfaced` | ✅ done |
| GET `/api/performance/striking-distance/{job_id}` | rows within band incl. `top_query`; band is config-driven | `tests/test_striking_distance.py::test_band_and_floor_from_config` | pending |
| GET `/api/performance/coverage-diff/{job_id}` | three keyed lists; `uncrawled_earning` excludes already-crawled URLs | `tests/test_coverage_diff.py::test_three_lists_and_join` | pending |
| Priority queue | GA4-absent job ranks byte-identically to today (regression) | `tests/test_page_priority.py::test_ga4_absent_matches_gsc_only_baseline` | pending |

## Acceptance criteria → tests

| ID | Criterion | Test | Status |
|----|-----------|------|--------|
| PB1 | `PerformanceRecord` GA4/index fields default `None`; stores round-trip them; absent GA4 stays `None` not `0` | `test_performance_model.py::test_pb1_ga4_and_index_fields_round_trip` · `::test_pb1_absent_ga4_reads_back_as_none_not_zero` | ✅ done |
| PB2 | Bundle upsert merges GA4+GSC for a period; second ingest updates, not duplicates; GA4-only re-ingest preserves prior GSC (**dirty-state, P8**) | `test_performance_ingest.py::test_reingest_updates_not_duplicates` · `::test_ga4_only_reingest_preserves_prior_gsc_via_endpoint` · `test_performance_model.py::test_pb1_gsc_only_upsert_preserves_prior_ga4` | ✅ done |
| PB3 | Striking-distance returns only in-band pages with a target query | `tests/test_striking_distance.py::test_only_in_band_returned` | pending |
| PB4 | Conversion weighting raises a high-conversion page's rank; no-GA4 job unchanged | `tests/test_page_priority.py::test_conversion_weighting_optin` | pending |
| PB5 | `crawled_not_indexed` page appears in index-reconciliation report | `tests/test_index_reconcile.py::test_not_indexed_surfaced` | pending |
| PB6 | Domain-mismatched bundle → 403, zero rows written; job-not-found → 404; bad version → 400 | `test_performance_ingest.py::test_domain_mismatch_returns_403_and_writes_nothing` · `::test_job_not_found_returns_404` · `::test_unsupported_version_returns_400` | ✅ done |
| PB7 | Coverage-diff classifies a bundle-only URL as `uncrawled_earning` and a traffic-less crawled page as `zero_traffic_crawled` | `tests/test_coverage_diff.py::test_classification` | pending |
| PB8 | Bundle older than staleness window flagged stale; fresh = False; unknown = None; boundary correct | `test_performance_model.py::test_pb8_days_since_and_is_stale` · `test_performance_ingest.py::test_stale_bundle_flagged` | ✅ done |
| PB9 | `gtm_audit.paused_tags` surfaced in the status/response | `tests/test_performance_ingest.py::test_gtm_audit_surfaced` | pending |

**Adversarial / P-pattern coverage:** PB2 dirty-state re-ingest (P8); PB4 monotonicity (more
conversions ⇒ not lower rank, P7); PB1/PB2 null-vs-zero (P2); PB6 domain guard (security); URL-join
normalisation both sides (P11).

---

## Phasing (recommended)

- **Phase 1 (ship first):** PB1, PB2, PB6, PB8 — the contract + ledger extension + safe ingest. Makes
  GA4 data *land* and display. Lowest risk.
- **Phase 2:** PB3 (striking-distance → rewriter) and PB7 (coverage-diff) — the highest-value derived
  reports.
- **Phase 3:** PB4 (conversion weighting), PB5 (index reconcile), PB9 (GTM audit surface).

### Phase 1 — SHIPPED 2026-08-06 (as-built notes & deviations)

Landed: `api/models/performance.py` (PB1 fields), ledger schema + `_migrate()` +
`save/get_performance_records` in both `sqlite_store.py` and `redis_store.py` (PB1),
`api/services/performance_freshness.py` (PB8), `api/routers/performance.py` →
`POST /api/performance/ingest` (PB2/PB6), registered in `main.py`. Tests:
`tests/test_performance_model.py`, `tests/test_performance_ingest.py`.

Deviations from the spec above, made during implementation:

1. **`top_queries` and `site` (gtm_audit / site_search) are accepted but NOT yet
   persisted** in Phase 1 — they feed the Phase 2/3 derived reports (PB3/PB7/PB9),
   so their side tables are deferred to those phases. The ingest response reports
   them under a `deferred: [...]` list so nothing is silently dropped (P2). The
   spec's "separate table for top_queries" is therefore a Phase 2 item, not Phase 1.
2. **PB6 matches the bundle's `site_url` against the crawl JOB's `target_url`**
   (`is_same_domain`, which treats www as same-site) — *not* against the WordPress
   credentials domain. The WP `_validate_wp_domain_for_*` helpers are WP-specific;
   the job-domain match is the correct guard for a performance bundle. Mismatch →
   403 `DOMAIN_MISMATCH`, zero rows written (verified).
3. **`job_id` is a query param** on the endpoint (`?job_id=...`); the bundle body
   carries no job id (it's site-oriented). The endpoint ties the bundle to a crawl
   via that param + the `site_url`↔`target_url` domain check.
4. **Merge correctness (P8) is enforced in two places:** the router read-merges so a
   GA4-only bundle can't zero prior GSC (and vice-versa), and the sqlite `ON CONFLICT`
   COALESCE-merges GA4/index so the legacy GSC-only `/api/gsc/ingest` path can't wipe
   GA4. Both directions are regression-tested.
5. **Response adds `stale` (PB8), `deferred`, and `invalid_urls`** beyond the spec's
   `{ingested, sources, period, unmatched_urls}`.

**Review fixes (learning-qa pre-flight), all regression-tested:**

1. **One join key (P11, was HIGH).** Matched rows are stored under the **crawled
   page's** URL — the key the page-priority consumer (`crawl.py`) reads by — not the
   raw bundle URL. Storage, the matched/unmatched diff, and the downstream lookup now
   share one key, so a trailing-slash/`www`/scheme difference can't persist a row the
   consumer never finds. Unmatched bundle URLs are held out (reported in
   `unmatched_urls`), not stored under an orphan key. Test:
   `test_trailing_slash_bundle_url_stored_under_crawled_key`.
2. **Malformed URL is non-fatal (P2).** URLs are normalised **before** the save, so a
   scheme-less URL lands in `invalid_urls` instead of raising a 500 *after* other rows
   commit. Test: `test_malformed_bundle_url_is_skipped_not_fatal`.
3. **Honest freshness (PB8/P6).** A row that carries fields forward from an older
   bundle is stamped with `earlier(new, prior)` — the oldest contributing source's
   date — not optimistically the newest. Test:
   `test_carried_forward_row_reports_oldest_source_vintage`.
4. **`INVALID_SITE_URL` 400.** A bare-host / `sc-domain:` `site_url` (netloc == "")
   returns a clear 400, not a confusing 403. Test: `test_invalid_site_url_returns_400`.

**Independent review (post-implementation), fixes applied:**

- **F1 (MED-HIGH) — `www`/scheme join.** `normalise_url` folds neither `www.` nor
  http/https, so the earlier join only reconciled trailing-slash/case/params — the
  spec over-promised. Added `_match_key` (normalise + `_strip_www` + drop scheme),
  used for matching only (storage still under the crawled url). The "crawl
  example.org / GSC property www.example.org" config now joins. Test:
  `test_www_and_scheme_differences_still_join`.
- **F2 (MED) — Redis coverage.** The production store's GA4 merge path was untested.
  Added `tests/test_performance_redis.py` (round-trip, absent→None, GSC-only preserves
  GA4) against a field-merging fake.
- **F3 (LOW) — `earlier()` corruption edge** hardened to prefer the parseable side.
  Test: `test_pb8_earlier_picks_oldest_and_handles_unparseable`.
- **Gap — duplicate URL in one bundle** now merges to one row (records keyed by
  storage_key); `ingested` counts distinct rows. Test:
  `test_duplicate_bundle_urls_merge_to_one_row`.
- **Gap — `index_state` carry-forward** tested: `test_index_state_carried_forward_when_new_gsc_omits_it`.

**Adjacent — found, NOT fixed (F4, pre-existing).** The legacy `/api/gsc/ingest`
(`api/routers/gsc.py:283`) builds records keyed on the **raw GSC URL** and leaves
`source_generated_at=None`. It never *wipes* GA4 (its `None` GA4 is COALESCE-preserved),
but because it doesn't share `_match_key`/crawled-page keying, its rows can land under a
different key than the bundle + page-priority consumer use. Out of scope for this change;
flagged for a Phase 2 follow-up (unify `gsc.py` onto the same join-key + freshness stamp).

---

## Out of scope

- Building GSC/GA4/GTM OAuth inside TalkingToad (Option B) — parked with the identity model unless
  PB-A is decided otherwise.
- The **producer** side (how the sibling app assembles the bundle) — that's the other app's spec; this
  spec defines only the contract TalkingToad accepts and the consumption behaviour.
- AI Overview / AI-Mode click separation — GSC does not expose it via API today; do not promise it.
- Any write-back to Google.
