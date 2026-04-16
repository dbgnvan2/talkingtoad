# TalkingToad — Nonprofit SEO Crawler

## Project Overview

TalkingToad is a lightweight, web-based SEO crawler for nonprofit organisations. It replicates the essential functionality of Screaming Frog SEO Spider — free, zero-installation, simple results — deployed on Vercel with a React frontend and Python/FastAPI backend.

**GitHub:** https://github.com/dbgnvan2/talkingtoad
**Spec:** `nonprofit-crawler-spec-v1.4.md` + v1.5 extensions + v1.9 Image Intelligence
**Current Version:** 1.9

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
│   │   ├── engine.py            # Async BFS crawler (~600 lines)
│   │   ├── issue_checker.py     # SEO issue detection (~1100 lines)
│   │   ├── image_analyzer.py    # Image analysis and scoring (~500 lines)
│   │   ├── parser.py            # BeautifulSoup HTML extraction
│   │   ├── normaliser.py        # URL normalization + WP noise detection
│   │   ├── robots.py            # robots.txt parser
│   │   └── sitemap.py           # XML sitemap parser
│   ├── models/                  # Pydantic models (Job, Page, Issue, Fix, Image)
│   │   └── image.py             # ImageInfo data model
│   ├── routers/                 # API endpoints (crawl, fixes, utility, verified, ai)
│   └── services/                # Business logic
│       ├── wp_fixer.py          # WordPress REST API integration (~1200 lines)
│       ├── ai_analyzer.py       # Gemini/OpenAI integration
│       ├── report_generator.py  # PDF audit generation (fpdf2)
│       ├── excel_generator.py   # Excel export (openpyxl)
│       ├── job_store.py         # SQLite/Redis abstraction
│       └── image_optimizer.py   # WebP conversion + SEO renaming
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

## Key Features (v1.9)

1. **Crawler:** Async engine with robots.txt/sitemap support and 50+ SEO issue checks.
2. **WordPress Fix Manager:** One-click remediation for titles, meta, and headings via WP REST API.
3. **Image Intelligence Engine (v1.9):**
   - 3-level data architecture: Scan (instant) → Fetch (live WP + image file) → AI Analysis
   - WordPress Media Library integration (alt text, title, caption, description)
   - Performance scoring (file size, compression, load time)
   - Accessibility scoring (alt text quality, length, semantic accuracy)
   - AI-powered alt text generation with vision models
   - GEO-optimized metadata (see `geo_image_ai_spec.md`)
4. **AI Readiness:** /llms.txt generator and AI semantic audit (Gemini/OpenAI).
5. **Reporting:** Professional 8.5" x 11" PDF audits and tabbed Excel workbooks.

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

### GEO-Optimized AI Analysis (Upcoming)

**Specs:** See `geo_image_ai_spec.md` and `geo_image_ai_prompt.md`

**Objective:** Generate semantically aligned, entity-rich Alt Text and Long Descriptions that satisfy both WCAG 2.2 and Generative Engine Optimization (GEO) standards.

**Triple-Context Packet:**
1. Image bytes (high-resolution for vision analysis)
2. Page context (300 chars before/after + H1)
3. Global settings (org name, location pool, topic entities)

**Output Requirements:**
- Alt text: 80-125 chars with 1 local entity + 1 topic entity
- Long description: 150-300 words, GEO-rich, factual for AI Overviews
- Entity density: Names, Places, Theories (not just keywords)

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

- **GUI Architecture:** DO NOT change the GUI structure or navigation flow on your own. You MUST have explicit instructions from the user before altering how data is displayed or navigated.
- **Python:** Async-first, Pydantic models, strictly typed, `load_dotenv()` required in service entry points.
- **React:** Functional components, Tailwind CSS, explicit loading/error states for all API calls.
- **Reporting:** 1-inch margins, Letter format, Latin-1 safe text cleaning.
- **Testing:** Integration tests for all export and AI endpoints.
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
