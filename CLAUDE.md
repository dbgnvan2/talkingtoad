# TalkingToad — Nonprofit SEO Crawler

> **What this file is:** the lean, machine-readable rulebook for working in this repo. Rules, constraints, and file paths only. No version history, no feature descriptions.
>
> **Historical narrative and feature snapshots** live in [`docs/legacy_changelog.md`](docs/legacy_changelog.md).
>
> **Current behaviour** lives in the canonical docs:
> `docs/functional-specification.md` (read-only master) · `docs/architecture.md` · `docs/api.md` · `docs/issue-codes.md` · `docs/thresholds.md` · `docs/specs/`.

---

## Project Overview

Lightweight web-based SEO crawler for nonprofit organisations — Screaming-Frog-style technical SEO, plus image intelligence, WordPress fix automation, and AI-readiness checks.

- **GitHub:** https://github.com/dbgnvan2/talkingtoad
- **Specs index:** `docs/specs/README.md`
- **Current version:** 2.6.0 (tag `v2.6-stabilized`). v2.6 stabilization phase is **complete**; v3.0 feature implementation is now active — see `PLAN-V3.0.md`.
- **Issue catalogue:** 131 codes in `_CATALOGUE` / `_ISSUE_SCORING` / `_AI_READINESS_CONFIDENCE` (see `docs/issue-codes.md`)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python 3.11+ + FastAPI |
| HTTP Client | httpx (async) |
| HTML Parser | BeautifulSoup4 + lxml |
| PDF Parser | pypdf |
| PDF Generator | fpdf2 (Letter format, Latin-1 safe text cleaning) |
| Excel Generator | openpyxl (tabbed workbooks) |
| Image Processing | Pillow (WebP optimization) |
| AI Analysis | Google Gemini / OpenAI |
| Data Store | SQLite (dev) / Upstash Redis (prod) |
| Hosting | Vercel SPA frontend + Railway container backend (see `docs/deployment-railway.md`) |

---

## Critical Local Files (DO NOT COMMIT)

- `wp-credentials.json` — WordPress API credentials
- `.env` — main environment variables
- `.env-ttoad` — custom override environment variables
- `talkingtoad.db` — local SQLite database

Treat any new credential/secret file as in this class by default; add it to `.gitignore` in the same change that introduces it.

---

## Directory Structure

```
TalkingToad/
├── api/                         # FastAPI backend
│   ├── crawler/                 # Async crawl engine + issue detection
│   │   ├── engine.py            # Async BFS crawler
│   │   ├── issue_checker.py     # SEO issue detection (_CATALOGUE source of truth)
│   │   ├── image_analyzer.py    # Image analysis and scoring
│   │   ├── parser.py            # BeautifulSoup HTML extraction
│   │   ├── normaliser.py        # URL normalization + WP noise detection
│   │   ├── fetcher.py           # is_ssrf_safe() + fetch_page()
│   │   ├── robots.py            # robots.txt parser
│   │   └── sitemap.py           # XML sitemap parser
│   ├── models/                  # Pydantic models (Job, Page, Issue, Fix, Image)
│   ├── routers/                 # API endpoints
│   │   ├── crawl.py             # Crawl lifecycle + summary/pages/comparison
│   │   ├── fixes.py             # Fix-manager router registration
│   │   ├── fixes_shared.py      # Shared fix helpers (get_store, validators)
│   │   ├── fix_title.py         # Title/meta fix domain
│   │   ├── fix_heading.py       # Heading fix domain
│   │   ├── fix_image.py         # Image-metadata fix domain
│   │   ├── fix_orphaned_media.py
│   │   ├── fix_batch_optimizer.py
│   │   ├── fix_link.py          # Link/anchor fix domain
│   │   ├── verified.py          # Re-verification endpoints
│   │   ├── ai.py                # AI advisor/rewriter/analyzer endpoints
│   │   ├── geo.py               # GEO settings + image GEO metadata
│   │   └── utility.py           # llms.txt, ignored patterns, exports
│   └── services/                # Business logic
│       ├── wp_fixer.py          # WordPress REST API integration
│       ├── wp_title_fixer.py    # Title trim helpers
│       ├── wp_heading_fixer.py  # Heading helpers
│       ├── wp_image_fixer.py    # Image metadata + Workflow A/B optimization
│       ├── wp_client.py         # Authenticated WP REST client
│       ├── wp_shared.py         # Shared field specs, get_fixable_codes
│       ├── ai_analyzer.py       # Gemini/OpenAI integration
│       ├── advisor.py           # Quality advisor (v2.2)
│       ├── rewriter.py          # Content rewriter (v2.2)
│       ├── report_generator.py  # PDF audit generation (fpdf2)
│       ├── excel_generator.py   # Excel export (openpyxl)
│       ├── job_store.py         # SQLite/Redis abstraction
│       ├── image_processor.py   # WebP optimization + SEO renaming
│       ├── exif_injector.py     # GPS EXIF coordinate injection
│       ├── upload_validator.py  # Pre-upload validation
│       └── batch_optimizer.py   # Batch job management
├── frontend/                    # React + Vite SPA
│   ├── src/pages/               # Home, Progress, Results (Results.jsx — see PLAN-V3.0.md M9.3 refactor note)
│   ├── src/components/          # FixManager, LLMSTxtGenerator, etc.
│   └── src/data/issueHelp.js    # Help content; MUST stay in sync with _CATALOGUE
├── tests/                       # Pytest suite (asyncio)
└── docs/                        # Flat structure — no architecture/, api/, reference/ subdirs
    ├── README.md                # Documentation index
    ├── architecture.md          # System design
    ├── api.md                   # API reference
    ├── issue-codes.md           # Auto-generated from _CATALOGUE
    ├── thresholds.md            # Canonical numeric thresholds
    ├── functional-specification.md  # READ-ONLY master
    ├── legacy_changelog.md      # Evicted historical content
    ├── pending/                 # Pending micro-spec proposals (see rules below)
    └── specs/                   # Per-feature specs
        ├── core-crawler/
        ├── image-analysis/
        ├── ai-readiness/
        └── wordpress-integration/
```

