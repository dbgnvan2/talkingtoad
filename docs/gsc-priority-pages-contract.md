---
status: current
last_reviewed: 2026-08-14
---
# Contract: `priority_pages.json` — what TalkingToad reads (v1)

**Audience:** the sibling **GSC reporting app** (the producer) and TalkingToad (the consumer).
**This is the frozen hand-off contract.** TalkingToad's parser
(`api/services/gsc_priority.py::parse_priority_upload`) reads exactly the fields below. If the GSC
app changes a field name or shape, TT's parser must change with it — keep this doc and the parser
in lock-step (a save→re-parse round-trip test on a real sample guards drift, P19).

> **This is NOT the rich `PerformanceBundle`.** That larger contract
> (`docs/pending/2026-08-11_performance-bundle-producer-contract.md`: GA4 sessions,
> `conversions_by_event`, URL-Inspection `index_state`, GTM) is a **future** enhancement. v1 uses
> the flat `priority_pages.json` the GSC app **already emits** — no GSC-side code change is needed.

## Delivery — user upload, not a server push
TalkingToad is hosted (Railway/Vercel); it **cannot read** a file on the user's Mac. The GSC app
just **writes** `priority_pages.json` (it already does, to `~/Documents/GSC Reports/<period>/`).
The user then **attaches that file** on TalkingToad's scan-start screen; the browser reads it and
embeds the parsed object in the crawl request:

```
POST /api/crawl/start
{ "target_url": "https://livingsystems.ca", "gsc_priority": <the priority_pages.json object> }
```

The GSC app does **not** POST to TalkingToad — no TT URL, no shared secret, no push code.

## The shape (exactly as produced today)
```json
{
  "generated_for": "talkingtoad",
  "site": "livingsystems.ca",
  "source": "…/pages.csv",
  "count": 50,
  "pages": [
    {
      "url": "https://livingsystems.ca/",
      "path": "/",
      "clicks": 138,
      "impressions": 1494,
      "avg_position": 23.5,
      "top_queries": ["living systems counselling", "living systems"],
      "inquiries": 1
    }
  ]
}
```

## Fields TalkingToad reads

**Top level**
| Field | Required | TalkingToad's use |
|---|---|---|
| `generated_for` | recommended | If present it **must** equal `"talkingtoad"`, else the file is rejected (a different tool's file). Absent is tolerated. |
| `pages` | **yes** | The payload. Must be a non-empty array. |
| `site` | optional | Informational only — TT derives the domain from the page URLs, so an empty/bare-host `site` is fine. |
| `count` | optional | Informational (not validated against `len(pages)`). |
| `source` | ignored | — |

**Per page (`pages[]`)** — file order **is** priority order (highest first)
| Field | Required | Type | TalkingToad's use |
|---|---|---|---|
| `url` | **yes** | absolute `https://…` | Crawl-seed order (ii) **and** the ledger join key (i). Must be the **same registrable domain** as the scan; off-domain/blank rows are **held out and counted** ("used N of M"). |
| `clicks` | optional | int (default 0) | Ranking (i). |
| `impressions` | optional | int (default 0) | Ranking (i); **CTR is derived** = `clicks / impressions`. |
| `avg_position` | optional | float | Ranking (i) → `position`. |
| `inquiries` | optional | int **or null** | Conversion signal (i) → `ga4_conversions_mo`. **Null/absent stays "unknown"; a present `0` is a real measured zero** — never send `0` to mean "no data" (it would corrupt ranking). |
| `top_queries` | optional | list of **strings** | Striking-distance list (i). Plain query strings (not objects). |
| `path` | ignored | — | TT derives it. |

## Validation & rejection (what TT does with a bad file)
- **Wrong tool:** `generated_for` present and ≠ `"talkingtoad"` → **422 `INVALID_PRIORITY_FILE`**.
- **Wrong site:** no page matches the scan's domain → **422 `INVALID_PRIORITY_FILE`** ("is this the right site's file?").
- **Malformed:** not an object, or no `pages` array → **422 `INVALID_PRIORITY_FILE`**.
- **Partial:** off-domain / blank-`url` rows are dropped and the count is reported in the scan's
  `scope_notes` ("seeded N of M pages (K held out)"), never silently.
- **Over budget:** if the seed has ≥ `max_pages` in-domain URLs, TT warns that non-priority pages
  may not be crawled (the seed **orders** the crawl, it does not **restrict** it).

## What TT does with it
- **(ii) Crawl order:** the `url` list is crawled **first** (fronted in the frontier right after the
  homepage), subject to the same robots.txt / SSRF / scope / `max_pages` rules as any URL.
- **(i) Ranking:** after the crawl, each page's `clicks / impressions / avg_position / inquiries`
  is joined onto the crawled page and written to the Performance Ledger, so the **Page Priority**
  queue ranks by Search Console reality. Freshness is stamped from **upload time** (the file has no
  `generated_at`; add one if real staleness display is ever wanted).

## Producer checklist (GSC app)
- [x] Emit `pages[].url` as **absolute** `https://host/path`, same domain as the site.
- [x] Keep file order = priority order.
- [x] `generated_for: "talkingtoad"`.
- [ ] Send `inquiries: null` (or omit the field) when a page has **no** conversion data; use `0`
      **only** for a genuine measured zero. TalkingToad preserves a received `null`/absent as
      *unknown* (it does **not** rank the page as proven-zero, and shows a dash), but treats a
      received `0` as a measured zero that ranks/displays as zero. **F9 currently defaults missing
      conversions to `0`, which collapses this distinction — change it to emit `null` so a page with
      unknown conversions isn't mistaken for one measured at zero.**
- [ ] *(optional, future)* add `generated_at` (ISO-8601 UTC) for freshness display.

## Versioning
This is **v1** (flat priority list). The richer `PerformanceBundle` is a separate, additive path;
adopting it later does not break this one. Any change to the field names/shape above is a contract
change — update this doc **and** `parse_priority_upload` together.
