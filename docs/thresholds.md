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
| External-link check concurrency (global) | 10 | `engine.py` `_EXT_CONCURRENCY` | `TT_EXT_CONCURRENCY` |
| External-link check concurrency **per host** | 1 | `engine.py` `_EXT_PER_HOST_CONCURRENCY` | `TT_EXT_PER_HOST_CONCURRENCY` |
| Delay between checks to the **same** host | 0.25 s | `engine.py` `_EXT_PER_HOST_DELAY_S` | `TT_EXT_PER_HOST_DELAY_S` |
| `Retry-After` honoured, capped at | 5 s | `fetcher.py` `_RETRY_AFTER_MAX_S` | `CRAWL_RETRY_AFTER_MAX_S` |
| Query variant cap per path | 50 | `api/crawler/normaliser.py` (variant limit) | — |
| Image HEAD-fetch timeout | 3 seconds | `api/crawler/engine.py:900` | — |
| Content-discovery REST timeout | 6 seconds | `api/crawler/content_discovery.py` `_REST_TIMEOUT` | — |
| Scope resolution URL cap per type/category | 5000 (50 pages × 100/page) | `api/crawler/content_discovery.py` `_MAX_REST_PAGES` × `_REST_PER_PAGE` | — |
| Near-duplicate shingle size (word n-gram) | 5 | `api/crawler/checkers/cross_page.py` `_SHINGLE_SIZE` | `TT_SHINGLE_SIZE` |
| Near-duplicate min words to judge a page | 150 | `cross_page.py` `_MIN_WORDS_FOR_DUP` | `TT_MIN_WORDS_FOR_DUP` |
| Near-duplicate Jaccard threshold (NEAR_DUPLICATE_BODY) | 0.80 | `cross_page.py` `_NEAR_DUP_JACCARD` | `TT_NEAR_DUP_JACCARD` |
| Boilerplate-ratio threshold (BOILERPLATE_RATIO_HIGH) | 0.60 | `cross_page.py` `_BOILERPLATE_RATIO` | `TT_BOILERPLATE_RATIO` |
| Min pages for site-scoped entity/near-dup checks | 3 | `cross_page.py` `_MIN_PAGES_SITE_CHECKS` | `TT_MIN_PAGES_SITE_CHECKS` |
| Near-dup exact-Jaccard cap (above ⇒ MinHash prefilter) | 400 pages | `cross_page.py` `_NEARDUP_EXACT_MAX` | `TT_NEARDUP_EXACT_MAX` |
| Near-dup MinHash permutations (min 1) | 128 | `cross_page.py` `_MINHASH_PERM` | `TT_MINHASH_PERM` |
| Boilerplate doc-frequency fraction (BOILERPLATE_RATIO_HIGH input) | 0.20 | `cross_page.py` `_BOILERPLATE_DOC_FRACTION` | `TT_BOILERPLATE_DOC_FRACTION` |
| Near-dup MinHash prefilter margin | 0.15 | `cross_page.py` `_MINHASH_MARGIN` | `TT_MINHASH_MARGIN` |
| Scope-discovery REST timeout | 6 seconds | `api/crawler/content_discovery.py` `_REST_TIMEOUT` | — |
| Scope-discovery REST page size | 100 items | `api/crawler/content_discovery.py` `_REST_PER_PAGE` | — |
| Scope-discovery pagination cap | 50 pages (≈5000 URLs/type; drop announced via `scope_notes`) | `api/crawler/content_discovery.py` `_MAX_REST_PAGES` | — |
| Per-category health-score cap | 20 points | `api/services/job_store_base.py` `_CATEGORY_IMPACT_CAP` | — |
| Per-target occurrence multiplier step (§2) | 0.25 per extra occurrence | `api/crawler/checkers/links.py` `_OCC_STEP` | `TT_OCCURRENCE_STEP` |
| Per-target occurrence multiplier ceiling (§2) | 2.0× | `api/crawler/checkers/links.py` `_OCC_CEIL` | `TT_OCCURRENCE_CEIL` |
| Priority-rank formula | `impact×10 − effort×6` | `api/crawler/checkers/registry.py` `make_issue` | — |
| Quick-win threshold | impact ≥ 4 and effort ≤ 1 | `api/models/issue.py` `Issue.quick_win` | — |
| Severity from impact | ≥8 critical · 4–7 warning · ≤3 info | `registry.py` `severity_from_impact` | — |
| Info tier from impact (2026-09-01) | 3 high (Key) · 2 medium (Notable) · 0–1 low | `registry.py` `INFO_TIER_HIGH_MIN_IMPACT` / `INFO_TIER_MEDIUM_MIN_IMPACT` / `info_tier` | — |
| `info_detail` → lowest info impact shown **and scored** | all 0 · notable 2 · key 3 · none (no info row) | `registry.py` `INFO_DETAIL_MIN_IMPACT` / `info_row_excluded` | — |

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

