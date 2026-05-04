# TalkingToad — Extension Spec v1.5

> **Status:** Planned — not yet implemented.
> **Parent spec:** `nonprofit-crawler-spec-v1.4.md` (source of truth for all existing behaviour).
> This document defines new checks and data fields identified through gap analysis against Screaming Frog SEO Spider. All additions are backward-compatible with the v1.4 data model unless noted.

---

## §E1 — Security Checks (new category: `security`)

These checks are detectable from HTTP response headers and HTML content alone — no browser rendering required.

### E1.1 HTTP Page (`HTTP_PAGE`)

| Field       | Value |
|-------------|-------|
| Code        | `HTTP_PAGE` |
| Category    | `security` |
| Severity    | `critical` |
| Description | Page is served over HTTP, not HTTPS |
| Recommendation | Migrate to HTTPS and configure a server-side 301 redirect from HTTP to HTTPS |

**Detection logic:** If the crawled URL scheme is `http://` (after following all redirects to the final URL), emit this issue. Do not emit if the HTTP page redirects to an HTTPS URL (that case is already covered by redirect issues).

---

### E1.2 Mixed Content (`MIXED_CONTENT`)

| Field       | Value |
|-------------|-------|
| Code        | `MIXED_CONTENT` |
| Category    | `security` |
| Severity    | `warning` |
| Description | HTTPS page loads resources over HTTP |
| Recommendation | Update all resource URLs to use HTTPS. Check images, scripts, stylesheets, and iframes |

**Detection logic:** For pages served over HTTPS, scan the HTML for any `src` or `href` attribute values that begin with `http://` on the following elements: `<img>`, `<script>`, `<link rel="stylesheet">`, `<iframe>`. Emit once per page (not once per resource). Store the count of mixed-content resources in `Issue.extra["mixed_count"]`.

---

### E1.3 Missing HSTS Header (`MISSING_HSTS`)

| Field       | Value |
|-------------|-------|
| Code        | `MISSING_HSTS` |
| Category    | `security` |
| Severity    | `info` |
| Description | HTTPS page is missing the Strict-Transport-Security header |
| Recommendation | Add `Strict-Transport-Security: max-age=31536000; includeSubDomains` to all HTTPS responses. Configure in your web server or CDN |

**Detection logic:** For HTTPS pages only, check the response headers for the presence of `strict-transport-security`. Emit if absent. Only check on the homepage and first 10 unique subdomains/paths to avoid noise (once per host is sufficient).

**Scoping:** Emit once per unique host (not once per page).

---

### E1.4 Unsafe Cross-Origin Link (`UNSAFE_CROSS_ORIGIN_LINK`)

| Field       | Value |
|-------------|-------|
| Code        | `UNSAFE_CROSS_ORIGIN_LINK` |
| Category    | `security` |
| Severity    | `info` |
| Description | External link opens in a new tab without `rel="noopener"` or `rel="noreferrer"` |
| Recommendation | Add `rel="noopener noreferrer"` to all `<a target="_blank">` links pointing to external URLs |

**Detection logic:** During HTML parsing, for each `<a>` tag where `target="_blank"` and `href` is an external URL, check the `rel` attribute. Emit if neither `noopener` nor `noreferrer` is present. Emit once per page (not once per link). Store the count in `Issue.extra["unsafe_link_count"]`.

---

## §E2 — URL Structure Checks (new category: `url_structure`)

These checks examine the URL string itself — no fetching required beyond what the crawler already does.

### E2.1 Uppercase URL (`URL_UPPERCASE`)

| Field       | Value |
|-------------|-------|
| Code        | `URL_UPPERCASE` |
| Category    | `url_structure` |
| Severity    | `warning` |
| Description | URL path contains uppercase characters |
| Recommendation | Use lowercase-only URLs. Redirect uppercase variants to the lowercase canonical URL |

**Detection logic:** After normalising the URL, check `urlparse(url).path` for any character in `A-Z`. Do not check the scheme or host (already lowercased by the normaliser).

---

### E2.2 URL Contains Spaces (`URL_HAS_SPACES`)

| Field       | Value |
|-------------|-------|
| Code        | `URL_HAS_SPACES` |
| Category    | `url_structure` |
| Severity    | `warning` |
| Description | URL contains encoded spaces (`%20`) |
| Recommendation | Replace spaces in URLs with hyphens |

