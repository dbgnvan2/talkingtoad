# TalkingToad — Nonprofit SEO Crawler

## Project Overview

TalkingToad is a lightweight, web-based SEO crawler for nonprofit organisations. It replicates the essential functionality of Screaming Frog SEO Spider — free, zero-installation, simple results — deployed on Vercel with a React frontend and Python/FastAPI backend.

**GitHub:** https://github.com/dbgnvan2/talkingtoad
**Spec:** `nonprofit-crawler-spec-v1.4.md` + v1.5 extensions + v1.9 Image Intelligence + v1.9.1 Optimization
**Current Version:** 1.9.1

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python 3.11+ + FastAPI |
| HTTP Client | httpx (async) |
| HTML Parser | BeautifulSoup4 + lxml |
| PDF Parser | pypdf |
| PDF Generator | fpdf2 (Letter format, robust Unicode) |
| Excel Generator | openpyxl (Tabbed workbooks) |
| Image Processing| Pillow (WebP optimization) |
| AI Analysis | Google Gemini / OpenAI |
| Data Store | SQLite (dev) / Upstash Redis (prod) |
| Hosting | Vercel (frontend SPA + Python serverless) |

---

## Directory Structure

```
TalkingToad/
├── api/                         # FastAPI backend
│   ├── crawler/                 # Async crawl engine + issue detection
│   │   ├── engine.py            # Async BFS crawler (~1000 lines)
│   │   ├── issue_checker.py     # SEO issue detection (~1500 lines)
│   │   ├── image_analyzer.py    # Image analysis and scoring (~500 lines)
│   │   ├── parser.py            # BeautifulSoup HTML extraction
│   │   ├── normaliser.py        # URL normalization + WP noise detection
│   │   ├── robots.py            # robots.txt parser
│   │   └── sitemap.py           # XML sitemap parser
│   ├── models/                  # Pydantic models (Job, Page, Issue, Fix, Image)
│   │   └── image.py             # ImageInfo data model
│   ├── routers/                 # API endpoints (crawl, fixes, utility, verified, ai)
│   └── services/                # Business logic
│       ├── wp_fixer.py          # WordPress REST API integration (~2500 lines)
│       ├── ai_analyzer.py       # Gemini/OpenAI integration
│       ├── report_generator.py  # PDF audit generation (fpdf2)
│       ├── excel_generator.py   # Excel export (openpyxl)
│       ├── job_store.py         # SQLite/Redis abstraction
│       ├── image_processor.py   # WebP optimization + SEO renaming
│       ├── exif_injector.py     # GPS EXIF coordinate injection
│       ├── upload_validator.py  # Pre-upload validation
│       └── batch_optimizer.py   # Batch job management
├── frontend/                    # React + Vite SPA
│   ├── src/pages/               # Home, Progress, Results (~3500 lines)
│   ├── src/components/          # FixManager, LLMSTxtGenerator, etc.
│   └── src/data/issueHelp.js    # Help content for all issue codes
├── tests/                       # Pytest suite (asyncio)
└── docs/                        # Specifications and API reference
    ├── api.md                   # Full API endpoint reference
    ├── architecture.md          # System design and data flow
    ├── issue-codes.md           # All 50+ issue codes with explanations
    └── overview.md              # Feature descriptions and use cases
```

---

## Critical Local Files (DO NOT COMMIT)
- `wp-credentials.json`: WordPress API credentials
- `.env`: Main environment variables
- `.env-ttoad`: Custom override environment variables
- `talkingtoad.db`: Local SQLite database

---

## Key Features (v1.9.1)

1. **Crawler:** Async engine with robots.txt/sitemap support and 50+ SEO issue checks.
2. **WordPress Fix Manager:** One-click remediation for titles, meta, and headings via WP REST API.
3. **Image Intelligence Engine (v1.9):**
   - 3-level data architecture: Scan (instant) → Fetch (live WP + image file) → AI Analysis
   - WordPress Media Library integration (alt text, title, caption, description)
   - Performance scoring (file size, compression, load time)
   - Accessibility scoring (alt text quality, length, semantic accuracy)
   - AI-powered alt text generation with vision models
   - GEO-optimized metadata (see `geo_image_ai_spec.md`)
