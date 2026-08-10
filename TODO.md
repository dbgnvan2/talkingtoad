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
- [x] **E5 citability-grade GUI surface** — done 2026-07-22 (owner approved "do both"): `CitabilityBadge` (green ≥70 / amber ≥40 / red) shown as a column on the Page Priority queue and the By-Page view; `citability_grade` added to the `/pages` payload. Tests: `test_api.py::...test_pages_includes_citability_grade`, `PagePriorityPanel.test.jsx`, `ByPagePanel.test.jsx`.
- [ ] **E5 "Originality lens" label (optional):** the danger-page-type presentation from idea #1 (mirror how-to / definition-only / untested review) is still not built. Low priority; the citability grade + near-duplicate/boilerplate codes already cover most of the signal.
- [ ] **Pre-existing frontend fix-map drift:** `FixInlinePanel.jsx` `CODE_TO_FIELD` includes `TITLE_H1_MISMATCH → seo_title`, which is **not** in the backend `wp_shared._CODE_TO_FIELD` — so the inline fix likely fails backend-side. Pre-existing (not introduced by §7); `test_frontend_backend_code_parity.py::test_inline_fix_codes_are_backend_fixable` currently excludes it. Decide: add `TITLE_H1_MISMATCH` to the backend map, or remove the frontend entry, then drop the exclusion.
- [ ] **Cosmetic (§2):** internal broken pages (`engine.py:566`) emit `extra={"source_url": …}`, so `collapse_per_target_occurrences` leaves their `occurrence_urls` empty (it reads `target_url`/`redirect_to`). Scoring unaffected (n=1, self-attributed) and the source is captured in `broken_link_sources`; unify the key for consistency if convenient.

### Deferred from the 2026-07-23 E5-GUI /csdp sweep (learning-qa findings, not fixed)
- [ ] **P9 — `/pages` loads all issues per request (scaling):** `get_pages` (`crawl.py:784`) calls `store.get_all_issues(job_id)` and reconstructs every `Issue` model on *every* paginated request, just to grade the ≤50 URLs shown. On a large crawl (≈10k issue rows at the 500-page default) each page-flip through the By-Page view re-materialises all rows. Not a correctness bug, and it mirrors the accepted `/page-priority` precedent, but `/pages` is browsed interactively so the amplification is worse. *Deferred:* the clean fix is a scoped issue query (`WHERE page_url IN (<the 50 URLs>)`) or pushing the `ai_readiness` impact rollup into the same SQL aggregate that already computes `issue_counts` — a store-level change across both SQLite + Redis, out of scope for the wrap-up. Acceptable for the nonprofit target (≤500 pages) in the meantime.
- [ ] **P6/P7 — citability grade ignores job-level `suppressed_codes`:** `compute_citability_grade` is fed raw `get_all_issues` rows, so a user-dismissed `ai_readiness` code still charges the By-Page / Page-Priority citability column, even though site health (`get_summary`) drops it. Pre-existing *class* issue (both `/pages` and `/page-priority`), surfaced — not introduced — by E5. *Deferred:* thread `get_suppressed_codes()` into both grade call sites (or filter suppressed codes from `rows_by_url` before grading) so the grade reconciles with the suppression state the user set.

### Deferred from the 2026-08-06 Analytics + Performance-Bundle /csdp sweep
Shipped this session: the **Analytics & Measurement** issue category (6 no-API crawl-time codes) and **Performance Bundle ingestion Phase 1** (PB1/PB2/PB6/PB8). Reviewed three times (two per-feature learning-qa passes, one independent general-purpose review, one consolidated integration sweep); all in-scope findings fixed. Deferred items:

