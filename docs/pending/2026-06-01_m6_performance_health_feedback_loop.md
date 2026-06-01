---
status: shipped
proposed: 2026-06-01
shipped: 2026-06-01
author: Architect (M6 cycle, TalkingToad session) + user strategy discussion
type: feature
source: PLAN-V3.0.md Milestone 6, reframed per 2026-06-01 GSC division-of-labour discussion
commits: M6.2 a03009b, M6.3 d5a965a, M6.1+M6.4 5ab994d
note: ALL of 6.1–6.4 are now SHIPPED. OAuth round-trip proven live vs livingsystems.ca.
  Compiler — describe the whole milestone as CURRENT behaviour.
---

# M6 — Performance-Health Feedback Loop (GSC Integration)

> **IMPLEMENTATION STATUS (2026-06-01):**
> - ✅ **6.2 Performance Ledger — SHIPPED** (`a03009b`): `PerformanceRecord` model, two
>   `CrawledPage` lifecycle date fields, store save/get with batch upsert keyed on
>   `(url, period)` across SQLite + Redis.
> - ✅ **6.3 Refresh Trigger — SHIPPED** (`d5a965a`): `refresh_trigger.evaluate_refresh(records,
>   health_score, *, today)` → `ReviewFlag{flagged, reasons}`; staleness (>180d), traffic
>   decay (>20% vs 3-mo avg), Vulnerable-Star, Hidden-Gem; deterministic `today`; 22 tests.
> - ⏸️ **6.1 Live GSC OAuth ingest + 6.4 GSCInsightsPanel — NOT SHIPPED, blocked on Google
>   OAuth credentials.** Local redirect URI: `http://localhost:8000/api/gsc/callback`.
>
> **Compiler note:** when this spec is folded into the functional specification, describe 6.2
> and 6.3 as CURRENT shipped behaviour and 6.1/6.4 as PLANNED (blocked on credentials) — do
> not present the OAuth path as implemented.

> **⛔ Blocked on credentials.** Unlike M3/M4/M5/M7, this milestone needs a Google Cloud
> OAuth app (client id/secret) and a one-time browser consent. Build only after the
> **Prerequisites** below are satisfied. The data-shaping/algorithm sub-specs (6.2, 6.3)
> CAN be built + tested with mocked GSC data ahead of real credentials; 6.1's live path
> cannot.

## Where this sits in the stack (the division of labour)

| Tool | Question it answers | Repo |
|---|---|---|
| **SERP-Discovery** (separate) | "What should I build?" — search intent, volume, difficulty | `serp-discovery` (parked — see `docs/PARKED-SERP-DISCOVERY.md`) |
| **TalkingToad** | "Is it built correctly?" — structure, extractability, GEO authority | this repo |
| **GSC (the bridge)** | "How does the world actually see what I built?" — measured performance | M6, here |

GSC is **not** keyword research and **not** a structural auditor. It is the **reality-check
layer** that closes the loop: it tells you which of TalkingToad's findings actually matter
(the pages that get traffic) and whether the GEO moat is working (high impressions + low
clicks on a question query → the page's Answerability/ExtractabilityScore is failing →
re-audit in TalkingToad).

## The core idea: the Authority Matrix
Correlate **GSC performance** with TalkingToad's per-page **HealthScore** to prioritise work:

| | High HealthScore | Low HealthScore |
|---|---|---|
| **High performance** | Healthy stars (maintain) | **Vulnerable Stars** — earn traffic but architecturally brittle → top of the structural-fix queue |
| **Low performance** | **Hidden Gems** — structurally perfect but not ranking → signal SERP-Discovery to re-check intent | Low priority |

Plus a **lifecycle** view over time: `created_at` → `last_technical_improvement_at` →
monthly GSC scores → automated "Review for Improvements" flag.

---

## Prerequisites (USER — must be done before 6.1 live path)
- [ ] Create a Google Cloud project + OAuth consent screen (External, scope
      `https://www.googleapis.com/auth/webmasters.readonly`).
- [ ] Create OAuth client credentials; set env vars: `GSC_OAUTH_CLIENT_ID`,
      `GSC_OAUTH_CLIENT_SECRET`, `GSC_OAUTH_REDIRECT_URI` (all OPTIONAL — when unset the
      whole GSC surface is invisible and TalkingToad behaves exactly as today).
- [ ] **ONE app-wide** client id/secret — NOT one per website. Each site owner connects
      their own Google account once (one token per account, covering all their GSC
      properties). Token encryption reuses the M2.3 Fernet pattern (`AI_CREDS_ENCRYPTION_KEY`)
      or a separate `GSC_ENCRYPTION_KEY` — decide before 6.1.
- [ ] **Multi-account caveat:** storing per-site-owner tokens at scale overlaps the parked
      Identity Model (`docs/TODO-MULTITENANT.md`). For a SINGLE site (one Google account,
      e.g. livingsystems.ca) this is fine and unblocked. For many client accounts, the
      token-ownership model needs the multi-tenant work first.

---

## 6.1 — GSC Data Ingest Service
- **New** `api/services/gsc_client.py`.
- **OAuth flow** (opt-in): `GET /api/gsc/connect` → redirect to Google (503 when env unset);
  `GET /api/gsc/callback?code=...` → exchange + store encrypted token; `POST /api/gsc/disconnect`.
