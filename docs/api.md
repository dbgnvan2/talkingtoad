---
status: current
last_updated: 2025-01-XX
api_version: 3.0
---

# API Reference

> **Project version:** 3.0 — see `../PLAN-V3.0.md` for the full plan.
> **Deployment:** The backend runs on Railway (long-lived
> container). The Vercel-Python-serverless deployment is deprecated.
> See [`deployment-railway.md`](deployment-railway.md).

**Base URL:** `https://<your-railway-service>.up.railway.app` (prod) /
`http://localhost:8000` (dev).
The Vercel frontend proxies `/api/*` to the Railway backend via the
`BACKEND_HOST` env var.

All POST/PATCH requests require `Content-Type: application/json` unless
they accept multipart uploads (image-upload endpoints).
All endpoints require `Authorization: Bearer <token>` except
`/api/health`. Production refuses to start if `AUTH_TOKEN` is unset
(see [`thresholds.md`](thresholds.md) and `api/main.py::_assert_production_safe`).

For per-endpoint acceptance criteria see
[`functional-specification.md`](functional-specification.md). For the
full coverage matrix (which test exercises which endpoint) see the
same doc's §9 verification matrix.

---

## Crawl Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/crawl/discover-scope` | Partial-scan setup: read-only probe of a URL's content types. Body `{target_url}` → `{is_wordpress, discovery_tier, types[], categories[], category_scope_supported, notes}`. No credentials; SSRF-guarded per hop. |
| POST | `/api/crawl/start` | Submit a new crawl job. Returns `job_id`. Optional `settings.content_scope = {mode, type_keys[], category_ids[]}` restricts the crawl to selected content types (`mode="types"`); omitted / `mode="full"` crawls the whole site. May return `scope_notes[]`. |
| POST | `/api/crawl/scan-page?url={url}` | Fetch and analyse a single URL synchronously. Returns `job_id` immediately. |
| GET | `/api/crawl/{job_id}/status` | Poll job progress and status. |
| POST | `/api/crawl/{job_id}/cancel` | Cancel a running crawl. |
| GET | `/api/crawl/{job_id}/results` | Retrieve paginated results. |
| GET | `/api/crawl/{job_id}/results/{category}` | Results filtered by category. |
| POST | `/api/crawl/{job_id}/rescan-url?url={url}` | Re-fetch a single page, rerun checks, update stored issues. Sends cache-bypass headers. |
| GET | `/api/crawl/{job_id}/page-priority` | Page Priority Work Queue: ranks the job's crawled pages by the Authority Matrix (Vulnerable Stars first, then Traffic Decay/Staleness, then worst-health; Hidden Gems surfaced as opportunities). Works with or without GSC data. Returns `{pages: [{url, health_score, gsc, review_flag: {flagged, reasons}, ...}], total}`. |

## Export

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/crawl/{job_id}/export/csv` | Full results as CSV. |
| GET | `/api/crawl/{job_id}/export/csv/{category}` | Category results as CSV. |
| GET | `/api/crawl/{job_id}/export/pdf` | Professional PDF report. Query params: `include_help`, `include_pages`, `summary_only`. |
| GET | `/api/crawl/{job_id}/export/excel` | Tabbed Excel report grouped by category. |
| GET | `/api/crawl/{job_id}/export/ai-images-pdf` | Export AI image analysis results as a PDF report. |

## Image Intelligence (v1.9)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/crawl/{job_id}/images` | Paginated list of images with scores. Query params: `page`, `limit`, `sort_by` (score/size/load_time). |
| GET | `/api/crawl/{job_id}/images/summary` | Image analysis summary: totals, scores, breakdowns by issue and format. |
| POST | `/api/crawl/{job_id}/images/fetch` | Fetch live image details from WordPress + image file (Level 2 data). Body: `{"image_urls": [...]}`. |
| POST | `/api/crawl/{job_id}/images/analyze-ai` | Analyze an image with AI vision model (Level 3 data). Body: `{"image_url": "..."}`. |
| GET | `/api/crawl/{job_id}/orphaned-images` | List images in WordPress media library not found on any crawled page. |
| GET | `/api/crawl/{job_id}/orphaned-pages` | List crawled pages not linked from any other crawled page. |