**Detection logic:** Check if `%20` or `+` (as space) appears in the URL path or query string.

---

### E2.3 URL Contains Underscores (`URL_HAS_UNDERSCORES`)

| Field       | Value |
|-------------|-------|
| Code        | `URL_HAS_UNDERSCORES` |
| Category    | `url_structure` |
| Severity    | `info` |
| Description | URL path uses underscores instead of hyphens |
| Recommendation | Use hyphens as word separators in URL paths. Google treats underscores as word-joiners, not separators |

**Detection logic:** Check if `_` appears in `urlparse(url).path`.

---

### E2.4 URL Too Long (`URL_TOO_LONG`)

| Field       | Value |
|-------------|-------|
| Code        | `URL_TOO_LONG` |
| Category    | `url_structure` |
| Severity    | `info` |
| Description | URL exceeds 115 characters |
| Recommendation | Shorten the URL slug. Long URLs are harder to share and may be truncated in search results |

**Detection logic:** If `len(url) > 115`, emit this issue.

---

## §E3 — Pagination Links (`PAGINATION_LINKS_PRESENT`)

| Field       | Value |
|-------------|-------|
| Code        | `PAGINATION_LINKS_PRESENT` |
| Category    | `metadata` |
| Severity    | `info` |
| Description | Page declares `rel="next"` or `rel="prev"` pagination link elements |
| Recommendation | No action required. Pagination signals are informational. Ensure the linked pages are crawlable |

**Detection logic:** During HTML parsing, scan `<link rel="next" ...>` and `<link rel="prev" ...>` in `<head>`. If either is present, emit `PAGINATION_LINKS_PRESENT` as an informational data point. Store the href values in `Issue.extra["next"]` and `Issue.extra["prev"]`.

**Data field:** Add `pagination_next: str | None` and `pagination_prev: str | None` to `ParsedPage` and `CrawledPage`.

---

## §E4 — Meta Refresh Redirect (`META_REFRESH_REDIRECT`)

| Field       | Value |
|-------------|-------|
| Code        | `META_REFRESH_REDIRECT` |
| Category    | `redirect` |
| Severity    | `warning` |
| Description | Page uses a `<meta http-equiv="refresh">` tag to redirect users |
| Recommendation | Replace meta refresh redirects with server-side 301 redirects. Meta refresh causes a delay, can confuse users, and is poor for SEO |

**Detection logic:** Scan `<meta http-equiv="refresh">` tags in `<head>`. If found, parse the `content` attribute. If it contains `url=` (case-insensitive), the tag is being used as a redirect — emit the issue. Store the target URL in `Issue.extra["refresh_url"]` and the delay in seconds in `Issue.extra["delay_seconds"]`.

If `content` is just a number with no URL (e.g., `<meta http-equiv="refresh" content="30">`), this is a page-reload, not a redirect — do not emit an issue.

---

## §E5 — Content Quality (`THIN_CONTENT`)

| Field       | Value |
|-------------|-------|
| Code        | `THIN_CONTENT` |
| Category    | `metadata` |
| Severity    | `warning` |
| Description | Page has fewer than 300 words of body content |
| Recommendation | Expand the page content to at least 300 words. Thin pages are less likely to rank well and may not provide enough value to users |

**Detection logic:** Extract all visible text from the `<body>` element (excluding `<nav>`, `<header>`, `<footer>`, `<aside>`, `<script>`, `<style>` tags). Split by whitespace and count tokens. If `word_count < 300`, emit this issue.