4. **Image Optimization Module (v1.9.1):**
   - Download existing WP images → optimize → upload as NEW file
   - Upload local images → optimize → upload to WordPress
   - WebP conversion with target file size < 200KB
   - GPS EXIF coordinate injection
   - SEO filename generation (keyword-city-small.webp)
   - GEO AI metadata generation (alt text, description, caption)
   - Batch processing with pause/resume/cancel controls
   - Local archiving of originals and optimized files
5. **AI Readiness:** /llms.txt generator (on-demand, not auto-generated) and AI semantic audit (Gemini/OpenAI). Shows "Retrieved" badge when saved content exists, "Recommendation" badge when generated from crawl data.
6. **Reporting:** Professional 8.5" x 11" PDF audits and tabbed Excel workbooks.

---

## Recent Enhancements (v1.9.2)

### Banner H1 Suppression
`suppress_banner_h1` defaults to `True` everywhere (model, frontend, rescan, standalone scan). Only the first H1 is considered a banner candidate. CSS classes (`entry-title`, `page-title`, etc.) are also used as a signal. Single-H1 pages never have their only H1 removed.

### Fix Panel Enhancements
- **TITLE_H1_MISMATCH:** Dual editor (SEO Title + Content H1 Heading) with individual and combined apply buttons. Uses `change_heading_text` endpoint.
- **LINK_EMPTY_ANCHOR:** Per-link "Fixed" buttons that remove individual hrefs from the issue. Backend: `POST /api/fixes/mark-anchor-fixed`. Empty anchors now capture `aria_label` and `has_children` data.
- **Duplicate Issues:** TITLE_DUPLICATE, META_DESC_DUPLICATE, TITLE_META_DUPLICATE_PAIR now show the duplicate URLs in the UI.
- **SEMANTIC_DENSITY_LOW:** Full KB breakdown (text, scripts, styles, SVG, markup) with a visual bar and diagnosis of the biggest contributor.
- **Issue Extra Data:** All 50+ issue codes now include diagnostic data in `extra` so the user can see what triggered the issue.

### Auto-Rescan After Fix
After any WP fix (heading, title, meta, image), the page is automatically rescanned to update issues in the database. Health score refreshes live.

### Broken Link Source Tracking
Internal broken links track which page discovered them via `discovered_from` dict in engine. `extra.source_url` is populated. "Show Source Pages" endpoint has fallback to issue extra when links table is empty.

### Ignored Image Patterns
Global config: `POST/GET/DELETE /api/ignored-image-patterns`. Substring match patterns (e.g. `/location.svg`) to exclude theme icons from IMG_ALT_MISSING. Stored in `ignored_image_patterns` table. UI in Settings > "Ignored Imgs" tab.

### Sitemap & Robots.txt Discovery Display
Sitemap and Crawlability category tabs show what was found (sitemap URL, URL count, robots.txt rules) even when there are no issues. Data stored on job record.

### Scoring Fixes
- **Image Scoring:** Performance score no longer requires `load_time_ms` -- `file_size_bytes` alone (from HEAD requests) is sufficient. Image health score includes all images with file size data, not just fully-fetched ones.
- **Health Score:** Trailing slashes are normalized when matching issues to crawled pages.

### WordPress Integration Fixes
- **`find_post_by_url`:** Falls back to single-slug match when exact URL doesn't match (handles different parent paths). Image attachment finder strips WP size suffixes (e.g. `-600x403`) from filenames.
- **Heading Text Change:** `POST /api/fixes/change-heading-text` endpoint. Handles inline HTML, entity encoding, and whitespace normalization. Preserves `<h1>` tag attributes. Heading text is HTML-escaped before insertion to prevent XSS.

### Security Hardening (v1.9.3)
- **SSRF Protection:** `target_url` is validated against private/internal IPs (localhost, 169.254.x.x, 10.x.x.x, 192.168.x.x) via DNS resolution before crawl starts. Redirect chains are also validated — each hop is checked and blocked if it resolves to a private IP. Validation lives in `api/crawler/fetcher.py:is_ssrf_safe()`.
- **Authentication:** AI (`/api/ai/*`), GEO (`/api/geo/*`), and utility (`/api/*`) routers now require `AUTH_TOKEN` bearer auth. The `/api/health` endpoint is exempt (on a separate public router).
- **XSS Prevention:** `change_heading_text` in `wp_fixer.py` now HTML-escapes `new_text` before inserting into `<h{level}>` tags, preventing stored XSS via WordPress post content.
- **RedisJobStore Parity:** Added missing `get_ignored_image_patterns()`, `add_ignored_image_pattern()`, `remove_ignored_image_pattern()`, `get_ignored_image_pattern_list()` methods. Updated `update_job()` `_ALLOWED` whitelist to match SQLite (added `phase`, `external_links_checked`, `external_links_total`, `robots_txt_found`, `robots_txt_rules`, `sitemap_found`).

