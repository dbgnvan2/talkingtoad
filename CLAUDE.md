# TalkingToad — Nonprofit SEO Crawler

## Project Overview

TalkingToad is a lightweight, web-based SEO crawler for nonprofit organisations. It replicates the essential functionality of Screaming Frog SEO Spider — free, zero-installation, simple results — deployed on Vercel with a React frontend and Python/FastAPI backend.

**GitHub:** https://github.com/dbgnvan2/talkingtoad
**Spec:** `nonprofit-crawler-spec-v1.4.md` (source of truth for all behaviour)
**Initial test site:** livingsystems.ca

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python 3.11+ + FastAPI |
| HTTP Client | httpx (async) |
| HTML Parser | BeautifulSoup4 + lxml |
| Rate Limiting | slowapi |
| Logging | python-json-logger (structured JSON to stdout) |
| Data Store | SQLite (dev) → Upstash Redis (prod) |
| Hosting | Vercel (frontend + serverless functions) |
| Testing | pytest + pytest-asyncio (asyncio_mode = auto) |

---

## Directory Structure

```
TalkingToad/
├── CLAUDE.md
├── README.md
├── vercel.json                  # Vercel routing config
├── .env.example                 # Template — never commit .env
├── requirements.txt             # Python backend deps
├── pytest.ini                   # pytest config (asyncio_mode = auto)
├── nonprofit-crawler-spec-v1.4.md
├── api/                         # FastAPI backend (Vercel Python runtime)
│   ├── main.py                  # App entry point, middleware
│   ├── models/                  # Pydantic models + DB schemas
│   │   ├── job.py
│   │   ├── page.py
│   │   ├── link.py
│   │   └── issue.py
│   ├── routers/                 # API route handlers
│   │   ├── crawl.py             # /api/crawl/* endpoints
│   │   └── utility.py           # /api/health, /api/robots, /api/sitemap
│   ├── services/                # Business logic layer
│   │   ├── job_store.py         # Job/result persistence abstraction
│   │   ├── rate_limiter.py      # slowapi setup
│   │   └── auth.py              # Bearer token middleware
│   └── crawler/                 # Crawl engine
│       ├── engine.py            # Async crawl orchestrator
│       ├── fetcher.py           # httpx page fetcher
│       ├── parser.py            # BeautifulSoup4 + lxml extraction
│       ├── normaliser.py        # URL normalisation + deduplication
│       ├── robots.py            # robots.txt parser
│       ├── sitemap.py           # Sitemap auto-discovery + parsing
│       └── issue_checker.py     # Issue detection logic per spec §3
├── frontend/                    # React + Vite SPA
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── pages/
│       │   ├── Home.jsx         # URL entry form
│       │   ├── Progress.jsx     # Crawl progress (polling)
│       │   ├── Results.jsx      # Results dashboard (tabbed)
│       │   └── Export.jsx       # CSV download
│       ├── components/          # Shared UI components
│       └── hooks/               # Custom React hooks (useCrawl, usePolling)
├── tests/                       # pytest test suite
│   ├── conftest.py              # Shared fixtures
│   ├── test_normaliser.py       # URL normalisation + dedup
│   ├── test_robots.py           # robots.txt parsing
│   ├── test_sitemap.py          # Sitemap parsing (index, gzip, fallback)
│   ├── test_issue_checker.py    # Issue code generation
│   ├── test_api.py              # API endpoint integration tests
│   └── test_crawl_engine.py     # Crawl engine unit tests
└── docs/                        # Project documentation
    ├── architecture.md           # System design decisions
    ├── api.md                   # API endpoint reference
    ├── issue-codes.md           # Full issue code reference
    └── user-guide.md            # End-user help for nonprofit staff
```

---

## Local Development

### Backend
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Edit with local values
uvicorn api.main:app --reload --port 8000
```
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local        # Set VITE_API_URL=http://localhost:8000
npm run dev
```
- Frontend: http://localhost:5173

### Tests
```bash
# From project root with venv active
pytest tests/ -v
```

---

## Coding Standards

### Python (backend)
- Python 3.11+, strict type annotations throughout
- Async-first: all I/O operations must be `async`
- Pydantic models for all request/response schemas
- Raise `HTTPException` with the standard error codes from spec §6.5
- Never block the event loop — use `httpx.AsyncClient` exclusively
- Per-request HTTP timeout: 5 seconds (env: `CRAWL_REQUEST_TIMEOUT_S`)
- All log output via `python-json-logger` — no bare `print()` statements
- Include `job_id` in every log entry where applicable

