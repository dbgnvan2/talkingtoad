# TalkingToad — Implementation Plan

> This plan follows the spec in `nonprofit-crawler-spec-v1.4.md` §15.
> Work through milestones in order. Each milestone ends with passing tests before moving to the next.

---

## Milestone 0 — Project Scaffold (DONE)
- [x] CLAUDE.md, README structure
- [x] vercel.json, .env.example, .gitignore
- [x] requirements.txt, pytest.ini
- [x] Directory structure: api/, frontend/, tests/, docs/
- [x] Docs stubs: architecture.md, api.md, issue-codes.md, user-guide.md

---

## Milestone 1 — Core URL & Crawl Utilities

**Goal:** The building blocks that all other code depends on. Fully tested before anything crawls.

### 1.1 URL Normaliser (`api/crawler/normaliser.py`)
- [ ] Normalise URL: lowercase scheme+host, strip trailing slash, remove fragments
- [ ] Strip tracking params: utm_*, ref, session_id, sid, fbclid, gclid
- [ ] Preserve other query params; treat `?page=2` and `?page=3` as distinct
- [ ] Domain boundary check: `www` = same domain; other subdomains = external
- [ ] Query variant cap: flag path when >50 unique query variants discovered

**Tests:** `tests/test_normaliser.py`
- Trailing slash stripping
- Fragment removal
- UTM param stripping
- Non-UTM param preservation
- www-prefix same-domain detection
- Subdomain external detection
- Query variant cap logic

### 1.2 robots.txt Parser (`api/crawler/robots.py`)
- [ ] Fetch `robots.txt` for a domain via httpx
- [ ] Parse `Disallow` rules for `NonprofitCrawler` and `*` user agents
- [ ] Parse `Crawl-delay` directive
- [ ] Parse `Sitemap:` directives (used by sitemap auto-discovery)
- [ ] Return `is_allowed(url)` method
- [ ] Handle missing robots.txt gracefully (log warning, allow all)

**Tests:** `tests/test_robots.py`
- Disallow rule enforcement
- Wildcard user agent fallback
- Crawl-delay extraction
- Sitemap directive extraction
- Missing robots.txt handled without error

### 1.3 Sitemap Parser (`api/crawler/sitemap.py`)
- [ ] Auto-discover: try `/sitemap.xml`, then check `robots.txt` Sitemap: directives
- [ ] Handle sitemap index files (`<sitemapindex>`) — fetch and parse each child
- [ ] Handle standard sitemaps (`<urlset>`) — extract `<loc>` URLs
- [ ] Handle gzipped sitemaps (detect Content-Encoding: gzip, decompress)
- [ ] Accept user-supplied sitemap URL override
- [ ] Return `SITEMAP_MISSING` info issue when not found

**Tests:** `tests/test_sitemap.py`
- Standard sitemap parsing
- Sitemap index (nested) parsing
- Gzip sitemap decompression
- Auto-discovery fallback
- SITEMAP_MISSING issue emitted when not found

---

## Milestone 2 — Crawl Engine

**Goal:** A working async crawler that can fetch pages, follow links, and store results.

