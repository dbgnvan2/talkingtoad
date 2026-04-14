# TalkingToad — Critical Review Document

> **Last Updated:** 2024-04-13
> **Purpose:** Provide context for external review of architecture, code quality, and improvement opportunities.

---

## 1. Project Summary

**TalkingToad** is a free, web-based SEO crawler for nonprofit organizations. It replicates essential Screaming Frog functionality with zero installation, deployed on Vercel.

**Key Value Proposition:**
- Nonprofits get enterprise-level SEO auditing without cost or technical complexity
- Direct WordPress integration allows fixes without coding
- Plain-English explanations instead of SEO jargon

**Target Users:** Nonprofit staff with limited technical expertise managing their own WordPress sites.

---

## 2. Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  React Frontend │────▶│  FastAPI Backend │────▶│  WordPress Site │
│  (Vite + Tailwind)    │  (Python 3.11+)  │     │  (REST API)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       ▼
        │               ┌─────────────────┐
        └──────────────▶│  SQLite (dev)   │
                        │  Redis (prod)   │
                        └─────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Crawl Engine | `api/crawler/engine.py` | Async orchestrator for page fetching |
| Issue Checker | `api/crawler/issue_checker.py` | Per-page and cross-page SEO analysis |
| Parser | `api/crawler/parser.py` | BeautifulSoup HTML extraction |
| WP Fixer | `api/services/wp_fixer.py` | WordPress REST API integration for fixes |
| Results UI | `frontend/src/pages/Results.jsx` | Main results dashboard (~3500 lines) |

### Data Flow

1. User submits URL → Backend creates job, starts async crawl
2. Crawler fetches pages respecting robots.txt, extracts metadata/links
3. Issue checker runs per-page checks during crawl, cross-page checks after
4. Results stored in job store (SQLite/Redis)
5. Frontend polls status, displays results with fix capabilities
6. User can connect WordPress credentials to apply fixes directly

---

## 3. Tech Stack Decisions

| Choice | Rationale | Trade-offs |
|--------|-----------|------------|
| **FastAPI + async** | High concurrency for crawling | Complexity of async code |
| **SQLite (dev) / Redis (prod)** | Simple local dev, scalable prod | Two storage backends to maintain |
| **BeautifulSoup + lxml** | Robust HTML parsing | Slower than regex for simple extractions |
| **Vercel deployment** | Free tier for nonprofits, easy deploys | 10s function timeout limits crawl speed |
| **No user accounts (Phase 1)** | Simplicity, faster MVP | No persistent history across sessions |
| **Bearer token auth** | Simple, stateless | Single shared token, not per-user |

---

## 4. Recent Changes (This Session)

### Heading Level Change Fixes
- **Bug Fixed:** Regex group indexes were wrong in `_change_heading_level_in_content` — was comparing closing tag `</h2>` instead of heading text content
- **Generalized:** `convert_heading_to_bold` now accepts any level (1-6), not hardcoded to H4

### Heading Source Analysis (New Feature)
- **Problem:** Users couldn't understand why some headings couldn't be fixed
- **Solution:** New `analyze_heading_sources()` function identifies where each heading lives:
  - `post_content` — In main post/page content (fixable via API)
  - `reusable_block` — In a reusable block (fixable via API)
  - `widget` — In WordPress widget (not fixable via API)
  - `acf_field` — In Advanced Custom Fields (not fixable via API)
  - `unknown` — Theme template, plugin output, shortcode (not fixable)
- **UI:** Shows source badges, disables fix controls for non-fixable headings
- **Debug Panel:** Shows raw content analysis for troubleshooting

### Text Matching Improvements
- **Problem:** Whitespace differences between crawled text and raw content caused matching failures (e.g., `"(online) or"` vs `"(online)or"`)
- **Solution:** `_normalize_text_for_comparison()` now removes ALL whitespace before comparing
- **Fallback:** When heading text matches but level differs (already changed), still marks as fixable

### Duplicate Detection Fix
- **Problem:** Redirect pages (301/302) were flagged as duplicates of their target pages
- **Solution:** Skip pages with 3xx status or `redirect_url` from duplicate detection

---

## 5. Known Limitations & Technical Debt

### Architecture Issues

| Issue | Impact | Potential Fix |
|-------|--------|---------------|
| **Results.jsx is 3500+ lines** | Hard to maintain, slow to load | Split into smaller components |
| **No request queuing** | Vercel timeout can kill long crawls | Add background job queue (e.g., Celery, Bull) |
| **Single bearer token** | No per-user isolation | Add user accounts (Phase 3) |
| **Synchronous fix application** | Slow for bulk fixes | Parallelize with rate limiting |

### Code Quality Concerns

