# GEO Analyzer v2.1 — Implementation Plan

**Date:** 2026-05-03  
**Spec source:** User review document "What I'd Actually Build Into Your Page Analyzer"  
**Scope:** Extend TalkingToad with a full AI GEO (Generative Engine Optimization) page analyzer  
**Status:** Awaiting user approval before any code is written

---

## Acceptance Criteria

Each criterion is tagged with its evidence strength: **(E)** Empirically supported · **(P)** Plausible / mechanism-based · **(S)** Speculative.  
Tags follow the spec verbatim. Every criterion has a test.

---

### Section 1 — Crawler Accessibility (E)

**GEO.1.1 (E)** — robots.txt reports allow/block status for: GPTBot, OAI-SearchBot, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended, CCBot, Applebot-Extended, Bytespider, and any other bot in `ai_bots.py`.  
*Already implemented (AI_BOT_* codes). No new work.*  
*Test: `test_ai_bots.py::test_all_known_bots_classified`*

**GEO.1.2 (E)** — HTTP status, redirect chain, canonical tag are checked per page.  
*Already implemented. No new work.*

**GEO.1.3 (E) — NEW** — Compare raw HTML (no-JS fetch, which we already do) against a set of JS-framework signals. If the page body relies on JS rendering (React/Vue/Angular shell pattern, `<div id="root"></div>`, `<app-root>`, etc.) AND visible text in raw HTML is less than 80% of total body text, emit `RAW_HTML_JS_DEPENDENT`.  
*Implementation: static pattern check in `issue_checker.py` using `page.text_to_html_ratio` and a new `page.is_spa_shell` flag from parser.*  
*Test: `tests/test_geo_static_checks.py::test_raw_html_js_dependent_fires_for_spa_shell`*

---

### Section 2 — Content Extractability (P)

**GEO.2.1 (P)** — Single H1, no skipped heading levels.  
*Partially implemented (H1_MISSING, H1_MULTIPLE, HEADING_SKIP). No new work.*

**GEO.2.2 (P) — NEW** — `STRUCTURED_ELEMENTS_LOW`: compute ratio of structured elements (bullet lists `<ul>/<ol>`, tables `<table>`, definition lists `<dl>`, code blocks `<pre>/<code>`) to total word count. Flag if a 300+ word indexable page has a structured-element ratio below 0.05 (fewer than 5 structured-element items per 100 words).  
*Implementation: parser extracts counts; issue_checker.py evaluates ratio.*  
*Test: `tests/test_geo_static_checks.py::test_structured_elements_low_fires`*

**GEO.2.3 (P) — NEW** — `FIRST_VIEWPORT_NO_ANSWER`: for 300+ word pages, check whether the first 500 words contain a direct-answer signal — any of: a bolded sentence, a `<strong>` or `<em>` sentence, a sentence starting with "X is", "X means", "X refers to", a TL;DR label, a summary heading, or an "In short" / "In brief" / "Key takeaway" phrase.  
*Implementation: new static check in `issue_checker.py`.*  
*Test: `tests/test_geo_static_checks.py::test_first_viewport_no_answer_fires`*

**GEO.2.4 (P) — NEW (LLM)** — Chunk self-containedness: split page by H2/H3, send each section to LLM with prompt: *"Read this section in isolation. Can a reader understand the main claim without the rest of the article? Answer Yes or No, then give one sentence reason."* Report a per-section score (Yes/No + reason). Aggregate: if >50% of sections score No, emit `CHUNKS_NOT_SELF_CONTAINED`.  
*Implementation: `api/services/geo_analyzer.py::score_chunk_containedness()`*  
*This is LLM-based and runs on-demand via the GEO Report endpoint, not during crawl.*  
*Test: `tests/test_geo_analyzer.py::test_chunk_containedness_scoring` (mock LLM)*

---

### Section 3 — Answer Density (E, partial)

**GEO.3.1 (E) — NEW (LLM)** — Extract the page's central claim using LLM. Check whether that claim (or a close paraphrase) appears in the first 200 words. Emit `CENTRAL_CLAIM_BURIED` if not.  
*Implementation: `geo_analyzer.py::extract_central_claim()`*  
*Test: `tests/test_geo_analyzer.py::test_central_claim_detection` (mock LLM)*

