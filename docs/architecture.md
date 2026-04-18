# Architecture

## System Overview

```
[Browser Frontend]  →  [API Layer]  →  [Crawler Engine]  →  [Results Store]
     React/Vite          FastAPI           Python/             SQLite (dev) /
     Vercel              Vercel Edge       httpx +             Upstash Redis (prod)
                         Functions         BeautifulSoup4
                                           + lxml
```

---

## Key Design Decisions

### Async crawl jobs

Crawl jobs run asynchronously. The user submits a URL and receives a `job_id`. The frontend polls `/api/crawl/{job_id}/status` every 2 seconds (backing off to 5 seconds after 60 seconds). This avoids Vercel serverless timeout constraints.

### Data store abstraction

All job/result persistence goes through `api/services/job_store.py`. SQLite is used locally; Upstash Redis in production. The `DATABASE_URL` env var switches between them transparently. The `fixes` table is stored in the same abstraction.

### URL normalisation

All URLs are normalised before deduplication (spec §2.7):
- Strip trailing slashes (root `/` is kept)
- Lowercase scheme and host
- Remove fragment identifiers (`#section`)
- Strip UTM and tracking parameters (`utm_source`, `utm_medium`, `fbclid`, `gclid`, `ref`, `sid`, `session_id`)
- Preserve all other query parameters
- Cap query-string variants per path at 50

### External link checking

External links are status-checked only (HEAD, fall back to GET on 405) — not crawled further. Caps: 50/page, 500/job. Social media domains that block bots are noted as `EXTERNAL_LINK_SKIPPED` rather than falsely flagged as broken.

### WordPress noise path skipping

WordPress sites generate large volumes of auto-generated URLs that have no SEO value:
- Author archives (`/author/...`)
- Category and tag archives (`/category/...`, `/tag/...`)
- Date archives (`/2024/`, `/2024/03/`, `/2024/03/15/`)
- Paginated archives (`/page/2/`)
- Feed URLs (`/feed/`, `?feed=rss2`)
- Search result pages (`?s=query`)
- Numeric author queries (`?author=1`)

These are detected by `normaliser.is_wp_noise_path()` and skipped during the crawl when `skip_wp_archives=True` (the default). This keeps results focused on real content pages.

### Image Intelligence: 3-Level Data Architecture (v1.9)

**CRITICAL ARCHITECTURAL PRINCIPLE - DO NOT VIOLATE**

Image analysis uses a 3-level data architecture that balances speed, completeness, and site compatibility:

#### Level 1: Scan (Automatic during crawl)
- **Data sources:** HTML parsing + HTTP HEAD requests only
- **Gets:** Alt text, title (from `<img>` tags), file size, content-type
- **Does NOT call WordPress API** - would be too slow (100 images = 100+ API requests)
- **Works on ANY site** (not just WordPress)
- **Fast:** Already has HTML, HEAD requests only fetch headers
- **Issues detected:** IMG_ALT_MISSING, IMG_ALT_TOO_SHORT, IMG_ALT_TOO_LONG, IMG_ALT_GENERIC, IMG_OVERSIZED (from file size)
- **Data source:** `html_only`

#### Level 2: Fetch (Manual button, per-image or batch)
- **Data sources:** WordPress REST API (slug-based queries) + Image file download
- **Gets:** Caption, description, WP alt text (may differ from HTML), intrinsic dimensions, exact file size, load time, content hash
- **Uses slug-based WP API queries** (correct approach, see wp_fixer.py:1602)
- **WordPress-specific:** Only works on WordPress sites
- **Slower:** Requires API call + image download per image
- **Use cases:**
  - Get full WordPress metadata (caption, description)
  - Verify updates after pushing changes to WordPress
  - Re-analyze and update scores with complete data
- **Issues detected:** All image issues with accurate scoring
- **Data source:** `full_fetch`

#### Level 3: AI Analysis (Manual button, per-image or batch)
- **Data sources:** Vision model analysis (Gemini/OpenAI)
- **Gets:** AI-generated image description, suggested alt text, semantic quality scores
- **Optional:** GEO-optimized analysis with entity-rich metadata
- **Use cases:**
  - Generate alt text suggestions
  - Analyze image content for semantic accuracy
  - Create GEO-optimized metadata (entities, location anchors)
- **Data source:** AI analysis metadata stored separately

**Why this architecture:**
1. **Scan speed:** Can't afford WP API calls during crawl (would 10x crawl time)
2. **Universal compatibility:** HTML scan works on any site, WP API only works on WordPress
3. **Data freshness:** Fetch verifies current WordPress state after updates
4. **User control:** User decides when to invest time in fetching complete data

### WordPress Fix Manager

The Fix Manager connects directly to a WordPress site and applies SEO fixes:

1. **Cookie-based authentication** — TalkingToad POSTs to a custom login URL, stores the session cookie, then fetches the REST API nonce from `wp-admin`. Application Passwords are not required.
2. **Nonce extraction** — Parses the `wp.apiFetch.createNonceMiddleware("...")` call from the `wp-admin` page HTML. This is the correct REST nonce (not Wordfence or heartbeat nonces which also appear on the page).
3. **SEO plugin auto-detection** — Checks the WP plugins list for Yoast SEO or Rank Math, then uses the correct meta key names for each:
   - Yoast: `_yoast_wpseo_title`, `_yoast_wpseo_metadesc`
   - Rank Math: `rank_math_title`, `rank_math_description`
4. **Fix deduplication** — Multiple issue codes can point to the same fix field (e.g., `TITLE_MISSING`, `TITLE_TOO_SHORT`, and `TITLE_TOO_LONG` all fix `seo_title`). Deduplication is by `(page_url, field)` tuple.
5. **Stop-on-failure apply** — The apply step applies fixes sequentially and stops on the first failure, marking subsequent fixes as pending. The user corrects the error and retries.