### JavaScript/React (frontend)
- React 18 functional components, hooks only — no class components
- Tailwind CSS utility classes — no custom CSS unless unavoidable
- Polling: 2s for first 60s, then 5s; stop immediately on terminal status
- Progress bar: indeterminate spinner when `pages_total` is null
- Plain English in all user-facing copy — no SEO jargon

---

## Key Spec Rules (non-negotiable)

1. **URL normalisation:** Strip trailing slashes, lowercase scheme+host, remove fragments, strip UTM/tracking params, preserve other query params. Cap query variants per path at 50.
2. **Domain boundaries:** `www` prefix is same domain; other subdomains are external.
3. **Crawl ethics:** Always check `robots.txt` before crawl. Min delay 200ms. User-Agent must identify the tool.
4. **External link caps:** 50/page, 500/job. HEAD requests (fall back to GET on 405).
5. **Admin path skipping:** `/wp-admin/*`, `/wp-login.php`, `/admin/*`, login paths — skip by default.
6. **Canonical scoping:** Only emit `CANONICAL_MISSING` for pages with query strings OR near-duplicates. Not for all pages.
7. **Favicon check:** Homepage only — emit `FAVICON_MISSING` once per crawl.
8. **Phase 2 fields:** Collect `has_viewport_meta`, `schema_types`, `external_script_count`, `external_stylesheet_count` during Phase 1 crawl — store in DB, suppress from UI until Phase 2.
9. **Auth:** Bearer token (`Authorization: Bearer <token>`) from day one. Token set via `AUTH_TOKEN` env var.
10. **Error responses:** Always return `{"error": {"code": "...", "message": "...", "http_status": ...}}`.

---

## Documentation Requirements

**You must maintain these as the project evolves:**

- `docs/api.md` — keep in sync with every endpoint change
- `docs/issue-codes.md` — update when issue codes change
- `docs/user-guide.md` — plain-English help for nonprofit staff; update when UI changes
- `docs/architecture.md` — update when major architectural decisions are made
- Inline docstrings on all public functions and classes
- Update `README.md` when setup steps change

---

## Testing Requirements

**All new code must include tests. Regressions are not acceptable.**

### Mandatory test coverage:
- URL normalisation (all rules in spec §2.7)
- Query string deduplication and 50-variant cap
- robots.txt parsing and rule enforcement
- Sitemap parsing: index files, gzip, fallback to `SITEMAP_MISSING`
- Redirect chain and loop detection
- Canonical tag scoping logic (the three conditions)
- All issue code generation functions
- API endpoints: happy path + all error codes from spec §6.5
- Rate limiting middleware
- Auth token middleware
- External link cap enforcement

### Test conventions:
- Use `pytest-asyncio` with `asyncio_mode = auto`
- Use `httpx.AsyncClient` as the async test client for FastAPI
- Mock external HTTP calls — tests must not hit real websites
- Use descriptive test names: `test_<what>_<condition>_<expected_result>`
- Group related tests in classes when testing the same module

---

## Phase Tracking

### Phase 1 — MVP (current focus)
See `nonprofit-crawler-spec-v1.4.md` §15 for the full checklist.

**Core deliverables:**
- [ ] Crawler engine + async job queue
- [ ] URL normalisation + domain boundary logic
- [ ] robots.txt + sitemap parsing
- [ ] All Phase 1 issue checks (broken links, metadata, headings, redirects, crawlability, duplicates)
- [ ] Full REST API (all endpoints in spec §6)
- [ ] Rate limiting + auth token
- [ ] React frontend (URL entry → progress → results → CSV export)
- [ ] Full test suite
- [ ] Vercel deployment

### Phase 2 — Extended Checks
- Internal link analysis + orphan detection
- Schema markup, image analysis, mobile viewport, performance signals
- Phase 2 issue codes surfaced in UI
- PDF export

### Phase 3 — Productisation
- User accounts, scheduled crawls, white-label mode

---

## Environment Variables

See `.env.example` for all variables. Required in production:
- `DATABASE_URL` — Upstash Redis connection string
- `ALLOWED_ORIGINS` — comma-separated CORS origins (no wildcards in prod)
- `CRAWLER_USER_AGENT` — must identify the tool with a URL
- `AUTH_TOKEN` — bearer token for endpoint protection

---

## Deployment

Deployed via `vercel.json`:
- `/api/*` → `api/main.py` (Python serverless)
- `/*` → `frontend/dist` (React SPA)

Set environment variables in Vercel dashboard after first deploy.