> All canonical docs live flat in `docs/`. Earlier READMEs referenced `docs/architecture/`, `docs/api/`, `docs/reference/` subdirectories — those never existed.

---

## Hard Constraints (read these before changing anything)

### Specification Change Management (load-bearing)

1. **READ-ONLY files:** `docs/functional-specification.md`, `docs/thresholds.md`, and any file with `status: current` frontmatter. You are strictly forbidden from editing these directly.
2. **Micro-spec first:** Before writing any implementation code or tests for a new feature, enhancement, or bug fix, write a targeted micro-specification snippet.
3. **Save the proposal:** Place the snippet in `docs/pending/` using the naming convention `YYYY-MM-DD_feature-name.md`.
4. **Stop and notify:** After saving the pending file, stop immediately and notify the user to review and approve. Do not modify source code until approval is explicitly granted.

After approval:
- Implement the change and write the tests in the same cycle.
- Update `docs/issue-codes.md` (auto-generator) and `docs/thresholds.md` if scoring or numeric bounds changed.

### Per-item completion workflow (standing rules, user-directed 2026-05-31)

After **each** spec/item is implemented, reviewed, and green, do all of the following before moving on:
1. **Run the Gemini Compiler** — `./scripts/run_compiler.sh` folds every `docs/pending/*.md` into `docs/functional-specification.md` (the one sanctioned write to that READ-ONLY file) and clears `docs/pending/`. The script backs up the spec and aborts if Gemini output looks truncated. Run it after every spec is done — not only at milestone boundaries.
2. **Update `PLAN-V4.0.md`** — when an item ships a user-facing feature/code with its V4 explainer, record it in the V4 worked-examples tally so the future education layer stays current.
3. **Push to GitHub** — `git push origin main` after each item (commits land on `main`; the bridge operates on `main`).

### WordPress Safety

- **DO NOT IMPLEMENT URL CHANGES VIA WP API.** The WordPress REST API is not reliable for operations that change URLs (slugs, permalinks, redirects). Do not add endpoints or fix flows that do this.
- **DO NOT AUTOMATE IMAGE LINK UPDATES IN POSTS/PAGES.** Image optimization uploads a new file; the user manually replaces the old image in the post.
- **Domain-validate every WP call.** Every WP-touching endpoint must call `_validate_wp_domain_for_job(store, job_id)` or `_validate_wp_domain_for_url(url)`. Mismatches return 403 `DOMAIN_MISMATCH`.

### GUI Architecture

- **DO NOT change the GUI structure or navigation flow on your own.** Explicit user instructions are required before altering how data is displayed or navigated.

### Security Defaults

- **SSRF:** All outbound fetches go through `api/crawler/fetcher.py:is_ssrf_safe()`. Private/internal IPs are blocked at start *and* on every redirect hop.
- **Auth:** `/api/ai/*`, `/api/geo/*`, and `/api/*` utility routers require `AUTH_TOKEN` bearer auth via `require_auth`. In production, an empty `AUTH_TOKEN` is **fail-closed**. `/api/health` is the only public endpoint (separate router).
- **XSS:** Any helper that injects user-supplied text into HTML (e.g. `change_heading_text`) must HTML-escape before insertion.

---

## Coding Standards

### CRITICAL: Testing and Documentation Requirements

**You must create tests for all new functionality. No exceptions.**

1. Write tests first, or immediately after implementing the feature.
2. Update documentation in `/docs` for any architectural or behaviour change.
3. Update `CLAUDE.md` only if rules, constraints, or paths change — not for feature descriptions.
4. Never commit untested code.