**GEO.3.2 (E) — NEW (LLM)** — Query generation and scoring: LLM generates 5–10 realistic user queries the page could answer. For each query, score: does the page contain a self-contained passage that directly answers it? Report as a table: Query | Best Chunk | Answers? (Yes/Partial/No).  
*Implementation: `geo_analyzer.py::generate_and_score_queries()`*  
*Test: `tests/test_geo_analyzer.py::test_query_generation_and_scoring` (mock LLM)*

**GEO.3.3 (E) — NEW (static)** — Count verifiable factual claims per 100 words: sentences containing at least one of: a number, a year (4-digit), a named entity pattern (capitalized multi-word noun phrase), a percentage. Report as `factual_density` metric.  
*Implementation: static regex in `geo_analyzer.py::count_factual_density()`*  
*Test: `tests/test_geo_analyzer.py::test_factual_density_counting`*

**GEO.3.4 (E) — NEW (static)** — Count sourced claims: sentences in the body that contain an outbound hyperlink (implying attribution). Report `sourced_claim_ratio` = sourced sentences / total sentences. Flag `CLAIMS_UNSOURCED` if ratio < 0.05 on a 500+ word page.  
*Implementation: static check using parsed links data already in `ParsedPage.links`.*  
*Test: `tests/test_geo_static_checks.py::test_claims_unsourced_fires`*

---

### Section 4 — Authority Signals (E for citations, P for rest)

**GEO.4.1 (E) — NEW (static)** — Outbound link classification: categorise each external link by domain pattern:
- `authority`: `.gov`, `.edu`, `.ac.uk`, `nih.gov`, `who.int`, `ieee.org`, `arxiv.org`, `doi.org`, `pubmed.ncbi`, `github.com`, `developer.mozilla.org`, known documentation domains
- `reference`: Wikipedia, official vendor docs
- `promotional`: links to the same org's other domains, affiliate patterns

Emit `OUTBOUND_AUTHORITY_LINKS_LOW` if page has 300+ words and 0 authority-class outbound links.  
*Implementation: `api/services/link_classifier.py` (new file), called from `issue_checker.py`.*  
*Test: `tests/test_link_classifier.py::test_classifies_authority_links`*

**GEO.4.2 (P) — NEW (static)** — Author byline detection: check HTML for `rel="author"`, `itemprop="author"`, `class` patterns matching `author|byline|contributor`, JSON-LD `author` field, or a `<meta name="author">` tag. Emit `AUTHOR_BYLINE_MISSING` on blog/article pages (BlogPosting schema or /blog/ URL) that have none.  
*Implementation: new parser field `page.author_detected: bool`; check in `issue_checker.py`.*  
*Test: `tests/test_geo_static_checks.py::test_author_byline_missing_fires`*

**GEO.4.3 (P) — NEW (static)** — datePublished detection: check JSON-LD `datePublished` field AND visible text (regex for date patterns in first 100 words or in a byline region). Emit `DATE_PUBLISHED_MISSING` if absent on blog/article pages.  
Emit `DATE_MODIFIED_MISSING` if `dateModified` absent in JSON-LD (separate, lower-severity issue).  
*Implementation: parser extracts from schema_blocks + visible text; issue_checker.py evaluates.*  
*Test: `tests/test_geo_static_checks.py::test_date_published_missing_fires`*

**GEO.4.4 (P) — NEW (LLM)** — Promotional content interruption detection: split page by H2/H3 sections; for each section, LLM prompt: *"Is this section part of the main article topic, or is it promoting a different product/service? Answer: main_content or promotional."* If >1 section in the middle of the article (not first/last) is classified promotional, emit `PROMOTIONAL_CONTENT_INTERRUPTS`.  
*Implementation: `geo_analyzer.py::detect_promotional_interruptions()`*  
*Test: `tests/test_geo_analyzer.py::test_promotional_detection` (mock LLM)*

---

### Section 5 — Structured Data (P)

**GEO.5.1 (P) — NEW (static)** — Validate JSON-LD present: check that `@type` and `@context` are present in every JSON-LD block. Emit `JSON_LD_INVALID` (distinct from `JSON_LD_MISSING`) if blocks parse but lack required fields.  
*Implementation: uses `page.schema_blocks` already extracted by parser.*  
*Test: `tests/test_geo_static_checks.py::test_json_ld_invalid_fires`*

