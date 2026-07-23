---
status: current
last_reviewed: 2026-05-27
---
# TalkingToad — Project TODO & Technical Debt

This file tracks infrastructure improvements, testing gaps, and future features that aren't part of the current milestone but are critical for long-term stability.

## ⚠️ CRITICAL CONSTRAINTS

**DO NOT IMPLEMENT URL CHANGES VIA WP API:**
- The WordPress REST API is NOT reliable for operations that change URLs (slugs, permalinks, redirects)
- Modifying URLs can corrupt the WP database and break internal link structures
- Any URL-related fixes must be manual or use WP admin interface directly

**DO NOT AUTOMATE IMAGE LINK UPDATES IN POSTS/PAGES:**
- When images are renamed/optimized/replaced, the user MUST manually update links in posts/pages
- The WP backend database structure for post content and media references is too complex and risky to automate
- DO NOT attempt to "be helpful" by automatically updating post content with new image URLs

## 🔴 High Priority: Stability & QA
- [ ] **Frontend Component Testing:** Set up Vitest and React Testing Library.
    - [ ] Add "smoke tests" for `Results.jsx` to ensure it handles null/loading states without crashing.
    - [ ] Test the `ExportReportModal` and `LLMSTxtGenerator` components.
- [ ] **API Error Boundaries:** Implement a React Error Boundary around the main `Results` view to catch and report crashes rather than showing a white screen.
- [ ] **End-to-End (E2E) Testing:** Set up Playwright to test the full "Start Crawl -> View Results -> Export PDF" happy path.
- [ ] **WP Integration Tests:** Build test suite that runs against the `/test-page/` on livingsystems.ca to catch real-world issues (URL resolution, entity encoding, heading changes).

## 🟡 Medium Priority: UX & Polish
- [ ] **Rescan All Pages:** Add button to re-check all pages in an existing crawl without re-crawling from scratch.
- [ ] **Persistent Settings:** Save the user's preferred PDF export options (Help Text ON/OFF) in localStorage.
- [ ] **Real-time Log Streaming:** Instead of just a progress bar, show a "Live Console" during the crawl for power users.

## 🟢 Low Priority: Tech Debt
- [ ] **Type Safety:** Migrate `Results.jsx` and other large components to TypeScript.
- [ ] **CSS Refactoring:** Clean up duplicate Tailwind classes in `Results.jsx` into shared base components.

### Deferred from the 2026-07-22 R5/GEO /csdp sweep
- [x] **§2 dual-path integration test** — done 2026-07-22: `test_per_target_occurrences.py::test_full_crawl_and_rescan_score_broken_links_identically` drives both `run_crawl` and `_fetch_and_check_page` on the same 3-broken-link page and asserts identical collapsed impact.
- [ ] **E5 citability-grade GUI surface (needs owner decision):** the backend grade ships (`compute_citability_grade`, returned on `/page-priority` as `citability_grade`), but it is **not displayed** anywhere — the GUI-change constraint requires explicit owner direction on where/how to show it (e.g. a per-page badge on the Page Priority queue, a column in Results). Also unbuilt: the "Originality lens" label (danger-page-type presentation from idea #1). Decide presentation, then wire the frontend.
- [ ] **Pre-existing frontend fix-map drift:** `FixInlinePanel.jsx` `CODE_TO_FIELD` includes `TITLE_H1_MISMATCH → seo_title`, which is **not** in the backend `wp_shared._CODE_TO_FIELD` — so the inline fix likely fails backend-side. Pre-existing (not introduced by §7); `test_frontend_backend_code_parity.py::test_inline_fix_codes_are_backend_fixable` currently excludes it. Decide: add `TITLE_H1_MISMATCH` to the backend map, or remove the frontend entry, then drop the exclusion.
- [ ] **Cosmetic (§2):** internal broken pages (`engine.py:566`) emit `extra={"source_url": …}`, so `collapse_per_target_occurrences` leaves their `occurrence_urls` empty (it reads `target_url`/`redirect_to`). Scoring unaffected (n=1, self-attributed) and the source is captured in `broken_link_sources`; unify the key for consistency if convenient.

---

## ✅ Completed

- [x] **Orphaned Page Detection:** `ORPHAN_PAGE` issue code detects pages with no internal links pointing to them (v1.5)
- [x] **Orphaned Image Detection:** WP Media Library scan for images not used on any crawled page (v1.9.2)
- [x] **Image Download & Optimization Module:** Download → resize → WebP → GPS EXIF → SEO rename → upload (v1.9.1)
- [x] **Pre-upload Validation:** File size, GPS, format checks (v1.9.1)
- [x] **GEO Metadata Generation:** AI-powered alt text, description, caption with geographic entities (v1.9.1)
- [x] **Two-Step WP API Upload:** Binary upload + metadata PATCH (v1.9.1)
- [x] **Batch Processing:** Parallel execution with pause/resume/cancel (v1.9.1)
- [x] **Banner H1 Suppression:** Auto-detect theme-injected banner headings (v1.9.2)
- [x] **Fix Panel Enhancements:** Title/H1 dual editor, per-link anchor fix, duplicate URL display (v1.9.2)
- [x] **Auto-rescan After Fix:** Pages rescan automatically after WP fixes, health score refreshes live (v1.9.2)
- [x] **Issue Extra Data:** All 50+ issue codes include diagnostic data in `extra` (v1.9.2)
- [x] **Ignored Image Patterns:** Global config to exclude theme SVG icons from issue checks (v1.9.2)
- [x] **Image Scoring Fix:** Performance score works with file_size_bytes alone (v1.9.2)
- [x] **Health Score Fix:** Trailing slash normalization in URL matching (v1.9.2)
- [x] **Broken Link Source Tracking:** `discovered_from` dict + Show Source Pages fallback (v1.9.2)
- [x] **Sitemap & Robots.txt Display:** Discovery data shown even with no issues (v1.9.2)