## Stacked-link card detection (E6 / E6.1, 2026-09-01)

All values live in `api/config/link_patterns.json` (rule 9: editorial config,
not code constants). These decide what counts as a *card* — the container
requirement is what stops `LINK_STACKED_DUPLICATE` from meaning "any URL linked
twice anywhere on the page". See functional-specification §4.15 E6.1.

| Threshold | Value | Source |
|---|---|---|
| Minimum anchors to form a group | 2 | `link_patterns.json` `min_group_size` |
| Max navigational links a card may hold | 15 | `link_patterns.json` `max_card_links` |
| Max share of page text a card may hold | 0.5 | `link_patterns.json` `max_card_text_fraction` |
| Min page text before the text-share guard applies | 500 chars | `link_patterns.json` `min_page_text_for_fraction` |
| `<article>` counts as a card when the page holds | ≥ 2 articles | `api/crawler/parser.py` `_is_card_container` |
| Text-share guard applies only when the page holds | 1 card candidate | `api/crawler/parser.py` `_is_card_container` |
| Tags that are never a card | `main`, `body`, `html`, `role="main"` | `api/crawler/parser.py` `_NEVER_CARD_TAGS` |
| Class-pattern match mode | equals, or prefix + `-`/`_` | `api/crawler/parser.py` `_class_matches_pattern` |

> The text-share guard is deliberately inert in two cases, both measured. Below
> `min_page_text_for_fraction` a ratio over a tiny denominator carries no
> information, and a one-card stub is legitimately most of its own text. And on
> a page holding **several** card candidates — a listing — no one of them is
> "the page": a long card beside a short one can hold >50% of a two-item
> listing's text and was being dropped while its identical sibling was reported.

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
| llms.txt validity (per llmstxt.org) | Only a Markdown `# Title` H1 required; `>` summary, `##` sections and link count are optional (no cap). Missing H1 → INVALID | `api/crawler/engine.py` (post-fetch validation) |

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
| Crawl-start (per bearer token, 2026-09-02) | 10 per hour | `api/services/rate_limiter.py` `CRAWL_START_LIMIT` — keyed on the token hash via `rate_limit_key`, never on `X-Forwarded-For`; `tests/test_rate_limits.py` observes the 429 |
| Exports (PDF/Excel) | 30 per hour | `EXPORT_LIMIT` |
| AI analyses | 60 per hour | `AI_ANALYSIS_LIMIT` |
| Citation ingestion (`POST /api/jobs/{job_id}/ai-citations`) | 10 per minute | `CITATIONS_LIMIT` |

## Frontend / UI

| Threshold | Value | Source |
|---|---|---|
| `apiFetch` (FixManager) default timeout | 30 seconds | `frontend/src/components/FixManager.jsx:26` |
| Progress polling — first 60 s | every 2 seconds | `frontend/src/hooks/usePolling.js` |
| Progress polling — after 60 s | every 5 seconds | same |
| Vite dev-server proxy default target | `http://localhost:8000` | `frontend/vite.config.js` (overridable via `API_URL` env) |

## Performance ledger / bundle

| Threshold | Value | Source |
|---|---|---|
| Performance-bundle staleness window | 35 days | `api/services/performance_freshness.py` `STALENESS_DAYS_DEFAULT` |

