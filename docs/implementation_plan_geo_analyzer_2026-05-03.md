# GEO Analyzer v2.1 — Implementation Plan

**Date:** 2026-05-03 (revised same day)  
**Spec source:** User review "What I'd Actually Build Into Your Page Analyzer" + follow-up guidance  
**Scope:** Extend TalkingToad with a full AI GEO (Generative Engine Optimization) page analyzer  
**Status:** Awaiting user approval before any code is written  
**New dependency (optional):** `playwright` + Chromium — required for GEO.1.3b/c/d only; all other checks work without it

---

## Evidence Tier System

Every check in the analyzer output carries one of three labels. These are shown in the UI, weighted in scoring, and determine how confidently recommendations are worded.

| Tier | Label | Meaning | Weight |
|---|---|---|---|
| **Empirical** | `E` | Backed by published measurement — specifically Aggarwal et al. (2023) and confirmed follow-ups | High |
| **Mechanistic** | `M` | Follows from how retrieval/chunking demonstrably works — raw HTML accessibility, heading-based chunk boundaries, first-screen content | Medium |
| **Conventional** | `C` | Industry advice or emerging convention without confirmed impact measurement | Low |

The scorecard weights Empirical checks highest, Mechanistic second, Conventional last.  
Users can see this in the UI so they know which recommendations are load-bearing.

### Jargon Filter

Any advice source using terms below is treated as low-evidence by default.  
These terms are generated to make heuristics sound like science:

> Synthesis Readiness, Citation Share, Token Uncertainty, Query Surface Area, Semantic Density, Objective Fact-Density, Authority Gradient, Retrieval Affinity

**Existing codebase debt:** `SEMANTIC_DENSITY_LOW` uses one of these terms. The underlying check (text-to-HTML ratio < 10%) is legitimate and mechanistic — raw HTML with little visible text is a real accessibility problem. The name is jargon. This is flagged as a follow-up rename: `HTML_CONTENT_RATIO_LOW`. Not changed in this PR to avoid breaking existing stored issues, but documented.

### Threshold Policy

Specific numerical thresholds (ratios, percentages, word counts) must come from one of:
1. A published paper with a reported measurement
2. A mechanistically derivable limit (e.g., "above the fold" ≈ first paragraph or first viewport)
3. A configurable default that the user or codebase can adjust

Thresholds that appear only in vendor blog posts or conversations are **not used**. Where a threshold cannot be grounded, the check reports a count or ratio as a metric (no pass/fail). Affected items from the prior plan draft are called out below.

---

## Aggarwal et al. Checks — Highest Priority

The Aggarwal (2023) paper is the primary empirical ground truth for GEO. Three tactics showed **measurable lift** in controlled testing against generative engines. These checks carry `Empirical` tier and the highest scorecard weight.

**GEO.A.1 (Empirical) — NEW (static)** — `STATISTICS_COUNT_LOW`: count sentences containing a specific number with context (e.g., "speeds up to 40 Gbps", "reduces errors by 23%", "released in March 2024"). A statistic is a numeric value paired with a unit, comparison, or date. Report count per 500 words. Flag if a 500+ word page has zero statistics.  
*No threshold borrowed from conversation. Pass/fail: zero statistics = issue. Count reported as metric.*  
*Test: `tests/test_geo_static_checks.py::test_statistics_count_low_fires_on_zero`*

**GEO.A.2 (Empirical) — NEW (static)** — `EXTERNAL_CITATIONS_LOW`: count outbound links that point to external authoritative sources (see link classifier). A citation is an outbound link in body text (not navigation or footer). Flag if a 500+ word page has zero body-text citations to external sources.  
*The existing `CLAIMS_UNSOURCED` (GEO.3.4) overlaps — these are unified under the Aggarwal framing with `EXTERNAL_CITATIONS_LOW` as the primary code.*  
*Test: `tests/test_link_classifier.py::test_external_citations_low_fires`*