- [ ] **F4 — legacy `/api/gsc/ingest` keys ledger rows on the raw GSC URL** (`api/routers/gsc.py:283`), not the crawled-page key the new bundle ingest + page-priority consumer use, and leaves `source_generated_at=None`. Pre-existing; does not lose data (GA4 is COALESCE-preserved) but GSC rows can land under a key nothing reads. *Deferred (adjacent, out of scope):* factor `_match_key` out of `api/routers/performance.py` into a shared module and route `gsc.py` through it + stamp `source_generated_at`. Also spun off as a task chip. Add a trailing-slash/www/scheme regression test.
- [ ] **Phase 2/3 of Performance Bundle ingestion** (`docs/pending/2026-08-06_performance-bundle-ingestion.md`): PB3 striking-distance→AI rewriter (highest value), PB7 coverage/cross-signal diff, PB4 conversion-weighted priority, PB5 index-status reconciliation, PB9 GTM-audit surface; plus persistence of `top_queries` / site-level payloads (currently accepted and reported under `deferred`) and all frontend surfacing.
- [ ] **Cross-signal reconcile (open risk, not a bug):** a page can be flagged `ANALYTICS_TAG_MISSING` (markup-only crawl check) while its ledger row shows GA4 sessions from an ingested bundle (tag fires via a path the crawler can't see). No artifact is produced today because Phase 1 merges no derived reports — but PB7's `tag_missing_but_active` should reconcile these two signals when built.

### Deferred from the 2026-08-07 category-visibility fix
Shipped: added the `analytics` category to the two frontend CATEGORIES arrays (`Results.jsx`, `SummaryPanel.jsx`) and the PDF `cat_list` (`report_generator.py`) — it had been invisible in the UI and audit PDF; the same omission had also dropped `rendering` + `semantic_html` from the PDF. New guard: `test_frontend_backend_code_parity.py::test_category_display_lists_cover_every_backend_category`.

- [ ] **Dead `duplicate` category tile (pre-existing):** `"duplicate"` appears in both frontend CATEGORIES grids and the PDF `cat_list`, but **no `_CATALOGUE` code emits `category="duplicate"`** (near-duplicate/duplicate detection lives under other categories). So the "Duplicates" tile/row is always 0. *Deferred (pre-existing, not introduced here):* either wire duplicate-detection codes to a real `duplicate` category or drop the dead tile. The new parity test only checks for *missing* categories, so it won't flag this extra key.
- [ ] **Single source of truth for the category list:** the category set is hand-mirrored in 4 places (registry + 2 frontend arrays + PDF list). The new parity test binds them, but the durable fix is to derive the frontend/PDF lists from one exported list (e.g. a generated JSON like `issue-codes.md`) so a new category can't be half-added again.
- [ ] **`_ANALYSIS_CATEGORY_MAP` covers only 9/13 categories (pre-existing, surfaced by the 2026-08-07 sweep):** in `api/crawler/engine.py`, `security`, `image`, `rendering`, and `semantic_html` belong to **no** analysis-toggle group. Full crawls are unaffected (`enabled_analyses=None` ⇒ all categories run), but a **partial** analysis selection (`_enabled_categories`) silently excludes those four — and there is no toggle that enables them (P2/P3). *Deferred (pre-existing, out of scope for the display-list fix; not confirmed user-facing — depends on whether the frontend exposes partial analysis toggles).* Before fixing: check what `enabled_analyses` values the frontend actually sends; if partial selection is reachable, either map the four categories to groups or make them always-run, and add a test that a restricted selection still runs security/image/rendering/semantic_html. Needs its own micro-spec.

---

## ✅ Completed

- [x] **Technical-debt cleanup batch — CLN0–CLN8 (2026-08-08):** cleared the
  accumulated sweep deferrals (folded into functional-spec §4.9 + §4.14; pending
  specs deleted). Done: **CLN0** scope-discovery transient≠absent (SD1–SD8, the
  2026-08-07 spec); **CLN1** dropped dead `duplicate` tile; **CLN2** single-source
  category list (`registry.CATEGORY_DISPLAY` → generated JSON + PDF); **CLN3**
  `_ANALYSIS_CATEGORY_MAP` completeness; **CLN4** unified GSC/bundle join key +
  `source_generated_at` (was F4); **CLN5** citability/health honour suppressed
  codes (was P6/P7); **CLN6** `TITLE_H1_MISMATCH` now WP-fixable; **CLN7** `/pages`
  scopes its issue-load (was P9); **CLN8** internal broken-page `occurrence_urls`.
  Still deferred (explicitly out of the batch): Performance-Bundle Phase 2/3
  (PB3–PB9) + cross-signal reconcile, and the E5 "Originality lens" label.
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
