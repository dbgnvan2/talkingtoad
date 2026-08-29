# Producer spec: the Performance Bundle TalkingToad wants from the reporting app

**Date:** 2026-08-11
**Audience:** the sibling GSC + GA4 + GTM reporting app (the **producer**).
**Status:** proposal — defines the data contract; no TalkingToad code change is implied by
this document except where a field feeds a pending consumer phase (noted per-field).
**Pairs with:** [`2026-08-06_performance-bundle-ingestion.md`](2026-08-06_performance-bundle-ingestion.md)
(the consumer side, Phase 1 shipped). This spec is the mirror: what the producer must **emit**.

> **Framing.** Do not model the output on the current weekly CSV export. Model it on the
> JSON contract below. The CSVs were "make-do"; this spec is the target. Every field here is
> obtainable from the GSC Search Analytics API, the GSC URL Inspection API, the GA4 Data API,
> or the GTM API — the acquisition source is named for each field so the producer can implement
> it directly.

---

## 1. How TalkingToad consumes this (why the shape matters)

TalkingToad ranks a nonprofit's pages by **traffic × conversions × health**, flags
striking-distance and index problems, and reconciles what the crawl sees against what actually
earns. It does **not** do OAuth to Google — the producer owns acquisition; TalkingToad owns
consumption. The bundle is the entire interface.

Each field below is tagged with the TalkingToad feature it powers:

| Tag | Feature | Consumer status |
|---|---|---|
| **RANK** | Page Priority queue (traffic × health) | shipped |
| **CONV** | Conversion-weighted priority (donations/forms float up) — PB4 | pending; **this is the highest-value gap** |
| **STRIKE** | Striking-distance → AI title/meta rewriter — PB3 | pending |
| **INDEX** | Index-status reconciliation ("Google found it, isn't indexing it") — PB5 | pending |
| **COVER** | Coverage / cross-signal diff (uncrawled-earning, zero-traffic, tag-missing-but-active) — PB7 | pending |
| **GTM** | GTM container health surface — PB9 | pending |
| **FRESH** | Staleness display — PB8 | shipped |

Emit the **full** payload now. TalkingToad already accepts the whole contract (Phase 1 persists
the core; the rest is accepted and lights up as consumer phases land). Producing everything now
means no producer change when those phases ship.

---

## 2. Transport

- **Endpoint:** `POST {TALKINGTOAD_BASE}/api/performance/ingest?job_id={JOB_ID}`
- **Auth:** `Authorization: Bearer {AUTH_TOKEN}` (the TalkingToad `AUTH_TOKEN`).
- **Body:** one `PerformanceBundle` JSON document (§3), `Content-Type: application/json`.
- **Domain guard:** `bundle.site_url`'s registrable domain **must** match the target job's
  crawl domain (www-insensitive) or ingest returns **403 `DOMAIN_MISMATCH`** and writes nothing.
- **One bundle = one site + one period.** Send separate bundles per period.
- **Response** (already implemented): `{ingested, sources, period, unmatched_urls, invalid_urls,
  stale, deferred}`. The producer should **log `unmatched_urls`** — those are bundle URLs that
  matched no crawled page (usually a URL-keying problem, see §7, or a genuine uncrawled-earning
  page for COVER).

---

## 3. Envelope

```jsonc
{
  "bundle_version": 1,
  "site_url": "https://livingsystems.ca/",   // registrable domain must match the job (§2)
  "generated_at": "2026-08-11T09:00:00Z",     // ISO-8601 UTC; drives FRESH staleness
  "granularity": "month",                      // "month" | "week"  (see §8)
  "period": "2026-07",                          // "YYYY-MM" for month, "YYYY-Www" for week
  "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
  "prev_date_range": {"start": "2026-06-01", "end": "2026-06-30"}, // optional; enables deltas
  "sources": ["gsc", "gsc_inspection", "ga4", "gtm"], // which sub-sources are populated below
  "producer": {"name": "gsc-reporter", "version": "2.3.0"},        // optional provenance
  "coverage": {                                 // optional but STRONGLY wanted (P2/P9 honesty)
    "gsc_pages_total": 179,
    "url_inspection_pages_requested": 179,
    "url_inspection_pages_returned": 150,       // if you couldn't inspect all (rate limit), say so
    "url_inspection_capped": true,
    "ga4_property_id": "properties/123456789",
    "gsc_property": "sc-domain:livingsystems.ca",
    "timezone": "America/Vancouver",
    "currency": "CAD"
  },
  "pages": [ /* §4 */ ],
  "site":  { /* §6 */ }
}
```