**GEO.A.3 (Empirical) — NEW (static)** — `QUOTATIONS_MISSING`: count direct quotations from named sources — text in `<blockquote>` tags, or text in quotation marks immediately followed by an attribution pattern ("according to [Name]", "— [Name]", "says [Name]", "[Name] stated"). Flag if a 500+ word page has zero quotations.  
*Test: `tests/test_geo_static_checks.py::test_quotations_missing_fires`*

**GEO.A.4 (Empirical) — NEW (static)** — `ORPHAN_CLAIM_TECHNICAL`: for technical/how-to pages (schema type `TechArticle`, `HowTo`, or URL patterns `/how-to/`, `/guide/`, `/tutorial/`, `/setup/`), detect substantive factual claims not paired with a source link or attribution. A claim is: a sentence asserting a specific capability, number, or procedure. An orphan claim is one where neither the sentence nor the surrounding `<p>` contains an outbound link. Report count. Flag if ≥3 orphan claims detected.  
*This implements the "claim-source pairing" requirement from the review.*  
*Test: `tests/test_geo_static_checks.py::test_orphan_claim_technical_fires`*

---

## Acceptance Criteria

---

### Section 1 — Crawler Accessibility

**GEO.1.1 (Empirical)** — robots.txt allow/block per AI bot.  
*Already implemented (AI_BOT_* codes). No new work.*

**GEO.1.2 (Mechanistic)** — HTTP status, redirects, canonical.  
*Already implemented. No new work.*

**GEO.1.3 (Mechanistic) — NEW** — JS rendering comparison. Three distinct checks, each with a separate issue code. Runs on-demand as part of the GEO Report (not the main crawl — Playwright is too slow for bulk scanning).

**GEO.1.3a (Mechanistic, Static) — `RAW_HTML_JS_DEPENDENT`**: fast check during regular crawl. Detect SPA-shell pattern in raw HTML (`<div id="root">`, `<div id="app">`, `<app-root>`, `<ng-app>`) with near-zero visible text (`text_to_html_ratio < 0.05`). If both conditions are true, emit issue immediately without Playwright. This is the cheap first-pass signal.  
*Implementation: `parser.py` adds `is_spa_shell: bool`; `issue_checker.py` evaluates.*  
*Test: `tests/test_geo_static_checks.py::test_raw_html_js_dependent_fires_for_spa_shell`*

**GEO.1.3b (Mechanistic, GEO Report) — `JS_RENDERED_CONTENT_DIFFERS`**: Playwright full render comparison. Fetch the page URL three ways:
1. `httpx` with `User-Agent: GPTBot/1.0` (AI crawler)
2. `httpx` with `User-Agent: ClaudeBot/1.0` (AI crawler)
3. Playwright headless Chromium, `wait_until="networkidle"`, max 5 second hard timeout

Extract visible text from each via BeautifulSoup (`get_text(separator=" ", strip=True)`). Tokenise (split on whitespace, lowercase). Compute token-set difference: tokens in rendered but absent from raw. If the added token set is >20% of the rendered page's total tokens, emit `JS_RENDERED_CONTENT_DIFFERS`.  
*The 20% threshold is mechanistically grounded: below that level, the difference is likely navigation/decorative JS; above it, substantive content is JS-gated.*  
*Implementation: `api/services/js_renderer.py` (new). Playwright runs in a subprocess via `asyncio.to_thread` to avoid blocking the event loop.*  
*Test: `tests/test_js_renderer.py::test_js_rendered_content_differs_fires` (mock Playwright)*

