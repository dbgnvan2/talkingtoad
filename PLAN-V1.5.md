# TalkingToad — v1.5 Extension Implementation Plan

> **Reference spec:** `nonprofit-crawler-spec-v1.5-extensions.md`
> **Prerequisites:** All Milestone 6 (Vercel deployment) tasks from `PLAN.md` complete.
> Work through milestones in order. Each milestone ends with passing tests before moving on.

---

## Milestone A — Data Model & Infrastructure

**Goal:** Extend the database schema and Pydantic models to hold the new fields. No new issue checks yet — just plumbing. All existing tests must continue to pass.

### A.1 — Add new issue categories (`api/models/issue.py`)

- [ ] Add `"security"` and `"url_structure"` to `PHASE_1_CATEGORIES`
- [ ] Add all new issue codes to the issue catalogue (constants or enum) used by `issue_checker.py`

### A.2 — Extend `CrawledPage` model (`api/models/page.py`)

- [ ] Add fields: `word_count: int | None`, `crawl_depth: int | None`, `pagination_next: str | None`, `pagination_prev: str | None`, `amphtml_url: str | None`
- [ ] All new fields default to `None` (backward-compatible)

### A.3 — Extend `ParsedPage` dataclass (`api/crawler/parser.py`)

- [ ] Add the same five fields to `ParsedPage` with `None` defaults
- [ ] No parsing logic yet — populate them in Milestone B

### A.4 — SQLite schema migration (`api/services/job_store.py`)

- [ ] Add `ALTER TABLE crawled_pages ADD COLUMN` for each new field (guarded with `IF NOT EXISTS` equivalent — use `try/except` on the `ALTER TABLE` statement since SQLite lacks `IF NOT EXISTS` for `ALTER`)
- [ ] Update `_row_to_page()` to read the new columns
- [ ] Update `save_pages()` INSERT to write the new columns

### A.5 — Redis store update (`api/services/job_store.py`)

- [ ] `RedisJobStore._load_pages()` already deserialises from JSON — new fields will be present as `None` automatically once `CrawledPage` is updated (Pydantic handles missing keys)
- [ ] Verify `save_pages()` serialises the new fields

### A.6 — Frontend: add new category tabs (`frontend/src/pages/Results.jsx`)

- [ ] Add `{ key: 'security', label: 'Security' }` and `{ key: 'url_structure', label: 'URL Structure' }` to the `CATEGORIES` array
- [ ] Both tabs use the existing `CategoryTab` component — no new UI code needed

**Tests for A:**
- [ ] `test_issue_checker.py` — no regressions; new category names accepted
- [ ] `test_api.py` — `GET /api/crawl/{id}/results` returns new categories in `by_category`
- [ ] SQLite round-trip: save a `CrawledPage` with new fields, read it back, assert values match

---

## Milestone B — Parser Extensions

**Goal:** Populate the new `ParsedPage` fields during HTML parsing. No issue emission yet.

### B.1 — Word count (`api/crawler/parser.py`) — spec §E5

- [ ] After parsing `<body>`, extract all visible text, excluding tags: `nav`, `header`, `footer`, `aside`, `script`, `style`
- [ ] Split by whitespace, count tokens → `page.word_count`
- [ ] Set to `None` for non-HTML content types

### B.2 — Pagination links (`api/crawler/parser.py`) — spec §E3

- [ ] Scan `<link rel="next">` and `<link rel="prev">` in `<head>`
- [ ] Populate `page.pagination_next` and `page.pagination_prev` with the `href` values (or `None`)

### B.3 — Meta refresh detection (partial) (`api/crawler/parser.py`) — spec §E4

- [ ] Scan `<meta http-equiv="refresh">` in `<head>`
- [ ] Parse the `content` attribute: if it contains `url=` (case-insensitive), store target URL
- [ ] Store result as a new `ParsedPage` field `meta_refresh_url: str | None` (add to A.2/A.3 if not already there)

### B.4 — AMP HTML link (`api/crawler/parser.py`) — spec §E6

- [ ] Scan `<link rel="amphtml" href="...">` in `<head>`
- [ ] Populate `page.amphtml_url` with the `href` value (or `None`)

### B.5 — Engine: crawl depth tracking (`api/crawler/engine.py`) — spec §E7