### Banner H1 suppression

When `suppress_banner_h1` is enabled (default: `true`), the issue checker detects and removes theme-injected banner H1 headings before running H1 checks. Detection uses two signals:

1. **Position:** Only the first H1 in the DOM is a candidate (themes inject banners before content).
2. **CSS class:** Common banner classes (`entry-title`, `page-title`, `page-header`, `banner-title`, `hero-title`, `archive-title`).

The first H1 is suppressed if it mismatches the page title OR carries a banner CSS class. Suppression is only applied when there are 2+ H1s, so it never removes the only heading on the page.

### `discovered_from` tracking for internal broken links

The crawler maintains a `discovered_from` map that records which page first linked to each internal URL. When an internal URL returns a 4xx/5xx status, the source page URL is attached to the issue's `extra.source_url` field. This enables the frontend to display "source pages" for internal broken links and offer a one-click rescan of the linking page after the issue is fixed. URLs seeded from the sitemap are recorded as `"(sitemap)"`.

### Image scoring with partial data

Image performance scoring no longer requires a full fetch (Level 2) to produce useful results. When only `file_size_bytes` is available from the Level 1 scan (HTTP HEAD request), the scorer can still flag `IMG_OVERSIZED` issues. This means oversized images are caught during the initial crawl without needing WordPress API calls.

### Health score trailing slash normalisation

The health score calculation normalises trailing slashes on both page URLs and issue URLs using `RTRIM(page_url, '/')` in SQL queries. This prevents mismatches where the crawled page URL has a trailing slash but the stored issue URL does not (or vice versa), which previously caused some pages to appear healthier than they actually were.

### Auto-rescan after fix

The frontend supports rescanning individual pages after fixes are applied. When a broken link source page is displayed, the user can click "Rescan Page" to re-fetch and re-check that page via `POST /api/crawl/{job_id}/rescan-url`. The rescan sends cache-bypass headers and updates stored issues, so the results view reflects the current state of the page. A manual URL input is also available for cases where source pages are not automatically tracked.

### Issue scoring and priority

Every issue has:
- `impact` (1–10): how badly the issue harms SEO or user experience
- `effort` (1–5): how hard it is to fix (1 = trivial, 5 = major dev work)
- `priority_rank = (impact × 10) − (effort × 2)`: higher = fix sooner

Health Score = `max(0, 100 − Σ issue impacts)` across all issues on the site.

### Auth

A bearer token (`Authorization: Bearer <token>`) gates all crawl endpoints. Set `AUTH_TOKEN` in environment variables. This is a deployment gate, not user authentication — it prevents the public from using the API without a token.

---

## Vercel Deployment

- `vercel.json` routes `/api/*` to `api/main.py` (Python serverless)
- All other requests serve the React SPA from `frontend/dist`
- Vercel Pro recommended (30s function timeout vs 10s on Hobby)

---

## Crawler Pipeline (in order)

1. Normalise and validate the start URL
2. Fetch and parse `robots.txt`
3. Discover and parse XML sitemap (index files, gzip, nested sitemaps)
4. **HTTPS redirect check** — verify `http://` version redirects to `https://`
5. **llms.txt check** — verify `/llms.txt` presence and format (spec §2.1)
6. Seed the crawl queue from both the start URL and all sitemap URLs
6. For each URL in the queue:
   a. Skip if already visited, over query variant cap, admin path, or WP noise path
   b. Check `robots.txt` — flag `ROBOTS_BLOCKED`, skip
   c. Check URL structure (string-only: case, length, spaces, underscores)
   d. Fetch the page (`httpx.AsyncClient`, 5s timeout, 10 redirect max)
   e. Handle errors: redirect loops, timeouts, login redirects
   f. Parse HTML: extract all fields into `ParsedPage`
   g. Run per-page issue checks (`check_page()`)
   h. Queue new internal URLs discovered via links
   i. Collect external links and image URLs for post-crawl checking
7. Check all external links (HEAD/GET)
8. Check all collected image URLs (HEAD)
9. Check AMP URLs declared via `<link rel="amphtml">`
10. Run cross-page checks (duplicates, orphan pages)
11. Apply category filter if `enabled_analyses` was specified

---

### Phase 2 Field Strategy

Phase 2 fields (`has_viewport_meta`, `schema_types`, `external_script_count`, `external_stylesheet_count`) are collected during the Phase 1 crawl and stored in the database. They are surfaced in the UI from Phase 1 onwards — these are now active checks:
- `MISSING_VIEWPORT_META` — emitted when `has_viewport_meta` is False
- `SCHEMA_MISSING` — emitted when `schema_types` is empty on an indexable page

External script and stylesheet counts are stored for future Phase 2 performance checks but not yet surfaced as issues.

### AI-Readiness Module (v1.7)

Extends the audit capability to evaluate how "quotable" and "crawlable" a site is for LLMs and AI agents (Gemini, Perplexity, etc.):
- **llms.txt validation** — Checks for the presence and format of `/llms.txt` as an instruction file for AI.
- **Semantic Density** — Audits the Text-to-HTML ratio to ensure AI tokenizers aren't overwhelmed by code-bloat.
- **AI Schema** — Flags pages missing JSON-LD, the preferred structured data format for AI Knowledge Graphs.
- **Conversational Headings** — Identifies subheadings that don't use interrogative words (How, What, Why), which LLMs prefer for matching natural-language queries.
- **AI Analysis Engine** — Integrates with Gemini/OpenAI to provide automated remediation suggestions for titles, meta descriptions, and semantic alignment.