**GEO.1.3c (Mechanistic, GEO Report) — `CONTENT_CLOAKING_DETECTED`**: built on top of GEO.1.3b. If `JS_RENDERED_CONTENT_DIFFERS` fires (rendered adds substantial content), additionally check whether the added tokens meaningfully change the page's apparent topic. Method: extract top-10 TF-IDF keywords from raw text and from rendered text independently. If Jaccard similarity of the two keyword sets is < 0.3, the topic has shifted — emit `CONTENT_CLOAKING_DETECTED` (higher severity than `JS_RENDERED_CONTENT_DIFFERS`).  
*Cloaking is particularly damaging for GEO: an AI bot sees a different page than users, making any citation untrustworthy.*  
*No external library needed: simple TF-IDF over the token sets with standard Python.*  
*Test: `tests/test_js_renderer.py::test_content_cloaking_detected_on_topic_shift`*

**GEO.1.3d (Mechanistic, GEO Report) — `UA_CONTENT_DIFFERS`**: compare GPTBot/1.0 and ClaudeBot/1.0 raw-fetch responses against the Playwright-rendered result. If either AI-UA fetch returns meaningfully less content (>20% fewer tokens) than the rendered page, emit `UA_CONTENT_DIFFERS`. This catches sites that serve stripped pages to known AI crawlers.  
*Separate from `CONTENT_CLOAKING_DETECTED` — this is about UA discrimination, not topic shift.*  
*Test: `tests/test_js_renderer.py::test_ua_content_differs_fires_on_ai_bot_stripping`*

**Playwright dependency note:** `playwright` Python package + Chromium binaries (~180MB) added as an optional dependency. `js_renderer.py` guards the import: `try: from playwright.async_api import async_playwright; HAS_PLAYWRIGHT = True except ImportError: HAS_PLAYWRIGHT = False`. If Playwright is not installed, GEO.1.3b/c/d are skipped and the GEO report notes "JS rendering unavailable — install playwright". Install command: `pip install playwright && playwright install chromium`.

---

### Section 2 — Content Extractability

**GEO.2.1 (Mechanistic)** — H1/heading hierarchy.  
*Already implemented. No new work.*

**GEO.2.2 (Mechanistic) — NEW** — `STRUCTURED_ELEMENTS_LOW`: count structured elements (`<ul>`, `<ol>`, `<table>`, `<dl>`, `<pre>`, `<code>`) and report count as a metric in the GEO report. **No pass/fail threshold** — the "1 list per 300 words" figure is conversation-derived and not used. Threshold-free reporting only; users see the count and judge.  
*Implementation: parser adds `structured_element_count`.*  
*Test: `tests/test_geo_static_checks.py::test_structured_element_count_reported`*

**GEO.2.3 (Mechanistic) — NEW** — `FIRST_VIEWPORT_NO_ANSWER`: check whether the first 150 words (mechanistically: what fits in a typical first viewport for a text-heavy page) contain a direct-answer signal: a sentence starting with "[X] is", "[X] means", "[X] refers to"; or a TL;DR / summary label; or an "In short" / "The short answer is" / "Key takeaway:" phrase.  
*First 150 words is mechanistic — it's what a chunker reading top-to-bottom sees before encountering headings.*  
*Test: `tests/test_geo_static_checks.py::test_first_viewport_no_answer_fires`*

**GEO.2.4 (Mechanistic) — NEW (LLM)** — Chunk self-containedness: split page by H2/H3, send each section to LLM: *"Read this section in isolation. Can a reader understand the main claim without the rest of the article? Yes or No, then one-sentence reason."* If >50% of sections score No, emit `CHUNKS_NOT_SELF_CONTAINED`. LLM-only, runs in GEO Report.  
*Test: `tests/test_geo_analyzer.py::test_chunk_containedness_scoring` (mock LLM)*

---

### Section 3 — Answer Density

**GEO.3.1 (Mechanistic) — NEW (LLM)** — `CENTRAL_CLAIM_BURIED`: LLM extracts the page's central claim; check if it appears in the first 150 words. Flag if not.  
*Test: `tests/test_geo_analyzer.py::test_central_claim_detection` (mock LLM)*