Bundle data whose `generated_at` is older than this window is flagged `stale` on
ingest (PB8). Chosen as "older than roughly one monthly refresh cycle" given GSC's
~2–3-day reporting lag. Distinct from the Refresh-Trigger constants (Authority
Matrix): 180-day technical-improvement staleness and 20% traffic-decay drop.

---

## Report and crawl disclosure (E1-E7, 2026-08-29)

| Threshold | Value | Source |
|---|---|---|
| Image URLs collected per job | 150 | `TT_IMAGE_URL_CAP_PER_JOB` env, `api/crawler/engine.py` |
| Image dimension pass — total download budget | 48 MB | `TT_IMAGE_DIMENSION_TOTAL_BYTES` env, `api/crawler/engine.py` |
| Image dimension pass — skip a single file over | 12 MB | `TT_IMAGE_DIMENSION_MAX_BYTES` env, `api/crawler/engine.py` |
| Image dimension pass — max images measured | 150 | `TT_IMAGE_DIMENSION_MAX_COUNT` env, `api/crawler/engine.py` |
| Image dimension pass — concurrent downloads | 6 | `TT_IMAGE_DIMENSION_CONCURRENCY` env, `api/crawler/engine.py` |
| Image dimension pass — Pillow pixel ceiling | 80,000,000 | `api/crawler/engine.py` (set once at import) |
| SSRF resolution cache TTL | 120 s | `TT_SSRF_CACHE_TTL_S` env, `api/crawler/fetcher.py` |
| IMG_POOR_COMPRESSION — minimum pixels | 10,000 (100×100) | `min_pixels_for_bpp`, `api/crawler/image_analyzer.py` |
| IMG_POOR_COMPRESSION — weight that overrides the pixel floor | 50 KB | `min_bytes_for_bpp`, `api/crawler/image_analyzer.py` |
| Image dimension pass — overall time budget | 45 s | `TT_IMAGE_DIMENSION_BUDGET_S` env, `api/crawler/engine.py` |
| Image dimension pass — per-image timeout | 8 s | `TT_IMAGE_DIMENSION_TIMEOUT_S` env, `api/crawler/engine.py` |
| Image dimension pass — assumed size when HEAD gives none | 150 KB | `api/crawler/engine.py` |
| Broken-link source pages listed per issue | 50 | `TT_BROKEN_LINK_SOURCE_CAP` env, `api/crawler/engine.py`, `api/crawler/checkers/links.py` |
| Performance-data staleness (report presentation) | 60 days | `TT_PERF_STALE_DAYS` env, `api/services/page_priority.py` |
| Prevalence tier "systemic" | share >= 0.30 AND >= 20 pages | `api/config/prevalence.json` |
| Prevalence tier "widespread" | share >= 0.10 AND >= 10 pages | `api/config/prevalence.json` |
| Roadmap items shown per phase | 12 | `api/services/remediation.py` `build_roadmap(limit_per_phase=...)` |
| Stacked-link group minimum size | 2 | `api/config/link_patterns.json` `min_group_size` |
| Evidence rows stored per issue | 20 | `TT_EVIDENCE_CAP` env, `api/crawler/checkers/security.py` |
| Evidence rows rendered in the lists and the PDF | 10 | `TT_EVIDENCE_ROW_CAP` env, `api/services/issue_evidence.py`. Overridable per call via `evidence_lines(row_cap=…)`; `/page-details` and the Excel export pass `UNCAPPED` (D6). The **stored** cap above is NOT lifted by either — `truncated_at_capture` declares when it bit. |
| Live page-details requests | 60/hour | `DETAILS_LIMIT`, `api/services/rate_limiter.py` — `/page-details` fetches the live page per click (D6) |
| CWV pages measured (default / max) | 10 / 25 | `api/config/web_vitals.json` |
| CWV poor band — LCP / INP / CLS | 4000ms / 500ms / 0.25 | `api/config/web_vitals.json` (Google's own boundaries) |
| CWV minimum request interval | 1.1s | `api/config/web_vitals.json` — 0.91 req/s, under both published limits: PSI 100 queries/100s (the binding one) and CrUX 150/min |
| Blueprint title / description / lead bounds | 60 chars / 70-160 chars / 40-80 words | `api/config/blueprints.json` (mirrors the catalogue's own thresholds) |
| Blueprint lead grounding overlap floor | 50% of meaningful words | `api/services/blueprints.py` |
| Off-site linking sites shown | 20 | `TT_OFFSITE_SITE_CAP` env, `api/services/offsite.py` |
| Off-site minimum incoming links to count as authority | 2 | `TT_OFFSITE_MIN_INCOMING` env |
| Off-site leverage health ceiling | 80 | `TT_OFFSITE_LEVERAGE_HEALTH` env |
| Performance-ledger join warning floor | 5% of pages | `TT_PERF_JOIN_WARN_RATIO` env, `api/services/page_priority.py` |
| Top pages by impressions shown | 15 | `build_performance_summary(top_n=...)` |
| Entity description minimum words | 5 | `api/config/entity_values.json` `min_description_words` |

Below the join-warning floor, a ledger that *has* rows for the domain is almost
certainly failing to match rather than genuinely covering few pages, so it logs
loudly instead of reporting a confident wrong total (P19 + P2).

Both image and broken-link caps **announce what they drop** — the report prints
"analysed 150 of 1,284 images" and "showing 50 of 120 linking pages" whenever the
cap bites, and says nothing when it does not (rule 6, P9).

The prevalence tiers require **both** a share and a page count. A share alone
would call 3-of-8 pages on a small site "systemic"; a count alone would say the
same of 20-of-5,000. Prevalence is a reporting lens only — it does not enter any
score. The `TT_PERF_STALE_DAYS` window is distinct from the 35-day ingest
staleness above: that one flags a bundle at ingest, this one governs how the
report *presents* data whose reporting period has aged.

---

## Info tiers and the `info_detail` scan setting (2026-09-01)

| Threshold | Value | Source |
|---|---|---|
| Info tier boundaries | impact 3 → high (Key) · impact 2 → medium (Notable) · impact 0–1 → low | `api/crawler/checkers/registry.py` `INFO_TIER_HIGH_MIN_IMPACT = 3`, `INFO_TIER_MEDIUM_MIN_IMPACT = 2` |
| Catalogue split at these bounds | 9 high · 61 medium · 53 low (of 123 info codes) | `tests/test_info_tiers.py::test_counts_snapshot_9_61_53` |
| `info_detail` levels, loosest → tightest | `all` (min impact 0) · `notable` (2) · `key` (3) · `none` (no info row) | `registry.py` `INFO_DETAIL_MIN_IMPACT`; order = `INFO_DETAIL_LEVELS` |
| Default level | `all` — byte-identical to the pre-setting model | `api/models/job.py` `CrawlSettings.info_detail` |

The tier is a function of impact, never a catalogue field, so these two constants are the
only place the grading lives. The setting is applied to the score in the same slot as
job-level `suppressed_codes` (before site-scope election, cluster suppression and the category
cap) and to every list and export through the same predicate. See functional-specification §4.0.2.

---

## Striking distance (PB3, Phase 4 U4.1, 2026-09-02)

| Threshold | Value | Source |
|---|---|---|
| Position band (inclusive) | 5 – 15 | `api/config/striking_distance.json` `position_min` / `position_max` |
| Impressions floor (monthly) | 50 | `api/config/striking_distance.json` `impressions_min` |

A crawled page whose latest ledger row sits in the band with at least the floor's impressions
is listed by `GET /api/crawl/{job_id}/striking-distance`; `tests/test_striking_distance.py` pins
the three values (P29).

---

## Fix Focus checklist

| Threshold | Value | Source |
|---|---|---|
| Fix Focus min impact (inclusion floor) | 4 (warning+) | `api/crawler/checkers/registry.py` `FIX_FOCUS_MIN_IMPACT` |
| Fix Focus max pages per focus | 10 | `api/crawler/checkers/registry.py` `FIX_FOCUS_MAX_PAGES` |

The floor excludes info-level issues (impact < 4) so the checklist stays a
high-priority worklist (FF2.C). The 10-page cap bounds each focus (SEO, AI/GEO)
to a finite list; overflow is announced via `pages_total`/`items_hidden`, never
silently dropped (FF2.E). See functional-specification §6.11.

---

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
