# TalkingToad — Nonprofit SEO Crawler

## Project Overview

TalkingToad is a lightweight, web-based SEO crawler for nonprofit organisations. It replicates the essential functionality of Screaming Frog SEO Spider — free, zero-installation, simple results — deployed on Vercel with a React frontend and Python/FastAPI backend.

**GitHub:** https://github.com/dbgnvan2/talkingtoad
**Spec:** `nonprofit-crawler-spec-v1.4.md` + v1.5 extensions
**Current Version:** 1.8

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
│   │   ├── parser.py            # BeautifulSoup HTML extraction
│   │   ├── normaliser.py        # URL normalization + WP noise detection
│   │   ├── robots.py            # robots.txt parser
│   │   └── sitemap.py           # XML sitemap parser
│   ├── models/                  # Pydantic models (Job, Page, Issue, Fix)
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

## Key Features (v1.8)

1. **Crawler:** Async engine with robots.txt/sitemap support and 50+ SEO issue checks.
2. **WordPress Fix Manager:** One-click remediation for titles, meta, and headings via WP REST API.
3. **Image Intelligence Engine:** Automated WebP optimization and SEO-friendly renaming.
4. **AI Readiness:** /llms.txt generator and AI semantic audit (Gemini/OpenAI).
5. **Reporting:** Professional 8.5" x 11" PDF audits and tabbed Excel workbooks.

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
| `PLAN.md` | Implementation milestones and checklist |
| `TODO.md` | Technical debt and future improvements |