**GEO.3.2 (Empirical) — NEW (LLM)** — Query generation and scoring: LLM generates 5–10 queries the page targets. For each: does the page contain a self-contained passage answering it? Report as table: Query | Best Chunk | Answers? (Yes/Partial/No).  
*Test: `tests/test_geo_analyzer.py::test_query_generation_and_scoring` (mock LLM)*

**GEO.3.3 (Empirical)** — Statistics count: covered by GEO.A.1 above. No separate criterion.

**GEO.3.4 (Empirical)** — Sourced claims / external citations: covered by GEO.A.2 above. No separate criterion.

---

### Section 4 — Authority Signals

**GEO.4.1 (Empirical) — NEW (static)** — Outbound link classification: categorise each external body-text link:
- `authority`: `.gov`, `.edu`, `.ac.*`, `nih.gov`, `who.int`, `arxiv.org`, `doi.org`, `pubmed.ncbi`, `github.com`, `developer.mozilla.org`, W3C, IETF, IANA, known documentation domains (MDN, PyPI, npm, etc.)
- `reference`: Wikipedia, official vendor docs
- `promotional`: same-org domains, recognisable affiliate URL patterns

Report counts in GEO report. `EXTERNAL_CITATIONS_LOW` (GEO.A.2) uses this classifier.  
*Implementation: `api/services/link_classifier.py` (new file).*  
*Test: `tests/test_link_classifier.py::test_classifies_authority_domains`*

**GEO.4.2 (Mechanistic) — NEW (static)** — `AUTHOR_BYLINE_MISSING`: on blog/article pages (BlogPosting schema or /blog/ URL), check for `rel="author"`, `itemprop="author"`, class patterns `author|byline|contributor`, JSON-LD `author` field, or `<meta name="author">`. Flag if none found.  
*Test: `tests/test_geo_static_checks.py::test_author_byline_missing_fires`*

**GEO.4.3 (Mechanistic) — NEW (static)** — Date signals: check JSON-LD `datePublished` field AND visible text for date patterns near byline region. Emit `DATE_PUBLISHED_MISSING` if absent on blog/article pages. Emit `DATE_MODIFIED_MISSING` (lower severity) if `dateModified` absent in JSON-LD.  
*Test: `tests/test_geo_static_checks.py::test_date_published_missing_fires`*

**GEO.4.4 (Conventional) — NEW (LLM)** — `PROMOTIONAL_CONTENT_INTERRUPTS`: split by H2/H3; LLM classifies each mid-article section as `main_content` or `promotional`. If >1 mid-article section is promotional, emit issue.  
*Conventional tier: mechanism is plausible (polluted chunks) but no published measurement of effect size.*  
*Test: `tests/test_geo_analyzer.py::test_promotional_detection` (mock LLM)*

---

### Section 5 — Structured Data

**GEO.5.1 (Conventional) — NEW (static)** — `JSON_LD_INVALID`: validate that every JSON-LD block has both `@type` and `@context`. Flag malformed blocks.  
*Conventional tier: schema's actual influence on LLM citations is unconfirmed.*  
*Test: `tests/test_geo_static_checks.py::test_json_ld_invalid_fires`*

**GEO.5.2 (Conventional) — NEW (static)** — `FAQ_SCHEMA_MISSING`: detect FAQ section (heading "FAQ" or "Frequently Asked Questions", or ≥3 question-form H3s), check for `FAQPage` JSON-LD. Flag if FAQ detected but no schema.  
*Conventional tier.*  
*Test: `tests/test_geo_static_checks.py::test_faq_schema_missing_fires`*

**GEO.5.3 (Conventional) — reporting only** — Report which of Article / TechArticle / BlogPosting / HowTo / Person schema types are present. No issue emitted for absence — informational metric only.

---

### Section 6 — Optional / Speculative (Conventional)

**GEO.6.1 (Conventional)** — llms.txt: already implemented. Shown in UI with Conventional badge. No score impact.