**GEO.5.2 (P) — NEW (static)** — `FAQ_SCHEMA_MISSING`: detect FAQ section in HTML (heading "FAQ", "Frequently Asked Questions", or ≥3 consecutive `<dt>/<dd>` or question-formatted H3s), and if detected, check whether `FAQPage` schema is present. Emit if FAQ detected but no FAQPage schema.  
*Implementation: new static check in `issue_checker.py`.*  
*Test: `tests/test_geo_static_checks.py::test_faq_schema_missing_fires`*

**GEO.5.3 (P) — NEW (static)** — Check that `Article`, `TechArticle`, `BlogPosting`, `HowTo`, or `Person` (for author) schema types are present where contextually expected (as plausible signals, not hard requirements). Report which are present in the GEO report's structured data section — informational, no issue code emitted for absence alone.  
*Implementation: `geo_analyzer.py::audit_schema_types()` — reporting only.*  
*Test: `tests/test_geo_analyzer.py::test_schema_type_audit`*

---

### Section 6 — Optional / Speculative (S)

**GEO.6.1 (S)** — llms.txt at root: already implemented. Label as informational (S-level).  
*No new work.*

**GEO.6.2 (S) — NEW** — `AI_TXT_MISSING`: check for `/ai.txt` at site root. Report as informational-only (severity: `info`, evidence label: `S`). No impact on health score.  
*Implementation: engine fetches `{origin}/ai.txt` during crawl; issue emitted if absent.*  
*Test: `tests/test_geo_static_checks.py::test_ai_txt_missing_emitted`*

---

### Section 7 — Query-Match Test (most useful)

**GEO.7.1 (E) — NEW (LLM)** — For a given page, LLM generates 10 realistic user prompts the page targets. For each prompt: extract the most relevant 200–400 token chunk from the page. Score: does that chunk alone answer the prompt with a citable fact? (Yes / Partial / No + reason). Return as a structured table.  
*Implementation: `geo_analyzer.py::run_query_match_test()`. Separate from GEO.3.2 (which scores existing queries); this generates and tests simultaneously.*  
*Test: `tests/test_geo_analyzer.py::test_query_match_test` (mock LLM)*

---

### Section 8 — Additional Detections (from page analysis)

**GEO.8.1 (P) — NEW (static)** — Code block presence for technical articles: on pages with schema type `TechArticle` or `HowTo`, or URL patterns `/how-to/`, `/tutorial/`, `/setup/`, `/guide/`, or ≥1 setup-step list (numbered list with ≥3 items), flag `CODE_BLOCK_MISSING_TECHNICAL` if no `<pre>` or `<code>` elements exist.  
*Implementation: new parser field `page.code_block_count`; check in `issue_checker.py`.*  
*Test: `tests/test_geo_static_checks.py::test_code_block_missing_technical_fires`*

**GEO.8.2 (P) — NEW (static)** — Comparison table detection: if H2/H3 headings or body text contain comparison signals ("vs", "versus", "compared to", "difference between", "X vs Y"), check for presence of a `<table>`. Emit `COMPARISON_TABLE_MISSING` if comparison signals found but no table.  
*Implementation: new parser field `page.table_count`; check in `issue_checker.py`.*  
*Test: `tests/test_geo_static_checks.py::test_comparison_table_missing_fires`*

**GEO.8.3 (E) — NEW (static)** — External authority vs promotional link ratio: ratio of `authority` links to total outbound links. Report as metric in GEO report. Emit `LINK_PROFILE_PROMOTIONAL` if >80% of outbound links are to the same organisation's own domains (internal brand promotion).  
*Implementation: uses `link_classifier.py` from GEO.4.1.*  
*Test: `tests/test_link_classifier.py::test_link_profile_promotional_fires`*

---

### Section 9 — Model Selection UI

**GEO.9.1 — NEW** — GEO/AI Settings panel (in Results page, or as a dedicated Settings tab) allows selecting the AI model used for LLM-based GEO checks. Options:
- `gpt-4o` (default if OpenAI key present)
- `gpt-4o-mini`
- `gemini-1.5-flash` (default if only Gemini key)
- `gemini-1.5-pro`
- `gemini-2.0-flash`

