---
status: current
last_reviewed: 2026-05-28
---

# TalkingToad — Canonical Thresholds Table

> **Single source of truth for every numeric threshold the app uses.**
> Sourced from constants in the code. When a spec or other doc cites a
> number, it should match this table or link here.
>
> If a threshold here disagrees with the code, the **code is the truth** —
> file an issue and update this doc.

Per docs-review §7.2 — these used to be scattered across multiple specs
with conflicting values (e.g. `URL_TOO_LONG` quoted as 115 in v1.5 spec
but actually 200 in code). Consolidated here so doc drift becomes
impossible.

---

## How to read this table

- **Threshold:** what the value controls
- **Value:** the number the code uses
- **Source:** file:line where the constant or check lives (verified
  against `main` at the date above)
- **Env override:** if non-empty, the env var that lets ops change it
  without code changes

---

## Crawler behaviour

| Threshold | Value | Source | Env override |
|---|---|---|---|
| Max pages per crawl (default) | 500 | `api/crawler/engine.py:47` `_DEFAULT_MAX_PAGES` | `MAX_PAGES_PER_CRAWL` |
| Per-request fetch timeout | 5 seconds | `api/crawler/fetcher.py:20` `_DEFAULT_TIMEOUT` | `CRAWL_REQUEST_TIMEOUT_S` |
| Rescan timeout | 20 seconds | `api/crawler/fetcher.py:21` `_RESCAN_TIMEOUT` | `RESCAN_TIMEOUT_S` |
| Fetch retries (transient failures only) | 1 | `api/crawler/fetcher.py` `_MAX_RETRIES` | `CRAWL_MAX_RETRIES` |
| Fetch retry backoff base | 0.5 seconds (×2^attempt) | `api/crawler/fetcher.py` `_RETRY_BACKOFF_S` | `CRAWL_RETRY_BACKOFF_S` |
| Max redirect hops | 10 | `api/crawler/fetcher.py:26` `_MAX_REDIRECTS` | — |
| Min crawl delay | 200 ms | `api/crawler/engine.py:48` `_MIN_CRAWL_DELAY_MS` | — |
| Default crawl delay | 500 ms | `api/crawler/engine.py:104` `CrawlSettings.crawl_delay_ms` | — |
| External link cap per page | 50 | `api/crawler/engine.py:49` `_EXTERNAL_LINK_CAP_PER_PAGE` | — |
| External link cap per job | 500 | `api/crawler/engine.py:50` `_EXTERNAL_LINK_CAP_PER_JOB` | — |
| Query variant cap per path | 50 | `api/crawler/normaliser.py` (variant limit) | — |
| Image HEAD-fetch timeout | 3 seconds | `api/crawler/engine.py:900` | — |
| Per-category health-score cap | 20 points | `api/services/job_store_base.py` `_CATEGORY_IMPACT_CAP` | — |
| Priority-rank formula | `impact×10 − effort×6` | `api/crawler/checkers/registry.py` `make_issue` | — |
| Quick-win threshold | impact ≥ 4 and effort ≤ 1 | `api/models/issue.py` `Issue.quick_win` | — |
| Severity from impact | ≥8 critical · 4–7 warning · ≤3 info | `registry.py` `severity_from_impact` | — |

## HTML / page size

| Threshold | Value | Source | Notes |
|---|---|---|---|
| Max HTML response size | 5 MB | `api/crawler/fetcher.py:106` `_MAX_HTML_BYTES` | Larger responses are not parsed |
| Page-too-large warning | 300 KB | `api/crawler/checkers/registry.py` `_DEFAULT_PAGE_SIZE_LIMIT_KB` | Per-job-configurable via `CrawlSettings.page_size_limit_kb` |

## Image size

| Threshold | Value | Source |
|---|---|---|
| `IMG_OVERSIZED` warning | 200 KB | `api/crawler/engine.py:110` `CrawlSettings.img_size_limit_kb` |
| `IMG_OVERSCALED` factor | 2.0× rendered size | `api/crawler/image_analyzer.py` (intrinsic > 2× rendered) |
| `IMG_POOR_COMPRESSION` ratio | > 0.5 bytes/pixel | `api/crawler/image_analyzer.py` |
| `IMG_FORMAT_LEGACY` floor | > 50 KB for JPEG/PNG/GIF | `api/crawler/image_analyzer.py` |
| Image-optimization target file size | < 200 KB (WebP) | `api/services/image_processor.py` |
| Image-optimization target width (default) | 1200 px | `api/routers/image_router.py` default |
| Image-optimization width valid range | 100–4000 px | `api/routers/image_router.py` Pydantic `ge=100, le=4000` |
| Batch optimizer parallel limit | 1–10, default 3 | `api/routers/batch_optimizer_router.py` |
| Batch optimizer max URLs per batch | 500 | `api/routers/batch_optimizer_router.py` |