**Required test types:**
- **Unit tests** for business logic (issue detection, scoring, analysis).
- **Integration tests** for API endpoints (request → response → side effects).
- **Architecture constraint tests** for design rules (e.g. "scan must never call WP API", catalogue ↔ help ↔ scoring ↔ confidence-label parity).
- **Serialization tests** for API responses (verify every model field a frontend reads is included).

**Test file naming:**
- `test_[feature].py` — feature tests
- `test_[component]_integration.py` — integration tests
- `test_architecture_constraints.py` — design-rule enforcement

### CRITICAL: API Contract Tests (Non-Negotiable)

**Any endpoint called by frontend code must have an integration test before the frontend code is written.**

1. Write the integration test first with realistic data.
2. Verify the response schema — fields, types, optionality.
3. Assert every field the frontend depends on. If the frontend does `data.pages[0].content`, assert `.content` exists in the test.
4. Test error cases — 404, 500, invalid input, missing auth.
5. Only then write the frontend code.

**Example:**

```python
def test_pages_endpoint_has_content_field(self, client):
    """Frontend code assumes page.content exists. This test fails if the API schema changes."""
    response = client.get("/api/crawl/job-id/pages?limit=1")
    page = response.json()["pages"][0]
    assert "content" in page, "Frontend code depends on page.content field"
```

**Consequences of skipping this:** frontend code breaks silently in production, users see "nothing happens" errors, the bug is caught after implementation, not during planning. This is not optional.

### Planning Requirement: Integration Tests in Implementation Plan

Every implementation plan (written before code) must include a table of API endpoints:

| Endpoint | Frontend expects | Test name | Status |
|---|---|---|---|
| GET `/api/crawl/{job_id}/pages` | `url`, `title` (NOT `content`) | `test_pages_endpoint_has_url_not_content` | Pending |
| POST `/api/ai/rewriter` | `rewrite`, `stopped_by_limit` | `test_rewriter_response_schema` | Pending |

Before any code: every test in this table must be written and passing.

### CRITICAL: Self-Review Before Every Commit

After writing any function — before staging it — answer these review questions in code (as tests), not in your head.

**For every text-processing function (regex search, word count, score input):**
1. What is the *actual* text in the buffer? Name every section that could appear in it.
2. Is there any text in the buffer that should NOT count toward the result? (footers, appendices, GEO NOTES, nav elements, metadata sections)
3. What input produces a passing/matching result for the *wrong* reason? Write one test that tries to fool the function with that input.

**For every scoring function (any function returning a 0–1 score or numeric rating):**
1. Is the denominator fixed or dynamic? If dynamic, what can inflate or shrink it?
2. What input produces the *highest* score? Is that actually the best content?
3. Does more failure always produce a lower score? Write one monotonicity test.

**The one-question shortcut:** "What would a correct-looking but wrong result look like?" If you can describe it, write a test that produces it and assert it fails.

A function without at least one adversarial test case is not done.

### Code Quality Standards

- **Python:** async-first, Pydantic models, strictly typed, `load_dotenv()` in service entry points.
- **React:** functional components, Tailwind CSS, explicit loading/error states for every API call. Hooks before any early return.
- **Linting:** ESLint with `react-hooks/rules-of-hooks: 'error'` is wired into the frontend build — hooks violations block the build. Do not disable.
- **Reporting:** Letter format, 1-inch margins, Latin-1-safe text cleaning.
- **Issue codes — source of truth:** `api/crawler/issue_checker.py` (`_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`). `frontend/src/data/issueHelp.js` and `docs/issue-codes.md` must stay in sync — the parity tests will fail otherwise.
- **CI guards:** endpoint-coverage test, issue-codes.md generator-sync test, dead-code allowlist. Do not bypass; fix the underlying drift.

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

## Key Documentation Pointers

**Start here:** `docs/README.md` — flat documentation index.

**Specifications (per feature domain):**

| Feature | Latest Version | File |
|---|---|---|
| Core Crawler | v1.5 | `docs/specs/core-crawler/README.md` |
| Image Analysis | v1.9.1 | `docs/specs/image-analysis/README.md` |
| AI-Readiness | v2.0 (in progress for v3.0) | `docs/specs/ai-readiness/README.md` |
| WordPress Integration | v1.0 | `docs/specs/wordpress-integration/README.md` |

**Canonical references:**

| Document | Purpose |
|---|---|
| `docs/architecture.md` | System design, data flow, design decisions |
| `docs/api.md` | Full API endpoint reference |
| `docs/issue-codes.md` | All issue codes — auto-generated from `_CATALOGUE` |
| `docs/thresholds.md` | Every numeric threshold the app uses |
| `docs/functional-specification.md` | READ-ONLY master spec |
| `docs/legacy_changelog.md` | Historical narrative and superseded feature snapshots |

**Project management:**

| File | Purpose |
|---|---|
| `PLAN-V3.0.md` | v3.0 plan: 11 milestones, release phasing |
| `PLAN.md` | Original pre-v3 implementation plan |
| `TODO.md` | Technical debt and future improvements |
| `REVIEW_SPEC.md` | Code review specification |