## Fix Manager (WordPress integration)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/fixes/generate/{job_id}` | Connect to WordPress, generate proposed fixes from crawl issues. |
| GET | `/api/fixes/{job_id}` | List all fixes for a job (pending, approved, applied, skipped, failed). |
| DELETE | `/api/fixes/media/{media_id}?force=true` | Permanently delete a media item from WordPress. |
| GET | `/api/fixes/orphaned-media/{job_id}` | List WordPress media items not found in the crawl. |
| GET | `/api/fixes/orphaned-media/{job_id}/csv` | Download orphaned media list as a CSV file. |
| POST | `/api/fixes/update-image-meta?image_url={url}&alt_text={txt}` | Update alt text, title, or caption for a WordPress media item. |
| POST | `/api/fixes/optimize-image?job_id={id}&image_url={url}&new_filename={name}` | Download, optimize, rename, and replace an image across all WP posts. |
| PATCH | `/api/fixes/{fix_id}` | Update a single fix — change `proposed_value` or `status`. |
| POST | `/api/fixes/mark-anchor-fixed` | Mark a single empty-anchor link as fixed. Removes from the issue's anchor list; deletes issue when none remain. |
| POST | `/api/fixes/apply/{job_id}` | Apply all approved fixes to WordPress. Stops on first failure. |
| DELETE | `/api/fixes/{job_id}` | Delete all fixes for a job (to regenerate from scratch). |

### Heading Fix Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/fixes/analyze-heading-sources?page_url={url}&job_id={id}` | Identify where each heading lives (post content, widget, theme, etc.) |
| POST | `/api/fixes/heading-to-bold?page_url={url}&heading_text={text}&level={n}` | Convert a heading to bold text. Level 1-6, default 4. |
| POST | `/api/fixes/change-heading-level?page_url={url}&heading_text={text}&from_level={n}&to_level={n}` | Change a heading from one level to another (H1-H6). |
| POST | `/api/fixes/change-heading-text?page_url={url}&old_text={text}&new_text={text}&level={n}` | Change the text of a heading in WordPress post content. |
| GET | `/api/fixes/find-heading?job_id={id}&heading_text={text}&level={n}` | Find all pages containing a specific heading. |
| POST | `/api/fixes/bulk-replace-heading?job_id={id}&heading_text={text}&from_level={n}&to_level={n}` | Change a heading level across all pages in a crawl job. Omit `to_level` to convert to bold. |

## AI Analysis (v1.7 AI-Readiness Module)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/analyze` | Analyze a page using AI and provide remediation suggestions. |
| GET | `/api/ai/test` | Test connectivity to AI provider (Gemini/OpenAI). Response: `{success: bool, message: str}` plus `{sample}` on success. (No `api_key_read` field.) Used by the Connections panel's "Test LLM" button. On provider failure `analyze_with_ai` raises `AIAnalysisError`; the endpoint returns `{success: false, message}` — an error is never surfaced as content. |
| POST | `/api/ai/page-advisor` | Get AI-generated SEO recommendations for a specific page. |
| POST | `/api/ai/site-advisor` | Get AI-generated site-wide SEO recommendations. |
| POST | `/api/ai/faq-schema` | Generate ready-to-paste FAQPage JSON-LD from the page's FAQ Q&A (`{job_id, page_url}` → `{jsonld, question_count, refused, reason}`). Re-fetches the page (SSRF-safe); builds schema only from answers present in the HTML — refuses (never fabricates) if answers are JS-only. Copy/export only; never writes to WordPress. |

## AI Citation Ingestion (M5)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/jobs/{job_id}/ai-citations` | Ingest per-URL AI citation data from the sibling phrase tool. |

