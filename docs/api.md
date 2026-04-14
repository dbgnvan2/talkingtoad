# API Reference

Base URL: `https://yourcrawler.vercel.app` (prod) / `http://localhost:8000` (dev)

All POST/PATCH requests require `Content-Type: application/json`.
All endpoints require `Authorization: Bearer <token>`.

---

## Crawl Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/crawl/start` | Submit a new crawl job. Returns `job_id`. |
| POST | `/api/crawl/scan-page?url={url}` | Fetch and analyse a single URL synchronously. Returns `job_id` immediately. |
| GET | `/api/crawl/{job_id}/status` | Poll job progress and status. |
| POST | `/api/crawl/{job_id}/cancel` | Cancel a running crawl. |
| GET | `/api/crawl/{job_id}/results` | Retrieve paginated results. |
| GET | `/api/crawl/{job_id}/results/{category}` | Results filtered by category. |
| POST | `/api/crawl/{job_id}/rescan-url?url={url}` | Re-fetch a single page, rerun checks, update stored issues. Sends cache-bypass headers. |

## Export

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/crawl/{job_id}/export/csv` | Full results as CSV. |
| GET | `/api/crawl/{job_id}/export/csv/{category}` | Category results as CSV. |

## Fix Manager (WordPress integration)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/fixes/generate/{job_id}` | Connect to WordPress, generate proposed fixes from crawl issues. |
| GET | `/api/fixes/{job_id}` | List all fixes for a job (pending, approved, applied, skipped, failed). |
| PATCH | `/api/fixes/{fix_id}` | Update a single fix — change `proposed_value` or `status`. |
| POST | `/api/fixes/apply/{job_id}` | Apply all approved fixes to WordPress. Stops on first failure. |
| DELETE | `/api/fixes/{job_id}` | Delete all fixes for a job (to regenerate from scratch). |

### Heading Fix Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/fixes/analyze-heading-sources?page_url={url}&job_id={id}` | Identify where each heading lives (post content, widget, theme, etc.) |
| POST | `/api/fixes/heading-to-bold?page_url={url}&heading_text={text}&level={n}` | Convert a heading to bold text. Level 1-6, default 4. |
| POST | `/api/fixes/change-heading-level?page_url={url}&heading_text={text}&from_level={n}&to_level={n}` | Change a heading from one level to another (H1-H6). |
| GET | `/api/fixes/find-heading?job_id={id}&heading_text={text}&level={n}` | Find all pages containing a specific heading. |
| POST | `/api/fixes/bulk-replace-heading?job_id={id}&heading_text={text}&from_level={n}&to_level={n}` | Change a heading level across all pages in a crawl job. Omit `to_level` to convert to bold. |

## AI Analysis (v1.7 AI-Readiness Module)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/analyze` | Analyze a page using AI and provide remediation suggestions. |

#### Heading source analysis response

```json
{
  "page_url": "https://example.com/about",
  "post_id": 123,
  "post_type": "page",
  "headings": [
    {
      "level": 2,
      "text": "Our Mission",
      "source": "post_content",
      "fixable": true,
      "source_details": { "post_id": 123, "post_type": "page" }
    },
    {
      "level": 1,
      "text": "About Us",
      "source": "unknown",
      "fixable": false,
      "source_details": { "note": "May be in theme template or plugin output" }
    }
  ]
}
```

Heading sources:
- `post_content` — In main post/page content (fixable via API)
- `reusable_block` — In a reusable block/pattern (fixable via API)
- `widget` — In a WordPress widget (edit in WP Admin)
- `acf_field` — In an Advanced Custom Fields field (edit in WP Admin)
- `unknown` — Theme template, plugin output, or shortcode (edit in WP Admin)

### Fix statuses

| Status | Meaning |
|---|---|
| `pending` | Generated, awaiting review |
| `approved` | User has approved this fix for application |
| `applied` | Successfully written to WordPress |
| `failed` | Application attempt failed — `error` field contains details |
| `skipped` | User has chosen not to apply this fix |

### Fix generation request body

```json
{
  "wp_credentials_path": "/path/to/wp-credentials.json"
}
```

The credentials file format:
```json
{
  "site_url": "https://yoursite.com",
  "login_url": "https://yoursite.com/custom-login-path",
  "username": "your-username",
  "password": "your-password"
}
```

### Fix PATCH body

```json
{
  "proposed_value": "Updated page title",
  "status": "approved"
}
```

