# Nonprofit Website Crawler Tool — Full Product Specification

**Version:** 1.4
**Date:** April 2026
**Author:** Dave / Living Systems Counselling Society
**Initial Test Site:** livingsystems.ca
**Changes from v1.3:** Fixed has_favicon type to bool|null; removed duplicate httpx in requirements.txt; added INVALID_CATEGORY and JOB_ALREADY_COMPLETE error codes; added cancel endpoint response schema; scoped CANONICAL_MISSING to pages with query strings or detected near-duplicates only; downgraded OG_TITLE_MISSING and OG_DESC_MISSING to info; added vercel.json deployment stub; added pytest asyncio_mode config note; added health endpoint response schema; added Content-Type note on POST requests; split issue code table into Phase 1 and Phase 2 tables.

---

## 1. Project Overview

### 1.1 Purpose

A lightweight, web-based SEO crawler tool designed specifically for nonprofit organisations. It duplicates the essential functionality of Screaming Frog SEO Spider without the cost, installation complexity, or feature overload that makes enterprise tools inaccessible to nonprofits.

### 1.2 Core Value Proposition

- **Free or very low cost** — appropriate for nonprofits on tight budgets
- **Zero installation** — runs entirely in a browser
- **Simple, actionable results** — non-technical staff can understand and act on findings
- **Fast to run** — suitable for small-to-medium nonprofit sites (under ~500 pages)

### 1.3 Target Users

- Primary: Nonprofit administrators, communications staff, or volunteers managing a website
- Secondary: SEO consultants or digital agencies serving nonprofits
- Initial: Living Systems Counselling Society (livingsystems.ca)

---

## 2. Technical Architecture

### 2.1 Overview

```
[Browser Frontend]  →  [API Layer]  →  [Crawler Engine]  →  [Results Store]
     React/Vite          FastAPI           Python/             SQLite or
     Vercel              Vercel Edge       httpx +             Upstash Redis
                         Functions         BeautifulSoup
                                           + lxml
```

### 2.2 Frontend

- **Framework:** React with Vite
- **Hosting:** Vercel (free tier to start)
- **UI Library:** Tailwind CSS (keep it simple and lightweight)
- **Key Pages:**
  - Home / URL Entry
  - Crawl Progress (live updates via polling)
  - Results Dashboard (tabbed by issue category)
  - Issue Detail view (per URL)
  - Export page (CSV download)

### 2.3 Backend

- **Framework:** Python with FastAPI
- **Hosting:** Vercel Serverless Functions (initial), migrate to AWS Lambda or a small EC2/Lightsail instance if Vercel timeouts become a bottleneck
- **HTTP Client:** `httpx` with async support — preferred over `requests` because it integrates natively with FastAPI's async architecture, supports connection pooling, and handles timeouts more predictably. Also used as the async test client in pytest.
- **HTML Parser:** `BeautifulSoup4` with `lxml` as the parser backend — `lxml` is faster and more lenient with malformed HTML than Python's built-in `html.parser`, which matters when crawling real-world nonprofit sites
- **Crawl Engine:** `httpx` + `BeautifulSoup4` + `lxml` for initial version; upgrade to `Scrapy` if performance demands it
- **Job Queue:** Background task via FastAPI `BackgroundTasks` initially; upgrade to Celery + Redis (Upstash) for larger crawls
- **Data Store:** SQLite for development; Upstash Redis or PlanetScale (MySQL) for production persistence

### 2.4 Crawl Architecture

- Crawl jobs are **asynchronous** — user submits a URL, gets a job ID, frontend polls for status
- Each job stores progress and results in the data store
- Respects `robots.txt` and enforces a configurable crawl delay (default: 500ms between requests)
- Crawl depth is configurable (default: unlimited within the same domain)
- Max pages per crawl: 500 (soft limit for free tier; expandable)
- Stays within the submitted domain — no following external links as crawl targets (see Section 2.7 for domain boundary rules)
- External links are **status-checked only** (HEAD request, capped per Section 2.8) but not crawled further
- User-Agent string identifies the crawler clearly (e.g., `NonprofitCrawler/1.0`)

### 2.5 Vercel Timeout Mitigation

Vercel serverless functions time out at 10 seconds (Hobby) or 30 seconds (Pro). Strategy:

1. Crawl is broken into **batches of pages**
2. Frontend polls a `/job/{job_id}/status` endpoint
3. Each batch runs within the timeout window and commits results to the data store
4. When all batches complete, results are assembled for the dashboard
5. Per-request HTTP timeout is set to **5 seconds** — well below the function timeout ceiling — so a single slow page cannot exhaust the entire function window

### 2.6 CORS Policy

The frontend and backend are hosted on separate origins and require explicit CORS configuration.

- Allow requests from the Vercel frontend domain (e.g., `https://yourcrawler.vercel.app`) and any custom domain
- Allow methods: `GET`, `POST`, `OPTIONS`
- Allow headers: `Content-Type`, `Authorization` (for future auth)
- Do **not** use wildcard `*` origins in production
- Configure via `fastapi.middleware.cors.CORSMiddleware`
- Store allowed origins in environment variable `ALLOWED_ORIGINS` (comma-separated list)

### 2.7 Domain Boundary Rules

The crawler must have a clear, consistent definition of "same domain":

