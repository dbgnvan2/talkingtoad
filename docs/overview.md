# TalkingToad — Application Overview

TalkingToad is a web-based SEO audit tool built for nonprofit organisations. It replicates the core functionality of Screaming Frog SEO Spider with no installation, no cost, and output in plain English rather than technical jargon.

---

## What It Does

### 1. Crawl a Website

The user enters a URL and clicks **Start Crawl**. The backend:

1. Fetches and parses `robots.txt` — pages disallowed to crawlers are flagged, not skipped.
2. Discovers and parses the XML sitemap (index files, gzip, and nested sitemaps supported). If no sitemap exists, a `SITEMAP_MISSING` issue is emitted.
3. Checks whether the HTTP version of the site redirects to HTTPS. Flags `HTTPS_REDIRECT_MISSING` if not.
4. Crawls all internal pages breadth-first, following links. Sitemap URLs are also seeded into the queue so pages with no inbound links are still audited.
5. Skips admin paths (`/wp-admin/`, `/wp-login.php`, `/admin/`, login/logout URLs) and optionally WordPress auto-generated noise pages (author archives, category/tag archives, date archives, paginated archives, feed URLs, search result pages).
6. URL-normalises every candidate before queuing (strip tracking params, lowercase scheme+host, remove fragments, strip trailing slashes, cap query-string variants per path at 50).
7. After the internal crawl, checks all external links found (HEAD requests, GET fallback; 50/page cap, 500/job cap). Social media platforms that block bots are noted rather than falsely flagged.
8. Checks for broken images (HEAD requests on image `src` URLs; 200-image cap per job).
9. Checks AMP URLs declared via `<link rel="amphtml">`.
10. Runs cross-page duplicate detection (title duplicates, meta description duplicates, near-duplicate pairs).
11. Detects orphan pages — internal pages with no inbound links from other crawled pages.

### 2. Detect SEO Issues

Issues are detected at three scopes:

| Scope | When | Examples |
|---|---|---|
| Per URL (pre-fetch) | Before fetching | URL_UPPERCASE, URL_TOO_LONG |
| Per page (post-fetch) | After parsing each page | TITLE_MISSING, H1_MISSING, LANG_MISSING |
| Cross-page | After all pages crawled | TITLE_DUPLICATE, ORPHAN_PAGE |

**Active issue categories:** metadata, heading, broken_link, redirect, crawlability, duplicate, sitemap, security, url_structure, ai_readiness.

Every issue has an **impact score** (1–10) and **effort score** (1–5). Priority is `(impact × 10) − (effort × 2)`. The top 5 highest-priority issues per crawl are surfaced in the summary tab.

**Health Score** = `max(0, 100 − Σ issue impacts)` across all issues on the site. Displayed as 0–100.

### 3. AI Readiness Module (v1.7)

Audits how "quotable" and "crawlable" a site is for LLMs and AI agents:
- **llms.txt validation** — Checks for the presence and format of `/llms.txt` as an instruction file for AI.
- **llms.txt generator** — Automatically creates a curated `/llms.txt` file from high-value crawl results.
- **AI Analysis Engine** — Uses Google Gemini or OpenAI to rewrite titles and meta descriptions for AI "quotability" and check semantic alignment of headings.

### 4. WordPress Fix Manager

For WordPress sites, TalkingToad can connect directly and apply fixes:

1. **Authenticate** — cookie-based login via a custom login URL, then fetch the WP REST API nonce from `wp-admin`.
2. **Generate fixes** — for each fixable issue (missing title, meta description, OG tags, noindex), look up the post/page via the REST API and generate a proposed new value.
3. **Review** — the Fix Manager UI shows current values and AI-proposed replacements. The user can edit, approve, or skip each fix individually.
4. **Apply** — approved fixes are written back to WordPress via `PATCH /wp-json/wp/v2/posts/{id}` using the appropriate SEO plugin meta keys (Yoast SEO or Rank Math auto-detected).
5. Stops on the first failure so the user can correct and retry.

### 4. Results Dashboard