Selected model persisted via `GET/POST /api/geo/ai-model` endpoint (stored in same table as GEO settings).  
*Test: `tests/test_geo_settings.py::test_model_selection_persisted`*

**GEO.9.2 — NEW** — Model selector shown in UI with a note indicating which models are available based on configured API keys. Falls back gracefully if selected model is unavailable.  
*Frontend: `GeoSettingsModal.jsx` updated with model selector dropdown.*

---

### Section 10 — GEO Report API + Frontend

**GEO.10.1 — NEW** — `POST /api/ai/geo-report` endpoint: accepts `job_id` (and optional `url` override for scan-page jobs). Runs all LLM-based checks (GEO.2.4, GEO.3.1, GEO.3.2, GEO.4.4, GEO.7.1) using the configured model. Returns a structured `GEOReport` object. Caches result on job record.  
*Test: `tests/test_geo_report_endpoint.py::test_geo_report_endpoint_returns_structured_result`*

**GEO.10.2 — NEW** — `GEOReport` Pydantic model with sections matching the 7 spec categories. Each finding has: `code`, `label`, `evidence_strength` (E/P/S), `score` (0–100), `findings` list, `pass_fail`.  
*Test: `tests/test_geo_report_endpoint.py::test_geo_report_model_validates`*

**GEO.10.3 — NEW** — Frontend `GEOReportPanel.jsx`: displays the full GEO report with:
- Section cards for each of the 7 categories, each with an E/P/S confidence badge
- Query-Match Test displayed as a table (Query | Chunk | Answered?)
- Chunk self-containedness displayed as a per-section list
- Overall GEO score (0–100) with colour coding
- "Run GEO Analysis" button (triggers `POST /api/ai/geo-report`)
- Shows spinner + estimated wait time while running
- Cached results load instantly on re-visit  
*Integrated into the AI Readiness tab as a new subsection below existing panels.*

---

## New Issue Codes Summary

| Code | Category | Severity | Evidence | Static/LLM |
|---|---|---|---|---|
| `RAW_HTML_JS_DEPENDENT` | ai_readiness | warning | E | Static |
| `STRUCTURED_ELEMENTS_LOW` | ai_readiness | info | P | Static |
| `FIRST_VIEWPORT_NO_ANSWER` | ai_readiness | warning | P | Static |
| `OUTBOUND_AUTHORITY_LINKS_LOW` | ai_readiness | warning | E | Static |
| `AUTHOR_BYLINE_MISSING` | ai_readiness | warning | P | Static |
| `DATE_PUBLISHED_MISSING` | ai_readiness | info | P | Static |
| `DATE_MODIFIED_MISSING` | ai_readiness | info | P | Static |
| `JSON_LD_INVALID` | ai_readiness | warning | P | Static |
| `FAQ_SCHEMA_MISSING` | ai_readiness | warning | P | Static |
| `AI_TXT_MISSING` | ai_readiness | info | S | Static |
| `CODE_BLOCK_MISSING_TECHNICAL` | ai_readiness | warning | P | Static |
| `COMPARISON_TABLE_MISSING` | ai_readiness | info | P | Static |
| `CLAIMS_UNSOURCED` | ai_readiness | warning | E | Static |
| `LINK_PROFILE_PROMOTIONAL` | ai_readiness | info | E | Static |
| `CHUNKS_NOT_SELF_CONTAINED` | ai_readiness | warning | P | LLM (report) |
| `CENTRAL_CLAIM_BURIED` | ai_readiness | warning | E | LLM (report) |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | ai_readiness | warning | P | LLM (report) |

---

## New Files

| File | Purpose |
|---|---|
| `api/services/geo_analyzer.py` | All LLM-based GEO analysis functions |
| `api/services/link_classifier.py` | Outbound link authority classification |
| `frontend/src/components/GEOReportPanel.jsx` | Full GEO report display |
| `tests/test_geo_static_checks.py` | Tests for all new static issue codes |
| `tests/test_geo_analyzer.py` | Tests for LLM-based checks (mock LLM) |
| `tests/test_link_classifier.py` | Tests for link classification |
| `tests/test_geo_settings.py` | Model selection persistence tests |
| `tests/test_geo_report_endpoint.py` | API endpoint integration tests |