- **Signature:** `async def fetch_page_performance(domain: str, *, days: int = 30) ->
  list[PagePerformanceMetric]` where `PagePerformanceMetric = {url, clicks, impressions,
  ctr, position}`.
- **Constraints:** GSC Search Analytics API; **exponential backoff** on 429/5xx; cache 12h.
  Filter by `searchAppearance` for AI-Overview when the API exposes it; else pull total Web
  and note the limitation in `extra`.
- **Auth:** the `/api/gsc/*` router requires `require_auth` (consistent with ai.py/geo.py).
- **SSRF:** the only outbound calls are to Google's API hosts — not user-supplied URLs.
  Tokens never logged or returned.
- **Evaluator:** mock the GSC API response for a URL; assert the client parses + returns the
  `PagePerformanceMetric`. Mock a 429 then 200; assert backoff retried and succeeded.

## 6.2 — The Performance Ledger
- **New** `api/models/performance.py` → `PerformanceRecord` (Pydantic):
  `url, created_at, last_technical_improvement_at, gsc_clicks_mo, gsc_impressions_mo,
  gsc_ctr_mo, gsc_avg_position_mo, period (YYYY-MM), recorded_at`.
- **New CrawledPage fields** (`api/models/page.py`): `page_created_at: str | None`,
  `last_technical_improvement_at: str | None` (set when a WP fix is applied / page is
  re-scanned cleaner).
- **Store:** add `save_performance_records(records)` / `get_performance_records(url|domain)`
  to the store interface (SQLite + Redis). **Batch upsert** keyed on `(url, period)` — adding
  a record for an existing `(url, period)` UPDATES, never duplicates.
- **Evaluator:** insert a `PerformanceRecord` for an existing `(url, period)` twice → one row,
  updated values (no duplicate).

## 6.3 — Automated Refresh Trigger ("Review for Improvements")
- **New** `api/services/refresh_trigger.py`.
- **Signature:** `evaluate_refresh(record: PerformanceRecord, health_score: int, *,
  today: date) -> ReviewFlag` where `ReviewFlag = {flagged: bool, reasons: list[str]}`.
  (Explicit `today` for determinism, per M4/M5.)
- **Triggers (any TRUE → flagged):**
  - **Staleness:** `(today - last_technical_improvement_at).days > 180` → reason "Staleness".
  - **Traffic decay:** `clicks_3mo_avg` vs `clicks_1mo` drop `> 20%` → reason "Traffic Decay".
  - *(Matrix, optional 6.3b):* high impressions + HealthScore < threshold → reason
    "Vulnerable Star"; structurally healthy + near-zero clicks → reason "Hidden Gem"
    (the latter is the hand-off signal to SERP-Discovery).
- **HealthScore source:** reuse the per-page score already derived from issue impact
  (`max(0, 100 - sum(page issue impacts))`, as M5 does), or the site `health_score` in the
  crawl summary — confirm which granularity at build time.
- **Evaluator:** 200-day-stale record → flagged, reason "Staleness". 25% click drop →
  flagged, reason "Traffic Decay". Fresh + stable → not flagged.

## 6.4 — Surfacing (opt-in, lazy-loaded)
- New `GSCInsightsPanel.jsx` (lazy via `React.lazy`), invisible when GSC env unset.
- Per-page GSC fields on the existing pages view; the Authority Matrix as a sortable view
  (Vulnerable Stars first). Reviewed flags shown as a "Review for Improvements" badge.
- **No GUI restructure** — new panel/badges only.

## Issue codes (optional, if surfaced as findings — all 3 registries)
- `GSC_HIGH_IMP_LOW_CTR` (**Established**) — >100 impressions, <1% CTR. Impact 5.
- `GSC_POSITION_DECAYING` — drop >5 places vs previous pull (needs ledger history).
- These are net-new codes → full registry + issueHelp (V4) + issue-codes.md parity if added.

## Tests
- 6.1 mocked-API parse + backoff (above). 6.2 upsert-no-duplicate. 6.3 staleness + decay
  evaluators. Contract tests for `/api/gsc/connect|callback|disconnect` (503 when unset,
  token stored, disconnect removes). **Pages endpoint includes nullable GSC fields.**
  End-to-end without GSC env vars → tool behaves exactly as today (the opt-in guarantee).

## Security check
- **SSRF:** No user-URL fetch; only Google API hosts. **Auth:** Yes (`/api/gsc/*` +
  `require_auth`). **WordPress:** No. **XSS:** No. **Secrets:** OAuth tokens encrypted at
  rest, never logged/returned.

## Documentation impact
`docs/api.md` (+GSC endpoints), `docs/security-model.md` (token threat model — new),
`docs/issue-codes.md` (regenerate IF GSC codes added). `docs/thresholds.md` READ-ONLY
(180-day / 20% / CTR constants live in code).

## Build order when unblocked
1. 6.2 + 6.3 first (mocked data — no credentials needed): ledger schema + refresh algorithm
   + evaluators. Fully orche-able.
2. 6.1 live OAuth path + 6.4 panel — only after the user supplies Google OAuth credentials.