### Bug Fixes (v1.9.3)
- **Missing `import re`:** Added module-level `import re` in `engine.py` — was only imported inside `_fetch_image_full()` but used at top-level for `/llms.txt` parsing.
- **PDF/Excel Export:** Fixed `get_images()` unpacking in export endpoints — method returns `list[ImageInfo]`, not a tuple.

### Security: WordPress Domain Validation (v1.9.4)
- **Cross-site protection:** All 22 WP-touching endpoints now validate that `wp-credentials.json` domain matches the crawl job's target domain. Prevents data leakage (reading wrong site's media library) and accidental writes (modifying wrong WordPress site) when scanning multiple client domains.
- **Validation helpers:** `_validate_wp_domain_for_job(store, job_id)` for job-based endpoints, `_validate_wp_domain_for_url(url)` for URL-based endpoints. Returns 403 DOMAIN_MISMATCH on mismatch.
- **DELETE media endpoint hardened:** Now requires `job_id` parameter for domain verification.
- **AI router:** `apply-geo-metadata` validates domain before writing to WordPress.

### UI: Domain Display (v1.9.4)
- **Progress page:** Domain shown in prominent green badge during scanning.
- **Results page:** Domain appended to all section headers from backend `summary.target_url` — "Audit Results - domain", "Metadata - domain", "Orphaned Images - domain", etc.
- **Backend:** `get_summary()` now includes `target_url` in both SQLite and Redis stores.

### Frontend Quality (v1.9.4)
- **React hooks fix:** `useMemo` in `CategoryTab` and `SeverityTab` was placed after early return, violating Rules of Hooks and causing blank category pages. Moved above early return.
- **FixInlinePanel hooks fix:** 10 hooks (`useState`/`useEffect`/`useRef`) were after an early return for `TITLE_H1_MISMATCH`. Moved conditional return after all hooks.
- **ESLint:** Added `.eslintrc.cjs` with `react-hooks/rules-of-hooks: 'error'`. Build now runs `eslint --quiet` before `vite build` — hooks violations block the build.
- **File Save dialog:** Downloads (CSV, PDF, Excel) use `showSaveFilePicker` API for a proper Save As dialog with filename/folder selection. Falls back to standard download on unsupported browsers.

### Report Improvements (v1.9.4)
- **PDF category pages:** Each issue type now shows count of affected pages, description, and full URL listings (was showing only issue names with no data).
- **PDF help text:** Uses rich help content from `issueHelp.js` (via `api/services/issue_help_data.py`) instead of empty DB fields. Plain black text, no blue shading boxes. Sub-headings bold 9pt, body text regular 10pt.
- **PDF Top 10 Pages:** Color-coded issue counts (red/amber/blue) on one line instead of truncated text. URLs in normal weight font.
- **PDF orphan prevention:** Issue titles kept together with their help text — page breaks inserted before the title if insufficient room remains.
- **PDF Help Text option:** Available for both full and summary-only reports (was hidden when Summary Only checked).
- **PDF issue sorting:** Within each category, issues sorted by severity (critical first) then by affected page count.
- **PDF filenames:** Use domain name instead of job ID (e.g. `TalkingToad-Audit-example.com.pdf`). Same for Excel and CSV exports. Frontend extracts filename from Content-Disposition header.
- **PDF action checklist:** "What to Do Next" page with top 15 prioritized actions, checkboxes, severity colors, and recommendations.
- **PDF AI executive summary:** Optional 3-5 sentence plain-language narrative generated via Gemini/OpenAI, inserted as Page 2. Skipped gracefully if no AI keys configured.
- **Excel export fix:** `ImageInfo` objects converted via `.to_dict()` instead of crashing on `.get()` call.

