# Plan: GSC → TalkingToad performance hand-off — USER UPLOAD of priority_pages.json

**Date:** 2026-08-14 (rev 2 — pivoted to user upload; contract reconciled to the real file)
**Status:** APPROVED 2026-08-14 (all recommendations accepted) — building. Consumer work is all
TalkingToad; this doc serves as the implementation spec (contract §3 + acceptance criteria §6).
**Decisions locked with user:** Architecture is **user-mediated upload** (the browser reads the
file and sends bytes; the hosted server never touches the user's disk). Integration is **optional**
(TT runs fully without it — no GSC app, no upload, normal scan). Wants **both** (i) metrics for
ranking and (ii) a priority-page list to seed the crawl.
**Decisions (accepted):** D-N1 = **order** the frontier · D-N2 = **only `priority_pages.json`**
for v1 (defer rich bundle) · D-N3 = **multipart field on `/start`** · D-N4 = **freshness from
upload time** · D-N5 = **optional attach control on the scan-start screen**.

---

## 1. Why upload, not push (resolved)
- TT is hosted (Railway/Vercel); it **cannot read** `~/Documents/GSC Reports/.../priority_pages.json`
  off the user's Mac. A "download" is the server generating bytes and streaming them to the browser;
  the reverse — an **upload** — is the browser reading a user-picked file and sending the bytes. The
  server touches only its own memory in both directions.
- Upload makes the feature **optional & universal** (no file → normal scan), **decoupled** (the GSC
  app needs zero knowledge of TT — no URL, no secret, no push code), and it fixes the **timing**
  (the file is attached when the user starts a scan, so it's available before the crawl).

## 2. Key finding — ONE file serves both flows
The real `priority_pages.json` already contains, per page: `url`, `clicks`, `impressions`,
`avg_position`, `inquiries`, `top_queries`. That is enough for **both**:
- **(ii) crawl seed** — the ranked `pages[].url` list → crawl those first.
- **(i) ranking** — `clicks/impressions/avg_position/inquiries` → the Performance Ledger → Page
  Priority (ctr derived = clicks/impressions).

So **v1 needs NO new GSC code and NO rich `PerformanceBundle`.** TT reads the file GSC already
emits. The richer bundle (GA4 sessions, `conversions_by_event`, `index_state`, GTM) is a **later,
optional** enhancement — out of scope here.

## 3. The contract — what TT reads from `priority_pages.json` (reconciled to the real file)

**Top level**
| Field | Type | TT use | Notes / gap |
|---|---|---|---|
| `generated_for` | str | sanity check (== "talkingtoad") | reject with a clear error if absent/other |
| `site` | str (**bare host**, e.g. `livingsystems.ca`) | domain guard | **GAP:** it's a bare host, not a full origin. TT derives the **registrable domain** from `site` *and* from `pages[].url` hosts, and validates it against the scan's target domain (mismatch → reject, don't seed) |
| `count` | int | sanity check vs `len(pages)` | |
| `pages[]` | list | the payload | |

**Per page (`pages[]`)**
| Field | Type | TT use | Notes / gap |
|---|---|---|---|
| `url` | str (absolute https) | (ii) seed order **and** (i) ledger key | required; skip a row with no/off-domain url (announce count) |
| `clicks` | int | (i) ranking | |
| `impressions` | int | (i) ranking; **ctr = clicks/impressions** (guard ÷0) | ctr is derived, not supplied |
| `avg_position` | float | (i) ranking (→ `position`) | name maps to TT's `position` |
| `inquiries` | int | (i) conversion signal (→ `conversions`) | GSC's inquiry count; a real measured 0 is meaningful |
| `top_queries` | **list[str]** | (i) striking-distance list | **GAP:** plain strings, not `{query,clicks,…}` objects like the rich bundle — TT stores them as query strings only |
| `path` | str | ignored (derivable) | |

**Absent (TT tolerates; features stay dark in v1):** `ga4` sessions, `conversions_by_event`,
`source_breakdown`, `inspection.index_state`, `gtm_audit`, and any **timestamp/period**. Because
there's no `generated_at`, TT stamps **freshness from the upload time** (a later GSC change could add
`period`/`generated_at` if real staleness display is wanted).

## 4. Target flow
```
User runs GSC app (scheduled/GUI) → writes ~/Documents/GSC Reports/<period>/priority_pages.json   [already works]
User starts a scan in TT → optionally ATTACHES that file (browser reads it, POSTs bytes)
  TT stores the parsed seed with the job
  (ii) crawl fronts the seed URLs in the frontier (ordered), then crawls normally
  (i)  after the crawl, TT joins the seed's per-page metrics to crawled pages → ledger → Page Priority
No file attached → normal scan (unchanged).
```

## 5. Work items — TalkingToad only (GSC app unchanged for v1)

- **U1 — Upload endpoint + parse (NEW).** Accept the file with the scan. Either a multipart field on
  `POST /api/crawl/start` (`gsc_priority_file`) or a companion `POST /api/crawl/{job_id}/priority-upload`
  called immediately after start (see D-N3). Parse the §3 contract, domain-guard, hold out
  off-domain/blank URLs (announce "used N of M"), persist the parsed list on the job. Contract test
  first (valid file, wrong-domain reject, missing file = no-op, malformed = 400).
- **U2 — Crawl seeding (NEW, ii).** Pass the seed URLs to the engine as a **priority ordering** of
  the frontier (front them; then normal crawl). Advisory, capped, announced; unknown/404/off-domain
  seed URLs are skipped, never fatal. Dirty-state test: seed present vs absent.
- **U3 — Ledger join for ranking (i).** After the crawl, map each seed page → `PerformanceRecord`
  (`clicks, impressions, ctr=derived, position=avg_position, conversions=inquiries`, `top_queries`)
  and write to the existing Performance Ledger via the existing `perf_join` matching (same machinery
  the current `/api/performance/ingest` uses, just sourced from the uploaded file instead of a POST).
  Page Priority then reflects it. Test: uploaded metrics reach the ledger and change ranking.
- **U4 — Frontend (NEW; GUI change → needs your OK on placement).** An **optional** file input on the
  scan-start screen: "Attach GSC priority file (optional)". Clear empty/error states; shows
  "seeded N of M pages, metrics for K" after the run. No file → nothing changes.

## 6. Acceptance criteria → tests
| ID | Criterion | Test |
|---|---|---|
| U1 | Parses the real `priority_pages.json` shape; wrong-domain → reject; no file → no-op; malformed → 400 | `tests/test_priority_upload.py` (fixture = a real trimmed file) |
| U1 | "used N of M" announced when rows are held out (off-domain/blank url) | same |
| U2 | A scan with a seed fronts the seed URLs; without a seed, crawls normally (dirty-state) | `tests/test_crawl_priority_seed.py` |
| U2 | Seed is advisory: a 404/off-domain seed URL is skipped, not fatal | same |
| U3 | Uploaded metrics land in the ledger (ctr derived, position=avg_position, conversions=inquiries) and move Page Priority | `tests/test_priority_upload_ledger.py` |
| U4 | Scan screen renders the optional input; empty/error states; post-run summary | `frontend`: `…/__tests__/PriorityUpload.test.jsx` |

## 7. Reconciliation with the GSC agent's report (c6c773e)
- ✅ The producer file is real, correct, and the empty-`site` fix (`c6c773e`) is **useful to us** —
  though TT will derive the domain from the page URLs regardless, so it's robust to a bare/empty site.
- ⚠️ The agent's conclusion "point TalkingToad at the file" does **not** work (hosted server, no
  disk access) — this plan's **upload** is how the file actually reaches TT.
- ⚠️ `priority_pages.json` is **not** the rich `PerformanceBundle`; that's fine — v1 reads the flat
  file. No GSC change is required for v1.
- 🔒 **Contract freeze:** if the GSC app ever changes `priority_pages.json`'s field names/shape, U1's
  parser breaks. The §3 table is the shared contract; a round-trip test in TT uses a **real** sample
  file so drift is caught (P19).

## 8. Open decisions (confirm before build)
- **D-N1 (ii semantics):** seed = **order** the frontier (recommended) or **restrict** the crawl to
  the seed + linked pages?
- **D-N2 (single file):** confirm v1 uses **only** `priority_pages.json` for both (i)+(ii)
  (recommended), deferring the rich bundle / GA4 / index-status / GTM.
- **D-N3 (attach mechanism):** file as a **multipart field on `/start`** (recommended) or a separate
  `/{job_id}/priority-upload` right after start?
- **D-N4 (freshness):** v1 stamps freshness from **upload time** (recommended), or ask the GSC agent
  to add `generated_at`/`period` to the file now?
- **D-N5 (GUI placement, U4):** an optional attach control on the **scan-start screen** — approve, or
  a different spot?

## 9. Sequencing
Approve plan + D-N1…N5 → one TT micro-spec in `docs/pending/` (contract-test-first) → build
U1→U2→U3→U4 → csdp → end-to-end verify with the real `monthly-2026-08-10/priority_pages.json` on
livingsystems.ca. **GSC app: no code needed for v1** (keep emitting the file it already emits).

## 10. Explicitly NOT in v1
No server-to-server push. No GSC-side code. No rich `PerformanceBundle` / GA4 / URL-Inspection / GTM.
No new Google OAuth in TT. TT remains fully functional with no upload.