**Envelope rules**
- `bundle_version` is `1`. Unknown version → 400.
- `sources[]` lists only sub-sources actually populated. A field from an unlisted source must be
  **absent/null**, never `0` (§5, the null-vs-zero rule — load-bearing).
- `coverage` is how the producer stays honest about what it *couldn't* get (rate-limited URL
  inspection, sampled GA4). Never let a partial pull look complete.

---

## 4. Per-page object (`pages[]`)

Include **every URL you have any GSC or GA4 data for** — including URLs TalkingToad may not have
crawled (that's the COVER signal; don't pre-filter to crawled pages). One object per page.

```jsonc
{
  "url": "https://livingsystems.ca/counselling/",   // absolute, canonical; see §7 keying rules

  "gsc": {                                            // source: GSC Search Analytics API — RANK/STRIKE
    "clicks": 63, "impressions": 2210, "ctr": 0.0285, "position": 8.4,
    "prev": {"clicks": 51, "impressions": 2040, "ctr": 0.025, "position": 9.1}, // optional; trend
    "top_queries": [                                  // STRIKE — dimensions=["page","query"]
      {"query": "family counselling vancouver", "clicks": 22, "impressions": 480,
       "ctr": 0.0458, "position": 6.1},
      {"query": "bowen theory therapist", "clicks": 9, "impressions": 210,
       "ctr": 0.0429, "position": 7.8}
    ]                                                 // cap top ~25 by clicks; report the cap in coverage
  },

  "inspection": {                                     // source: GSC URL Inspection API — INDEX
    "index_state": "indexed",                         // controlled vocab, §4.1
    "verdict": "PASS",                                // PASS | NEUTRAL | FAIL | PARTIAL (optional)
    "google_canonical": "https://livingsystems.ca/counselling/",
    "user_canonical":   "https://livingsystems.ca/counselling/",
    "last_crawl_time": "2026-07-28T14:03:00Z",
    "robots_txt_state": "ALLOWED",                    // optional
    "page_fetch_state": "SUCCESSFUL"                  // optional
  },

  "ga4": {                                            // source: GA4 Data API — RANK/CONV/COVER
    "sessions": 210, "engaged_sessions": 150, "engagement_rate": 0.71,
    "active_users": 138, "screen_page_views": 260,
    "avg_engagement_time_sec": 74.0,
    "conversions": 6,                                 // CONV — total key events on this page
    "conversions_by_event": {                         // CONV — the nonprofit gold; §4.2
      "contact_form_submit": 4, "donate": 1, "newsletter_signup": 1
    },
    "source_breakdown": {                             // COVER + GEO; sessions by channel, §4.3
      "organic_search": 120, "direct": 55, "referral": 18,
      "organic_social": 8, "ai_referral": 9, "paid": 0, "email": 0
    }
  }
}
```

Any sub-block (`gsc` / `inspection` / `ga4`) is **omitted entirely** if that source wasn't pulled
for this URL. Within a block, an individual metric is `null` if unmeasured, `0` only if a real zero.

### 4.1 `index_state` controlled vocabulary (INDEX)

Map the URL Inspection `coverageState` string to exactly one token:

| Token | Maps from `coverageState` (examples) |
|---|---|
| `indexed` | "Submitted and indexed", "Indexed, not submitted in sitemap" |
| `crawled_not_indexed` | "Crawled - currently not indexed" |
| `discovered_not_indexed` | "Discovered - currently not indexed" |
| `excluded_noindex` | "Excluded by 'noindex' tag" |
| `excluded_canonical` | "Alternate page with proper canonical tag", "Duplicate, Google chose different canonical than user", "Duplicate without user-selected canonical" |
| `blocked_robots` | "Blocked by robots.txt" |
| `not_found` | "Not found (404)", "Soft 404" |
| `not_in_gsc` | URL unknown to the property / inspection returned no data |
| `unknown` | any state not above, or inspection not run for this URL |