## Metadata thresholds (title, meta description, URL)

| Threshold | Value | Source |
|---|---|---|
| `TITLE_TOO_SHORT` (under N chars) | < 30 | `api/crawler/issue_checker.py` `check_page` (title block) |
| `TITLE_TOO_LONG` (over N chars) | > 60 | `api/crawler/issue_checker.py` `check_page` (title block) |
| `META_DESC_TOO_SHORT` | < 70 | `api/crawler/issue_checker.py` `check_page` (meta-desc block) |
| `META_DESC_TOO_LONG` | > 160 | `api/crawler/issue_checker.py` `check_page` (meta-desc block) |
| `URL_TOO_LONG` | > 200 chars | `api/crawler/checkers/url_structure.py` `check_url_structure` |

## Image alt-text thresholds

| Threshold | Value | Source |
|---|---|---|
| `IMG_ALT_TOO_SHORT` | < 5 chars | `api/crawler/image_analyzer.py` (per-image alt-quality scoring) |
| `IMG_ALT_TOO_LONG` | > 125 chars | `api/crawler/image_analyzer.py` (per-image alt-quality scoring) |
| GEO alt-text target range | 80–125 chars | `api/services/ai_analyzer.py` GEO prompt |
| GEO long-description target | 150–300 words | `api/services/ai_analyzer.py` GEO prompt |

## Content / heading thresholds

| Threshold | Value | Source |
|---|---|---|
| `THIN_CONTENT` (word count) | < 300 | `api/crawler/issue_checker.py` `check_page` (thin-content block) |
| `HIGH_CRAWL_DEPTH` | > 4 clicks from homepage | `api/crawler/issue_checker.py` `check_page` (crawl-depth block) |
| `STRUCTURED_ELEMENTS_LOW` activates at word count | ≥ 500 | `api/crawler/checkers/ai_readiness.py` `_run_geo_checks` |
| `FIRST_VIEWPORT_NO_ANSWER` activates at word count | > 200 | `api/crawler/checkers/ai_readiness.py` `_run_geo_checks` |
| Long-paragraph detection | > 150 words | `api/crawler/parser.py:1113` `_count_long_paragraphs` |
| GEO Conversational H2 minimum | word_count ≥ 300 | `api/crawler/issue_checker.py` `check_page` (conversational-H2 block) |
| `FAQ_SCHEMA_MISSING` question count trigger | ≥ 3 (or a "FAQ" heading present) | `api/crawler/checkers/ai_readiness.py` `_run_geo_checks` |
| `FAQ_ANSWERS_NOT_IN_HTML` answer-present minimum | ≥ 40 chars in raw HTML | `api/crawler/checkers/ai_readiness.py` `_FAQ_ANSWER_MIN_CHARS` |
| `FAQ_ANSWERS_NOT_IN_HTML` fire condition | ≥ 2 missing **and** ≥ 50% of FAQ answers | `api/crawler/checkers/ai_readiness.py` `_run_geo_checks` |
| FAQ question detection | accordion/`<details>`/heading titles ending in `?` | `api/crawler/parser.py` `_extract_faq_blocks` |

## Content extraction windows (ParsedPage)

These are the pre-computed text buffers every GEO check reads from.
Single extraction path = no buffer-agreement bugs.

| Buffer | Size | Source |
|---|---|---|
| `first_200_words` | First 200 words of `<body>` text (excludes nav/header/footer/aside/script/style) | `api/crawler/parser.py:117, 262` |
| `first_600_words` | First 600 words of body text (same exclusions) | `api/crawler/parser.py:118, 263` |
| Surrounding-text window for images | ±300 chars | `api/crawler/parser.py:848` `_extract_surrounding_text` |

## GEO / AI-readiness scoring

| Threshold | Value | Source |
|---|---|---|
| `SEMANTIC_DENSITY_LOW` | text-to-HTML ratio < 10% | `api/crawler/issue_checker.py` `check_page` (AI-readiness block) |
| `JS_RENDERED_CONTENT_DIFFERS` | rendered adds > 20% new tokens | `api/services/js_renderer.py:39` `_DIFF_THRESHOLD` |
| `CONTENT_CLOAKING_DETECTED` | rendered vs raw Jaccard < 0.30 | `api/services/js_renderer.py:40` `_JACCARD_THRESHOLD` |
| `UA_CONTENT_DIFFERS` | AI bot UA gets > 20% fewer tokens than rendered | `api/services/js_renderer.py:39` |
| JS render timeout | 5 seconds | `api/services/js_renderer.py:38` `_PLAYWRIGHT_TIMEOUT_MS` |
| Top-N keyword window for Jaccard | 10 keywords | `api/services/js_renderer.py:41` `_TOP_N_KEYWORDS` |
| AI bot reference table max age before "stale" warning | 365 days | `api/services/ai_bots.py` `MAX_AGE_DAYS` (v2.0 spec §3.2) |
| llms.txt URL count limit | > 20 URLs → INVALID | `api/crawler/engine.py` (post-fetch validation) |