**GEO.6.2 (Conventional) — NEW** — `AI_TXT_MISSING`: check for `/ai.txt` at site root during crawl. Informational only, `severity: info`. No scorecard weight.  
*Test: `tests/test_geo_static_checks.py::test_ai_txt_missing_emitted`*

---

### Section 7 — Query-Match Test

**GEO.7.1 (Empirical) — NEW (LLM)** — For a given page, LLM generates 10 realistic user prompts the page targets. For each: extract most relevant 200–400 token chunk. Score: does that chunk alone answer the prompt with a citable fact? (Yes / Partial / No + reason). Return as structured table.  
*Implementation: `geo_analyzer.py::run_query_match_test()`*  
*Test: `tests/test_geo_analyzer.py::test_query_match_test` (mock LLM)*

---

### Section 8 — Additional Page-Level Detections

**GEO.8.1 (Mechanistic) — NEW (static)** — `CODE_BLOCK_MISSING_TECHNICAL`: on pages with TechArticle/HowTo schema or URL patterns `/how-to/`, `/tutorial/`, `/setup/`, `/guide/`, with a numbered list of ≥3 steps, check for `<pre>` or `<code>`. Flag if absent.  
*Test: `tests/test_geo_static_checks.py::test_code_block_missing_technical_fires`*

**GEO.8.2 (Mechanistic) — NEW (static)** — `COMPARISON_TABLE_MISSING`: H2/H3 headings or body text contain comparison signals ("vs", "versus", "compared to", "difference between") but no `<table>` present.  
*Test: `tests/test_geo_static_checks.py::test_comparison_table_missing_fires`*

**GEO.8.3 (Empirical) — NEW (static)** — `LINK_PROFILE_PROMOTIONAL`: if >80% of outbound body-text links point to the same organisation's own domains, emit issue.  
*The 80% threshold is mechanistically derivable (near-total promotional = no external authority signals) and not borrowed from any particular number in this conversation.*  
*Test: `tests/test_link_classifier.py::test_link_profile_promotional_fires`*

---

### Section 9 — Model Selection UI

**GEO.9.1 — NEW** — `GET/POST /api/geo/ai-model` endpoint. Persists the selected LLM model for GEO analysis to the same store as GEO settings. Options:
- `gpt-4o` (default if OpenAI key present)
- `gpt-4o-mini`
- `gemini-1.5-flash` (default if only Gemini key)
- `gemini-1.5-pro`
- `gemini-2.0-flash`

API returns available options filtered by which keys are configured.  
*Test: `tests/test_geo_settings.py::test_model_selection_persisted`*

**GEO.9.2 — NEW** — `GeoSettingsModal.jsx` updated: add model selector dropdown showing only models available for configured keys. Falls back gracefully ("no model available" state) if no keys present.

---

### Section 10 — GEO Report API + Frontend

**GEO.10.1 — NEW** — `POST /api/ai/geo-report` endpoint: accepts `job_id`. Runs all LLM checks (GEO.2.4, GEO.3.1, GEO.3.2, GEO.4.4, GEO.7.1) using the configured model. Returns `GEOReport`. Caches on job record.  
*Test: `tests/test_geo_report_endpoint.py::test_geo_report_endpoint_returns_structured_result`*

**GEO.10.2 — NEW** — `GEOReport` Pydantic model: sections for each category, each finding has `code`, `label`, `evidence_tier` (Empirical/Mechanistic/Conventional), `score`, `findings`, `pass_fail`. Aggarwal checks shown first and weighted highest in overall score.  
*Test: `tests/test_geo_report_endpoint.py::test_geo_report_model_validates`*

**GEO.10.3 — NEW** — `GEOReportPanel.jsx`: 
- Overall GEO score (0–100), Aggarwal sub-score shown separately
- Section cards with tier badge (colour-coded: gold = Empirical, blue = Mechanistic, gray = Conventional)
- Query-Match Test as table: Query | Best Chunk | Answered?
- Chunk self-containedness as per-section list
- "Run GEO Analysis" button, spinner, cached result detection
- Integrated into AI Readiness tab as a top-level section