Keep `verdict`, `google_canonical`, `user_canonical` too: a `google_canonical` ≠ `user_canonical`
is a high-value duplicate/canonical signal TalkingToad already cares about.

### 4.2 `conversions_by_event` — the highest-value addition (CONV)

This is the single thing the current CSV export cannot give and TalkingToad most needs: **key
events (GA4 conversions) attributed to the page**, broken down by event.

- **Source:** GA4 Data API `runReport`, dimensions `["pagePath"]` (or `landingPagePlusQueryString`
  for landing attribution — pick one and state it in `coverage`), plus `["eventName"]`; metric
  `keyEvents` (a.k.a. `conversions`). Filter `eventName` to the property's key-event set.
- **Labels:** map raw GA4 event names to stable semantic keys via a small producer-side config, so
  TalkingToad sees `donate` / `contact_form_submit` / `newsletter_signup` / `file_download` rather
  than whatever the GTM tag happened to be named. Include the raw event name in a `raw` sibling map
  if convenient, but the semantic keys are what CONV ranks on.
- **`conversions`** (the block total) must equal the sum of `conversions_by_event` for that page.
- Pages with zero key events: send `"conversions": 0` **only** if GA4 was queried for this page
  (a real measured zero — that's a valid "content that earns traffic but converts nothing" signal).
  If GA4 wasn't pulled for the page, omit the `ga4` block.

### 4.3 `source_breakdown` — sessions by channel, per page (COVER, GEO)

- **Source:** GA4 `runReport`, dimensions `["pagePath","sessionDefaultChannelGroup"]` (or
  `sessionSourceMedium`), metric `sessions`.
- **`ai_referral` is high-value and must be computed, not assumed.** GA4's default channel grouping
  does not reliably isolate LLM referrers; classify a session as `ai_referral` when its
  `sessionSource` host matches a maintained allowlist. Seed list (extend as engines appear):
  `chatgpt.com`, `chat.openai.com`, `perplexity.ai`, `gemini.google.com`, `bard.google.com`,
  `copilot.microsoft.com`, `bing.com/chat`, `claude.ai`, `you.com`, `poe.com`, `phind.com`.
- Keys are session counts per channel; use the fixed key set in the example (`organic_search`,
  `direct`, `referral`, `organic_social`, `ai_referral`, `paid`, `email`, plus `other`). Sum need
  not equal `sessions` exactly (attribution rounding) — that's fine.

---

## 5. The null-vs-zero rule (load-bearing — P2)

> **Absence ≠ zero.** A missing measurement is `null` or an omitted field. `0` means "we queried
> and it was genuinely zero."

TalkingToad distinguishes "no GA4 source" from "zero sessions" and will corrupt rankings if the
producer sends `0` for unqueried data. Concretely:
- No GA4 pull for a page → omit the whole `ga4` block (don't send zeros).
- GA4 pulled, page had no conversions → `"conversions": 0` is correct and useful.
- URL inspection not run for a page (rate-limited out) → omit `inspection` or set
  `index_state: "unknown"`; **never** guess `indexed`.

---

## 6. Site-level object (`site{}`)

```jsonc
"site": {
  "conversions_total": 41,                             // GA4 key events, whole site, the period
  "conversions_by_event": {"contact_form_submit": 22, "donate": 8, "newsletter_signup": 6,
                           "file_download": 5},
  "source_breakdown": {"organic_search": 100, "direct": 152, "referral": 16,
                       "organic_social": 14, "ai_referral": 9, "paid": 0, "email": 0},
  "ga4_site_search_terms": [{"term": "sliding scale", "count": 22},
                            {"term": "fees", "count": 9}],   // GA4 view_search_results / search term
  "gtm_audit": {                                       // GTM API v2 live container version — GTM/PB9
    "container_id": "GTM-XXXXXXX",
    "ga4_config_present": true,                         // a GA4 config/"Google tag" tag exists & unpaused
    "consent_mode_present": true,                       // consent initialization detected
    "paused_tags": ["Old UA - Universal Analytics"],   // tag.paused == true
    "legacy_ua_tags": ["Old UA - Universal Analytics"], // UA tags still present (should be 0)
    "tags_total": 14,
    "broken_triggers": [                               // tags whose firing trigger / referenced var is missing
      {"tag": "Donate Thankyou", "reason": "firing trigger 12 not found"}
    ]
  }
}
```

- **`gtm_audit`** — source: Tag Manager API v2, read the **live** container version's `tag[]`,
  `trigger[]`, `variable[]`. `ga4_config_present` = any GA4 config tag (`gaawc` / "Google tag"
  `googtag`) that is not paused. `broken_triggers` = tags referencing a `firingTriggerId` or
  variable that doesn't exist in the version. Read-only; TalkingToad never calls GTM itself.
- **`ga4_site_search_terms`** — source: GA4 search-term dimension (from `view_search_results`),
  feeds a future content-gap surface; low urgency but cheap to include.

---

## 7. URL keying rules (so rows actually join — P11)

TalkingToad joins bundle URLs to crawled pages after normalising (lowercases host, folds `www.`,
folds http/https, strips trailing slash, drops tracking params). The producer must therefore emit
**resolvable absolute URLs**:

- **Absolute, with scheme and host** — `https://livingsystems.ca/counselling/`. Never a bare path
  (`/counselling/`) and never `sc-domain:` / hostname-only forms. GA4 gives you `pagePath`; prepend
  the property's origin (`hostName` dimension, or the known site origin) to form the absolute URL.
- **Drop GA4 junk keys** — `(not set)`, `(other)`, empty path rows: exclude them (or roll into a
  single `site`-level figure), never emit as a page.
- Prefer `https`, lowercased host. Keep the path's real trailing slash as Google reports it —
  TalkingToad normalises either way, but be consistent.
- Query strings: strip GA4/GSC tracking params; keep semantically-meaningful ones only if they
  denote distinct pages. When in doubt, send the canonical (path-only) URL.

---

## 8. Period granularity (one open decision — recommendation)

The TalkingToad ledger currently keys **monthly** rows (`period: "YYYY-MM"`), which is what the
shipped ingest expects.

- **Recommended:** emit **monthly** bundles keyed `YYYY-MM` (aligns with the ledger's trend rows;
  no consumer change). Run the pull after each month closes with `dataState=final` for GSC.
- **Optional weekly snapshot:** if you also want a rolling "latest 7/28 days" view, send
  `granularity: "week"`, `period: "YYYY-Www"`. **This needs a small consumer change** (the ledger
  must accept a weekly period key) — flag it and we'll scope it separately; don't block the monthly
  path on it.
- Always send `date_range` (and `prev_date_range` when you can) so TalkingToad shows an exact
  window and can compute deltas without inferring them.

---

## 9. Priority tiers — build in this order

**Tier 1 — must-have (unlocks the ranking we actually want):**
1. `pages[].ga4.conversions` + `conversions_by_event` (CONV) — **the top gap**.
2. `pages[].gsc` clicks/impressions/ctr/position (RANK) — you already have this; keep it, but as
   absolute-URL-keyed JSON per §7.
3. `pages[].inspection.index_state` (INDEX) — new; URL Inspection API.
4. Correct null-vs-zero discipline (§5) and URL keying (§7) — cheap, and everything depends on it.

**Tier 2 — high-value derived signals:**
5. `pages[].gsc.top_queries[]` (STRIKE) — enables the AI rewriter to target the near-miss query.
6. `pages[].ga4.source_breakdown` incl. computed `ai_referral` (COVER, GEO).
7. Include **uncrawled-but-earning** URLs in `pages[]` (COVER) — don't filter to crawled pages.

**Tier 3 — nice-to-have:**
8. `site.gtm_audit` (GTM/PB9), `site.ga4_site_search_terms`, `prev`/`prev_date_range` deltas,
   richer inspection fields (`verdict`, canonical pair).

---

## 10. Worked example (abbreviated, livingsystems.ca)

```jsonc
{
  "bundle_version": 1,
  "site_url": "https://livingsystems.ca/",
  "generated_at": "2026-08-11T09:00:00Z",
  "granularity": "month",
  "period": "2026-07",
  "date_range": {"start": "2026-07-01", "end": "2026-07-31"},
  "sources": ["gsc", "gsc_inspection", "ga4", "gtm"],
  "coverage": {"gsc_pages_total": 179, "url_inspection_pages_returned": 179,
               "ga4_property_id": "properties/123456789",
               "gsc_property": "sc-domain:livingsystems.ca", "timezone": "America/Vancouver"},
  "pages": [
    {
      "url": "https://livingsystems.ca/emotional-pain-and-suffering/",
      "gsc": {"clicks": 11, "impressions": 5133, "ctr": 0.0021, "position": 8.61,
              "top_queries": [{"query": "emotional pain", "clicks": 6, "impressions": 3100,
                               "ctr": 0.0019, "position": 8.2}]},
      "inspection": {"index_state": "indexed", "verdict": "PASS",
                     "google_canonical": "https://livingsystems.ca/emotional-pain-and-suffering/",
                     "user_canonical": "https://livingsystems.ca/emotional-pain-and-suffering/"},
      "ga4": {"sessions": 34, "engaged_sessions": 10, "engagement_rate": 0.2941,
              "avg_engagement_time_sec": 189.1, "conversions": 0, "conversions_by_event": {},
              "source_breakdown": {"organic_search": 20, "direct": 8, "ai_referral": 2, "referral": 4}}
    },
    {
      "url": "https://livingsystems.ca/contact_us/",
      "gsc": {"clicks": 2, "impressions": 60, "ctr": 0.033, "position": 12.0, "top_queries": []},
      "inspection": {"index_state": "indexed", "verdict": "PASS"},
      "ga4": {"sessions": 30, "engaged_sessions": 18, "engagement_rate": 0.60,
              "conversions": 2, "conversions_by_event": {"contact_form_submit": 2},
              "source_breakdown": {"organic_search": 12, "direct": 15, "referral": 3}}
    }
  ],
  "site": {
    "conversions_total": 41,
    "conversions_by_event": {"contact_form_submit": 22, "donate": 8, "newsletter_signup": 6, "file_download": 5},
    "source_breakdown": {"organic_search": 100, "direct": 152, "referral": 16,
                         "organic_social": 14, "ai_referral": 9},
    "ga4_site_search_terms": [{"term": "sliding scale", "count": 22}],
    "gtm_audit": {"container_id": "GTM-XXXXXXX", "ga4_config_present": true,
                  "consent_mode_present": true, "paused_tags": [], "legacy_ua_tags": [],
                  "tags_total": 12, "broken_triggers": []}
  }
}
```

---

## 11. Producer acceptance checklist

- [ ] One bundle per site per period; `site_url` registrable domain = target crawl domain.
- [ ] All page `url`s are absolute `https://host/path` (§7); no bare paths, no `(not set)`, no `sc-domain:`.
- [ ] `pages[]` includes uncrawled-but-earning URLs (not filtered to crawled pages).
- [ ] Per-page `conversions_by_event` present wherever GA4 was pulled; block total = sum of events.
- [ ] `ai_referral` computed from a source-host allowlist, not GA4's default grouping.
- [ ] `index_state` mapped to the controlled vocab (§4.1); un-inspected pages are `unknown`/omitted, never guessed.
- [ ] Null-vs-zero discipline honoured everywhere (§5): unqueried → absent/null; measured zero → `0`.
- [ ] `generated_at` (UTC) and `date_range` always present; `coverage` reports any cap/sampling.
- [ ] `sources[]` lists only populated sub-sources.
- [ ] Posts to `/api/performance/ingest?job_id=…` with bearer auth; logs `unmatched_urls` from the response.

---

## Out of scope for the producer
- No write-back to Google. Read-only acquisition.
- No AI-Overview / AI-Mode click isolation (GSC doesn't expose it via API today) — don't fabricate it;
  `ai_referral` above is GA4 *referral traffic from AI apps*, a different, real signal.
- TalkingToad's consumer phases (PB3/PB4/PB5/PB7/PB9) are separate work; the producer only needs to
  emit the fields — they activate as those phases ship.
