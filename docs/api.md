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
| POST | `/api/crawl/start` | Submit a new crawl job. Returns `job_id`. Optional `settings.content_scope = {mode, type_keys[], category_ids[]}` restricts the crawl to selected content types (`mode="types"`); omitted / `mode="full"` crawls the whole site. Optional `gsc_priority` = a parsed GSC `priority_pages.json` object (the browser reads the file and embeds it) — seeds the crawl with high-traffic pages first and joins Search Console metrics into the ledger for ranking; domain-guarded, a wrong-site/wrong-tool file → 422 `INVALID_PRIORITY_FILE` (§6.12). May return `scope_notes[]`. |
| POST | `/api/crawl/scan-page?url={url}` | Fetch and analyse a single URL synchronously. Returns `job_id` immediately. Records `settings.single_page = true` on the job it creates, so a later rescan reproduces a one-page audit instead of a full-site crawl. |
| POST | `/api/crawl/{job_id}/rescan` | **Re-run a past scan with the settings it was originally run with.** Creates a NEW job; the source job is never mutated (the previous scan is what `/comparison` measures the new one against). Reuses the stored `settings` and `priority_seed`, so a GSC-ordered scan keeps its ordering without re-uploading the file. Returns `{job_id, source_job_id, mode, status, poll_url}` plus `scope_notes[]` when `/start` would have emitted them. `mode` is `"crawl"` (202, `status: "queued"`) or `"single_page"` (the scan already ran synchronously, `status: "complete"`) — a single-page source rescans as a single page, detected by `settings.single_page` or, for jobs predating 2026-09-01, the `orphan_detection.status == "skipped_single_page"` marker; it runs **unauthenticated**. The stored URL is re-validated through `is_ssrf_safe()` on every call → 403 `BLOCKED_URL`. A partial `content_scope` re-resolves against the live site → 422 `SCOPE_EMPTY` if it now resolves to nothing. 404 `JOB_NOT_FOUND`; 409 `CRAWL_IN_PROGRESS` while the source job is `queued`/`running`. Shares `/start`'s launcher and its `CRAWL_START_LIMIT` rate limit. |
| GET | `/api/crawl/{job_id}/status` | Poll job progress and status. |
| POST | `/api/crawl/{job_id}/cancel` | Cancel a running crawl. |
| GET | `/api/crawl/{job_id}/striking-distance` | **Phase 4 U4.1 (PB3).** Crawled pages whose latest ledger row ranks inside the striking-distance band (5–15) with ≥ 50 monthly impressions, sorted by impressions: `{pages: [{url, position, impressions, clicks, ctr, period, health_score, target_query, other_queries, rewrite_brief}], basis: {pages_crawled, pages_with_ledger, band, impressions_min, queries_from_seed}}`. `target_query` comes from the job's stored GSC priority seed (the ledger carries none) and is `null` otherwise. `basis` says why a list is empty. Read-only. |
| POST | `/api/crawl/{job_id}/recheck-all` | **Phase 4 U4.3.** Re-check every stored page of a finished job in place through the single-page rescan path, sequentially, honouring `crawl_delay_ms`, as a background task. 202 `{job_id, total, status: "started"}`; 409 `CRAWL_IN_PROGRESS` (job still running), 409 `RECHECK_IN_PROGRESS` (one already running); 404. Distinct from `/rescan` (a fresh crawl, new job): this updates the current job without discovering new pages. |
| GET | `/api/crawl/{job_id}/recheck-all/status` | `{job_id, running, done, total, resolved, added, unreadable, started_at, finished_at}`. Progress is in-process; after a restart it reads `running: false, total: 0` (the stored issues were updated page by page, nothing is lost). |
| GET | `/api/crawl/{job_id}/results` | Retrieve paginated results. |
| GET | `/api/crawl/{job_id}/results/{category}` | Results filtered by category. |
| POST | `/api/crawl/{job_id}/rescan-url?url={url}` | Re-fetch a single page, rerun checks, update stored issues. Sends cache-bypass headers. Reports outcomes at code level as well as by count: `resolved_codes`, `still_present_codes`, `newly_found_codes`, and `carried_over_codes` — findings whose code carries `needs_full_crawl` and so **cannot be evaluated on this path**. Carried-over findings are kept in the store and returned in `by_category`; they are never resolved or written to the fixed-issues ledger (see `checks_not_run` / `checks_not_run_reason`). `resolved`/`added` are row-count deltas and answer a different question from the code sets. A page that could not be read (403/429/5xx) returns `page_unreadable: true` with a `caveat` and changes nothing. A page that is **gone** (404/410) is different: its findings genuinely no longer apply, so nothing is carried over and they resolve normally. Every issue also carries `evidence_rows` — the rendered evidence ROW count, which is not `len(evidence)`. |
| GET | `/api/crawl/{job_id}/page-details?url={url}[&code={code}]` | **D6** — the offending items for a page (which links, which images, which fields), read **live** and **stored nowhere**. Omit `code` for every issue on the page; supply it for one. Reuses the hardened single-page fetch. Lifts the 10-row render cap so every captured row is returned; `items_total` states the page's real count and `truncated_at_capture` flags that the crawler kept fewer than it saw (capture caps are not lifted). `evidence_basis` is `page` for the 30 codes whose finding is the page itself, `items` otherwise. **Codes it could not evaluate are returned as entries with `evaluated: false` and a `not_evaluated_reason`, never omitted** — an absent code renders as "no longer on the page", i.e. a false all-clear. Three causes: the page is gone (404/410, `page_gone: true`), the code needs a full crawl, or it is a link code (external links are deliberately not re-checked here — one click would otherwise cost up to 50 outbound third-party requests). `items_shown` is the rendered ROW count, which is not `len(items)` (that also holds headings and an "… and N more" line). A page that could not be read returns `source: "stored"` with a caveat — never live-labelled. Rate limited (`DETAILS_LIMIT`, 60/hour), though see `TODO.md`: the limiter key is currently client-supplied, so no per-hour limit in the app is presently a bound. |
| GET | `/api/crawl/{job_id}/page-priority` | Page Priority Work Queue: ranks the job's crawled pages by the Authority Matrix (Vulnerable Stars first, then Traffic Decay/Staleness, then worst-health; Hidden Gems surfaced as opportunities). Works with or without GSC data. Returns `{pages: [{url, health_score, gsc, review_flag: {flagged, reasons}, ...}], total}`. |
| GET | `/api/crawl/{job_id}/fix-focus?focus={all\|seo\|geo}` | Fix Focus checklist. Generates+persists a frozen snapshot on first call, then returns it (no re-scan). Returns `{seo, geo, generated_at, scoring_model_version}` where each focus is `{pages: [{url, page_priority, items: [{issue_code, human_description, severity, impact, effort, priority_rank, quick_win, status}]}], pages_total, pages_shown, items_hidden}`. |
| POST | `/api/crawl/{job_id}/fix-focus/check` | Toggle a checklist item. Body `{page_url, issue_code, checked}`. Reversible. 404 `ITEM_NOT_FOUND` if the item isn't in the snapshot. |
| POST | `/api/crawl/{job_id}/fix-focus/regenerate` | Rebuild the snapshot from current stored issues, preserving checked/verified state for surviving items. |
| POST | `/api/crawl/{job_id}/fix-focus/verify-page?url={url}` | Re-scan one page (reuses `rescan-url`) and reconcile: items no longer seen → `verified`, still seen → `still_present`, new → `newly_found`. Returns `{url, reconciled, page_status, verified, still_present, newly_found}`; a page returning HTTP ≥ 400 is not reconciled (`reconciled:false`). |

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