Only the fields you include are updated.

## Utility

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | `{"status": "ok", "version": "1.7"}` |
| GET | `/api/robots?url={url}` | Fetch and parse robots.txt for a domain. |
| GET | `/api/sitemap?url={url}` | Fetch and parse sitemap(s) for a domain. |
| GET | `/api/utility/generate-llms-txt?job_id={id}` | Generate an /llms.txt file from crawl data. |

---

## Error Codes

| Code | HTTP | Description |
|---|---|---|
| `JOB_NOT_FOUND` | 404 | No job with given `job_id` |
| `JOB_ALREADY_RUNNING` | 409 | Crawl already in progress |
| `JOB_ALREADY_COMPLETE` | 409 | Job finished — cannot cancel |
| `INVALID_URL` | 422 | Malformed or unreachable URL |
| `INVALID_CATEGORY` | 422 | Unrecognised category slug |
| `CRAWL_LIMIT_EXCEEDED` | 429 | Rate limit reached |
| `CRAWL_FAILED` | 500 | Unrecoverable crawler error |
| `TARGET_UNREACHABLE` | 502 | Target website unreachable |

Error response shape:
```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "No crawl job found with the given ID.",
    "http_status": 404
  }
}
```

---

## Valid Category Slugs

`broken_link`, `metadata`, `heading`, `redirect`, `crawlability`, `duplicate`, `sitemap`, `security`, `url_structure`, `ai_readiness`

---

## POST /api/crawl/start — Request Body

```json
{
  "target_url": "https://example.org",
  "settings": {
    "max_pages": 200,
    "crawl_delay_ms": 500,
    "respect_robots": true,
    "skip_wp_archives": true,
    "img_size_limit_kb": 200,
    "enabled_analyses": ["link_integrity", "seo_essentials", "site_structure", "indexability"]
  }
}
```

### Settings fields

| Field | Type | Default | Description |
|---|---|---|---|
| `max_pages` | int | 500 | Maximum internal pages to crawl |
| `crawl_delay_ms` | int | 500 | Milliseconds between requests (min 200) |
| `respect_robots` | bool | true | Whether to honour robots.txt rules |
| `skip_wp_archives` | bool | true | Skip WordPress auto-generated archive/feed/search pages |
| `img_size_limit_kb` | int | 200 | Flag images larger than this many KB as IMG_OVERSIZED |
| `page_size_limit_kb` | int | 300 | Flag HTML pages larger than this many KB as PAGE_SIZE_LARGE |
| `enabled_analyses` | list\|null | null (all) | Restrict which issue categories are checked |
| `suppress_h1_strings` | list[str] | [] | H1 text strings to ignore (exact, case-insensitive) — for theme-injected banner headings |
| `suppress_banner_h1` | bool | false | Auto-detect and ignore H1s that share no words with the page title — handles parent-page banners injected by themes (Salient, Avada, Divi, etc.) without needing explicit strings |

### enabled_analyses groups

| Group | Categories covered |
|---|---|
| `link_integrity` | `broken_link`, `redirect` |
| `seo_essentials` | `metadata`, `duplicate`, `url_structure` |
| `site_structure` | `heading` |
| `indexability` | `crawlability`, `sitemap` |
| `ai_readiness` | `ai_readiness` |

The `security` category always runs regardless of toggles.

---

## GET /api/crawl/{job_id}/results — Summary Shape

```json
{
  "summary": {
    "pages_crawled": 42,
    "pages_with_errors": 3,
    "total_issues": 17,
    "health_score": 74,
    "by_severity": { "critical": 2, "warning": 8, "info": 7 },
    "by_category": { "metadata": 5, "heading": 3, "broken_link": 2 }
  },
  "issues": [
    {
      "code": "TITLE_MISSING",
      "category": "metadata",
      "severity": "critical",
      "description": "Page has no <title> tag",
      "recommendation": "Add a unique title tag...",
      "page_url": "https://example.com/about",
      "impact": 9,
      "effort": 1,
      "priority_rank": 88,
      "human_description": "Missing Name Tag",
      "extra": null
    }
  ]
}
```

`health_score` is 0–100. Formula: `max(0, 100 − Σ issue impacts)` across all issues.

`priority_rank` formula: `(impact × 10) − (effort × 2)`. Higher = fix sooner.

See `nonprofit-crawler-spec-v1.4.md` §6 for full request/response schemas.