- **Base domain match:** `livingsystems.ca` and `www.livingsystems.ca` are treated as the same domain (www-prefix normalisation)
- **Subdomains:** Any other subdomain (e.g., `blog.livingsystems.ca`) is treated as **external** unless explicitly configured as in-scope
- **Protocol:** `http://` and `https://` variants of the same domain are treated as the same domain
- **URL normalisation before deduplication:**
  - Strip trailing slashes
  - Lowercase the scheme and host
  - Remove fragment identifiers (`#section`)
  - Strip known tracking/session parameters before deduplication: `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `ref`, `session_id`, `sid`, `fbclid`, `gclid`
  - Preserve all other query parameters — treat `?page=2` and `?page=3` as distinct URLs
  - Apply a **per-job URL budget** to prevent runaway pagination crawls: if more than 50 unique query-string variants of the same path are discovered, log a warning and stop queuing new variants of that path
- **Configurable:** Allow the user to optionally include one additional subdomain in scope

### 2.8 External Link Checking Limits

Uncapped external link checking can turn the crawler into an unintentional load generator against third-party sites. Apply these constraints:

- Maximum **50 external link checks per crawled page**
- Maximum **500 external link checks per crawl job** (global cap)
- External checks use a **HEAD request** (fall back to GET if HEAD returns 405)
- External checks run with a **5-second timeout** — same as internal requests
- External checks are **deprioritised** — internal pages are fully crawled before external link status checks begin
- If the global cap is reached, remaining unchecked external links are recorded with `status_code: null` and `is_broken: false` (unknown), flagged with a note in the results

### 2.9 Password-Protected and Admin Pages

WordPress and many CMS platforms expose admin and login paths that the crawler should not attempt to audit:

- **Skip by default** any URL matching these path patterns:
  - `/wp-admin/*`
  - `/wp-login.php`
  - `/admin/*`
  - `/login`, `/logout`, `/signin`, `/signout`
  - `/user/login`, `/user/logout`
- If a page returns a **401 Unauthorized** or **403 Forbidden**, record the status code and skip — do not flag as a broken link
- If a page issues a **302 redirect to a login URL** (detectable by the redirect target matching login path patterns above), record as `LOGIN_REDIRECT` info-level issue and skip further crawling of that URL
- The skip list is hardcoded for MVP; configurable in Phase 2

---

## 3. Feature Specification

### 3.1 Phase 1 — Core Crawl (MVP)

These features ship in the first working version.

#### 3.1.1 Broken Links

- Crawl all internal links discovered on every page
- For external links: issue a HEAD request (fall back to GET if HEAD returns 405), subject to caps in Section 2.8
- Check HTTP status code for each URL
- Flag as broken: 404 Not Found, 410 Gone, 5xx Server Errors
- Flag as warning: 301/302 redirects (see redirect section)
- Report: broken URL + source page(s) where the link appears + HTTP status code + link text

#### 3.1.2 Metadata Analysis

For every crawled page, extract and evaluate:

| Field | Check |
|---|---|
| `<title>` tag | Missing, empty, duplicate, too short (<30 chars), too long (>60 chars) |
| Meta description | Missing, empty, duplicate, too short (<70 chars), too long (>160 chars) |
| Open Graph title (`og:title`) | Missing — emit `OG_TITLE_MISSING` (info) |
| Open Graph description (`og:description`) | Missing — emit `OG_DESC_MISSING` (info) |
| Canonical tag (`rel=canonical`) | Scoped check — see rules below |
| Favicon (`<link rel="icon">` or `<link rel="shortcut icon">`) | Checked **on the homepage only** — emit `FAVICON_MISSING` (info) once per crawl if absent |

**Canonical tag scoping rules:**
- If a page has a canonical tag pointing to itself (self-referencing): OK, no issue emitted
- If a page has a canonical tag pointing externally: emit `CANONICAL_EXTERNAL` (warning)
- If a page has **no** canonical tag AND has query string parameters: emit `CANONICAL_MISSING` (warning) — query-string pages are duplicate content risks
- If a page has **no** canonical tag AND is identified as a near-duplicate of another page (same title + meta description): emit `CANONICAL_MISSING` (warning)
- If a page has **no** canonical tag but has unique content and no query strings: no issue emitted — avoids flooding results on small sites where canonical tags are absent but harmless

#### 3.1.3 Heading Structure

For every page, extract heading hierarchy:

- Flag: Missing `<h1>` tag
- Flag: Multiple `<h1>` tags on same page
- Flag: Skipped heading levels (e.g., H1 → H3 with no H2)
- Report: Full heading outline per page for manual review

#### 3.1.4 Redirect Analysis

- Detect 301 and 302 redirects
- Detect redirect chains (A → B → C, more than one hop)
- Detect redirect loops (A → B → A)
- Report: full redirect chain for each affected URL

#### 3.1.5 Crawlability Issues

- Fetch and parse `robots.txt` before crawl begins (see Section 3.1.7 for sitemap parsing)
- Flag pages blocked by `robots.txt` directives
- Flag pages with `<meta name="robots" content="noindex">` or `nofollow`
- Detect pages with `X-Robots-Tag: noindex` HTTP header
- Flag pages discovered by crawl but missing from XML sitemap (requires sitemap — see 3.1.7)

#### 3.1.6 Duplicate Content Detection

- Detect exact duplicate page titles across the site
- Detect exact duplicate meta descriptions across the site
- Detect pages where both title and meta description are duplicated together
- Flag pages without a canonical tag that are near-duplicates (feeds into canonical scoping in 3.1.2)
- Report: grouped list of duplicates with their URLs

#### 3.1.7 Sitemap Parsing

WordPress and many nonprofit CMS platforms use sitemap index files. The crawler must handle:

- **Auto-discovery:** Check `/sitemap.xml` and parse `robots.txt` for `Sitemap:` directives
- **Sitemap index files:** If the sitemap is an index (contains `<sitemapindex>`), fetch and parse each child sitemap listed within it
- **Standard sitemaps:** Parse `<urlset>` entries, extracting each `<loc>` URL
- **Gzipped sitemaps:** Detect `Content-Encoding: gzip` and decompress before parsing
- **Fallback:** If no sitemap is found, record this as an info-level issue (`SITEMAP_MISSING`) and skip sitemap-based checks
- **Manual override:** Allow user to supply a sitemap URL explicitly if auto-discovery fails

---

### 3.2 Phase 2 — Extended Checks

These features are built after the MVP is validated with livingsystems.ca.

#### 3.2.1 Internal Link Analysis

- Map all internal links across the site
- Identify **orphan pages** — pages with no internal links pointing to them
- Identify **over-linked pages** — pages with an unusually high number of inbound links
- Report: link graph summary with inbound/outbound link counts per page
- Make admin path skip list from Section 2.9 configurable via UI

#### 3.2.2 Schema Markup Detection

- Detect presence of structured data (`<script type="application/ld+json">` or microdata)
- Identify schema types in use (Organization, LocalBusiness, Event, Person, Article, etc.)
- Flag pages with no schema markup
- Suggest recommended schema types for nonprofit use cases (Organization, Event, FAQPage)
- Do not validate schema — just detect presence/absence and type

#### 3.2.3 Image Analysis

- Detect images missing `alt` attribute
- Detect images with empty `alt` attribute (only OK for decorative images — flag for review)
- Detect oversized images (file size > 200KB where detectable via Content-Length header)
- Report: image URL, page source, issue type

#### 3.2.4 Page Performance Signals

- Report HTML response size in KB per page
- Emit `PAGE_TOO_LARGE` (warning) if HTML response exceeds 500KB
- Count external scripts and stylesheets loaded per page
- Emit `EXCESSIVE_EXTERNAL_DEPS` (warning) if external script + stylesheet count exceeds 10
- Note: Full Core Web Vitals requires browser rendering; this phase covers server-side signals only

#### 3.2.5 Mobile Usability

- Detect presence of `<meta name="viewport">` tag
- Flag pages missing viewport meta tag with `NO_VIEWPORT_META`
- This is a lightweight proxy signal — full mobile testing requires a headless browser (Phase 3 consideration)

---

### 3.3 Phase 3 — Future Considerations (Not in Scope Yet)

- JavaScript rendering support (headless Chromium via Playwright or Puppeteer)
- Full Core Web Vitals measurement
- Accessibility audit (WCAG checks)
- Historical crawl comparison (diff between two crawls)
- Scheduled automatic crawls with email alerts
- Multi-user accounts / saved crawl history
- **White-label mode:** Allow agencies or consultants serving nonprofits to deploy their own branded instance with a custom domain, logo, and colour scheme. Implementation model: separate Vercel deployments per tenant using environment-variable-driven theming, not a multi-tenant database architecture. Each tenant gets their own deployment with their own data store.

---

## 4. User Interface Requirements

### 4.1 Home / URL Entry

- Single text input: "Enter your website URL"
- Optional: sitemap URL input (shown always as an optional field; pre-populated if auto-discovery succeeds)
- Optional: crawl settings (max pages, crawl delay) — collapsed by default, expandable
- "Start Crawl" button
- Brief explainer: what the tool checks and why it matters for nonprofits
- Usage notice: "This tool is intended for use on websites you own or have permission to audit"
- No account required for MVP

### 4.2 Crawl Progress

- Live progress bar showing pages crawled / total (if known) — renders as indeterminate spinner when `pages_total` is null
- Status message (e.g., "Crawling: /about-us")
- Cancel crawl option
- Estimated time remaining (only shown when `pages_total` is known and at least 5 pages have been crawled)
- **Polling interval:** Frontend polls `/status` every **2 seconds** for the first 60 seconds, then backs off to every **5 seconds** thereafter. Stop polling immediately when a terminal status is received (`complete`, `failed`, or `cancelled`).

### 4.3 Results Dashboard

Tabbed interface with a **Summary tab**, one tab per issue category, and a **By Page tab**:

**Summary Tab:**
- Total pages crawled
- Issue count by category (broken links, metadata, headings, redirects, crawlability, duplicates)
- Colour-coded severity indicators (Red = Critical, Amber = Warning, Green = OK)
- Top 5 issues to fix first (prioritised by severity then frequency)

**Per-Category Tabs:**
- Paginated table of affected URLs — **50 issues per page**, with next/previous controls
- Filterable and sortable by severity
- Issue description column (plain English, not technical jargon)
- Recommended fix column (drawn from issue code recommendation copy — see Section 7)
- "Why it matters" tooltip explaining impact for nonprofits
- Link to the live page (opens in new tab)
- Clicking any URL in the table navigates to the By Page view filtered to that page

**By Page Tab:**
- Table of all crawled pages, sorted by total issue count descending (pages with the most problems first)
- Columns: URL, HTTP status, total issues, critical count, warning count, info count
- Clicking a row expands an inline detail panel showing every issue found on that page, grouped by category
- Each issue in the detail panel shows: severity badge, issue code, plain-English description, recommendation
- A "View live page" link opens the URL in a new tab
- Filterable by minimum severity (e.g., show only pages with at least one critical issue)
- Searchable by URL substring

### 4.4 Export

- Export each category as CSV
- Export full results as a single CSV
- CSV columns: URL, Issue Code, Severity, Category, Phase, Description, Recommendation
- Optional: PDF summary report (Phase 2)

### 4.5 Design Principles

- Clean, uncluttered interface — one action at a time
- Plain English throughout — avoid SEO jargon where possible
- Mobile-responsive (staff may use tablets)
- Accessible: sufficient contrast, keyboard navigable
- No ads, no upsell prompts in MVP

---

## 5. Data Model

### 5.1 Crawl Job

```
CrawlJob {
  job_id: UUID
  target_url: string
  sitemap_url: string | null
  status: enum [queued, running, complete, failed, cancelled]
  pages_crawled: int
  pages_total: int | null   // null when no sitemap available; updated as crawl progresses if discoverable
  started_at: datetime
  completed_at: datetime | null
  error_message: string | null
  settings: {
    max_pages: int,
    crawl_delay_ms: int,
    respect_robots: bool,
    include_subdomains: string[] | null
  }
}
```

### 5.2 Crawled Page

Phase 1 fields are collected in MVP. Phase 2 fields are collected from day one to avoid a schema migration later, but are only surfaced in the UI in Phase 2.

```
CrawledPage {
  page_id: UUID
  job_id: UUID (FK)
  url: string
  status_code: int
  redirect_url: string | null
  redirect_chain: string[] | null
  title: string | null
  meta_description: string | null
  canonical_url: string | null
  og_title: string | null
  og_description: string | null
  has_favicon: bool | null      // true/false for homepage; null for all other pages (not checked)
  h1_tags: string[]
  headings_outline: object      // h1–h6 hierarchy as nested JSON
  is_indexable: bool
  robots_directive: string | null
  response_size_bytes: int
  crawled_at: datetime

  // Phase 2 fields — collected during Phase 1 crawl, surfaced in Phase 2 UI only
  has_viewport_meta: bool
  schema_types: string[]
  external_script_count: int | null
  external_stylesheet_count: int | null
}
```

### 5.3 Link

```
Link {
  link_id: UUID
  job_id: UUID (FK)
  source_url: string
  target_url: string
  link_text: string | null
  link_type: enum [internal, external]
  status_code: int | null   // null if external link cap reached before check
  is_broken: bool
  check_skipped: bool       // true if status not checked due to external cap
}
```

### 5.4 Issue

The Issue model stores `page_url` directly as a denormalised field to avoid join complexity in the API layer. The `page_id` FK is retained for internal reference and future query optimisation.

```
Issue {
  issue_id: UUID
  job_id: UUID (FK)
  page_id: UUID (FK) | null
  page_url: string | null       // denormalised from CrawledPage.url — returned directly in API responses
  link_id: UUID (FK) | null
  category: enum [broken_link, metadata, heading, redirect, crawlability, duplicate, image, performance, mobile, sitemap, schema]
  severity: enum [critical, warning, info]
  issue_code: string
  description: string
  recommendation: string
}
```

---

## 6. API Endpoints

### 6.1 Crawl Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/crawl/start` | Submit a new crawl job. Returns `job_id`. |
| GET | `/api/crawl/{job_id}/status` | Poll job progress and status. |
| POST | `/api/crawl/{job_id}/cancel` | Cancel a running crawl. |
| GET | `/api/crawl/{job_id}/results` | Retrieve paginated results for a completed job. |
| GET | `/api/crawl/{job_id}/results/{category}` | Retrieve paginated results filtered by issue category. |
| GET | `/api/crawl/{job_id}/pages` | List all crawled pages with per-page issue counts. |
| GET | `/api/crawl/{job_id}/pages/issues?url={url}` | Retrieve all issues for a specific crawled page. |

### 6.2 Export

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/crawl/{job_id}/export/csv` | Download full results as CSV. |
| GET | `/api/crawl/{job_id}/export/csv/{category}` | Download category results as CSV. |

### 6.3 Utility

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check. Returns `{ "status": "ok", "version": "1.4" }`. |
| GET | `/api/robots?url={url}` | Fetch and parse robots.txt for a given domain. |
| GET | `/api/sitemap?url={url}` | Fetch, detect, and parse sitemap(s) for a given domain. |

### 6.4 Request and Response Schemas

> **Note:** All POST requests must include the header `Content-Type: application/json`. FastAPI will return a `422 Unprocessable Entity` if this header is missing on requests with a body.

---

#### POST `/api/crawl/start`

**Request body:**
```json
{
  "target_url": "https://livingsystems.ca",
  "sitemap_url": "https://livingsystems.ca/sitemap.xml",
  "settings": {
    "max_pages": 500,
    "crawl_delay_ms": 500,
    "respect_robots": true,
    "include_subdomains": []
  }
}
```
All fields in `settings` are optional and fall back to environment variable defaults.
`sitemap_url` is optional — omit to trigger auto-discovery.

**Success response — 202 Accepted:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "queued",
  "poll_url": "/api/crawl/3fa85f64-5717-4562-b3fc-2c963f66afa6/status"
}
```

---

#### GET `/api/crawl/{job_id}/status`

**Success response — 200 OK:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "running",
  "pages_crawled": 42,
  "pages_total": 110,
  "current_url": "https://livingsystems.ca/about-us/",
  "started_at": "2026-04-07T10:00:00Z",
  "completed_at": null,
  "estimated_seconds_remaining": 34,
  "error_message": null
}
```

**`pages_total`:** `null` when no sitemap is available. Progress bar renders as indeterminate spinner in this state.

**`estimated_seconds_remaining`:** Calculated as `(pages_total - pages_crawled) × average_seconds_per_page_so_far`. Only included when `pages_total` is not null and at least 5 pages have been crawled. `null` otherwise.

**Terminal states:** `status` of `complete`, `failed`, or `cancelled` signals the crawl is done. Frontend stops polling immediately on receipt of any terminal state.

---

#### POST `/api/crawl/{job_id}/cancel`

**Success response — 200 OK:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "cancelled"
}
```

**Failure:** Returns `JOB_NOT_FOUND` (404) if job does not exist, or `JOB_ALREADY_COMPLETE` (409) if the job has already finished.

---

#### GET `/api/crawl/{job_id}/results`

Supports pagination. Results are always sorted by severity (critical first) then category.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (1-indexed) |
| `limit` | int | 50 | Results per page (max 100) |
| `severity` | string | all | Filter by severity: `critical`, `warning`, `info` |

**Success response — 200 OK:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "summary": {
    "pages_crawled": 110,
    "total_issues": 47,
    "by_severity": { "critical": 8, "warning": 31, "info": 8 },
    "by_category": {
      "broken_link": 5,
      "metadata": 18,
      "heading": 6,
      "redirect": 4,
      "crawlability": 3,
      "duplicate": 7,
      "sitemap": 1
    }
  },
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_issues": 47,
    "total_pages": 1
  },
  "issues": [
    {
      "issue_id": "a1b2c3d4-...",
      "page_url": "https://livingsystems.ca/contact/",
      "category": "metadata",
      "severity": "critical",
      "issue_code": "META_DESC_MISSING",
      "description": "No meta description",
      "recommendation": "Add a meta description of 70–160 characters summarising what visitors will find on this page."
    }
  ]
}
```

Note: `summary.by_category` reflects Phase 1 categories only. `schema` and `performance` are added to the summary in Phase 2.

---

#### GET `/api/crawl/{job_id}/results/{category}`

Accepts a valid category slug: `broken_link`, `metadata`, `heading`, `redirect`, `crawlability`, `duplicate`, `sitemap`. (Phase 2 adds: `image`, `performance`, `mobile`, `schema`.)

Returns `422 INVALID_CATEGORY` with the list of valid slugs if an unrecognised value is passed.

Same pagination parameters as the full results endpoint. Response shape is identical, with `issues` filtered to the requested category.

---

#### GET `/api/crawl/{job_id}/pages`

Returns all crawled pages with per-page issue counts. Used to power the **By Page** tab.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `min_severity` | string | none | Filter to pages with at least one issue of this severity: `critical`, `warning`, `info` |
| `page` | int | 1 | Page number (1-indexed) |
| `limit` | int | 50 | Results per page (max 100) |

**Success response — 200 OK:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_pages_crawled": 110,
    "total_pages": 3
  },
  "pages": [
    {
      "url": "https://livingsystems.ca/contact/",
      "status_code": 200,
      "issue_counts": {
        "total": 5,
        "critical": 2,
        "warning": 2,
        "info": 1
      }
    }
  ]
}
```

Pages are sorted by `issue_counts.total` descending (most problems first).

---

#### GET `/api/crawl/{job_id}/pages/issues?url={url}`

Returns every issue found on a specific crawled page, grouped by category.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | The exact crawled URL to look up |

Returns `404 PAGE_NOT_FOUND` if the URL was not crawled in this job.

**Success response — 200 OK:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "url": "https://livingsystems.ca/contact/",
  "status_code": 200,
  "total_issues": 5,
  "by_category": {
    "metadata": [
      {
        "issue_id": "a1b2c3d4-...",
        "severity": "critical",
        "issue_code": "META_DESC_MISSING",
        "description": "No meta description",
        "recommendation": "Add a meta description of 70–160 characters summarising what visitors will find on this page."
      }
    ],
    "heading": [
      {
        "issue_id": "b2c3d4e5-...",
        "severity": "warning",
        "issue_code": "H1_MULTIPLE",
        "description": "More than one H1 on the page",
        "recommendation": "Remove extra H1 tags. Each page should have exactly one H1 that introduces the main topic."
      }
    ]
  }
}
```

---

### 6.5 Error Response Format

All API errors return a consistent JSON shape:

```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "No crawl job found with the given ID.",
    "http_status": 404
  }
}
```

**Standard error codes:**

| Code | HTTP Status | Description |
|---|---|---|
| `JOB_NOT_FOUND` | 404 | No job exists with the given `job_id` |
| `JOB_ALREADY_RUNNING` | 409 | A crawl is already in progress for this job |
| `JOB_ALREADY_COMPLETE` | 409 | Job has already finished — cannot cancel |
| `INVALID_URL` | 422 | The submitted URL is malformed or unreachable |
| `INVALID_CATEGORY` | 422 | Unrecognised category slug passed to results endpoint |
| `CRAWL_LIMIT_EXCEEDED` | 429 | Rate limit reached — too many crawls from this IP |
| `CRAWL_FAILED` | 500 | Crawler encountered an unrecoverable error |
| `TARGET_UNREACHABLE` | 502 | The target website could not be reached |

---

### 6.6 Rate Limiting

- Maximum **3 concurrent crawl jobs per IP address**
- Maximum **10 crawl jobs per IP per hour**
- Requests exceeding limits receive `429 Too Many Requests` with a `Retry-After` header
- Implement via `slowapi` for FastAPI
- Rate limit state stored in Redis (Upstash) in production; in-memory dict for local dev

---

## 7. Issue Code Reference

### 7.1 Phase 1 Issue Codes

Active in the MVP. All are surfaced in the Phase 1 results dashboard and CSV export.

| Code | Category | Severity | Description | Recommendation |
|---|---|---|---|---|
| `TITLE_MISSING` | metadata | critical | Page has no `<title>` tag | Add a unique title tag between 30–60 characters that clearly describes this page. |
| `TITLE_DUPLICATE` | metadata | warning | Same title used on multiple pages | Make each page title unique. Describe what makes this page different from others on your site. |
| `TITLE_TOO_SHORT` | metadata | warning | Title under 30 characters | Expand the title to 30–60 characters. Include your organisation name and the page topic. |
| `TITLE_TOO_LONG` | metadata | warning | Title over 60 characters | Shorten the title to under 60 characters. Google truncates longer titles in search results. |
| `META_DESC_MISSING` | metadata | critical | No meta description | Add a meta description of 70–160 characters summarising what visitors will find on this page. |
| `META_DESC_DUPLICATE` | metadata | warning | Same meta description on multiple pages | Write a unique meta description for this page that reflects its specific content. |
| `META_DESC_TOO_SHORT` | metadata | warning | Meta description under 70 characters | Expand the description to 70–160 characters to give search engines more context. |
| `META_DESC_TOO_LONG` | metadata | warning | Meta description over 160 characters | Shorten the description to under 160 characters. Longer descriptions are cut off in search results. |
| `OG_TITLE_MISSING` | metadata | info | Open Graph title tag missing | Add an `og:title` meta tag. This controls how your page title appears when shared on social media. |
| `OG_DESC_MISSING` | metadata | info | Open Graph description tag missing | Add an `og:description` meta tag. This controls the description shown when your page is shared on social media. |
| `CANONICAL_MISSING` | metadata | warning | No canonical tag — page has query strings or is a near-duplicate | Add a canonical tag pointing to the preferred URL for this page to prevent duplicate content issues. |
| `CANONICAL_EXTERNAL` | metadata | warning | Canonical points to a different domain | Review this canonical tag — it is pointing search engines to a page on a different website. |
| `FAVICON_MISSING` | metadata | info | No favicon found (homepage only) | Add a favicon to your site. This small icon appears in browser tabs and bookmarks and reinforces your brand. |
| `H1_MISSING` | heading | critical | No H1 tag found on page | Add a single H1 heading that clearly states the main topic of this page. |
| `H1_MULTIPLE` | heading | warning | More than one H1 on the page | Remove extra H1 tags. Each page should have exactly one H1 that introduces the main topic. |
| `HEADING_SKIP` | heading | warning | Heading levels skip (e.g., H1 → H3) | Fix the heading structure so levels are not skipped. Use H1, then H2, then H3 in order. |
| `BROKEN_LINK_404` | broken_link | critical | Link destination returns 404 Not Found | Remove or update this link. The page it points to no longer exists. |
| `BROKEN_LINK_410` | broken_link | critical | Link destination returns 410 Gone | Remove this link. The destination has been permanently removed. |
| `BROKEN_LINK_5XX` | broken_link | critical | Link destination returns a server error | Check whether the linked site is down. If the problem persists, remove or replace the link. |
| `REDIRECT_301` | redirect | info | Page returns a permanent redirect | Update any internal links pointing here to use the final destination URL directly. |
| `REDIRECT_302` | redirect | warning | Page returns a temporary redirect | Confirm whether this redirect is intentional. If permanent, change it to a 301 redirect. |
| `REDIRECT_CHAIN` | redirect | warning | Page involves a multi-hop redirect chain | Consolidate the redirect chain to a single direct redirect to the final destination. |
| `REDIRECT_LOOP` | redirect | critical | Redirect loop detected | Fix the redirect configuration immediately. This page cannot load and is invisible to search engines. |
| `LOGIN_REDIRECT` | crawlability | info | Page redirects to a login screen | This page requires a login to access. The crawler cannot audit it. Review manually if needed. |
| `ROBOTS_BLOCKED` | crawlability | warning | Page blocked by robots.txt | Check whether this page should be blocked. If not, update your robots.txt file. |
| `NOINDEX_META` | crawlability | warning | Page has a noindex meta tag | Confirm whether this page should be excluded from search results. Remove the noindex tag if not. |
| `NOINDEX_HEADER` | crawlability | warning | Page has a noindex HTTP header | Check your server configuration. This page is being hidden from search engines via an HTTP header. |
| `NOT_IN_SITEMAP` | crawlability | info | Crawlable page not listed in sitemap | Add this URL to your XML sitemap so search engines can find it more reliably. |
| `SITEMAP_MISSING` | sitemap | info | No sitemap found for this domain | Create an XML sitemap and submit it to Google Search Console. Most CMS platforms can generate one automatically. |
| `TITLE_META_DUPLICATE_PAIR` | duplicate | warning | Both title and meta description duplicated on another page | This page and another share identical title and meta description. Update both to be unique. |

### 7.2 Phase 2 Issue Codes

Collected during Phase 1 crawl (fields stored in DB) but only surfaced in the UI and CSV after Phase 2 is released.

| Code | Category | Severity | Description | Recommendation |
|---|---|---|---|---|
| `IMG_ALT_MISSING` | image | warning | Image missing alt attribute | Add an alt attribute to this image describing what it shows. This helps screen readers and search engines. |
| `IMG_ALT_EMPTY` | image | info | Image has empty alt attribute | If this image conveys meaning, add descriptive alt text. If purely decorative, an empty alt is acceptable. |
| `IMG_OVERSIZED` | image | warning | Image file size exceeds 200KB | Compress or resize this image to improve page load speed. |
| `PAGE_TOO_LARGE` | performance | warning | HTML response size exceeds 500KB | Review this page for unnecessary inline content, scripts, or styles that can be moved to external files. |
| `EXCESSIVE_EXTERNAL_DEPS` | performance | warning | More than 10 external scripts or stylesheets | Reduce the number of third-party scripts and stylesheets to improve page load speed. |
| `NO_VIEWPORT_META` | mobile | warning | Viewport meta tag missing | Add `<meta name="viewport" content="width=device-width, initial-scale=1">` to make this page mobile-friendly. |
| `NO_SCHEMA` | schema | info | No structured data found on page | Consider adding schema markup (e.g., Organization or Event) to help search engines understand your content. |

---

## 8. Logging

Structured logging is essential for debugging failed crawl jobs in production. All log output is written to **stdout** (Vercel streams stdout to its deployment dashboard automatically).

### 8.1 Log Format

Use structured JSON logging via Python's `logging` module with `python-json-logger`:

```json
{
  "timestamp": "2026-04-07T10:05:23Z",
  "level": "INFO",
  "job_id": "3fa85f64-...",
  "url": "https://livingsystems.ca/about-us/",
  "event": "page_crawled",
  "status_code": 200,
  "response_ms": 312
}
```

### 8.2 Log Events to Capture

| Event | Level | When |
|---|---|---|
| `job_started` | INFO | Crawl job begins |
| `job_completed` | INFO | Crawl job finishes successfully |
| `job_failed` | ERROR | Crawl job encounters unrecoverable error |
| `job_cancelled` | INFO | User cancels a running job |
| `page_crawled` | INFO | Each page successfully fetched |
| `page_error` | WARNING | Page fetch failed (timeout, connection error) |
| `page_skipped` | INFO | Page skipped (robots, admin path, login redirect) |
| `redirect_detected` | INFO | Redirect encountered, with chain detail |
| `external_link_checked` | DEBUG | External link status checked |
| `external_cap_reached` | WARNING | External link cap hit for a page or job |
| `sitemap_loaded` | INFO | Sitemap successfully parsed, URL count included |
| `sitemap_not_found` | WARNING | No sitemap discovered |
| `robots_loaded` | INFO | robots.txt successfully parsed |
| `robots_not_found` | WARNING | No robots.txt found |
| `query_variant_cap` | WARNING | URL query variant cap reached for a path |
| `rate_limit_hit` | WARNING | Request rejected due to rate limiting |

### 8.3 Log Levels

- **DEBUG** — verbose detail; disabled in production by default
- **INFO** — normal operational events; always on
- **WARNING** — unexpected but recoverable conditions; always on
- **ERROR** — unrecoverable failures; always on

Control via `LOG_LEVEL` environment variable (default: `INFO`).

---

## 9. Environment Variables

All time-based variables use a consistent suffix convention: `_MS` for milliseconds, `_S` for seconds, `_DAYS` for days.

### 9.1 Required

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Connection string for the data store | `sqlite:///./crawldb.sqlite` (dev) / Upstash Redis URL (prod) |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | `https://yourcrawler.vercel.app,https://yoursite.ca` |
| `CRAWLER_USER_AGENT` | User-Agent string sent with all crawl requests | `NonprofitCrawler/1.0 (+https://yourcrawler.vercel.app)` |

### 9.2 Optional / Defaults

| Variable | Unit | Description | Default |
|---|---|---|---|
| `MAX_PAGES_PER_CRAWL` | count | Hard cap on pages per crawl job | `500` |
| `DEFAULT_CRAWL_DELAY_MS` | ms | Default delay between requests | `500` |
| `MIN_CRAWL_DELAY_MS` | ms | Minimum delay users can set | `200` |
| `CRAWL_REQUEST_TIMEOUT_S` | s | Per-request HTTP timeout | `5` |
| `MAX_EXTERNAL_LINKS_PER_PAGE` | count | External link check cap per page | `50` |
| `MAX_EXTERNAL_LINKS_PER_JOB` | count | External link check cap per crawl job | `500` |
| `MAX_QUERY_VARIANTS_PER_PATH` | count | Max unique query string variants per path | `50` |
| `MAX_CONCURRENT_CRAWLS_PER_IP` | count | Rate limit: max active jobs per IP | `3` |
| `MAX_CRAWLS_PER_HOUR_PER_IP` | count | Rate limit: hourly crawl cap per IP | `10` |
| `RESULT_TTL_DAYS` | days | Days before crawl results are purged | `7` |
| `LOG_LEVEL` | — | Logging verbosity | `INFO` |

### 9.3 Future / Phase 3

| Variable | Description |
|---|---|
| `AUTH_TOKEN` | Simple passphrase token for protecting the crawl endpoint |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | Email credentials for scheduled crawl alerts |

---

## 10. Dependency Stubs

### 10.1 `requirements.txt`

```
# Web framework
fastapi>=0.110.0
uvicorn[standard]>=0.29.0

# HTTP client — also used as async test client via httpx.AsyncClient
httpx>=0.27.0

# HTML parsing
beautifulsoup4>=4.12.0
lxml>=5.2.0

# Logging
python-json-logger>=2.0.7

# Rate limiting
slowapi>=0.1.9

# Environment variables
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

### 10.2 `frontend/package.json` dependencies

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.2.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

### 10.3 `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`)

`pytest-asyncio` requires an explicit mode declaration. Set `asyncio_mode = "auto"` so async test functions are discovered and run without per-function decorators:

```ini
[pytest]
asyncio_mode = auto
```

Or in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 11. Deployment Configuration

### 11.1 `vercel.json`

Vercel requires explicit routing configuration to forward API requests from the frontend domain to the FastAPI backend. Place this file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "frontend/package.json",
      "use": "@vercel/static-build",
      "config": { "distDir": "dist" }
    },
    {
      "src": "api/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "api/main.py"
    },
    {
      "src": "/(.*)",
      "dest": "frontend/$1"
    }
  ]
}
```

**Notes:**
- The FastAPI app entry point is expected at `api/main.py`
- The React frontend build output is expected at `frontend/dist`
- All `/api/*` requests are proxied to FastAPI; all other requests serve the React SPA
- Vercel's Python runtime supports FastAPI via ASGI — no additional adapter needed
- Update `ALLOWED_ORIGINS` in Vercel environment settings after first deployment to include the assigned `.vercel.app` domain

### 11.2 Vercel Environment Variables

After deploying, set all required environment variables (Section 9.1) in the Vercel dashboard under **Project → Settings → Environment Variables**. Set `DATABASE_URL` to the Upstash Redis connection string for production.

---

## 12. Local Development Setup

### 12.1 Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### 12.2 Backend Setup

```bash
git clone https://github.com/your-org/nonprofit-crawler.git
cd nonprofit-crawler

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your local values

uvicorn api.main:app --reload --port 8000
```

Backend available at `http://localhost:8000`.
Interactive API docs at `http://localhost:8000/docs`.

### 12.3 Frontend Setup

```bash
cd frontend
npm install

cp .env.example .env.local
# Set VITE_API_URL=http://localhost:8000 in .env.local

npm run dev
```

Frontend available at `http://localhost:5173`.

### 12.4 Running Tests

```bash
# From project root with venv active
pytest tests/ -v
```

### 12.5 `.env.example`

```
DATABASE_URL=sqlite:///./crawldb.sqlite
ALLOWED_ORIGINS=http://localhost:5173
CRAWLER_USER_AGENT=NonprofitCrawler/1.0-dev
LOG_LEVEL=DEBUG
MAX_PAGES_PER_CRAWL=500
DEFAULT_CRAWL_DELAY_MS=500
MIN_CRAWL_DELAY_MS=200
CRAWL_REQUEST_TIMEOUT_S=5
MAX_EXTERNAL_LINKS_PER_PAGE=50
MAX_EXTERNAL_LINKS_PER_JOB=500
MAX_QUERY_VARIANTS_PER_PATH=50
MAX_CONCURRENT_CRAWLS_PER_IP=3
MAX_CRAWLS_PER_HOUR_PER_IP=10
RESULT_TTL_DAYS=7
```

---

## 13. Robots.txt & Crawl Ethics

- Always fetch and parse `robots.txt` before starting a crawl
- Honour `Disallow` rules by default (configurable override for site owners auditing their own site)
- Respect `Crawl-delay` directive in `robots.txt` if present and higher than the configured default
- Minimum crawl delay: 200ms — users can increase, not decrease below this
- Identify the crawler clearly in the User-Agent string — include a URL where the tool is described
- Do not store or expose any personal data discovered during crawl
- Display a usage notice in the UI: "This tool is intended for use on websites you own or have permission to audit"

---

## 14. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Crawl speed | ~2 pages/second (with 500ms delay) |
| Max pages (MVP) | 500 pages per crawl |
| Availability | 99% uptime (Vercel SLA) |
| Response time (API status polls) | <500ms |
| Per-request HTTP timeout | 5 seconds |
| Results pagination | 50 issues per page, max 100 |
| Frontend polling interval | 2s for first 60s, then 5s |
| Data retention | 7 days, then purged |
| Browser support | Chrome, Firefox, Safari, Edge (last 2 versions) |
| Mobile responsive | Yes — tablet minimum |
| Accessibility | WCAG 2.1 AA where feasible |
| Rate limiting | 3 concurrent / 10 per hour per IP |

---

## 15. Phased Development Roadmap

### Phase 1 — MVP (Weeks 1–4)
- [ ] Project scaffold: repo, `api/` and `frontend/` directories, `vercel.json`, `.env.example`, `pytest.ini`
- [ ] Backend crawler engine (Python, httpx, lxml, BeautifulSoup4, FastAPI)
- [ ] Async job queue with polling
- [ ] Domain boundary and URL normalisation logic (including query string deduplication)
- [ ] robots.txt and sitemap parsing (index files, gzip support)
- [ ] Admin/login path skip logic (Section 2.9)
- [ ] External link checking with per-page and per-job caps (Section 2.8)
- [ ] Scoped canonical tag checking (Section 3.1.2)
- [ ] Phase 1 checks: broken links, metadata (OG tags as info, favicon on homepage only), headings, redirects, crawlability, duplicates
- [ ] Paginated results endpoint with summary + per-category filtering + INVALID_CATEGORY validation
- [ ] Cancel endpoint with JOB_ALREADY_COMPLETE error
- [ ] Rate limiting middleware
- [ ] Standardised API error responses (all codes in Section 6.5)
- [ ] Structured JSON logging to stdout
- [ ] Environment variable configuration and `.env.example`
- [ ] `requirements.txt` and `package.json` with pinned baseline dependencies
- [ ] React frontend: URL entry, progress bar (indeterminate when pages_total unknown, 2s/5s polling), results dashboard (tabbed, paginated, filterable by severity), recommendation copy
- [ ] CSV export (with Phase column)
- [ ] Unit tests: URL normalisation, query string deduplication, redirect chain detection, canonical scoping logic, issue code generation, sitemap parsing, favicon homepage-only scoping
- [ ] Deployed on Vercel with `vercel.json` routing
- [ ] End-to-end test against livingsystems.ca

### Phase 2 — Extended Checks (Weeks 5–8)
- [ ] Internal link analysis and orphan page detection
- [ ] Configurable admin path skip list via UI
- [ ] Schema markup detection
- [ ] Image alt text and file size analysis
- [ ] Mobile viewport check
- [ ] Performance signals (PAGE_TOO_LARGE, EXCESSIVE_EXTERNAL_DEPS)
- [ ] Phase 2 issue codes surfaced in results UI and CSV
- [ ] Schema and performance added to results summary by_category
- [ ] PDF summary export

### Phase 3 — Productisation (Weeks 9–12)
- [ ] Simple auth token to gate crawl endpoint
- [ ] User accounts and saved crawl history
- [ ] Scheduled crawls with email alerts
- [ ] Crawl comparison (before/after diff)
- [ ] White-label mode (env-variable-driven theming, per-tenant Vercel deployments)
- [ ] Migration to AWS if Vercel limits are reached
- [ ] Public landing page and onboarding for other nonprofits

---

## 16. Tech Stack Summary

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | React + Vite + Tailwind CSS | Fast, lightweight, Vercel-native |
| Backend | Python + FastAPI | Excellent for async I/O, crawler libraries |
| HTTP Client | httpx (async) | Native async; doubles as pytest async test client |
| HTML Parser | BeautifulSoup4 + lxml | lxml is faster and more lenient on malformed HTML |
| Rate Limiting | slowapi | Lightweight, Redis-backed |
| Logging | python-json-logger | Structured JSON logs, Vercel stdout-compatible |
| Job Queue | FastAPI BackgroundTasks → Celery + Redis | Start simple, scale when needed |
| Data Store | SQLite (dev) → Upstash Redis / PlanetScale | Serverless-friendly |
| Hosting | Vercel (frontend + serverless functions) | Zero infra to start |
| Routing | vercel.json | Proxies /api/* to FastAPI, serves SPA otherwise |
| Export | Python csv module | No additional dependencies |
| Testing | pytest + pytest-asyncio (auto mode) | Standard Python; async-capable |
| Future | AWS Lambda + S3 + RDS | If Vercel limits are hit |

---

## 17. Open Questions — With Recommendations

These decisions should be made before handing the spec to Claude Code. A recommendation is provided for each based on the project's goals: start lean, validate quickly, avoid premature infrastructure.

---

**1. Data persistence: SQLite for local dev only, then migrate to Upstash Redis for production — or use Upstash from day one?**

**Recommendation: SQLite for dev, Upstash Redis for production from day one.**
Use SQLite locally — it requires zero setup and is ideal for early iteration. But configure Upstash Redis as the production data store from the first Vercel deployment. Upstash has a generous free tier (10,000 commands/day), is serverless-native, and avoids a disruptive migration later. The `DATABASE_URL` env var makes switching transparent in code.

---

**2. Vercel timeout strategy: Accept Vercel Pro (30s timeout) or implement chunked batch crawling from the start to support Hobby tier?**

**Recommendation: Start on Vercel Pro.**
Vercel Pro is $20/month and gives 30-second function timeouts, which is workable for small nonprofit sites. Chunked batch crawling is significantly more complex to implement correctly and is premature for an MVP targeting sites under 500 pages. Upgrade to chunked processing only if crawl jobs regularly exceed the 30-second window in practice. If cost is a concern, revisit after the first 3 months of real usage.

---

**3. Crawl engine: Proceed with `httpx` + `BeautifulSoup4` + `lxml`, or scaffold with `Scrapy` for better long-term scalability?**

**Recommendation: `httpx` + `BeautifulSoup4` + `lxml`.**
Scrapy is a mature, powerful framework but adds significant complexity — a separate process model, its own middleware and pipeline architecture, and a steep learning curve for maintenance. For a tool targeting sites under 500 pages, `httpx` + `BeautifulSoup4` is more than sufficient and keeps the codebase simple enough for solo maintenance. Migrate to Scrapy only if crawl speed or concurrency becomes a documented bottleneck.

---

**4. Auth: Completely open for MVP, or add a simple `AUTH_TOKEN` passphrase from day one?**

**Recommendation: Add AUTH_TOKEN from day one.**
An open endpoint on Vercel means anyone who finds the URL can trigger crawls of arbitrary third-party sites on your infrastructure. Even a simple bearer token check (`Authorization: Bearer <token>`) in the FastAPI middleware costs less than an hour to implement and prevents abuse before you're ready to go public. Set a strong token in the Vercel environment variables and embed it in the frontend at build time via `VITE_AUTH_TOKEN`. This is not user authentication — just a deployment gate. Remove or replace it with proper auth in Phase 3.

---

**5. Sitemap field in UI: Always show the sitemap URL input, or hide it until auto-discovery fails?**

**Recommendation: Always show it, pre-populated on success.**
Non-technical nonprofit staff won't know what a sitemap is or whether auto-discovery worked if the field is hidden. Showing the field always — with a helpful label like "Sitemap URL (optional — we'll find it automatically)" and pre-populating it when auto-discovery succeeds — builds transparency and lets users override if needed. It also surfaces the sitemap URL as a useful reference in itself.

---

**6. Result storage duration: 7-day TTL, or keep results indefinitely while the dataset is small in MVP?**

**Recommendation: 7-day TTL from day one.**
Even in MVP with a small dataset, setting a TTL establishes the right operational habit and prevents the data store from growing unbounded if the tool gets shared with other nonprofits before Phase 3 is ready. Upstash Redis makes TTL trivial to implement. If a user needs results longer than 7 days, the CSV export covers that need.

---

**7. Phase 2 field collection in Phase 1: Collect and store Phase 2 fields during Phase 1 crawl, suppress from UI until Phase 2?**

**Recommendation: Yes — collect all fields from day one.**
Collecting `has_viewport_meta`, `schema_types`, `external_script_count`, and `external_stylesheet_count` during the Phase 1 crawl adds negligible overhead per page (all are simple BeautifulSoup selectors). Storing them in the DB from the start means Phase 2 is a UI and reporting change only — no re-crawl required, no schema migration. This significantly reduces the effort and risk of the Phase 2 release.

---

*Spec v1.4 — prepared for handoff to Claude Code. All Phase 1 features are in scope for the initial implementation sprint. Resolve Open Questions (Section 17) before beginning.*