### New Issue Codes (v1.9.5)
- **OG_IMAGE_MISSING:** Missing `og:image` meta tag — critical for social media sharing previews.
- **TWITTER_CARD_MISSING:** Missing `twitter:card` meta tag for Twitter/X rich previews.
- **CONTENT_STALE:** Page `Last-Modified` header older than 12 months.
- **ANCHOR_TEXT_GENERIC:** Links use "click here", "read more", etc. (15 patterns matched).
- **HEADING_EMPTY:** H1-H6 tags with no text content.
- **WWW_CANONICALIZATION:** Both www and non-www versions resolve without redirecting to each other.
- **Fixability tagging:** Every issue tagged as `wp_fixable` (20), `content_edit` (27), or `developer_needed` (40). Exposed in API responses via `fixability` field.
- **Architecture parity test:** Enforces that every code in `issueHelp.js` matches `_CATALOGUE` and vice versa.

### Crawl Comparison (v1.9.5)
- `GET /api/crawl/{job_id}/comparison` — compares health score, issue counts, and severity breakdown against the previous crawl for the same domain.
- `list_jobs_by_domain()` added to SQLite and Redis job stores.

### AI Executive Summary (v1.9.5)
- `GET /api/crawl/{job_id}/executive-summary` — generates and caches a plain-language summary via AI.
- Cached on job record after first generation (`executive_summary` column).

### UI Improvements (v1.9.5)
- **Tab consolidation:** 17 flat tabs replaced with 5 grouped sections: Overview, Issues (10 categories), Media, Pages, Actions. "Fix History" placeholder removed.
- **GEO Settings:** Pre-crawl blocking prompt removed from Home page. Non-blocking banner added to Results Summary tab instead.
- **llms.txt generator:** No longer auto-generates on page load. User clicks "Generate Recommendation" button. Shows status badge: "llms.txt Retrieved" (green) when saved content exists, "llms.txt Recommendation" (amber) when generated from crawl data. "Save to Job Data" button only appears after generation.

---

## Image Intelligence Engine (v1.9)

### Architecture: 3-Level Data Model

1. **Level 1: Scan Details** (Instant, from initial crawl)
   - HTML attributes: alt, title, rendered dimensions
   - Surrounding text context (±200 chars)
   - Decorative detection
   - Data source: `html_only`

2. **Level 2: Fetch** (Live data from WordPress + image file)
   - WordPress Media Library: alt_text, title, caption, description
   - Image file analysis: intrinsic dimensions, format, file size, load time
   - Content hash for duplicate detection
   - Data source: `full_fetch`

3. **Level 3: AI Analysis** (Vision model analysis)
   - AI-generated image description
   - Suggested alt text (80-125 chars)
   - Accuracy and quality scores
   - Data source: AI analysis metadata

### Image Issue Codes
| Code | Category | Description |
|---|---|---|
| `IMG_ALT_MISSING` | accessibility | Non-decorative image missing alt text |
| `IMG_ALT_TOO_SHORT` | accessibility | Alt text < 5 characters |
| `IMG_ALT_TOO_LONG` | accessibility | Alt text > 125 characters |
| `IMG_ALT_GENERIC` | accessibility | Generic terms (e.g., "image", "photo") |
| `IMG_ALT_DUP_FILENAME` | accessibility | Alt text duplicates filename |
| `IMG_ALT_MISUSED` | accessibility | Decorative image has meaningful alt text |
| `IMG_OVERSIZED` | performance | File size > 200KB |
| `IMG_SLOW_LOAD` | performance | Load time > 1000ms |
| `IMG_OVERSCALED` | performance | Intrinsic size > 2x rendered size |
| `IMG_POOR_COMPRESSION` | performance | Bytes per pixel > 0.5 |
| `IMG_FORMAT_LEGACY` | performance | JPEG/PNG/GIF > 50KB (should use WebP/AVIF) |
| `IMG_NO_SRCSET` | technical | Missing srcset when scaled down |
| `IMG_BROKEN` | technical | HTTP 4xx/5xx status |
| `IMG_DUPLICATE_CONTENT` | technical | Same content hash as another image |

### GEO-Optimized AI Analysis (v1.9.1)

**Status:** ✅ Implemented and tested

**Specs:** See `geo_image_ai_spec.md` and `geo_image_ai_prompt.md`

**Objective:** Generate semantically aligned, entity-rich Alt Text and Long Descriptions that satisfy both WCAG 2.2 and Generative Engine Optimization (GEO) standards.

**Triple-Context Packet:**
1. Image bytes (high-resolution for vision analysis)
2. Page context (surrounding text + H1 from page)
3. Global settings (org name, location pool, topic entities)