### POST /api/jobs/{job_id}/ai-citations
**Auth:** Bearer token required  
**Rate limit:** 10/minute per IP  
**Body:** `CitationIngestionRequest` with `citations: [{url, engines: [{engine, count_30d, last_seen?}]}]`  
**Response:** `{matched_count, unmatched_count, unmatched_urls}`  
**Errors:** 401 (no auth), 404 (job not found), 422 (malformed body or job_id)  
**SSRF:** URLs are matched as strings only, never fetched

## GEO Analyzer (v2.1)

LLM-based content analysis for Generative Engine Optimization. Produces a structured `GEOReport` covering query matching, chunk self-containedness, central claim detection, JS rendering checks, and Aggarwal et al. evidence-tiered scoring.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/geo-report` | Generate (or return cached) GEO report for a job's URL. See schema below. |
| POST | `/api/ai/geo-faq` | Generate Schema.org FAQPage JSON-LD from a domain's GeoConfig. See schema below. |
| POST | `/api/ai/geo-llm-checks` | R8: opt-in LLM-driven GEO checks for a single page (one LLM call). Re-fetches + parses the page for its body text, then classifies. Body: `{page_url, job_id?}`. Returns `{verdict, issues: [{code, severity, priority_rank}]}` — the three checks are `CENTRAL_CLAIM_BURIED`, `CHUNKS_NOT_SELF_CONTAINED`, `PROMOTIONAL_CONTENT_INTERRUPTS`. A failed/refused LLM response yields an empty verdict, never a spurious finding; pages under 200 words return an empty verdict with a `note`. |
| POST | `/api/geo/entity-schema` | Generate nested Schema.org Organization JSON-LD from a domain's GeoConfig. See schema below. |
| GET | `/api/geo/ai-model` | List available AI models and the currently selected model. |
| POST | `/api/geo/ai-model` | Set the AI model for GEO analysis. Body: `{"model_id": "gpt-4o"}`. |

### `POST /api/ai/geo-report` Request

```json
{
  "job_id": "abc123",
  "url": "https://example.com/blog/article",
  "model": "gpt-4o",
  "force_refresh": false
}
```

`job_id` is required. `url` overrides the job's start URL (for per-page analysis). `force_refresh: true` bypasses the cached report.

### `POST /api/ai/geo-report` Response

```json
{
  "success": true,
  "cached": false,
  "report": {
    "url": "https://example.com/blog/article",
    "model_used": "gpt-4o",
    "overall_score": 0.72,
    "aggarwal_score": 0.67,
    "findings": [
      {
        "code": "QUERY_MATCH_SCORE",
        "label": "Query Match Score",
        "evidence_tier": "Empirical",
        "pass_fail": "pass",
        "score": 0.83,
        "findings": ["7/8 queries answered"],
        "details": {"answered": 7, "total": 8}
      }
    ],
    "query_match_table": [
      {"query": "What is OpenBrain?", "best_chunk": "...", "answered": "Yes", "reason": "..."}
    ],
    "chunk_containedness": [
      {"heading": "How Does It Work?", "self_contained": true, "reason": "..."}
    ],
    "js_rendering": {
      "js_rendered_content_differs": false,
      "content_cloaking_detected": false,
      "ua_content_differs": false,
      "raw_token_count": 1240,
      "rendered_token_count": 1258,
      "topic_jaccard": 0.91,
      "playwright_available": true,
      "error": null
    },
    "playwright_available": true,
    "error": null
  }
}
```

**Evidence tiers:** `Empirical` (Aggarwal et al. measured, weight 3) > `Mechanistic` (retrieval mechanics, weight 2) > `Conventional` (industry advice, weight 1). `aggarwal_score` is computed only from Empirical findings.

### `GET /api/geo/ai-model` Response

```json
{
  "selected": "gpt-4o",
  "available": [
    {"id": "gpt-4o", "provider": "openai", "label": "GPT-4o (recommended)"},
    {"id": "gpt-4o-mini", "provider": "openai", "label": "GPT-4o Mini (fast)"},
    {"id": "gemini-1.5-flash", "provider": "gemini", "label": "Gemini 1.5 Flash (fast)"},
    {"id": "gemini-1.5-pro", "provider": "gemini", "label": "Gemini 1.5 Pro"},
    {"id": "gemini-2.0-flash", "provider": "gemini", "label": "Gemini 2.0 Flash"}
  ]
}
```

Only models for which an API key is configured are returned in `available`.

### `POST /api/ai/geo-faq` Request (GA3)

```json
{
  "domain": "livingsystems.ca",
  "mode": "template",
  "limit": 8
}
```

`domain` (required): domain with a saved GeoConfig. `mode`: `"template"` (default, free, deterministic) or `"ai"` (LLM-enriched, falls back to template on failure). `limit`: max questions (1–20, default 8).

### `POST /api/ai/geo-faq` Response

```json
{
  "faq_block": {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "What is Bowen Theory and how does it help people in Vancouver?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "[Draft: write a concise 1-2 sentence answer about this topic for your organisation.]"
        }
      }
    ]
  },
  "questions": ["What is Bowen Theory and how does it help people in Vancouver?"],
  "mode_used": "template",
  "token_usage": null
}
```

Errors: `401` no auth, `422` unknown domain or empty `topic_entities`.

### `POST /api/geo/entity-schema` Request

```json
{
  "domain": "livingsystems.ca"
}
```

`domain` (required): domain with a saved GeoConfig.

### `POST /api/geo/entity-schema` Response

```json
{
  "jsonld": "{ ... }",
  "schema": {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Living Systems Counselling",
    "url": "https://livingsystems.ca",
    "sameAs": ["https://en.wikipedia.org/wiki/..."]
  },
  "valid": true,
  "warnings": []
}
```

Deterministic — no LLM calls. Generates nested Schema.org Organization JSON-LD from the domain's GeoConfig. Returns `warnings` if optional fields (e.g. `entity_wikipedia_url`) are missing.

Errors: `401` no auth, `422` unknown domain or empty `topic_entities`.

## GEO Image AI (v1.9)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/image/analyze-geo` | Analyze an image using GEO-optimized prompting with domain context. |
| POST | `/api/ai/image/apply-geo-metadata` | Apply GEO-generated metadata to an image (updates WordPress + database). |
| POST | `/api/geo/settings` | Save GEO configuration for a domain. |
| GET | `/api/geo/settings?domain={domain}` | Retrieve GEO configuration for a domain. |