## Health score formula

| Formula | Where |
|---|---|
| Health score | `max(0, 100 − Σ impact)` across all issues | `api/services/sqlite_store.py` `get_summary` |
| Priority rank | `(impact × 10) − (effort × 2)` | `api/crawler/checkers/registry.py` `make_issue` |
| Impact range | 0–10 | enforced by `tests/test_class1_invariants.py::test_scoring_values_are_in_valid_ranges` |
| Effort range | 0–5 | same test |
| Agent Health score | `max(0, 100 − Σ impact)` over agent-relevant issues, averaged per page | `api/services/job_store_base.py` `_compute_agent_health_score` |
| Agent-relevant set | categories `ai_readiness` / `rendering` / `semantic_html` ∪ codes `PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK` | `api/services/job_store_base.py` `_is_agent_issue` |

**R5 scope behaviors (2026-07-06, `scoring_model_version = "2026-07-06-r5"`).** No numeric bound changed —
the per-category cap stays **20** (row above). Two scope rules affect *how many times* an impact is charged,
not the cap value: (a) **site-scoped** codes (`HTTP_PAGE`, `HTTPS_REDIRECT_MISSING`, `MIXED_CONTENT`,
`MISSING_HSTS`, `WWW_CANONICALIZATION`) deduct once per site, not per page; (b) **noindex scope-reduction** —
a page with `NOINDEX_META`/`NOINDEX_HEADER` charges only the noindex code plus any `security`/`redirect`
codes; all other page-scoped codes on that page contribute 0. See functional-specification §4.0.1.

## AI provider configuration

| Threshold | Value | Source |
|---|---|---|
| Gemini API timeout | 20 seconds | `api/services/ai_analyzer.py` `_call_gemini` |
| OpenAI API timeout | 20 seconds | `api/services/ai_analyzer.py` `_call_openai` |
| Vision API timeout | 30 seconds | `api/services/ai_analyzer.py` `_call_openai_vision` |
| Image base64 fetch timeout | 10 seconds | `api/services/ai_analyzer.py:364` |
| Advisor LLM timeout | 30 seconds | `api/services/advisor.py:43` `_TIMEOUT` |
| Rewriter LLM timeout | 60 seconds | `api/services/rewriter.py:28` `_TIMEOUT` |
| Rewriter temperature | 0.2 | `api/services/rewriter.py` |
| Advisor temperature | 0.2 | `api/services/advisor.py` |

## API rate limits

| Endpoint group | Limit | Source |
|---|---|---|
| Default crawl-start (per IP) | 3 concurrent / 10 per hour | `api/services/rate_limiter.py` |
| AI analysis (per IP) | configurable via `AI_ANALYSIS_LIMIT` | `api/services/rate_limiter.py` |

## Frontend / UI

| Threshold | Value | Source |
|---|---|---|
| `apiFetch` (FixManager) default timeout | 30 seconds | `frontend/src/components/FixManager.jsx:26` |
| Progress polling — first 60 s | every 2 seconds | `frontend/src/hooks/usePolling.js` |
| Progress polling — after 60 s | every 5 seconds | same |
| Vite dev-server proxy default target | `http://localhost:8000` | `frontend/vite.config.js` (overridable via `API_URL` env) |

## Test infrastructure

| Threshold | Value | Source |
|---|---|---|
| Endpoint coverage allowlist max size | 10 entries | `tests/test_endpoint_coverage.py` `_ALLOWLIST` |
| Dead-code allowlist (catalogue codes without emission site) | 15 entries (v2.3 snapshot) | `tests/test_class1_invariants.py` `_DEAD_CODE_ALLOWLIST` |

---

## Cross-references

- **Per-issue thresholds** are also documented in
  [`issue-codes.md`](issue-codes.md) (auto-generated from `_CATALOGUE`)
- **Acceptance criteria** that cite numeric thresholds are in
  [`functional-specification.md`](functional-specification.md) and
  must agree with values here
- **Configuration** of overridable thresholds at deploy time is in
  [`deployment-railway.md`](deployment-railway.md)

## How to update a threshold

1. Change the constant in code (one place — that's why this table sources
   `file:line`).
2. Update the value in this table.
3. If the threshold appears in `functional-specification.md` acceptance
   criteria, update there too.
4. If `issue-codes.md` references the value, re-run
   `python scripts/generate_issue_codes_doc.py` — the doc auto-syncs.
5. Add or update a test that asserts the new behaviour (per
   CLAUDE.md self-review protocol).
6. Commit + push.

If a sweep ever finds disagreement between this doc and the code,
**the code is the truth** — update this doc, not the code, unless the
threshold change is itself intentional.