| Concern | Location | Notes |
|---------|----------|-------|
| **Regex complexity** | `wp_fixer.py` | Gutenberg block matching is fragile |
| **Error handling** | Various | Some exceptions silently logged, not surfaced to user |
| **Test coverage** | `wp_fixer.py` | No unit tests for WordPress fix functions |
| **Hardcoded values** | Issue checker | Some thresholds (e.g., title length) should be configurable |

### Missing Features (Planned)

| Feature | Phase | Spec Reference |
|---------|-------|----------------|
| Orphan page detection | 2 | §3.4 |
| Internal link analysis | 2 | §3.4 |
| Image optimization checks | 2 | §3.5 |
| PDF export | 2 | §6.4 |
| User accounts | 3 | §15 |
| Scheduled crawls | 3 | §15 |

---

## 6. Open Questions & Uncertainties

### Technical

1. **Custom Gutenberg blocks:** Should we parse block JSON attributes to find headings stored as `{"text": "..."}` instead of HTML?
2. **ACF field editing:** Should we add support for editing ACF fields via their REST API?
3. **Widget editing:** Is it worth adding widget editing via `/wp/v2/widgets` endpoint?
4. **Performance:** Is the whitespace-removal normalization too aggressive? Could it cause false positive matches?

### Product

1. **Scope creep:** How much WordPress-specific functionality should we add vs staying tool-agnostic?
2. **User confusion:** The "Theme/Plugin" label might be confusing — should we provide more specific guidance?
3. **Fix verification:** Should we auto-rescan after fixes to verify they worked?

### Security

1. **Credential storage:** WordPress credentials are stored in a JSON file — is this secure enough?
2. **Token rotation:** Should we implement token rotation or expiry?
3. **Rate limiting:** Current limits may be too permissive for production.

---

## 7. Areas Requesting Review

### High Priority

1. **`api/services/wp_fixer.py`** — Regex-based content manipulation is error-prone. Is there a better approach?
2. **`api/crawler/issue_checker.py`** — Duplicate detection and cross-page logic. Are there edge cases we're missing?
3. **Error handling patterns** — Are we failing gracefully and providing useful feedback?

### Medium Priority

4. **Frontend state management** — Results.jsx manages a lot of state. Should we use a state library?
5. **API design** — Are the endpoints RESTful and intuitive?
6. **Test coverage** — What critical paths are untested?

### Low Priority

7. **Performance optimization** — Any obvious bottlenecks?
8. **Accessibility** — Is the frontend accessible?
9. **Documentation** — Are the docs accurate and complete?

---

## 8. Code Examples for Context

### Heading Source Analysis (New)

```python
async def analyze_heading_sources(wp, page_url, crawled_headings):
    """Identify where each heading lives in WordPress."""
    # 1. Fetch post content via REST API
    # 2. Extract headings from raw HTML
    # 3. Check widgets, ACF fields, reusable blocks
    # 4. Match crawled headings to sources
    # 5. Return fixability status for each
```

### Text Normalization

```python
def _normalize_text_for_comparison(text: str) -> str:
    """Remove all whitespace for fuzzy matching."""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\u2010-\u2015\u2212]', '-', text)  # dashes
    text = re.sub(r'[\u2018\u2019]', "'", text)  # quotes
    text = re.sub(r'\s+', '', text)  # remove ALL whitespace
    return text.lower()
```

### Duplicate Detection (Updated)

```python
for page in pages:
    # Skip redirects — they shouldn't be flagged as duplicates
    if page.redirect_url or (300 <= page.status_code < 400):
        continue
    # ... build duplicate detection maps
```

---

## 9. File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `api/services/wp_fixer.py` | ~1200 | WordPress fix generation and application |
| `api/crawler/issue_checker.py` | ~1100 | SEO issue detection logic |
| `api/crawler/engine.py` | ~600 | Async crawl orchestration |
| `frontend/src/pages/Results.jsx` | ~3500 | Main results UI |
| `api/routers/fixes.py` | ~650 | Fix-related API endpoints |
| `api/routers/crawl.py` | ~400 | Crawl-related API endpoints |

---

## 10. How to Provide Feedback

When reviewing, please consider:

1. **Correctness:** Does the code do what it claims?
2. **Robustness:** What edge cases could break it?
3. **Maintainability:** Will this be easy to modify in 6 months?
4. **Performance:** Are there obvious inefficiencies?
5. **Security:** Are there vulnerabilities?
6. **UX:** Will users understand what's happening?

Feedback format suggestion:
```
## [Component/File]
### Issue: [Brief description]
- **Severity:** Critical / Major / Minor / Suggestion
- **Current behavior:** [What happens now]
- **Recommended change:** [What should change]
- **Rationale:** [Why this matters]
```

---

## Appendix: Key Specifications

- **Full spec:** `nonprofit-crawler-spec-v1.4.md`
- **Project setup:** `CLAUDE.md`
- **API reference:** `docs/api.md`
- **Issue codes:** `docs/issue-codes.md`