### 2.1 HTTP Fetcher (`api/crawler/fetcher.py`)
- [ ] Async page fetch with httpx (5s timeout)
- [ ] Follow redirects, record full chain
- [ ] Detect redirect to login path → log `LOGIN_REDIRECT`, skip
- [ ] Skip admin paths (wp-admin, wp-login.php, /admin/*, login paths)
- [ ] Return: status_code, headers, html_content, redirect_chain
- [ ] User-Agent from env var `CRAWLER_USER_AGENT`

### 2.2 Page Parser (`api/crawler/parser.py`)
- [ ] Extract all Phase 1 + Phase 2 fields from HTML:
  - title, meta_description, og_title, og_description, canonical_url
  - h1_tags, headings_outline (h1–h6 hierarchy)
  - is_indexable (meta robots + X-Robots-Tag)
  - robots_directive, has_favicon (homepage only)
  - All links (internal + external) with link text
  - Phase 2: has_viewport_meta, schema_types, external_script_count, external_stylesheet_count
- [ ] response_size_bytes from Content-Length or body length

### 2.3 Issue Checker (`api/crawler/issue_checker.py`)
- [ ] All Phase 1 issue codes (see docs/issue-codes.md)
- [ ] Canonical scoping rules (3 conditions from spec §3.1.2):
  1. Has query string → `CANONICAL_MISSING`
  2. Near-duplicate (same title + meta_desc as another page) → `CANONICAL_MISSING`
  3. Has canonical pointing externally → `CANONICAL_EXTERNAL`
- [ ] Favicon: check homepage only, emit once per job
- [ ] OG tags: `OG_TITLE_MISSING` and `OG_DESC_MISSING` as info
- [ ] Duplicate detection: cross-page title, meta_desc, title+meta_desc pairs

**Tests:** `tests/test_issue_checker.py`
- Each issue code generated under correct conditions
- Canonical scoping: all 3 conditions individually
- Favicon: only emitted for homepage
- Duplicate detection across multiple pages

### 2.4 Crawl Engine (`api/crawler/engine.py`)
- [ ] Async BFS/queue crawler within domain boundary
- [ ] robots.txt check before queuing each URL
- [ ] Respect crawl delay (min 200ms)
- [ ] Max pages cap (env: `MAX_PAGES_PER_CRAWL`)
- [ ] External link checking (HEAD → GET fallback), with caps from spec §2.8
- [ ] External links deprioritised — internal pages crawled first
- [ ] Query variant cap enforcement (50 per path)
- [ ] Job status updates: pages_crawled, pages_total, current_url
- [ ] Structured JSON logging for all log events from spec §8.2

**Tests:** `tests/test_crawl_engine.py`
- Domain boundary enforcement
- Admin path skipping
- robots.txt blocking
- External link cap enforcement
- Redirect chain detection and loop detection

---

## Milestone 3 — Data Layer & Job Store

**Goal:** Jobs and results persist through the API lifecycle.

### 3.1 Data Models (`api/models/`)
- [ ] `job.py`: CrawlJob model (Pydantic + DB schema)
- [ ] `page.py`: CrawledPage model — all Phase 1 + Phase 2 fields
- [ ] `link.py`: Link model
- [ ] `issue.py`: Issue model with all categories/severities/codes

### 3.2 Job Store (`api/services/job_store.py`)
- [ ] Abstraction layer: SQLite in dev, Upstash Redis in prod (switched via DATABASE_URL)
- [ ] Create, read, update CrawlJob
- [ ] Store/retrieve CrawledPage records per job
- [ ] Store/retrieve Issue records per job
- [ ] Paginated issue queries with severity and category filters
- [ ] TTL management (7-day expiry, env: `RESULT_TTL_DAYS`)
- [ ] Duplicate detection queries (cross-page title/meta_desc comparison)

---

## Milestone 4 — API Layer

**Goal:** All endpoints from spec §6 implemented and tested.

### 4.1 Auth Middleware (`api/services/auth.py`)
- [ ] Bearer token check on all `/api/crawl/*` endpoints
- [ ] Return 401 with standard error shape on failure

### 4.2 Rate Limiter (`api/services/rate_limiter.py`)
- [ ] `slowapi` setup: 3 concurrent / 10 per hour per IP
- [ ] In-memory for dev, Redis-backed for prod

### 4.3 Crawl Router (`api/routers/crawl.py`)
- [ ] `POST /api/crawl/start` — validate URL, create job, launch background task
- [ ] `GET /api/crawl/{job_id}/status` — return job progress
- [ ] `POST /api/crawl/{job_id}/cancel` — cancel running job; `JOB_ALREADY_COMPLETE` if done
- [ ] `GET /api/crawl/{job_id}/results` — paginated results with summary
- [ ] `GET /api/crawl/{job_id}/results/{category}` — filtered results; `INVALID_CATEGORY` validation
- [ ] `GET /api/crawl/{job_id}/pages` — all crawled pages with per-page issue counts; `min_severity` filter
- [ ] `GET /api/crawl/{job_id}/pages/issues?url=` — all issues for one page, grouped by category; `PAGE_NOT_FOUND` if not crawled
- [ ] `GET /api/crawl/{job_id}/export/csv` — full CSV download
- [ ] `GET /api/crawl/{job_id}/export/csv/{category}` — category CSV

### 4.4 Utility Router (`api/routers/utility.py`)
- [ ] `GET /api/health` — `{"status": "ok", "version": "1.4"}`
- [ ] `GET /api/robots?url=` — fetch and parse robots.txt
- [ ] `GET /api/sitemap?url=` — fetch and parse sitemap

### 4.5 App Entry Point (`api/main.py`)
- [ ] FastAPI app with CORS middleware (origins from env `ALLOWED_ORIGINS`)
- [ ] Register all routers
- [ ] Logging setup (python-json-logger, level from env `LOG_LEVEL`)
- [ ] Auth + rate limiter wired in

**Tests:** `tests/test_api.py`
- All endpoints: happy path
- All error codes from spec §6.5
- Auth: valid token passes, missing/invalid token rejected
- Rate limiting: 429 on exceeded
- `INVALID_CATEGORY` validation
- Pagination: page/limit/total_pages correct
- CSV export: correct columns and data

---

## Milestone 5 — React Frontend

**Goal:** Working UI from URL entry through results and export.

### 5.1 Home page (`frontend/src/pages/Home.jsx`)
- [ ] URL input + sitemap URL input (always shown, optional)
- [ ] Collapsed crawl settings (max pages, crawl delay)
- [ ] "Start Crawl" button — POST to `/api/crawl/start`
- [ ] Usage notice
- [ ] Navigate to Progress page on success

### 5.2 Progress page (`frontend/src/pages/Progress.jsx`)
- [ ] Polling hook: 2s for first 60s, then 5s (`frontend/src/hooks/usePolling.js`)
- [ ] Stop polling on terminal status (complete, failed, cancelled)
- [ ] Progress bar: indeterminate spinner when `pages_total` null
- [ ] Estimated time remaining (when `pages_total` known and ≥5 pages crawled)
- [ ] Current URL being crawled
- [ ] Cancel button → POST to cancel endpoint
- [ ] Navigate to Results on completion

### 5.3 Results dashboard (`frontend/src/pages/Results.jsx`)
- [ ] Summary tab: issue counts by category, colour-coded severity, top 5 issues
- [ ] One tab per category (broken_link, metadata, heading, redirect, crawlability, duplicate, sitemap)
- [ ] Paginated table: 50 issues/page, next/prev
- [ ] Filterable by severity
- [ ] Recommendation column per issue
- [ ] "Why it matters" tooltip
- [ ] Link to live page (new tab)
- [ ] Clicking a URL in any category tab navigates to the By Page view for that URL

### 5.4 By Page view (`frontend/src/pages/Results.jsx` — By Page tab)
- [ ] Table of all crawled pages, sorted by issue count descending
- [ ] Columns: URL, HTTP status, total issues, critical / warning / info counts
- [ ] Filter by minimum severity (show only pages with ≥1 critical, etc.)
- [ ] URL substring search
- [ ] Clicking a row expands an inline detail panel
- [ ] Detail panel: all issues for that page grouped by category
- [ ] Each issue shows: severity badge, issue code, description, recommendation
- [ ] "View live page" link in detail panel

### 5.4 Export (`frontend/src/pages/Export.jsx` or inline in Results)
- [ ] "Export CSV" per category
- [ ] "Export Full CSV" button

### 5.5 Shared components (`frontend/src/components/`)
- [ ] `SeverityBadge.jsx` — colour-coded red/amber/green/blue
- [ ] `IssueTable.jsx` — reusable paginated table
- [ ] `ProgressBar.jsx` — determinate + indeterminate
- [ ] `Tooltip.jsx` — "Why it matters" tooltip

---

## Milestone 6 — Deployment & End-to-End

- [ ] Deploy to Vercel with vercel.json routing
- [ ] Set all env vars in Vercel dashboard
- [ ] Configure Upstash Redis as production data store
- [ ] Update `ALLOWED_ORIGINS` to include `.vercel.app` domain
- [ ] End-to-end test crawl against `livingsystems.ca`
- [ ] Verify all Phase 1 issue codes appear correctly in results
- [ ] Verify CSV export completeness

---

## Testing Policy

- **No milestone is complete until its tests pass.**
- Mock all external HTTP calls in tests — never hit real websites.
- Regression tests are never deleted — only fixed or updated to match new spec behaviour.
- Before any PR/commit: `pytest tests/ -v` must pass with zero failures.

---

## Phase 2 (After MVP validation)

See spec §3.2 and §15 for full checklist:
- Internal link analysis + orphan detection
- Configurable admin path skip list
- Schema markup detection
- Image alt text + file size
- Mobile viewport check
- Performance signals
- Phase 2 UI + CSV surfacing
- PDF export

---

*Plan version: 1.0 — aligned with spec v1.4*