**Output Requirements:**
- Alt text: 80-125 chars with geographic and topic entities
- Description: 150-300 words, GEO-rich, factual for AI Overviews
- Entity density: Names, Places, Topics (not just keywords)

**Implementation:**
- Frontend: GeoAnalysisModal.jsx for reviewing/editing AI suggestions
- Frontend: GeoSettingsModal.jsx for configuring domain-specific settings
- Backend: `/api/ai/image/analyze-geo` for GEO analysis
- Backend: `/api/ai/image/apply-geo-metadata` for updating WordPress + database
- Backend: `/api/geo/settings` for saving/retrieving GEO configuration

**Configuration:** See section 5 in `geo_image_ai_spec.md`

### WordPress Integration

**Slug-Based Queries:** Uses WordPress REST API `slug` parameter for accurate image matching.

**Fields Fetched:**
- `alt_text`: WordPress alt text field
- `title`: Media title (HTML stripped)
- `caption`: Media caption (HTML stripped)
- `description`: Media description (HTML stripped)
- `source_url`: Full image URL for verification

**Exact URL Verification:** Only updates image metadata if WordPress `source_url` matches exactly.

---

## Image Optimization Module (v1.9.1)

### Two Workflows

**Workflow A: Existing Image (from crawl)**
1. Image already exists in WordPress (from crawl results)
2. Download original from WordPress URL
3. Resize → WebP → GPS EXIF → SEO rename
4. Archive original + optimized to local folder
5. Upload NEW optimized version to WordPress
6. **Result:** 2 files in WordPress (original stays, new added)
7. User manually replaces old image on page

**Workflow B: New Local Image (file picker)**
1. User selects file from local drive
2. Resize → WebP → GPS EXIF → SEO rename
3. Archive original + optimized to local folder
4. Upload to WordPress
5. **Result:** 1 file in WordPress (just the optimized one)

### Key Files

| File | Purpose |
|---|---|
| `api/services/exif_injector.py` | GPS coordinate injection via piexif |
| `api/services/upload_validator.py` | Pre-upload validation (size, GPS, format) |
| `api/services/batch_optimizer.py` | Batch job management with pause/resume/cancel |
| `api/services/image_processor.py` | WebP optimization + SEO filename generation |
| `api/services/wp_fixer.py` | `optimize_existing_image()` workflow |
| `frontend/src/components/OptimizeExistingModal.jsx` | Single image optimization UI |
| `frontend/src/components/BatchOptimizePanel.jsx` | Batch processing UI |

### Batch Processing

- Parallel execution with configurable concurrency (default: 3)
- Progress tracking per image
- Pause/resume without losing progress
- Cancel stops remaining images
- Per-image results with page URLs and error details

### Archive Structure

```
archive/
├── {job_id}/
│   ├── originals/{original_filename}
│   └── optimized/{seo_filename}.webp
```

### Tests

- `tests/test_image_optimization.py` - EXIF, SEO filename, validation, integration
- `tests/test_batch_optimizer.py` - Batch creation, controls, status, cleanup

---

## AI Integration (v1.7+)

### API Keys
Set in `.env` or `.env-ttoad`:
```
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
```
**Priority:** OpenAI is used if both keys are present; Gemini is the fallback.

### Gemini Configuration
- **Model:** `gemini-1.5-flash` (v1 stable endpoint)
- **Endpoint:** `https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent`
- **Timeout:** 20 seconds

### OpenAI Configuration
- **Model:** `gpt-4o`
- **Endpoint:** `https://api.openai.com/v1/chat/completions`
- **Timeout:** 20 seconds

### AI Prompt Library (`api/services/ai_analyzer.py`)
| Prompt Key | Purpose |
|---|---|
| `title_meta_optimize` | Rewrite title/meta for AI "quotability" (60/160 char limits) |
| `semantic_alignment` | Check H1 vs body content for conflicting signals |

### AI-Readiness Issue Codes
| Code | Severity | What it checks |
|---|---|---|
| `LLMS_TXT_MISSING` | info | No `/llms.txt` at site root |
| `LLMS_TXT_INVALID` | warning | Invalid format or >20 URLs |
| `SEMANTIC_DENSITY_LOW` | warning | Text-to-HTML ratio < 10% |
| `DOCUMENT_PROPS_MISSING` | warning | PDF missing Title/Subject metadata |
| `JSON_LD_MISSING` | warning | No JSON-LD structured data |
| `CONVERSATIONAL_H2_MISSING` | info | No question-based H2 headings |