## Image Optimization (v1.9.1)

### Single Image Optimization

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/fixes/optimize-existing` | Download existing WP image → optimize → upload as NEW file. |
| POST | `/api/fixes/optimize-upload` | Upload local file → optimize → upload to WordPress. |
| POST | `/api/fixes/optimize-existing-preview` | Preview optimization for an existing image (no changes made). |

### Batch Optimization

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/fixes/batch-optimize/start` | Start batch optimization job for multiple images. |
| GET | `/api/fixes/batch-optimize/{batch_id}/status` | Get batch job progress and results. |
| POST | `/api/fixes/batch-optimize/{batch_id}/pause` | Pause a running batch job. |
| POST | `/api/fixes/batch-optimize/{batch_id}/resume` | Resume a paused batch job. |
| POST | `/api/fixes/batch-optimize/{batch_id}/cancel` | Cancel a batch job. |
| GET | `/api/fixes/batch-optimize/list` | List all batch jobs (optionally filter by job_id). |

### Optimize Existing Request

```json
{
  "job_id": "abc123",
  "image_url": "https://example.com/wp-content/uploads/image.jpg",
  "target_width": 1200,
  "apply_gps": true,
  "generate_geo_metadata": true,
  "seo_keyword": "therapy"
}
```

### Optimize Existing Response