> **Auth (2026-09-02):** every `/api/*` route except `/api/health` requires the bearer token, enforced per router and verified for every registered route by `tests/test_auth_matrix.py`. `POST /api/wp-audit/{job_id}` (D3 WordPress configuration audit) had shipped without the guard and now has it; it has no frontend caller — see TODO.

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
**Rate limit:** 10/minute per bearer token (`CITATIONS_LIMIT`)  
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
| GET | `/api/wp/connection` | WordPress connectivity + account capabilities (read-only). See below. |
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
| `CRAWL_IN_PROGRESS_FOR_DOMAIN` | 409 | A queued or running crawl of the same domain exists (www stripped); both `/start` and `/rescan` refuse. Names the job. (Phase 3, 2026-09-02) |
| `RATE_LIMITED` | 429 | Rate limit reached — every limited route; body carries `message` with the limit and a `Retry-After` header (2026-09-02) |
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
| `info_detail` | `all` \| `notable` \| `key` \| `none` | `all` | **Which info tiers this scan shows AND counts toward the health score** (2026-09-01). `notable` keeps impact ≥ 2, `key` keeps impact 3 only, `none` keeps no info row. Detection is unchanged — every finding is still stored. Unknown value → 422 `INVALID_SETTINGS`. Echoed by `GET /api/crawl/{job_id}` under `settings`. |

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
    },
    "orphan_detection": {
      "status": "complete",
      "pages_analysed": 42,
      "pages_out_of_scope": 0,
      "archives_skipped": true,
      "pages_links_unread": 0
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

**Info detail (2026-09-01).** When the job's `settings.info_detail` is not `all`, `health_score`, `agent_health_score` and every per-page grade are computed over the info tiers the scan chose (see functional-specification §4.0.2). The summary always carries the reason:

```json
"info_detail": "notable",
"info_by_tier": { "high": 9, "medium": 42, "low": 98 },
"info_scored": 51,
"info_excluded": 98
```

`info_scored + info_excluded == by_severity.info`, always; `by_severity` and `total_issues` are the **stored** counts and never move with the level. Every issue in `issues[]` carries `info_tier` (`high` | `medium` | `low` | `null` unless info) and `scored` (false only for a revealed row the level excluded). Every list response carries `info_filtered: {hidden, by_tier, info_detail}` beside `filtered`.

`?info_detail=all` on `/results`, `/results/{category}` and `/pages/issues` is **reveal-only**: it may loosen the job's level (showing excluded rows with `scored: false`) but never tightens it, and never changes the score.

`orphan_detection` reports whether `ORPHAN_PAGE` ran, and over how much of the site. `status` is one of `complete`, `skipped_partial_scan`, `skipped_truncated`, `skipped_cancelled`, `skipped_single_page`, `skipped_failed`, `not_run` — **treat any unrecognised value as "did not run"**, never as complete. `pages_analysed` counts the pages the check reasoned over (HTML pages), not every fetched file. `pages_out_of_scope` is the shortfall: out-of-scope URLs on a partial scan, still-queued URLs on a truncation. Even on `complete`, `archives_skipped` (WordPress archives are skipped before their links are read) and `pages_links_unread` (pages that timed out, hit a login wall, or failed to parse) mean the graph was not exhaustive — surface both as caveats beside the result. `ORPHAN_PAGE` concludes that *nothing* links to a page, which is only decidable after crawling the whole site — so a partial scan, a `max_pages` truncation, or a cancellation suppresses the check rather than flagging every page whose only inbound link lives outside the crawl. **A suppressed check returns zero orphans**: clients must branch on `status` and never read an empty result as "no orphans found". The field is `null` on audits crawled before it existed.

`agent_health_score` (agent-readiness Phase 1) is a separate 0–100 score using the same per-page model, but the impact sum is restricted to **agent-relevant** issues: categories `ai_readiness` / `rendering` / `semantic_html` plus codes `PLACEHOLDER_LINK` and `WRONG_PLACEHOLDER_LINK`. `agent_readiness.breakdown[]` lists per-category issue counts and summed impact. More failing agent checks never raise the score (monotonic non-increasing).

`GET /api/crawl/{job_id}/pages/issues?url=…` additionally returns an `agent_issues` array — `[{ "code", "severity", "category", "tier" }]` — listing the agent-relevant issues on that page, where `tier` is the confidence label (falling back to severity).

`GET /api/crawl/{job_id}/pages` returns each page with `url`, `status_code`, `issue_counts`, and `citability_grade` — a per-page 0–100 GEO/AI-citability rollup (`100 − Σ impact of the page's charged ai_readiness issues`, cluster-suppression applied, no per-category cap). The same value is on each `/page-priority` row. Surfaced in the UI as the `CitabilityBadge` column (green ≥ 70 / amber ≥ 40 / red).

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

### GET `/api/wp/connection`

WordPress connectivity for the Connections panel (WA5, 2026-09-02). Auth required. **Read-only** —
the server logs in with the stored credentials and makes one call, `users/me`.

Always **200 with a state**, never an HTTP error for a connectivity problem: *not configured*,
*credentials rejected* and *logged in but under-privileged* are three different problems with three
different fixes, and collapsing them into one failure would rebuild the guessing error message this
work removed. `can_run_fixes` (edit_posts + edit_pages + upload_files) is separate from
`can_run_wp_audit` (manage_options) because an editor authenticates fine and still cannot list
plugins.

Optional `?job_id=` is domain-validated against the stored credentials and returns **403
`DOMAIN_MISMATCH`** on a mismatch. Without it there is no address to validate — the endpoint can
only ever contact the site in the credentials file. The payload never carries a password.

```json
{
  "configured": true,
  "authenticated": true,
  "site_url": "https://example.com",
  "user_id": 11,
  "roles": ["administrator"],
  "capabilities": {"edit_posts": true, "edit_pages": true,
                   "upload_files": true, "manage_options": true},
  "can_run_fixes": true,
  "can_run_wp_audit": true,
  "message": "Connected. This account can run the fixes and the configuration audit."
}
```

Not configured: `{"configured": false, "authenticated": false, "site_url": null, "message": "No WordPress credentials are stored…"}`.
Rejected: `configured: true`, `authenticated: false`, and `message` carries the client's own
diagnosis — the URL it posted to, whether the request was redirected, and the causes it cannot
distinguish.

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

## Performance Bundle Ingestion (2026-08-06, Phase 1)

Source-agnostic ingest of GSC + GA4 + index-state metrics from a sibling reporting
app (Option A — no Google OAuth in TalkingToad). Feeds the same Performance Ledger
as `/api/gsc/ingest`. Requires `Authorization: Bearer <token>`.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/performance/ingest?job_id=...` | Ingest a `PerformanceBundle` (v1) JSON body; merge per-URL GSC+GA4+index into the ledger. |

### POST `/api/performance/ingest`

Query param: `job_id` (required). Body: a `PerformanceBundle` v1 (see
`docs/pending/2026-08-06_performance-bundle-ingestion.md` for the full contract).
Per-URL GSC + GA4 + `index_state` are persisted for bundle URLs that match a
crawled page; `pages[].gsc.top_queries` and the `site` object (GTM audit, GA4
site-search) are accepted but persisted in a later phase — reported under `deferred`.

A matched row is stored under the **crawled page's** URL (the key the page-priority
consumer reads by), so a bundle/crawl difference of only a trailing slash, `www`, or
scheme still lands on the right row. Bundle URLs matching no crawled page are **held
out** (reported in `unmatched_urls`), not stored under an orphan key.

**Guards:** `bundle_version != 1` → 400 `UNSUPPORTED_BUNDLE_VERSION`; scheme/host-less
`site_url` → 400 `INVALID_SITE_URL`; unknown `job_id` → 404 `JOB_NOT_FOUND`; `site_url`
not the same site as the job's `target_url` → 403 `DOMAIN_MISMATCH` (zero rows written).

Response:

```json
{
  "ingested": 12,
  "sources": ["gsc", "ga4"],
  "period": "2026-07",
  "unmatched_urls": ["https://example.org/orphan"],
  "invalid_urls": [],
  "stale": false,
  "deferred": ["top_queries", "site"]
}
```

- `ingested` — rows persisted (bundle URLs that matched a crawled page).
- `unmatched_urls` — bundle URLs with no crawled page; held out (extend the crawl to capture them), not dropped silently.
- `invalid_urls` — bundle URLs that could not be parsed; skipped without aborting the ingest.
- `stale` — `true`/`false` from `generated_at` vs a 35-day window; `null` when the timestamp is missing/unparseable.
- `deferred` — payload sections accepted but not yet persisted (Phase 2/3).

---

## Parked / Not Shipped

- **Multi-tenant AI key management**: per-customer API keys, Customer Settings UI, Identity Model — not implemented. See [`TODO-MULTITENANT.md`](TODO-MULTITENANT.md).
- **GSC frontend panel (React)**: backend complete (M6.1 + M6.4), React UI deferred.
- **SERP Discovery**: separate repository. See [`PARKED-SERP-DISCOVERY.md`](PARKED-SERP-DISCOVERY.md).


## Per-domain issue filter (F1)

Presentational only — hides findings from the results lists and **never** changes
the health score.

| Method | Path | Body / Query | Notes |
|---|---|---|---|
| GET | `/api/domain-filters` | `?domain=` | Returns `{domain, rules[]}`; domain is normalised server-side. |
| POST | `/api/domain-filters` | `{domain, issue_code}` **or** `{domain, severity}` | Exactly one of the two → 422 otherwise. Unknown code → 404, unknown severity → 422. |
| DELETE | `/api/domain-filters` | `?domain=&issue_code=` or `&severity=` | No-op if the rule is absent. |

`GET /api/crawl/{job_id}/results` and `/results/{category}` additionally return:

```json
"filtered": {"domain": "example.com", "hidden": 31,
             "by_rule": {"severity:info": 28, "H1_MISSING": 3}}
```

Always present, `hidden: 0` when no rules apply. Consumers must render it: 123 of
170 codes are `info`, so a severity rule removes most findings and a shorter list
would otherwise read as a healthier site.

## Info detail — the `info_detail` scan setting (2026-09-01)

Unlike F1, this **does** change the health score: it is chosen at scan time, stamped on the
job, and named beside every number it changes. Summary shape and per-issue fields are under
"Summary Shape" above. Additional surfaces:

| Surface | What changes |
|---|---|
| `GET /api/crawl/{job_id}/pages/issues?url=…` | `by_category` is filtered to the level; `info_filtered: {hidden, by_tier, info_detail}` added; `?info_detail=all` reveals. |
| `GET /api/crawl/{job_id}/pages` | `citability_grade` follows the level; `issue_counts.total` / `.info` count the kept rows and `issue_counts.info_excluded` names what the level left out on that page (0 at `all`). `min_severity` still tests the stored severities. |
| `GET /api/crawl/{job_id}/page-priority` | `health_score` / `citability_grade` per row follow the level. |
| `GET …/export/pdf`, `…/export/excel` | Listed rows follow the level; the PDF Dashboard's "Info Notices" figure is the scored count with "(+N excluded)" beside it; the Scope & Caveats / Summary sheet carries "Scored at info detail '…': N info notices (…) excluded from this audit and from its health score by the scan setting." |
| `GET …/export/csv`, `…/export/csv/{category}` | Rows follow the level; every row carries an `info_tier` column (`high` / `medium` / `low`, blank for warning/critical) so a scoped CSV can be told apart from a quieter site. No caveat row (as with F1). |
| `POST /api/jobs/{job_id}/ai-citations` | The `AI_HIGH_VALUE_UNCITED` "healthy page" gate (page health ≥ 80) is computed at the job's level, like every other per-page grade. |
| `GET /api/crawl/{job_id}/comparison` | Adds `comparable: bool`, `reason: string|null`, `info_detail` and `health_score_basis` on `current` / `previous` (Phase 4: a partial analysis on either side also sets `comparable: false` with the reason). `comparable: false` with `reason: "info_detail differs (notable vs all)"` when the two jobs were scanned at different levels; the delta is still returned. |
| `POST /api/crawl/{job_id}/rescan` | The new job inherits `info_detail` with the other settings. |