**Exclusions:** Do not emit for:
- Pages with `noindex` meta robots (they're already flagged or intentionally hidden)
- Non-HTML pages (PDFs, images)
- Pages where `word_count == 0` (likely parsing failure or intentional single-element pages)

**Data field:** Add `word_count: int | None` to `ParsedPage` and `CrawledPage`. Store on all HTML pages regardless of whether the issue is emitted.

---

## §E6 — AMP HTML Link (`AMPHTML_BROKEN`)

| Field       | Value |
|-------------|-------|
| Code        | `AMPHTML_BROKEN` |
| Category    | `metadata` |
| Severity    | `warning` |
| Description | Page declares an AMP version via `<link rel="amphtml">` but the AMP URL returns a non-200 status |
| Recommendation | Fix the AMP URL or remove the `amphtml` link element if AMP is no longer in use |

**Detection logic:** Scan `<link rel="amphtml" href="...">` in `<head>`. If found:
1. Store the `href` value in `CrawledPage.amphtml_url`.
2. After the main crawl loop, fetch each unique `amphtml` URL discovered (HEAD request, same external-link logic). If the response status is not 200, emit `AMPHTML_BROKEN` with `Issue.extra["amphtml_url"]` and `Issue.extra["amp_status"]`.

**Data field:** Add `amphtml_url: str | None` to `ParsedPage` and `CrawledPage`.

---

## §E7 — Crawl Depth (`HIGH_CRAWL_DEPTH`)

| Field       | Value |
|-------------|-------|
| Code        | `HIGH_CRAWL_DEPTH` |
| Category    | `crawlability` |
| Severity    | `warning` |
| Description | Page is more than 4 clicks from the homepage |
| Recommendation | Improve internal linking so this page can be reached in 3 clicks or fewer from the homepage |

**Detection logic:** Track crawl depth during the BFS queue traversal. When a URL is discovered from a parent page, its depth = parent depth + 1. The homepage has depth 0. When a page's depth exceeds 4, emit `HIGH_CRAWL_DEPTH` with `Issue.extra["crawl_depth"]`.

**Data field:** Add `crawl_depth: int | None` to `ParsedPage` and `CrawledPage`.

**Implementation note:** Depth tracking requires storing `{url: depth}` alongside the queue. Use a `deque` of `(url, depth)` tuples instead of plain URLs, or maintain a parallel `dict[str, int]` of `url → depth`.

**Sitemap-seeded URLs:** Pages seeded from the sitemap (not discovered via HTML links) have an unknown depth. Assign them an initial depth of `None`; if the engine later reaches them through HTML links, the recorded depth is from that discovery. If they are only reachable via sitemap seeding, leave `crawl_depth = None` and do not emit `HIGH_CRAWL_DEPTH`.

---

## §E8 — Phase 2 / Future Items

The following items were identified in the gap analysis but are deferred to Phase 2 or later. They are listed here so they are not forgotten.

| # | Item | Rationale |
|---|------|-----------|
| 8.1 | `Last-Modified` header → `STALE_CONTENT` (info, >2 years) | Easy to collect; low priority for nonprofits |
| 8.2 | H2 tag extraction and duplicate H2 checks | Lower priority than H1; already stored in `headings_outline` |
| 8.3 | `is_nofollow` on individual `Link` records | Useful for link equity analysis; Phase 2 |
| 8.4 | Inlink / outlink counts pre-computed on `CrawledPage` | Avoids expensive joins; Phase 2 data model update |
| 8.5 | Text ratio (text bytes ÷ total HTML bytes) | Data field only; low actionability for nonprofits |
| 8.6 | Readability / Flesch score | Nice to have; low priority |

---

## §E9 — Issue Category Registry Update

Add the following to the Phase 1 category list (alongside existing: `broken_link`, `metadata`, `heading`, `redirect`, `crawlability`, `duplicate`, `sitemap`):

- `security` — new category for §E1 checks
- `url_structure` — new category for §E2 checks

Both categories must be:
- Included in `PHASE_1_CATEGORIES` in `api/models/issue.py`
- Displayed as tabs in the frontend Results dashboard
- Exportable via the CSV endpoint with category filtering

---

## §E10 — Data Model Changes

### `ParsedPage` additions (`api/crawler/parser.py`)

```python
word_count: int | None = None           # §E5
crawl_depth: int | None = None          # §E7
pagination_next: str | None = None      # §E3
pagination_prev: str | None = None      # §E3
amphtml_url: str | None = None          # §E6
```

### `CrawledPage` additions (`api/models/page.py`)

Same five fields as `ParsedPage` above, stored in the database.

### SQLite schema additions

```sql
ALTER TABLE crawled_pages ADD COLUMN word_count INTEGER;
ALTER TABLE crawled_pages ADD COLUMN crawl_depth INTEGER;
ALTER TABLE crawled_pages ADD COLUMN pagination_next TEXT;
ALTER TABLE crawled_pages ADD COLUMN pagination_prev TEXT;
ALTER TABLE crawled_pages ADD COLUMN amphtml_url TEXT;
```

### Engine queue change (`api/crawler/engine.py`)

Change `queue: deque[str]` to `queue: deque[tuple[str, int | None]]` (url, depth) to support crawl depth tracking (§E7).