```json
{
  "success": true,
  "old_url": "https://example.com/wp-content/uploads/image.jpg",
  "new_url": "https://example.com/wp-content/uploads/therapy-vancouver-small.webp",
  "new_media_id": 12345,
  "page_urls": ["https://example.com/services"],
  "file_size_kb": 85.5,
  "archive_paths": {
    "original": "archive/job123/originals/image.jpg",
    "optimized": "archive/job123/optimized/therapy-vancouver-small.webp"
  },
  "geo_metadata": {
    "alt_text": "Therapy session in progress at Vancouver counselling centre",
    "description": "Professional therapy services...",
    "caption": "Licensed therapist providing support"
  }
}
```

### Batch Start Request

```json
{
  "job_id": "abc123",
  "image_urls": [
    "https://example.com/wp-content/uploads/img1.jpg",
    "https://example.com/wp-content/uploads/img2.png"
  ],
  "target_width": 1200,
  "apply_gps": true,
  "generate_geo_metadata": true,
  "parallel_limit": 3
}
```

### Batch Status Response

```json
{
  "batch_id": "a1b2c3d4",
  "job_id": "abc123",
  "status": "running",
  "total": 10,
  "completed": 4,
  "failed": 1,
  "progress_percent": 50,
  "current_index": 5,
  "created_at": "2024-01-15T10:00:00",
  "started_at": "2024-01-15T10:00:05",
  "completed_at": null,
  "results": [
    {
      "image_url": "https://example.com/img1.jpg",
      "success": true,
      "new_url": "https://example.com/optimized1.webp",
      "new_media_id": 12345,
      "file_size_kb": 75.2,
      "page_urls": ["https://example.com/page1"],
      "error": null,
      "geo_metadata": { "alt_text": "...", "description": "...", "caption": "..." }
    }
  ]
}
```

### Batch Status Values

| Status | Description |
|---|---|
| `pending` | Job created but not yet started |
| `running` | Currently processing images |
| `paused` | Temporarily paused by user |
| `completed` | All images processed |
| `cancelled` | Stopped by user before completion |

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