- [ ] Change `queue` from `deque[str]` to `deque[tuple[str, int | None]]`
- [ ] Track a `depth_map: dict[str, int | None]` — set homepage depth to `0`
- [ ] When queuing a discovered link: `new_depth = (parent_depth + 1) if parent_depth is not None else None`
- [ ] Sitemap-seeded URLs get `depth = None`
- [ ] After parsing, assign `page.crawl_depth = depth_map[url]`
- [ ] Pass `page.crawl_depth` through `_engine_page_to_model()`

**Tests for B:**
- [ ] `test_crawl_engine.py` — mock pages with nav/footer; assert `word_count` excludes those elements
- [ ] `test_crawl_engine.py` — homepage depth is 0; linked page depth is 1; sitemap-only page depth is None
- [ ] `test_crawl_engine.py` — `pagination_next`, `amphtml_url` populated from mock HTML
- [ ] `test_crawl_engine.py` — `meta_refresh_url` populated for redirect meta tag, not for reload-only tag

---

## Milestone C — Issue Checks: Security (§E1)

**Goal:** Implement all four security issue checks in `issue_checker.py`.

### C.1 — `HTTP_PAGE` (spec §E1.1)

- [ ] In `check_page()`: if `page.url.startswith("http://")` (not https), emit `HTTP_PAGE`
- [ ] Do not emit if the page redirected to HTTPS (check `result.final_url`)

### C.2 — `MIXED_CONTENT` (spec §E1.2)

- [ ] In `check_page()`: for HTTPS pages, scan parsed HTML for `src` / `href` attributes on `img`, `script`, `link[rel=stylesheet]`, `iframe` that begin with `http://`
- [ ] Emit once per page; store count in `issue.extra["mixed_count"]`

### C.3 — `MISSING_HSTS` (spec §E1.3)

- [ ] In `check_page()`: for HTTPS pages, check `result.headers` for `strict-transport-security`
- [ ] Emit once per host — maintain a `hsts_checked_hosts: set[str]` set in the engine and pass it to `check_page()` (similar to the existing `favicon_emitted` flag pattern)

### C.4 — `UNSAFE_CROSS_ORIGIN_LINK` (spec §E1.4)

- [ ] In `check_page()`: scan all `<a target="_blank">` tags where `href` is external
- [ ] If `rel` does not contain `noopener` or `noreferrer`, emit once per page with `issue.extra["unsafe_link_count"]`

**Tests for C:**
- [ ] Each issue code: one test for the condition that triggers it, one for the condition that suppresses it
- [ ] `MISSING_HSTS` emits only once per host across multiple pages

---

## Milestone D — Issue Checks: URL Structure (§E2)

**Goal:** Implement four URL structure checks. These are pure string operations — no HTML parsing needed.

### D.1 — `URL_UPPERCASE` (spec §E2.1)

- [ ] Add a new `check_url_structure(url: str) -> list[Issue]` function in `issue_checker.py`
- [ ] Check `urlparse(url).path` for uppercase chars

### D.2 — `URL_HAS_SPACES` (spec §E2.2)

- [ ] Check if `%20` or `+` appears in URL path or query

### D.3 — `URL_HAS_UNDERSCORES` (spec §E2.3)

- [ ] Check if `_` appears in `urlparse(url).path`

### D.4 — `URL_TOO_LONG` (spec §E2.4)

- [ ] Check if `len(url) > 115`

### D.5 — Wire into engine (`api/crawler/engine.py`)

- [ ] Call `check_url_structure(url)` for every URL before fetching; add results to `all_issues`
- [ ] This runs before the fetch so it applies even to pages that time out

**Tests for D:**
- [ ] `test_issue_checker.py` — one test per issue code: positive and negative case
- [ ] Mixed case path → `URL_UPPERCASE`; all-lowercase path → no issue
- [ ] Path with `%20` → `URL_HAS_SPACES`
- [ ] Path with `_` → `URL_HAS_UNDERSCORES`
- [ ] URL with 116 chars → `URL_TOO_LONG`; 115 chars → no issue

---

## Milestone E — Issue Checks: Content & Metadata (§E3–§E6)

**Goal:** Wire up the remaining four checks using data already collected in Milestone B.

### E.1 — `PAGINATION_LINKS_PRESENT` (spec §E3)

- [ ] In `check_page()`: if `page.pagination_next or page.pagination_prev`, emit `PAGINATION_LINKS_PRESENT` (info)
- [ ] Store hrefs in `issue.extra["next"]` and `issue.extra["prev"]`