---

## Modified Files

| File | What changes |
|---|---|
| `api/crawler/parser.py` | Add: `is_spa_shell`, `author_detected`, `date_published`, `date_modified`, `code_block_count`, `table_count`, `structured_element_count`, `first_500_words` |
| `api/crawler/issue_checker.py` | Add 14 new static issue codes + scoring entries |
| `api/crawler/engine.py` | Fetch `/ai.txt` during crawl (alongside `/llms.txt`) |
| `api/routers/ai.py` | Add `POST /api/ai/geo-report` endpoint |
| `api/routers/geo.py` | Add `GET/POST /api/geo/ai-model` for model selection |
| `api/services/ai_analyzer.py` | Refactor to accept `model` parameter (used by geo_analyzer) |
| `api/models/job.py` | Add `geo_report: dict | None` field for caching |
| `frontend/src/data/issueHelp.js` | Add 17 new issue entries |
| `frontend/src/components/AIReadinessPanel.jsx` | Add GEOReportPanel integration + new issue groups |
| `frontend/src/components/GeoSettingsModal.jsx` | Add model selector dropdown |

---

## Implementation Order (with dependencies)

### Phase A — Parser extensions (no dependencies)
1. `parser.py`: add `is_spa_shell`, `author_detected`, `date_published`, `date_modified`, `code_block_count`, `table_count`, `structured_element_count`, `first_500_words`

### Phase B — Static checks (depends on Phase A)
2. `link_classifier.py`: new file, authority classification
3. `issue_checker.py`: add all 14 static issue codes (GEO.1.3, 2.2, 2.3, 3.3, 3.4, 4.1, 4.2, 4.3, 5.1, 5.2, 6.2, 8.1, 8.2, 8.3)
4. `engine.py`: add `/ai.txt` fetch
5. `issueHelp.js`: add all 17 new issue entries
6. `tests/test_geo_static_checks.py` + `tests/test_link_classifier.py`

### Phase C — Data model extensions (no dependencies)
7. `api/models/job.py`: add `geo_report` cache field
8. `api/routers/geo.py`: add model selection endpoint
9. `tests/test_geo_settings.py`

### Phase D — GEO Analyzer service (depends on Phase C)
10. `api/services/ai_analyzer.py`: add `model` parameter
11. `api/services/geo_analyzer.py`: full LLM analysis service
12. `api/routers/ai.py`: add `POST /api/ai/geo-report` endpoint
13. `tests/test_geo_analyzer.py` + `tests/test_geo_report_endpoint.py`

### Phase E — Frontend (depends on Phases B + D)
14. `GeoSettingsModal.jsx`: model selector
15. `GEOReportPanel.jsx`: full GEO report component
16. `AIReadinessPanel.jsx`: integrate GEOReportPanel + new issue groups
17. Architecture parity test must pass (`npm run build` clean)

---

## Adjacent Issues Found (not fixed in this change)

- `api/services/ai_analyzer.py` hardcodes `gemini-1.5-flash` and `gpt-4o` — GEO.9.1 will fix this by making model configurable, but existing `analyze_page` / `analyze_image` callers still use the old hardcoded logic. Should be a follow-up to unify.
- `api/routers/crawl.py` line 1306: `regex=` deprecated in FastAPI Query, should be `pattern=`. Minor, defer.
- `issue_checker.py` has no test for `BLOG_SECTIONS_MISSING` (just added). Should add in a follow-up.

---

## Human-Verifiable Criteria

These cannot be expressed as automated tests and require manual review:

| Criterion | How a reviewer verifies it |
|---|---|
| GEO report scores reflect reality for mindstudio.ai test page | Run GEO report on that URL; verify findings match the spec's analysis table |
| E/P/S confidence labels display correctly in UI | Load AI Readiness tab; confirm each issue shows correct badge |
| Query-match test table is readable | Inspect GEOReportPanel with real LLM results |
| Model selector falls back gracefully | Remove API keys; confirm no crash, just "no model available" message |
