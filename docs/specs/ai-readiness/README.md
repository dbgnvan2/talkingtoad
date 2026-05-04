# AI-Readiness Module Specifications

Audit site readiness for AI crawler access, citation, and content extraction.

## Specifications

| Version | Status | File | Description |
|---------|--------|------|-------------|
| v1.7 | ✅ Implemented | (in `../../architecture/architecture.md`) | Baseline module. `llms.txt` presence, semantic density, JSON-LD schema, conversational headings |
| v2.0 | ✅ Implemented | [v2-extended-module.md](v2-extended-module.md) | AI bot access checks (robots.txt), schema typing, content extractability, citation hooks |
| v2.1 | ✅ Implemented | [../../implementation_plan_geo_analyzer_2026-05-03.md](../../implementation_plan_geo_analyzer_2026-05-03.md) | GEO Analyzer: Aggarwal signals, JS rendering, LLM-based deep analysis |

## Key Features

### v1.7 (Implemented)

- `llms.txt` presence and format check
- Semantic density (text-to-HTML ratio < 10%)
- JSON-LD schema detection
- Conversational H2 headings

### v2.0 (Implemented)

- **AI Bot Access Checks** — Validates robots.txt for 20+ AI bots (training, search, user-fetch categories)
- **Schema Typing** — Infers page type and validates appropriate JSON-LD schema (`SCHEMA_TYPE_MISMATCH`, `SCHEMA_DEPRECATED_TYPE`, `SCHEMA_TYPE_CONFLICT`)
- **Content Extractability** — Checks for extractable text, thin content, unstructured content, image-heavy pages
- **Citation Hooks** — `CITATIONS_MISSING_SUBSTANTIAL_CONTENT`, `CITATIONS_ORPHANED`, `CITATIONS_SOURCES_INACCESSIBLE`
- **Heading Structure** — `BLOG_SECTIONS_MISSING`, `CONVERSATIONAL_H2_MISSING`

### v2.1 — GEO Analyzer (Implemented, May 2026)

**Static checks (fired during crawl, per-page):**

| Issue Code | Tier | What it checks |
|---|---|---|
| `STATISTICS_COUNT_LOW` | Empirical | First 150 words contain no numeric statistics |
| `EXTERNAL_CITATIONS_LOW` | Empirical | 500+ word page has zero external body links |
| `QUOTATIONS_MISSING` | Empirical | No blockquotes or attribution patterns |
| `ORPHAN_CLAIM_TECHNICAL` | Empirical | Technical page has 3+ unsourced factual claims |
| `RAW_HTML_JS_DEPENDENT` | Mechanistic | SPA shell with text-to-HTML ratio < 5% |
| `JS_RENDERED_CONTENT_DIFFERS` | Mechanistic | JS adds >20% new content tokens |
| `CONTENT_CLOAKING_DETECTED` | Mechanistic | JS/raw topic Jaccard similarity < 0.30 |
| `UA_CONTENT_DIFFERS` | Mechanistic | AI bots get <80% of rendered token count |
| `FIRST_VIEWPORT_NO_ANSWER` | Mechanistic | First 150 words lack a definition/answer signal |
| `AUTHOR_BYLINE_MISSING` | Mechanistic | Article page without detectable author attribution |
| `DATE_PUBLISHED_MISSING` | Mechanistic | Article without `datePublished` in JSON-LD or OG tags |
| `DATE_MODIFIED_MISSING` | Mechanistic | Article without `dateModified` |
| `CODE_BLOCK_MISSING_TECHNICAL` | Mechanistic | Technical how-to page lacks `<code>`/`<pre>` blocks |
| `COMPARISON_TABLE_MISSING` | Mechanistic | "vs" heading without an HTML table |
| `CHUNKS_NOT_SELF_CONTAINED` | Mechanistic | LLM: sections require context from elsewhere |
| `CENTRAL_CLAIM_BURIED` | Mechanistic | LLM: core claim appears after 150+ words of preamble |
| `LINK_PROFILE_PROMOTIONAL` | Mechanistic | Outbound links are predominantly affiliate URLs |
| `STRUCTURED_ELEMENTS_LOW` | Mechanistic | 500+ word page has no lists, tables, or code blocks |
| `JSON_LD_INVALID` | Conventional | JSON-LD block is missing `@type` or `@context` |
| `FAQ_SCHEMA_MISSING` | Conventional | FAQ-like headings without `FAQPage` schema |
| `PROMOTIONAL_CONTENT_INTERRUPTS` | Conventional | LLM: CTAs/sales copy interrupts informational content |
| `AI_TXT_MISSING` | Conventional | No `/ai.txt` at site root |

**LLM-based deep analysis (on-demand, per job):**

`POST /api/ai/geo-report` runs a structured LLM analysis producing a `GEOReport`:
- **Query Match Table** — AI generates 5–8 queries the page should answer; scores each Yes/Partial/No
- **Chunk Self-Containedness** — Each H2/H3 section checked for standalone comprehensibility
- **Central Claim Detection** — LLM identifies the core claim and checks it appears in first 150 words
- **Promotional Content Detection** — LLM flags CTAs/sales copy interrupting informational flow
- **JS Rendering Analysis** — Playwright-based fetch with GPTBot/ClaudeBot UA comparison

**Scoring:**
- `overall_score` — Weighted average across all tiers (Empirical ×3, Mechanistic ×2, Conventional ×1)
- `aggarwal_score` — Computed only from Empirical findings (Aggarwal et al. measured tactics)

## Evidence Confidence Labeling

Every GEO v2.1 check carries one of three evidence tiers (displayed in the UI):

- **Empirical** — Measured by Aggarwal et al. (2023); controlled evidence that these tactics increase AI citation rates
- **Mechanistic** — Derived from known retrieval mechanics (chunking, rendering, UA discrimination)
- **Conventional** — Industry practice; plausible but not independently measured

## Implementation

- **Static checks:** `api/crawler/issue_checker.py` — `_run_geo_checks()` function
- **Parser extensions:** `api/crawler/parser.py` — 9 new `ParsedPage` fields
- **Link classifier:** `api/services/link_classifier.py` — authority/reference/promotional URL classification
- **JS renderer:** `api/services/js_renderer.py` — Playwright + httpx multi-UA fetch + Jaccard comparison
- **GEO analyzer:** `api/services/geo_analyzer.py` — LLM orchestration, scoring, `GEOReport` dataclass
- **API:** `api/routers/ai.py` — `POST /api/ai/geo-report`; `api/routers/geo.py` — model selection
- **Frontend:** `frontend/src/components/GEOReportPanel.jsx` — report display component
- **Frontend:** `frontend/src/components/AIReadinessPanel.jsx` — embedded GEOReportPanel + issue groups

## Tests

| File | Coverage |
|---|---|
| `tests/test_geo_static_checks.py` | 30 tests — all static GEO issue codes |
| `tests/test_link_classifier.py` | 13 tests — authority/reference/promotional classification |
| `tests/test_js_renderer.py` | 16 tests — Playwright mock, Jaccard, UA comparison |
| `tests/test_geo_analyzer.py` | 16 tests — mock LLM, scoring, `to_dict` validation |

## Related Documentation

- Issue Codes: [issue-codes.md](../../issue-codes.md#geo-analyzer-v21)
- API: [api.md](../../api.md#geo-analyzer-v21)
- Implementation Plan: [implementation_plan_geo_analyzer_2026-05-03.md](../../implementation_plan_geo_analyzer_2026-05-03.md)