### E.2 — `META_REFRESH_REDIRECT` (spec §E4)

- [ ] In `check_page()`: if `page.meta_refresh_url is not None`, emit `META_REFRESH_REDIRECT` (warning)
- [ ] Parse `delay_seconds` from the content attribute value; store in `issue.extra`

### E.3 — `THIN_CONTENT` (spec §E5)

- [ ] In `check_page()`: if `page.word_count is not None and 0 < page.word_count < 300`, emit `THIN_CONTENT` (warning)
- [ ] Suppress if page has `noindex` meta robots

### E.4 — `AMPHTML_BROKEN` (spec §E6)

- [ ] In the engine, after the main crawl loop, collect all unique `amphtml_url` values from crawled pages
- [ ] HEAD-fetch each (reuse the external link checking pattern); if status ≠ 200, emit `AMPHTML_BROKEN`
- [ ] Store `amphtml_url` and `amp_status` in `issue.extra`

**Tests for E:**
- [ ] `PAGINATION_LINKS_PRESENT`: page with `rel="next"` → emits; page without → no emit
- [ ] `META_REFRESH_REDIRECT`: `<meta http-equiv="refresh" content="0; url=/new">` → emits; `content="30"` (reload, no URL) → no emit
- [ ] `THIN_CONTENT`: 50-word page → emits; 300-word page → no emit; noindex page → no emit
- [ ] `AMPHTML_BROKEN`: mocked AMP URL returning 404 → emits; 200 → no emit

---

## Milestone F — Issue Checks: Crawl Depth (§E7)

**Goal:** Emit `HIGH_CRAWL_DEPTH` for pages more than 4 clicks from the homepage.

### F.1 — Emit in engine after parse

- [ ] After `page.crawl_depth` is assigned, if `page.crawl_depth is not None and page.crawl_depth > 4`, emit `HIGH_CRAWL_DEPTH` with `issue.extra["crawl_depth"]`
- [ ] This fits naturally at the end of the per-page block in the engine loop

**Tests for F:**
- [ ] Crawl depth 5 → `HIGH_CRAWL_DEPTH`; depth 4 → no issue; depth `None` → no issue
- [ ] Verify depth increments correctly through a 3-hop link chain in a mock crawl

---

## Milestone G — Documentation & Issue Help

**Goal:** Keep docs and the frontend help system in sync with new checks.

### G.1 — `docs/issue-codes.md`

- [ ] Add entries for all new issue codes: `HTTP_PAGE`, `MIXED_CONTENT`, `MISSING_HSTS`, `UNSAFE_CROSS_ORIGIN_LINK`, `URL_UPPERCASE`, `URL_HAS_SPACES`, `URL_HAS_UNDERSCORES`, `URL_TOO_LONG`, `PAGINATION_LINKS_PRESENT`, `META_REFRESH_REDIRECT`, `THIN_CONTENT`, `AMPHTML_BROKEN`, `HIGH_CRAWL_DEPTH`

### G.2 — `frontend/src/data/issueHelp.js`

- [ ] Add help entries for each new issue code with: `definition`, `impact`, `fix` sections
- [ ] These power the `?` help button in `IssueTable` and `PageDetail` components

### G.3 — `docs/api.md`

- [ ] Document new `word_count`, `crawl_depth` fields in the `CrawledPage` response schema
- [ ] Document new `security` and `url_structure` category values in filter params

### G.4 — `docs/user-guide.md`

- [ ] Add plain-English descriptions of the new Security and URL Structure check categories

---

## Implementation Order Summary

```
A (data model + schema)
  └─ B (parser + depth tracking)
       ├─ C (security checks)
       ├─ D (URL structure checks)
       ├─ E (content/metadata checks)
       └─ F (crawl depth check)
            └─ G (docs + help text)
```

Milestones C, D, and E can be worked in parallel once B is complete. F depends only on the depth field from B.5.

---

## Estimated New Test Count

| Milestone | New tests |
|-----------|-----------|
| A | ~5 |
| B | ~8 |
| C | ~10 |
| D | ~10 |
| E | ~8 |
| F | ~3 |
| **Total** | **~44** |

All tests follow existing conventions: `test_<what>_<condition>_<expected_result>`, asyncio_mode = auto, no real HTTP calls.
