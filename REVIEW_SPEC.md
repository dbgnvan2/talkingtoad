# TalkingToad — Code Review Specification

## Purpose

This document defines what a thorough code review of the TalkingToad codebase should cover. Use it as a prompt for a fresh review session to get an unbiased, comprehensive assessment.

---

## 1. Security

### Authentication & Authorization
- [ ] `AUTH_TOKEN` bearer token validation — is it enforced on all endpoints?
- [ ] WordPress credentials handling (`wp-credentials.json`) — stored securely? Exposed in responses?
- [ ] API keys (Gemini, OpenAI) — leaked in logs or responses?
- [ ] Any endpoints accessible without auth that should require it?

### Injection & XSS
- [ ] SQL injection in SQLite queries — are all queries parameterized?
- [ ] XSS in any user-supplied content rendered in the frontend?
- [ ] Command injection via URL parameters passed to shell or regex?
- [ ] HTML injection via heading text, alt text, or other WP content edits?

### SSRF & Request Forgery
- [ ] Can a user supply a `target_url` that hits internal services (localhost, 169.254.x.x)?
- [ ] Does the crawler follow redirects to internal/private IPs?
- [ ] Are WP API requests scoped to the configured site only?

---

## 2. Data Integrity

### Database
- [ ] Race conditions in concurrent crawl jobs sharing the same SQLite DB?
- [ ] Orphaned records — do deleted jobs leave behind issues/pages/links/images?
- [ ] Transaction boundaries — are multi-step operations atomic?
- [ ] Schema migrations — do `ALTER TABLE` migrations handle existing data correctly?
- [ ] `update_job` allowed fields — can unexpected fields be injected?

### URL Normalization
- [ ] Trailing slash consistency between issues, crawled_pages, and links tables
- [ ] URL encoding/decoding consistency (unicode, spaces, special chars)
- [ ] Case sensitivity in URL comparisons

### State Management
- [ ] Can marking an issue as "fixed" corrupt the issue list (partial updates)?
- [ ] Does `mark-anchor-fixed` handle concurrent modifications?
- [ ] Health score calculation — verified against all edge cases?

---

## 3. Error Handling

### Backend
- [ ] Every `try/except` — are exceptions logged with context?
- [ ] Do API endpoints always return structured error responses (not raw exceptions)?
- [ ] Timeout handling — crawl, rescan, WP API calls, external link checks?
- [ ] What happens when the SQLite DB file is locked or corrupted?

### Frontend
- [ ] Does the Results page crash on null/undefined data?
- [ ] Are all `async` operations wrapped with error handling?
- [ ] Does the UI show meaningful errors vs. silent failures?
- [ ] What happens when the backend is unreachable?

---

## 4. Performance

### Crawl Engine
- [ ] Memory usage for large sites (500+ pages) — are pages held in memory?
- [ ] External link checking — can 500 HEAD requests block the event loop?
- [ ] Image HEAD requests — timeout and concurrency limits?
- [ ] Sitemap parsing for large sitemaps (10,000+ URLs)?

### Database Queries
- [ ] `get_all_issues` loads everything into memory — scalable for 5000+ issues?
- [ ] Health score calculation — N+1 query patterns?
- [ ] Missing indexes on frequently queried columns?

### Frontend
- [ ] Results.jsx is 2700+ lines — rendering performance with 1000+ issues?
- [ ] Image thumbnails in orphaned media list — loading 500+ images at once?
- [ ] Re-renders when summary refreshes — does it cascade to all children?

---

## 5. Production Readiness (Vercel Serverless)

### Serverless Constraints
- [ ] Vercel function timeout (10s free, 60s pro) — do crawl endpoints work?
- [ ] SQLite on serverless — file system is ephemeral, does this work?
- [ ] Background tasks (`background_tasks.add_task`) — do they run on Vercel?
- [ ] File uploads (image optimization) — serverless file system limits?

### Redis (Production Store)
- [ ] `RedisJobStore` — are all new methods implemented (not just stubs)?
- [ ] `update_issue_extra`, `get_ignored_image_patterns`, etc. — Redis equivalents?
- [ ] Are all new DB tables (`ignored_image_patterns`, job columns) mirrored in Redis?

### Configuration
- [ ] Environment variables — are all required vars documented?
- [ ] CORS configuration — is it correct for Vercel deployment?
- [ ] Rate limiting — is it applied to all expensive endpoints?

---

## 6. Code Quality

### Architecture
- [ ] Separation of concerns — is business logic in services, not routers?
- [ ] `wp_fixer.py` is 1800+ lines — should it be split?
- [ ] `Results.jsx` is 2700+ lines — should components be extracted?
- [ ] Duplicate code between `rescan_url`, `scan_page`, and engine crawl?

### Testing Gaps
- [ ] WP integration (heading changes, image metadata, post finder) — no real tests
- [ ] `change_heading_text` — tested against real HTML with inline tags?
- [ ] `find_attachment_by_url` search fallback — tested?
- [ ] Redis store — zero tests for any methods
- [ ] Report generation (PDF, Excel) — tested?
- [ ] Frontend: no tests for ImageAnalysisPanel, FixBrokenLinkPanel, SettingsToolbar

### Documentation
- [ ] Are all new API endpoints in `docs/api.md`?
- [ ] Are all new issue codes in `docs/issue-codes.md`?
- [ ] Does `CLAUDE.md` accurately reflect current behavior?

---

## 7. UX Issues

- [ ] Can the user tell when a fix was applied vs. when the issue was removed from the DB?
- [ ] After rescan, does the category tab data refresh or show stale counts?
- [ ] Is the health score formula documented anywhere the user can see it?
- [ ] When the orphaned images scan takes 30+ seconds, is there a progress indicator?
- [ ] Are error messages user-friendly or do they expose technical details?

---

## How to Use This

Start a fresh Claude Code session and run:

```
Review the TalkingToad codebase using the specification in REVIEW_SPEC.md.
Go through each section systematically. For each item, report:
- PASS: no issue found
- FAIL: describe the issue and how to fix it
- WARN: potential issue that needs investigation

Prioritize by severity: security > data integrity > production readiness > everything else.
```