### AI Endpoints
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/analyze` | Analyze a page using AI, returns remediation suggestions |
| GET | `/api/ai/test` | Test connectivity to Gemini/OpenAI providers |
| GET | `/api/utility/generate-llms-txt?job_id={id}` | Generate curated `/llms.txt` from crawl data |

---

## Issue Categories

| Category | Example Codes |
|---|---|
| `metadata` | TITLE_MISSING, META_DESC_TOO_LONG, OG_TITLE_MISSING |
| `heading` | H1_MISSING, H1_MULTIPLE, HEADING_SKIP |
| `broken_link` | BROKEN_LINK_404, IMG_BROKEN, EXTERNAL_LINK_TIMEOUT |
| `redirect` | REDIRECT_CHAIN, REDIRECT_LOOP, REDIRECT_302 |
| `crawlability` | ROBOTS_BLOCKED, NOINDEX_META, THIN_CONTENT, ORPHAN_PAGE |
| `duplicate` | TITLE_DUPLICATE, META_DESC_DUPLICATE |
| `sitemap` | SITEMAP_MISSING, NOT_IN_SITEMAP |
| `security` | HTTP_PAGE, HTTPS_REDIRECT_MISSING, MIXED_CONTENT |
| `url_structure` | URL_UPPERCASE, URL_HAS_SPACES, URL_TOO_LONG |
| `ai_readiness` | LLMS_TXT_MISSING, JSON_LD_MISSING, SEMANTIC_DENSITY_LOW |

**Scoring:** Each issue has `impact` (1-10) and `effort` (1-5). Priority = `(impact × 10) − (effort × 2)`.
**Health Score:** `max(0, 100 − Σ issue impacts)` across all issues.

---

## Coding Standards

### CRITICAL: Testing and Documentation Requirements

**YOU MUST create tests for ALL new functionality. NO EXCEPTIONS.**

When implementing new features:
1. **Write tests FIRST or IMMEDIATELY after** implementing the feature
2. **Update documentation** in `/docs` for any architectural changes
3. **Update CLAUDE.md** if coding standards or key features change
4. **Never commit untested code** - regressions waste user time and trust

**Required test types:**
- **Unit tests** for business logic (issue detection, scoring, analysis)
- **Integration tests** for API endpoints (request → response → side effects)
- **Architecture constraint tests** for design rules (e.g., "scan must never call WP API")
- **Serialization tests** for API responses (verify all model fields are included)

**Test file naming:**
- `test_[feature].py` for feature tests
- `test_[component]_integration.py` for integration tests
- `test_architecture_constraints.py` for design rule enforcement

### Code Quality Standards

- **GUI Architecture:** DO NOT change the GUI structure or navigation flow on your own. You MUST have explicit instructions from the user before altering how data is displayed or navigated.
- **Python:** Async-first, Pydantic models, strictly typed, `load_dotenv()` required in service entry points.
- **React:** Functional components, Tailwind CSS, explicit loading/error states for all API calls.
- **Reporting:** 1-inch margins, Letter format, Latin-1 safe text cleaning.
- **Issue Codes:** Source of truth is `api/crawler/issue_checker.py` (`_ISSUE_SCORING`, `_CATALOGUE`).
- **Frontend Help:** Issue explanations in `frontend/src/data/issueHelp.js` must match `docs/issue-codes.md`.

---

## Running Locally

```bash
# Backend
cd api && uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Tests
pytest tests/ -v
```

---

## Key Documentation

| File | Purpose |
|---|---|
| `docs/api.md` | Full API endpoint reference |
| `docs/architecture.md` | System design, data flow, design decisions |
| `docs/issue-codes.md` | All issue codes with explanations and fixes |
| `docs/overview.md` | Feature descriptions and crawl pipeline |
| `docs/image-scan-spec.md` | Image Intelligence Engine specification (v1.9) |
| `docs/image-scan-implementation-plan.md` | Image feature implementation roadmap |
| `geo_image_ai_spec.md` | GEO-Advanced Image Metadata Generator spec |
| `geo_image_ai_prompt.md` | Master prompt for 90+ score GEO optimization |
| `PLAN.md` | Implementation milestones and checklist |
| `TODO.md` | Technical debt and future improvements |