---

## New Issue Codes Summary

Ordered by scorecard weight (Empirical > Mechanistic > Conventional):

| Code | Tier | Severity | Static/LLM | Aggarwal? |
|---|---|---|---|---|
| `STATISTICS_COUNT_LOW` | Empirical | warning | Static | ✓ |
| `EXTERNAL_CITATIONS_LOW` | Empirical | warning | Static | ✓ |
| `QUOTATIONS_MISSING` | Empirical | warning | Static | ✓ |
| `ORPHAN_CLAIM_TECHNICAL` | Empirical | warning | Static | ✓ |
| `RAW_HTML_JS_DEPENDENT` | Mechanistic | warning | Static | |
| `JS_RENDERED_CONTENT_DIFFERS` | Mechanistic | warning | GEO Report (Playwright) | |
| `CONTENT_CLOAKING_DETECTED` | Mechanistic | error | GEO Report (Playwright) | |
| `UA_CONTENT_DIFFERS` | Mechanistic | warning | GEO Report (Playwright) | |
| `FIRST_VIEWPORT_NO_ANSWER` | Mechanistic | warning | Static | |
| `AUTHOR_BYLINE_MISSING` | Mechanistic | warning | Static | |
| `DATE_PUBLISHED_MISSING` | Mechanistic | info | Static | |
| `DATE_MODIFIED_MISSING` | Mechanistic | info | Static | |
| `CODE_BLOCK_MISSING_TECHNICAL` | Mechanistic | warning | Static | |
| `COMPARISON_TABLE_MISSING` | Mechanistic | info | Static | |
| `CHUNKS_NOT_SELF_CONTAINED` | Mechanistic | warning | LLM | |
| `CENTRAL_CLAIM_BURIED` | Mechanistic | warning | LLM | |
| `LINK_PROFILE_PROMOTIONAL` | Empirical | info | Static | |
| `JSON_LD_INVALID` | Conventional | warning | Static | |
| `FAQ_SCHEMA_MISSING` | Conventional | info | Static | |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | Conventional | info | LLM | |
| `AI_TXT_MISSING` | Conventional | info | Static | |
| `STRUCTURED_ELEMENTS_LOW` | Mechanistic | info | Static (metric only) | |

---

## New Files

| File | Purpose |
|---|---|
| `api/services/geo_analyzer.py` | All LLM-based GEO analysis functions |
| `api/services/js_renderer.py` | Playwright rendering + UA comparison + cloaking detection |
| `tests/test_js_renderer.py` | JS rendering comparison checks (mock Playwright) |
| `api/services/link_classifier.py` | Outbound link authority classification |
| `frontend/src/components/GEOReportPanel.jsx` | Full GEO report display |
| `tests/test_geo_static_checks.py` | All new static issue codes |
| `tests/test_geo_analyzer.py` | LLM-based checks (mock LLM) |
| `tests/test_link_classifier.py` | Link classification |
| `tests/test_geo_settings.py` | Model selection persistence |
| `tests/test_geo_report_endpoint.py` | API endpoint integration |

---

## Modified Files

| File | What changes |
|---|---|
| `api/crawler/parser.py` | Add: `is_spa_shell`, `author_detected`, `date_published`, `date_modified`, `code_block_count`, `table_count`, `structured_element_count`, `first_150_words`, `blockquote_count` |
| `api/crawler/issue_checker.py` | Add 15 new static issue codes + scoring; Aggarwal codes get highest `impact` values |
| `api/crawler/engine.py` | Fetch `/ai.txt` during crawl |
| `api/routers/ai.py` | Add `POST /api/ai/geo-report` |
| `api/routers/geo.py` | Add `GET/POST /api/geo/ai-model` |
| `api/services/ai_analyzer.py` | Add `model` parameter (used by geo_analyzer) |
| `api/models/job.py` | Add `geo_report: dict | None` field |
| `frontend/src/data/issueHelp.js` | Add 23 new issue entries (19 + 4 JS-rendering codes) |
| `frontend/src/components/AIReadinessPanel.jsx` | Integrate GEOReportPanel + new issue groups |
| `frontend/src/components/GeoSettingsModal.jsx` | Add model selector |