The frontend presents results in tabs by issue category. Each tab shows a sortable table of issues with:
- Issue code and plain-English description
- Affected page URL
- Severity badge (critical / warning / info)
- Impact and effort scores
- Direct link to a help article explaining the issue and how to fix it

Additional tabs: **Summary** (health score, top 5 priorities, counts by severity and category), **Fix Manager** (WordPress integration).

### 5. Export

Any results tab can be exported as a CSV file for sharing with a developer or filing in a project tracker.

---

## Issue Checks Performed

### Metadata
- Title missing, too short, too long, duplicate
- Meta description missing, too short, too long, duplicate
- OG title missing, OG description missing
- Title and H1 mismatch (no significant words in common)
- Canonical tag missing (query-string pages and near-duplicates), canonical pointing externally
- Canonical self-referencing tag absent on indexable pages (best practice)
- Language attribute (`<html lang>`) missing
- Favicon missing (homepage only)
- Both title and meta description duplicated across pages

### Headings
- H1 missing
- Multiple H1 tags
- Heading levels skipped (e.g. H1 → H3)

### Broken Links
- External and internal links returning 404, 410, 5xx
- Internal pages returning 4xx (e.g. page was deleted)
- Broken images (image `src` returning 4xx/5xx)
- External links that timed out
- Social/bot-blocked links (info notice, manual verification advised)

### Redirects
- Redirect loops
- Redirect chains (2+ hops)
- Temporary 302 redirects (should be 301 if permanent)
- Internal links pointing to redirecting URLs (update the link)
- Trailing-slash and case-normalisation redirects (handled by CMS — informational)
- Meta refresh redirects (should be server-side 301)

### Crawlability
- Pages blocked by robots.txt
- Pages with noindex meta tag or X-Robots-Tag: noindex header
- Pages that require login
- Pages not in sitemap
- Pages with thin content (< 300 words)
- Pages with high crawl depth (> 4 clicks from homepage)
- Orphan pages (no inbound internal links)
- Viewport meta tag missing (mobile-friendliness)
- Schema markup (JSON-LD or microdata) missing
- Internal links with rel="nofollow" (prevents PageRank flow)
- Empty link anchor text
- Page HTML exceeds 300 KB (configurable per crawl)
- Page timed out during crawl
- PDF files over 10 MB
- Images over 200 KB (file size)
- Broken AMP URLs

### Sitemap
- Sitemap missing entirely
- Crawled pages not listed in sitemap

### Security
- Pages served over HTTP (not HTTPS)
- HTTP version of site not redirected to HTTPS
- Mixed content (HTTP resources on an HTTPS page)
- HSTS header missing on HTTPS pages
- External links opening in new tab without rel="noopener"

### URL Structure
- Uppercase characters in URL path
- Encoded spaces in URL (%20)
- Underscores in URL path (hyphens recommended)
- URLs over 200 characters

### AI Readiness
- Missing or invalid /llms.txt instruction file
- Low semantic density (Text-to-HTML ratio < 10%)
- Missing internal PDF metadata (Title/Subject) for citations
- Missing JSON-LD structured data (AI Knowledge Graph)
- Non-conversational headings (missing question-based subheadings)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python 3.11+ + FastAPI |
| HTTP Client | httpx (async) |
| HTML Parser | BeautifulSoup4 + lxml |
| PDF Parser | pypdf |
| AI Analysis | Google Gemini / OpenAI |
| Data Store | SQLite (dev) / Upstash Redis (prod) |
| Hosting | Vercel (frontend SPA + Python serverless) |
| Auth | Bearer token (`Authorization: Bearer <token>`) |

---

## Crawl Limits and Ethics

- Minimum 200ms delay between requests (configurable, default 500ms)
- Respects `robots.txt` Crawl-delay directive
- Identifies itself via a descriptive User-Agent string
- Max 500 pages per crawl (configurable)
- External link cap: 50 per page, 500 per job
- Image check cap: 200 unique image URLs per job
- Query-string variant cap: 50 unique query strings per path