## Ignored Image Patterns

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/ignored-image-patterns` | List all ignored image URL patterns. |
| POST | `/api/ignored-image-patterns` | Add a URL substring pattern. Images matching any pattern are excluded from `IMG_ALT_MISSING` and other image checks. Body: `{"pattern": "/icon.svg", "note": "theme icons"}`. |
| DELETE | `/api/ignored-image-patterns?pattern={pat}` | Remove a pattern from the ignored list. |

## Utility

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | `{"status": "ok", "version": "1.9.1"}` |
| GET | `/api/ai/test` | Test connectivity to Gemini/OpenAI API providers. |
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
| `BLOCKED_URL` | 403 | URL targets a private or internal network (SSRF protection) |
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

`broken_link`, `metadata`, `heading`, `redirect`, `crawlability`, `duplicate`, `sitemap`, `security`, `url_structure`, `ai_readiness`, `rendering`, `semantic_html`

(`rendering` and `semantic_html` are the agent-readiness Phase 1 task-side categories.)

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
    "agent_health_score": 81,
    "agent_readiness": {
      "score": 81,
      "breakdown": [
        { "category": "ai_readiness", "issues": 4, "impact": 14 },
        { "category": "semantic_html", "issues": 2, "impact": 6 }
      ]
    },
    "by_severity": { "critical": 2, "warning": 8, "info": 7 },
    "by_category": { "metadata": 5, "heading": 3, "broken_link": 2 },
    "robots_txt": {
      "found": true,
      "rules": ["Disallow: /wp-admin/", "Allow: /wp-admin/admin-ajax.php"]
    },
    "sitemap": {
      "found": true,
      "url": "https://example.com/sitemap.xml",
      "url_count": 38
    }
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

`health_score` is 0–100. Formula: `max(0, 100 − Σ issue impacts)` across all issues. The health score calculation normalises trailing slashes on page URLs so that issues and pages always match correctly.

`agent_health_score` (agent-readiness Phase 1) is a separate 0–100 score using the same per-page model, but the impact sum is restricted to **agent-relevant** issues: categories `ai_readiness` / `rendering` / `semantic_html` plus codes `PLACEHOLDER_LINK` and `WRONG_PLACEHOLDER_LINK`. `agent_readiness.breakdown[]` lists per-category issue counts and summed impact. More failing agent checks never raise the score (monotonic non-increasing).

`GET /api/crawl/{job_id}/pages/issues?url=…` additionally returns an `agent_issues` array — `[{ "code", "severity", "category", "tier" }]` — listing the agent-relevant issues on that page, where `tier` is the confidence label (falling back to severity).

The `robots_txt` and `sitemap` objects are included in the summary when discovery data is available. Both may be `null` if the crawl has not yet completed the discovery phase.

`priority_rank` formula: `(impact × 10) − (effort × 2)`. Higher = fix sooner.

See `nonprofit-crawler-spec-v1.4.md` §6 for full request/response schemas.

---

## Google Search Console (M6.1 + M6.4)

**Opt-in:** All endpoints require `GSC_OAUTH_CLIENT_ID`, `GSC_OAUTH_CLIENT_SECRET`,
and `GSC_OAUTH_REDIRECT_URI` to be set. When unset, every endpoint returns **503**.

All endpoints require `Authorization: Bearer <token>`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/gsc/connect` | Initiate OAuth flow — redirects to Google consent. |
| GET | `/api/gsc/callback?code=...&state=...` | OAuth callback — exchanges code for credentials. |
| GET | `/api/gsc/status` | Connection status + list of GSC properties. |
| POST | `/api/gsc/disconnect` | Remove stored GSC credentials. |
| POST | `/api/gsc/ingest?site_url=...&job_id=...&days=30` | Fetch GSC data and store as PerformanceRecords. |
| GET | `/api/gsc/performance?url=...&health_score=50` | Get performance ledger rows + ReviewFlag for a URL. |

### GET `/api/gsc/status`

Connection status for the Connections / GSC panel. `configured: true` is returned on every 200
response (whether or not credentials are stored) so the frontend can distinguish
configured-but-unlinked (renders the **Connect** button) from genuinely-not-configured. When the
GSC environment is not configured at all, the endpoint returns **503**, which the client maps to
`configured: false`.

```json
{
  "connected": true,
  "properties": [
    {"site_url": "https://www.example.com/", "permission_level": "siteOwner"}
  ],
  "configured": true
}
```

Not-yet-linked (env configured, no stored creds): `{"connected": false, "properties": [], "configured": true}`.

### POST `/api/gsc/ingest`

Query params: `site_url` (required), `job_id` (required), `days` (optional, default 30).

```json
{"ingested": 42, "period": "2026-06"}
```

### GET `/api/gsc/performance`

Query params: `url` (required), `job_id` (optional), `health_score` (optional, default 50).

```json
{
  "records": [
    {
      "url": "https://example.com/page",
      "period": "2026-06",
      "gsc_clicks_mo": 10,
      "gsc_impressions_mo": 100,
      "gsc_ctr_mo": 0.1,
      "gsc_avg_position_mo": 5.0
    }
  ],
  "review_flag": {"flagged": false, "reasons": []}
}
```

---

## Parked / Not Shipped

- **Multi-tenant AI key management**: per-customer API keys, Customer Settings UI, Identity Model — not implemented. See [`TODO-MULTITENANT.md`](TODO-MULTITENANT.md).
- **GSC frontend panel (React)**: backend complete (M6.1 + M6.4), React UI deferred.
- **SERP Discovery**: separate repository. See [`PARKED-SERP-DISCOVERY.md`](PARKED-SERP-DISCOVERY.md).