---

## Implementation Order

### Phase A — Parser extensions
1. `parser.py`: add all new fields

### Phase B — Static checks
2. `link_classifier.py`: new file
3. `issue_checker.py`: all static codes (Aggarwal codes first, highest impact values)
4. `engine.py`: `/ai.txt` fetch
5. `issueHelp.js`: all 19 new entries
6. Tests: `test_geo_static_checks.py`, `test_link_classifier.py`

### Phase C — Data model + settings
7. `api/models/job.py`: `geo_report` field
8. `api/routers/geo.py`: model selection endpoint
9. Tests: `test_geo_settings.py`

### Phase D — GEO Analyzer service
10. `api/services/ai_analyzer.py`: `model` param
11. `api/services/js_renderer.py`: Playwright fetch + UA comparison + TF-IDF cloaking detection
12. `api/services/geo_analyzer.py`: full LLM service (integrates js_renderer for GEO.1.3b/c/d)
13. `api/routers/ai.py`: `POST /api/ai/geo-report`
14. Tests: `test_js_renderer.py`, `test_geo_analyzer.py`, `test_geo_report_endpoint.py`

### Phase E — Frontend
14. `GeoSettingsModal.jsx`: model selector
15. `GEOReportPanel.jsx`: full report component
16. `AIReadinessPanel.jsx`: integrate new panel + issue groups
17. Build + architecture parity test clean

---

## Adjacent Issues Found (not fixed in this change)

- **`SEMANTIC_DENSITY_LOW` uses jargon terminology.** The underlying check (text-to-HTML ratio) is legitimate and mechanistic. The name should be `HTML_CONTENT_RATIO_LOW`. Not renamed here to avoid breaking stored issue records, but documented as follow-up debt.
- `api/routers/crawl.py:1306` — `regex=` deprecated in FastAPI Query; should be `pattern=`. Minor, defer.
- `STRUCTURED_ELEMENTS_LOW` in the prior draft had a threshold of `0.05` derived from conversation. Removed — it now reports a metric only.
- `CLAIMS_UNSOURCED` from prior draft had a threshold of `< 0.05` derived from conversation. Removed — replaced by Aggarwal-grounded `EXTERNAL_CITATIONS_LOW` (zero external citations = flag).

---

## Meta-Audit Note (for the spec, not the analyzer)

The empirical foundation for GEO in 2026 is thin: the Aggarwal (2023) paper plus a small number of follow-ups. The Aggarwal tactics (citations, statistics, quotations) are the only ones with controlled measurement. Everything else in this plan is either mechanistic (plausible from first principles of how retrieval works) or conventional (industry consensus without measurement).

**Re-weighting protocol:** Periodically re-audit the evidence tier of each check against published literature. When a new paper provides measurement, the affected checks move from Conventional → Mechanistic or Mechanistic → Empirical, and the scorecard weights update. The tier label in each `_IssueSpec` in `issue_checker.py` is the single place to update — it propagates to the UI automatically.

---

## Human-Verifiable Criteria

| Criterion | How to verify |
|---|---|
| Aggarwal checks weighted highest in overall score | Run GEO report on any page; confirm Empirical section contributes more to score than Conventional |
| Evidence tier labels show correctly in UI | Load AI Readiness tab; confirm gold/blue/gray badges per tier |
| Query-match table is readable | Inspect GEOReportPanel with real LLM output |
| Model selector shows only available models | Remove one API key; confirm that model disappears from selector |
| `SEMANTIC_DENSITY_LOW` debt is visible in code | Check `issue_checker.py` comment on that entry |
