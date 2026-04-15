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
│   ├── models/                  # Pydantic models (Job, Page, Issue, Fix)
│   ├── routers/                 # API endpoints (crawl, fixes, utility, verified, ai)
│   └── services/                # Business logic (WP Fixer, PDF/Excel Gen, AI, Image)
├── frontend/                    # React + Vite SPA
│   ├── src/pages/               # Home, Progress, Results
│   └── src/components/          # FixManager, LLMSTxtGenerator, etc.
├── tests/                       # Pytest suite (asyncio)
└── docs/                        # Specifications and API reference
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

## Coding Standards

- **Python:** Async-first, Pydantic models, strictly typed, `load_dotenv()` required in service entry points.
- **React:** Functional components, Tailwind CSS, explicit loading/error states for all API calls.
- **Reporting:** 1-inch margins, Letter format, Latin-1 safe text cleaning.
- **Testing:** Integration tests for all export and AI endpoints.
