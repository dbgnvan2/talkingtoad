---
status: current
last_reviewed: 2026-07-06
---
# TalkingToad — Functional Specification

> **Status:** v2.6.0 (rock-solid baseline). Reflects shipped behaviour on
> `main` as of 2026-06-01.
> **Audience:** Independent QA reviewer / external verifier. You should
> not need to read the source code to use this document.
> **Purpose:** Describe what TalkingToad does in terms of observable
> behaviour, with acceptance criteria. Use this as a checklist when
> verifying the running application matches its specification.
>
> **Companion docs:**
> - `CLAUDE.md` — implementation conventions and tech stack
> - `architecture.md` — system architecture and data flow
> - `api.md` — API endpoint reference
> - `thresholds.md` — canonical table of every numeric threshold (acceptance criteria here cite these)
> - `issue-codes.md` — every issue code, auto-generated from `_CATALOGUE`
> - `deployment-railway.md` — production deployment
> - `PLAN-V3.0.md` — roadmap for features not shipped today

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Core user journeys](#2-core-user-journeys)
3. [Feature catalogue](#3-feature-catalogue)
4. [Audit capabilities](#4-audit-capabilities)
5. [Fix capabilities](#5-fix-capabilities)
6. [AI capabilities](#6-ai-capabilities)
7. [Reporting and export](#7-reporting-and-export)
8. [Non-functional requirements](#8-non-functional-requirements)
9. [Verification matrix](#9-verification-matrix)
10. [Known limitations](#10-known-limitations)

---

## 1. Purpose and scope

### 1.1 What TalkingToad does

TalkingToad is a web-based SEO auditing and remediation tool. It crawls a
target website, identifies SEO issues (broken links, missing metadata,
heading problems, image issues, AI-readiness gaps, etc.), and — for
WordPress sites — applies one-click fixes directly via the WP REST API.

### 1.2 Target users

- **Nonprofit staff** managing WordPress sites without dedicated dev
  support (primary)
- **SEO consultants** who audit client sites and want fixable findings
- **AI-readiness practitioners** evaluating how well a site is set up
  to be cited by AI search engines (Google AI Overviews, ChatGPT,
  Perplexity, etc.)

### 1.3 In scope

- Crawling and per-page issue detection
- Cross-page duplicate detection
- WordPress fix application (titles, meta, headings, images, links)
- Image optimization (resize, WebP, GPS EXIF, SEO filename)
- AI-assisted analysis and rewrite suggestions
- PDF, Excel, and CSV reports
- AI-readiness audit (GEO — Generative Engine Optimization)
- **GSC performance integration and Authority Matrix**

### 1.4 Out of scope (today)

- Server log analysis (no admin access to target sites)
- Live AI engine query testing ("does ChatGPT cite this page?")
- Headless browser DOM analysis beyond the optional JS-renderer service
- AI-engine-specific user-agent crawling (only declared bot table is
  used, not actual bot impersonation)
- Multi-tenant / multi-customer (Identity model and strict isolation are deferred until paid-customer launch)

### 1.5 Deployment model

- **Frontend:** Vercel-hosted React SPA, port 5173 in dev
- **Backend:** Railway-hosted FastAPI container, port 8000 in dev
- **Local dev:** `./talkingtoad.sh server` + `./talkingtoad.sh frontend`
  in separate terminals
- **Data store:** SQLite (dev), Upstash Redis (optional prod), or
  Railway-mounted SQLite volume

---

## 2. Core user journeys

Each journey lists numbered steps, the observable outcome at each step,
and acceptance criteria for the journey as a whole.

### Journey A — Run an SEO audit on a website

**Goal:** User wants a complete SEO report for `https://example.org`.

**Steps:**
1. User loads http://localhost:5173/ (or the deployed Vercel URL).
2. User enters `https://example.org` in the URL field.
3. (Optional) User adjusts max-pages (default 500), crawl delay (default
   500 ms), and/or supplies a sitemap URL override.
4. User clicks "Start Crawl".
5. **Observable:** browser navigates to `/progress/<job_id>` and shows a
   live progress indicator (pages crawled, current URL).
6. **Observable:** when the crawl completes, browser navigates to
   `/results/<job_id>` and shows the Summary tab.
7. Summary tab shows: total issues, issue counts by severity
   (critical/warning/info), issue counts by category, health score.

**Acceptance criteria:**
- The crawl respects robots.txt — disallowed paths are not fetched.
- Sitemap is auto-discovered and URLs from it are included if not
  already linked from the homepage.
- Crawl finishes within a bounded time (default `MAX_PAGES_PER_CRAWL = 500`).
- Every page returns one of: a HTTP status code, an issue, or both.
- **Page Health = `max(0, 100 − deduction)`**; **Site Health = mean of page scores**. Computed by
  the single shared function `job_store_base.compute_impact_health`, used by **both** the SQLite
  (dev) and Redis (prod) stores so the two cannot diverge (the pre-v1.5 density model survives only
  as its internal fallback). *(Audit 2026-07-03, Path A.)* **(R5.0)** The two former raw-uncapped-sum
  paths in `crawl.py` and `citations.py` now route through this same canonical capped-and-suppressed
  function, so all three health-score paths agree
  (`tests/test_scoring_paths_unified.py::test_all_health_paths_agree`).
- **Deduction = per-category caps + page-fatal bypass** *(audit R3 structural fix):* after cluster
  suppression, each category's charged impact is capped at **20** so correlated minor issues (and
  per-occurrence codes like many `BROKEN_LINK_*` on one page) can't stack a page to 0; **page-fatal
  codes bypass the cap** and are charged in full so a genuinely dead page still scores low. Fatal
  codes: `NOINDEX_META`, `NOINDEX_HEADER`, `ROBOTS_BLOCKED`, `PAGE_TIMEOUT`, `HTTP_PAGE`,
  `HTTPS_REDIRECT_MISSING`, `REDIRECT_LOOP`, `LOGIN_REDIRECT`.
- **Cluster suppression (R4):** when a parent code and its correlated children
  are present on the same page, only the parent is charged to the score, so one
  root cause is not double-counted. Suppressed issues remain fully visible in the
  issue list/counts — suppression is scoring-only. Rules:
  `SCHEMA_MISSING` ⊳ {`JSON_LD_MISSING`, `SCHEMA_ORG_MISSING`};
  `TITLE_META_DUPLICATE_PAIR` ⊳ {`TITLE_DUPLICATE`, `META_DESC_DUPLICATE`};
  `RAW_HTML_JS_DEPENDENT` ⊳ {`AI_CONTENT_NOT_IN_TEXT`, `CONTENT_NOT_EXTRACTABLE_NO_TEXT`, `CONTACT_INFO_NOT_IN_HTML`};
  `THIN_CONTENT` ⊳ {`CONTENT_THIN`}. **(R5.2)** The suppression clusters were extended per the R5
  spec (including the three former "merge" clusters — answer-first, chunk, social — re-cast as
  suppress-children so no code is deleted); see §4.0.1 for the full R5 scoring behavior.
- The Summary tab loads within 2 seconds of crawl completion.

### Journey B — Review and triage issues

**Goal:** User wants to understand and prioritize the issues found.

**Steps:**
1. From the Summary tab, user clicks an issue category (e.g. "Metadata").
2. **Observable:** the category panel lists every issue of that
   category, grouped by issue code, with the affected URL list.
3. User clicks an individual issue.
4. **Observable:** inline panel expands showing: severity badge,
   description, recommendation, "Why it matters" link to help text,
   confidence label (for ai_readiness issues), and a link to the live
   page.
5. User navigates to the "By Page" view.
6. **Observable:** every crawled page is listed with its total issue
   count, broken down by severity.

**Acceptance criteria:**
- Every issue shown has a help-text entry in `issueHelp.js` that matches
  its code (enforced by `test_architecture_constraints::TestIssueCodeParity`).
- ai_readiness issues display a confidence pill labelled
  "Established", "Reasonable proxy", or "Heuristic" per the spec
  taxonomy. This confidence is also serialized into the API response.
- Clicking a URL in any category tab navigates to the By Page view for
  that URL.
- The detail panel shows all issues for the page grouped by category.

### Journey C — Apply WordPress fixes

**Goal:** User has a WordPress site with auditable issues; wants to fix
them via the app.

**Pre-conditions:**
- A `wp-credentials.json` file exists at the project root with valid
  WP login credentials (`site_url`, `login_url`, `username`, `password`).
- The credentials' `site_url` domain matches the crawl job's target
  domain (cross-site protection).
- The WP site is reachable.

**Steps:**
1. From the Results page, user opens the "Fix Manager" tab.
2. User clicks "Generate Fixes".
3. **Observable:** for each fixable issue, the app proposes a value
   (e.g. trimmed title, suggested meta description) and presents it
   inline. The user reviews each suggestion.
4. User adjusts proposed values where needed (inline editing).
5. User clicks "Apply All Approved Fixes".
6. **Observable:** for each fix, the WP REST API is called; success or
   failure is shown per-fix.
7. The affected pages are auto-rescanned to reflect post-fix state.

**Acceptance criteria:**
- The app refuses to write an empty string to a text field (data-loss
  guard — see verified Defect #5 in docs-review-response).
- Domain mismatch (creds for `othersite.com`, crawl targets
  `example.com`) returns 403 DOMAIN_MISMATCH on every WP-touching
  endpoint.
- Re-running "Generate Fixes" idempotently regenerates proposals
  without duplicating them.
- Health score updates live after fixes are applied.

### Journey D — Optimize an image

**Goal:** User has an oversized image (>200 KB) flagged in the audit.

**Steps:**
1. From the Image Analysis tab, user clicks "Optimize" next to an
   oversized image.
2. **Observable:** a preview modal shows: original size/dimensions,
   estimated optimized size, target dimensions, projected savings %.
3. User confirms optimization with chosen settings (target width,
   apply GPS metadata, optional SEO keyword for filename, optional
   GEO AI-generated metadata).
4. **Observable:** the app downloads the original, optimizes to WebP,
   uploads the new file to WordPress as a separate media item.
5. **Observable:** both files now exist in WP media library; user is
   reminded to manually update post references to the new file.

**Acceptance criteria:**
- The original WP image is not modified or deleted.
- The new file is WebP format and ≤200 KB if the original was larger.
- GPS EXIF coordinates are injected per the configured GEO settings.
- The image URL is rejected with `SSRF_BLOCKED` if it resolves to a
  private/internal IP (M0.6.7).

### Journey E — Export an audit report

**Goal:** User wants to share findings with a non-technical stakeholder.

**Steps:**
1. From the Results page, user clicks "Export PDF".
2. **Observable:** a save-dialog opens (via the File System Access API
   on supporting browsers, or a regular download fallback).
3. User selects "Include Help Text" / "Summary Only" / "Include AI
   Executive Summary" options.
4. User saves the PDF.
5. **Observable:** PDF contains a cover page, executive summary (if
   selected), issue listings grouped by category with severity colour
   coding, a "What to Do Next" prioritized checklist, and per-page
   issue breakdowns.

**Acceptance criteria:**
- PDF filename includes the audited domain (e.g.
  `TalkingToad-Audit-example.com.pdf`).
- Critical issues appear in red, warnings in amber, info in blue.
- AI-readiness issues include a colour-coded evidence-tier line ("Established", "Reasonable proxy", "Heuristic") based on the `confidence_label`.
- Health score appears prominently on the cover page.
- The full URL is shown for every flagged page (not truncated).
- A category page break is inserted before each issue title to avoid
  orphaning help text.
- Excel export (alternate to PDF) produces a tabbed workbook with one
  sheet per category, including a Confidence column for AI-readiness issues.

### Journey F — Run AI-assisted content advisor

**Goal:** User wants AI feedback on a page's content quality for AI
search retrieval.

**Pre-conditions:** Configured AI provider credentials (handled dynamically via the backend `AIRouter`).

**Steps:**
1. From the Results page, user opens the GEO Report panel.
2. User selects one or more pages to analyze.
3. User clicks "Generate Report". (Optionally provides a `GeoConfig` payload via settings to validate authoritative entity representations.)
4. **Observable:** the AI advisor returns a structured analysis covering
   six properties: source fidelity, factual grounding,
   self-containment, structural fitness, authority signals, honest
   placeholder use.
5. (Optional) User clicks "Generate Rewrite Prompt" → "Apply Rewrite"
   to receive a faithful rewritten version.

**Acceptance criteria:**
- Every finding cites specific page text (no findings without evidence).
- The advisor does not score or rank — it provides qualitative findings only.
- The rewriter is a single LLM call with low temperature (0.2) and no variants.
- The rewriter and critic calls use the `AIRouter` for multi-provider routing and token usage tracking.
- If a `GeoConfig` is injected, the advisor prompt strictly validates findings against the specified authoritative entities.
- AI token and cost usage is logged to the `ai_usage` table asynchronously.

### Journey G — Connect GSC and analyze performance

**Goal:** User wants to see which high-traffic pages are structurally vulnerable.

**Steps:**
1. User opens the "Settings" or "Integrations" panel.
2. User clicks "Connect Google Search Console".
3. **Observable:** Browser redirects to Google OAuth consent; user approves access.
4. User returns to TalkingToad; browser shows "Connected" status.
5. User navigates to the "Results" page for a crawl.
6. **Observable:** A "GSC Insights" panel is available (or GSC columns appear in the By Page view).
7. User filters/sorts by "Vulnerable Stars".
8. **Observable:** The app lists pages with high impressions/clicks but critical structural issues.

**Acceptance criteria:**
- GSC tokens are stored encrypted and never exposed in logs or UI.
- Clicks, impressions, CTR, and position data are mapped correctly to the crawled URLs.
- The "Review for Improvements" badge appears on pages meeting the staleness or decay criteria.
- Disconnecting GSC successfully removes the encrypted tokens.

---

## 3. Feature catalogue

High-level inventory. Each row maps to detailed sections later.

| Feature | Capability | Status | Detail section |
|---|---|---|---|
| Async crawl engine | Crawls up to 500 pages with rate limiting + robots.txt respect | ✅ Shipped | §4 |
| Scan content-type scoping | Partial scan by Pages / Posts / category / Custom Post Types via REST or typed sitemaps | ✅ Shipped | §4.9 |
| 142 issue codes | 140+ SEO and AI-readiness issue checks | ✅ Shipped | §4 |
| Cross-page duplicate detection | Title / meta / title+meta duplicates across pages | ✅ Shipped | §4 |
| Confidence labelling | All 60 AI-readiness codes labelled Established/Reasonable-proxy/Heuristic | ✅ Shipped | §4.6 |
| GSC OAuth integration | OAuth flow to pull performance metrics (clicks/impressions) | ✅ Shipped | §4.8 |
| Performance Ledger | Per-page GSC metrics and technical improvement lifecycle tracking | ✅ Shipped | §4.8 |
| Refresh Trigger | Automated "Review for Improvements" flags (staleness, traffic decay) | ✅ Shipped | §4.8 |
| Authority Matrix | Correlation of HealthScore with GSC performance metrics | ✅ Shipped | §4.8 |
| Title fix manager | Generate + apply title/meta fixes via WP REST | ✅ Shipped | §5.1 |
| Heading fix manager | Find / change-level / change-text / bulk-replace / to-bold | ✅ Shipped | §5.2 |
| Image metadata fix | Update alt / title / caption / description | ✅ Shipped | §5.3 |
| Image optimization (single) | Workflow A: download → WebP → re-upload as new file | ✅ Shipped | §5.4 |
| Image optimization (upload) | Workflow B: upload local file → optimize → push to WP | ✅ Shipped | §5.4 |
| Batch image optimization | Parallel processing with pause/resume/cancel | ✅ Shipped | §5.5 |
| Orphaned media detection | Find WP media not referenced on any crawled page | ✅ Shipped | §5.6 |
| Broken-link verification | Re-check broken links and auto-clear fixed ones | ✅ Shipped | §5.7 |
| Link replacement | Swap one URL for another in a WP post's content | ✅ Shipped | §5.7 |
| Mark-fixed actions | Mark issues / anchors / broken-links as fixed | ✅ Shipped | §5.8 |
| Generic inline fix dispatcher | `apply-one` for any fixable issue from the inline panel | ✅ Shipped | §5.9 |
| WP value lookup | Read current WP field value for inline comparison | ✅ Shipped | §5.9 |
| Content Quality Advisor | Structured AI critique with 6 evaluation properties | ✅ Shipped | §6.1 |
| Content Rewriter | Single LLM call rewrite with low temperature | ✅ Shipped | §6.2 |
| Image AI analysis (basic) | Vision-model alt-text suggestion + accuracy scores | ✅ Shipped | §6.3 |
| Image AI analysis (GEO) | Geographic + topic entity-rich alt text and long description | ✅ Shipped | §6.3 |
| Executive summary (AI) | Plain-language 3–5 sentence narrative for PDF report | ✅ Shipped | §6.4 |
| PDF & Excel reports | 8.5×11 audit report with AI evidence tiers and CSV/Excel exports | ✅ Shipped | §7.1 |
| Verified links | Mark external URLs as known-good to suppress `EXTERNAL_LINK_SKIPPED` | ✅ Shipped | §5.10 |
| Suppressed issue codes | Globally exclude specific codes from health-score calc | ✅ Shipped | §8.4 |
| Exempt anchor URLs | Exclude specific anchor hrefs from `LINK_EMPTY_ANCHOR` flagging | ✅ Shipped | §8.4 |
| Ignored image patterns | Substring patterns to exclude theme SVGs from image checks | ✅ Shipped | §8.4 |
| llms.txt validation | Detect presence and validate `/llms.txt` at site root | ✅ Shipped | §4.6 |
| llms.txt generation | Curated `/llms.txt` from high-value crawled pages | ✅ Shipped | §5.11 |
| AI bot reference table | Robots.txt audit for GPTBot / ClaudeBot / etc. | ✅ Shipped | §4.6 |
| Schema typing per page | JSON-LD type match for inferred page type | ✅ Shipped | §4.6 |
| Citation ingestion endpoint | Receive per-URL AI citation data from sibling tool | ✅ Shipped | §6.5 |
| Multi-provider AI routing | AIRouter singleton handling text and vision endpoints | ✅ Shipped | §6.6 |
| Token usage tracking | Aggregation API `GET /api/ai/usage/stats` | ✅ Shipped | §6.6 |
| Schema-visible-content check | `SCHEMA_VISIBLE_MISMATCH` alignment check | ✅ Shipped | §4.6 |
| Content freshness suite | `CONTENT_DATE_STALE_VISIBLE`, `CONTENT_STAT_OUTDATED` | ✅ Shipped | §4.6 |
| AI-preview controls | `AI_PREVIEW_SUPPRESSED`, `AI_PREVIEW_BLOCKED_AT_BOT` | ✅ Shipped | §4.6 |
| AI content textuality | `AI_CONTENT_NOT_IN_TEXT` check for embedded content | ✅ Shipped | §4.6 |
| Visual companion nudge | `AI_NO_VISUAL_COMPANION` missing images diagnostic | ✅ Shipped | §4.6 |
| Main content ratio | `AI_MAIN_CONTENT_LOW_RATIO` structural flag | ✅ Shipped | §4.6 |
| Positional answerability | `GEO_SUMMARY_BURIED` checks position of first content node | ✅ Shipped | §4.6 |
| Complexity-Moat FAQ Gen | `POST /api/ai/geo-faq` JSON-LD generator | ✅ Shipped | §5.12 |
| Entity Schema Factory | `POST /api/geo/entity-schema` JSON-LD generator | ✅ Shipped | §5.12 |
| Multi-page GEO report | Generate GEO report across selected pages | 🟡 On feature/multi-page-geo branch | §10 |
| GSC OAuth integration | Pull AI Overview / AI Mode performance data | ✅ Shipped | §4.8 |
| Multi-tenant Identity | Multi-tenant customer credentials and logical isolation | ❌ Deferred | §10 |

---

## 4. Audit capabilities

The crawler emits **170 distinct issue codes** organised into 13
categories. Each code has: impact (0–10), effort (0–5), fixability
(`wp_fixable` / `content_edit` / `developer_needed`), and a confidence label.

**Scoring calibration (R3, 2026-07-03 — Model B, triangulated from two independent
expert reviews + audit).** Impact is **derived**, not hand-set:
`impact = matrix(confidence, effect_size)` where confidence ∈ {Heuristic, Reasonable
proxy, Established} (+ an Aggarwal "measured" lane) and effect_size ∈ {none, small,
moderate, large}; the 10-tier is reserved for documented page-removal
(`NOINDEX_META/HEADER`, `REDIRECT_LOOP`). A small documented override set adjudicates
the inter-reviewer divergences. The calibration record and `derive_impact()` live in
`registry.py`; `test_r3_calibration.py` asserts `_ISSUE_SCORING == derive_impact`.
- **Severity is derived from impact** (single source of truth — no drift):
  `impact ≥ 8 → critical`, `4–7 → warning`, `≤3 → info`.
- **Priority rank** `(impact × 10) − (effort × 6)` (effort weighted so real quick wins
  surface within an impact tier); plus a derived **`quick_win`** flag
  (`impact ≥ 4 AND effort ≤ 1`) for the UI's quick-wins list.

### 4.0 Audit engine architecture (Cycle K, v2.6 M9.1)

The single canonical list lives in
`api/crawler/checkers/registry.py` under `_CATALOGUE`, with scoring in
`_ISSUE_SCORING` and confidence labels in `_AI_READINESS_CONFIDENCE`. The
top-level module `api/crawler/issue_checker.py` is now a **thin facade**
that re-exports every historically importable name and orchestrates the
per-page checks across a `checkers/` package.

`docs/issue-codes.md` is **auto-generated** from `_CATALOGUE` by
`scripts/generate_issue_codes_doc.py`; the CI parity test fails if the generated file
drifts from the registry.

The `checkers/` package contains the following modules:

| Module | Responsibility |
|---|---|
| `registry.py` | Issue dataclasses, `_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`, `_STOP_WORDS`, size constants, `make_issue()` factory. |
| `metadata.py` | Canonical tag validation (`CANONICAL_*`). |
| `headings.py` | H1 presence, multiple H1s, empty headings, level skips. |
| `links.py` | Broken-link status mapping, redirect classification, auto-redirect heuristics. |
| `images.py` | Per-asset file-size limits (`IMG_OVERSIZED`, `PDF_TOO_LARGE`). |
| `security.py` | HTTP-page, mixed content, HSTS, unsafe cross-origin. |
| `crawlability.py` | `NOINDEX_*`, long-paragraph signal, post-crawl AMP HEAD result mapping. |
| `url_structure.py` | URL hygiene — length, casing, embedded spaces, underscores. |
| `ai_readiness.py` | `_run_geo_checks` + every GEO regex/counter helper (statistics, citations, quotations, orphan claims, answer signal, numbered steps). |
| `cross_page.py` | Post-crawl `TITLE_DUPLICATE`, `META_DESC_DUPLICATE`, `CANONICAL_MISSING`, `ORPHAN_PAGE` (gated on `link_graph_complete` — see §4.4). |
| `semantic_html.py` | Agent-readiness WP3 — `NON_SEMANTIC_BUTTON`, `INTERACTIVE_NO_ACCESSIBLE_NAME`, `LANDMARK_MAIN_MISSING`, `LANDMARK_NAV_MISSING`. |
| `__init__.py` | Package docstring. |

Agent-readiness WP4 (`PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK`) lives in
`links.py`, WP2 (`JS_DEPENDENT_NAVIGATION`) in `crawlability.py`, and WP5
(`SCHEMA_ORG_MISSING`, `CONTACT_INFO_NOT_IN_HTML`) in `metadata.py`. The
underlying signals are pre-computed on `ParsedPage` at parse time.

### 4.0.1 Scoring model R5 (2026-07-06)

The R5 scoring change (`scoring_model_version = "2026-07-06-r5"`) finished the safe remainder of the
external scoring spec on top of the R3/R4 calibration. It changes **how the health score is computed**.
The proposed cap increase to 25 remains declined (category cap stays **20**).

**§7 code merges/deletions (2026-07-22, owner re-opened).** Previously declined; now applied where the
codes share one detection pipeline: `SCHEMA_MISSING` **deleted** (duplicate of `JSON_LD_MISSING`, now the
sole schema-family parent); `TITLE_META_DUPLICATE_PAIR` **deleted** (`TITLE_DUPLICATE` and
`META_DESC_DUPLICATE` now each charge independently); `OG_TITLE_MISSING` + `OG_DESC_MISSING` +
`OG_IMAGE_MISSING` + `TWITTER_CARD_MISSING` **merged → `SOCIAL_PREVIEW_METADATA_MISSING`** (one row listing
the missing tags in `extra.missing_tags`). Net catalogue 157 → **152**. The **answer-first**
(`CENTRAL_CLAIM_BURIED`, `FIRST_VIEWPORT_NO_ANSWER`, `GEO_SUMMARY_BURIED`) and **chunk**
(`CHUNKS_NOT_SELF_CONTAINED`, `SECTION_CROSS_REFERENCES`, `SECTION_VAGUE_OPENER`) families are
**deliberately kept as suppress-children, not merged**: `CENTRAL_CLAIM_BURIED` / `CHUNKS_NOT_SELF_CONTAINED`
are emitted by the on-demand LLM path (`geo_llm.py`) while their would-be merge-mates are crawl-static
checks — merging would conflate an LLM verdict with a static heuristic under one code. Suppress-children
already delivers the no-double-count outcome across both pipelines.

**§2 per-target occurrence counting** — see R5.7 below.

- **R5.0 — Unified page-health computation.** There is now a single capped-and-suppressed deduction path.
  The two former raw-uncapped-sum paths in `crawl.py` and `citations.py` route through
  `job_store_base.compute_impact_health`, so the summary endpoint, the citations endpoint, and the
  function itself all return the same score for a given page.
  → `tests/test_scoring_paths_unified.py::test_all_health_paths_agree`
- **R5.1 — Site-scope.** `_IssueSpec` gains a `scope: page|site` field (default `page`). The TLS /
  site-config codes `HTTP_PAGE`, `HTTPS_REDIRECT_MISSING`, `MIXED_CONTENT`, `MISSING_HSTS`,
  `WWW_CANONICALIZATION` are `scope="site"`: a site-scoped finding deducts **once per site** (worst-affected
  representative page), never repeatedly across every page. `scope` is serialized in `_issue_dict()`.
  → `tests/test_site_scope.py::test_site_codes_declared_site_scope`,
  `::test_site_scope_single_deduction`, `::test_page_issues_include_scope`
- **R5.2 — Extended suppression clusters.** The R5 spec's clusters were ported into the suppression map
  (scoring-only; children stay visible and contribute 0 when the parent is present). The three former
  "merge" clusters (answer-first, chunk, social) are implemented as suppress-children — one existing
  parent elected, siblings → 0 — so no code is deleted. No cluster suppresses a `security` or `redirect`
  code. → `tests/test_r5_clusters.py::test_cluster_<name>_suppresses_children`,
  `::test_clusters_never_touch_security_redirect`
- **R5.3 — Noindex scope-reduction.** When `NOINDEX_META`/`NOINDEX_HEADER` fires on a page, all other
  page-scoped codes on that page contribute 0 **except** the `security` and `redirect` categories (and the
  noindex code itself) — a noindexed page is not penalised for content issues no one will index.
  → `tests/test_r5_clusters.py::test_noindex_scope_reduction`
- **R5.4 — Quick Wins.** The `quick_win` flag (`impact ≥ 4 AND effort ≤ 1`) is serialized in
  `_issue_dict()`, and the results/summary endpoint exposes a Quick-Wins list independent of priority
  ordering. → `tests/test_quick_wins.py::test_issue_dict_includes_quick_win`,
  `::test_summary_exposes_quick_wins_list`. *(Surfacing Quick Wins as the default landing view is a GUI
  change deferred pending explicit owner sign-off.)*
- **R5.5 — Severity derived at runtime.** `make_issue` derives severity via `severity_from_impact(impact)`
  rather than copying the stored `_IssueSpec.severity` literal, so severity can never drift from impact.
  → `tests/test_r5_severity.py::test_make_issue_severity_is_derived`
- **R5.6 — Scoring-model version stamp.** `CrawlJob` carries `scoring_model_version` (`"2026-07-06-r5"`),
  stamped on every saved audit and exposed in the summary response; audits predating the field read as
  `null`. → `tests/test_scoring_version.py::test_audit_carries_scoring_model_version`,
  `::test_summary_exposes_scoring_model_version`
- **R5.7 — Per-target occurrence counting (external §2, 2026-07-22).** Previously declined; now applied.
  The per-target codes `BROKEN_LINK_404/410/503/5XX`, `EXTERNAL_LINK_TIMEOUT`, `REDIRECT_301/302` were
  emitted once per offending link (many rows per source page, each deducting full impact — the old
  "5 × impact" distortion). `collapse_per_target_occurrences` (`api/crawler/checkers/links.py`) now
  collapses them to **one row per (page, code)** carrying `extra.occurrences` and `extra.occurrence_urls`,
  and **bakes an occurrence multiplier** `min(1 + 0.25·(n−1), 2.0)` into that row's `impact` (1→1.0,
  2→1.25, 5→2.0, 20→2.0). Because the multiplier is baked into the stored impact, every downstream scorer
  (both stores) applies §2 unchanged; the per-category cap still bounds independent problems on top.
  Old audits (per-link rows) keep their prior scores and are distinguished by `scoring_model_version`.
  → `tests/test_per_target_occurrences.py`

**Deploy note.** Site-scoping the TLS codes and the noindex reduction mean multi-page HTTP-site and
noindexed-page scores **rise once** under R5. A before/after crawl (per the R3 precedent) is the manual
deploy gate; monotonicity is preserved (`test_agent_score_monotonic_non_increasing` stays green).

### 4.1 Metadata category

Title, meta description, OG tags, canonical, favicon. Notable codes:
- `TITLE_MISSING` (critical) — page has no `<title>` tag
- `TITLE_TOO_LONG` (warning) — title >60 chars
- `TITLE_DUPLICATE` (warning) — same title on ≥2 pages. Pages that set
  `rel=canonical` to a *different* URL (e.g. paginated archive pages 2/3 that
  canonical → page 1) are excluded from duplicate grouping — they have
  self-declared as a secondary view and are not flagged (nor listed in another
  page's `duplicate_urls`). Same exclusion applies to `META_DESC_DUPLICATE` and
  `TITLE_META_DUPLICATE_PAIR`.
- `META_DESC_MISSING`, `META_DESC_TOO_LONG`
- `OG_TITLE_MISSING`, `OG_DESC_MISSING`, `OG_IMAGE_MISSING`
- `TWITTER_CARD_MISSING`
- `CANONICAL_MISSING` — only fires when (a) page has query string, OR
  (b) page is a near-duplicate, OR (c) canonical points externally
- `TITLE_H1_MISMATCH` — title and H1 differ significantly

### 4.2 Heading category

H1 / hierarchy / banner-suppression handling. Notable codes:
- `H1_MISSING` (critical) — no H1 found on the page
- `H1_MULTIPLE` — more than one H1 (excluding banner-detected ones)
- `HEADING_SKIP` — heading hierarchy skips a level (h2 → h4)
- `HEADING_EMPTY` — heading tag with no text
- `CONVERSATIONAL_H2_MISSING` — no question-shaped H2 headings (AI-readiness)

The banner-suppression logic detects theme-injected banner H1s
via CSS classes and excludes them from `H1_MULTIPLE` calculations.

### 4.3 Broken-link / redirect category

External link checking, redirect chain detection, login redirects.
- `BROKEN_LINK_404` (critical), `_410`, `_5XX`, `_503`
- `REDIRECT_LOOP` (critical), `_CHAIN`, `_301`, `_302`
- `EXTERNAL_LINK_TIMEOUT`, `EXTERNAL_LINK_SKIPPED`
- `LINK_EMPTY_ANCHOR` — `<a>` tag with no link text and no `aria-label`
- `ANCHOR_TEXT_GENERIC` — anchor text is "click here", "read more", etc.

### 4.4 Crawlability category

- `ROBOTS_BLOCKED` (critical) — page blocked by robots.txt but still reachable
- `NOINDEX_META`, `NOINDEX_HEADER` — distinguishes meta-set noindex from header-set
- `THIN_CONTENT` — fewer than 300 words; suppressed for noindex pages
- `ORPHAN_PAGE` — no internal link points to this page. Emitted **only when the
  crawl covered the whole site**: it is an absence-proof, and an inbound link
  living on a page the crawl never fetched is indistinguishable from no link at
  all. A content-type partial scan, a `max_pages` truncation, or a cancellation
  suppresses the check entirely rather than reporting every scoped-out linking
  page's targets as orphans. The reason is recorded on the job as
  `orphan_detection` — `{status, pages_analysed, pages_out_of_scope,
  archives_skipped, pages_links_unread}`, with `status` one of `complete`,
  `skipped_partial_scan`, `skipped_truncated`, `skipped_cancelled`,
  `skipped_single_page`, `skipped_failed`, `not_run`. It is returned in the
  crawl summary and rendered as its own state by the Orphaned Pages panel, the
  Results tile, the PDF caveats section and the Excel summary. A suppressed
  check yields zero orphans, so no surface may read zero as "none found", and
  any unrecognised status must be treated as "did not run". Even a `complete`
  crawl discloses two residual gaps: `archives_skipped` (WordPress archives are
  skipped before their outbound links are read) and `pages_links_unread` (pages
  that timed out, hit a login wall, or failed to parse). Link discovery reads
  every crawled page, not only those passing the HTML filter. The same gate and
  the same coverage record govern `GET /api/fixes/orphaned-media/{job_id}`,
  which is the identical absence-proof over the same page set.
  `orphan_detection` is `None` on audits crawled before this field existed.
- `HIGH_CRAWL_DEPTH` — page is >4 clicks from the homepage

### 4.5 Security and URL structure

- `HTTP_PAGE` — page served over HTTP (not HTTPS)
- `MIXED_CONTENT` — HTTPS page loads HTTP resources
- `MISSING_HSTS` — site doesn't send Strict-Transport-Security
- `UNSAFE_CROSS_ORIGIN_LINK` — `target="_blank"` without rel=noopener
- `WWW_CANONICALIZATION` — both www and non-www resolve without redirecting
- `URL_UPPERCASE`, `URL_HAS_SPACES`, `URL_HAS_UNDERSCORES`, `URL_TOO_LONG`

### 4.6 AI-readiness category (60 codes)

All ai_readiness codes carry a confidence label per the spec:

- **Established** (9 codes) — robots.txt / AI bot directives, plus direct markup validation:
  - `SCHEMA_VISIBLE_MISMATCH` — A value declared in JSON-LD structured data does not appear in the page's visible text. The author/publisher-node guard (`_is_author_publisher_node`, `api/services/schema_typing.py`) excludes structural nodes — including the WordPress SEO-plugin byline `Person` node (`/schema/person/<hash>` `@id`) — so a legitimate author graph-node does not fire the check site-wide (V2 false-positive fix, 2026-07-06). → adversarial + true-positive-preserved tests.
  - `AI_PREVIEW_SUPPRESSED` — X-Robots-Tag suppresses search/AI previews (`nosnippet` or `max-snippet:0`).
  - `AI_PREVIEW_BLOCKED_AT_BOT` — X-Robots-Tag directive specifically blocks an AI crawler (e.g. GPTBot).
  - `AI_CITED_PAGE` — Page has ingested AI citation count > 0 (informational positive signal).
  - Also includes legacy established codes: `AI_BOT_SEARCH_BLOCKED`, `AI_BOT_TRAINING_DISALLOWED`, `AI_BOT_USER_FETCH_BLOCKED`, `AI_BOT_DEPRECATED_DIRECTIVE`, `AI_BOT_BLANKET_DISALLOW`.

- **Reasonable proxy** (21 codes) — schema typing, JSON-LD extraction, date metadata, cloaking detection, plus:
  - `AI_CONTENT_NOT_IN_TEXT` — Key content is carried by images/video or locked inside an embed (iframe/PDF) that AI systems cannot read as text.
  - `CONTENT_DATE_STALE_VISIBLE` — The visible date shown on the page is old enough that the content reads as stale for its page type (cadence aware).
  - `AI_NO_VISUAL_COMPANION` — A substantial text page (article/service/FAQ) has no images or video to support its content (info nudge).
  - `AI_HIGH_VALUE_UNCITED` — Page is structurally healthy but has zero ingested AI citations.

- **Heuristic** (30 codes) — llms.txt, passage-quality, content-thinness micro-checks, plus:
  - `GEO_SUMMARY_BURIED` — Positional answerability auditor: the first substantive content node under an H2 or H3 is pushed down by non-content blocks (images, embeds, wrapper divs).
  - `AI_MAIN_CONTENT_LOW_RATIO` — The main content is less than 40% of the page's visible text (navigation, sidebar, or footer dominate).
  - `CONTENT_STAT_OUTDATED` — The page states an old year (≥24 months old) in a way that reads as current, with no mention of the present year.

**Improvements & Logic Highlights:**
- Schema blocks (`schema_blocks`) accurately flatten `@graph` nesting, with comprehensive handling for malformed JSON and arrays of objects at the root.
- Passage heuristics (e.g. `PARA_TOO_LONG`) explicitly strip structural chrome (`script`, `style`, `nav`, `header`, `footer`, `aside`) before counting to eliminate boilerplate false positives.
- `STATISTICS_COUNT_LOW` and `QUOTATIONS_MISSING` evaluate occurrences over a generous 1500-word window, preventing false penalties on longer articles.
- `LLMS_TXT_INVALID` validity follows the **llmstxt.org spec**, not stricter invented rules: after stripping a leading UTF-8 BOM, a file is `INVALID` only when it has **no Markdown H1 `# Title`** (soft-404 / non-Markdown body). A summary, section links, and link count are all optional — there is **no blockquote requirement, no minimum-URL requirement, and no 20-URL cap** — and no `text/plain` MIME requirement (see §4.6 fetcher note). This clears false flags on standard Yoast-generated files. A missing file is `LLMS_TXT_MISSING`; a soft-404 body still flags. → `docs/thresholds.md`, regenerated `docs/issue-codes.md`.
- **Fetcher body decoding.** `fetch_page` (`api/crawler/fetcher.py`) decodes non-HTML `text/*` bodies into `FetchResult.text` (size-bounded), so `text/plain` files such as `/llms.txt` are validated against real content rather than an empty body (2026-07-06 P2/P3 fix).

### 4.7 Other categories

- **Duplicate** — cross-page title/meta_desc detection
- **Sitemap** — `SITEMAP_MISSING`, `NOT_IN_SITEMAP`
- **Image** — oversized (>200 KB), oversized intrinsic (>2× rendered), missing alt text
- **Performance** — page size limit (default 300 KB), excessive external scripts

### 4.8 Performance & Authority Audit (GSC Integration)

TalkingToad integrates with Google Search Console (GSC) to correlate structural health with real-world search performance. This "reality-check layer" helps prioritise SEO fixes based on impact.

- **GSC Data Ingest:** An OAuth-based service (`GSCClient`) that fetches per-page performance metrics: clicks, impressions, CTR, and average position. Supports exponential backoff and 12-hour caching.
- **Authority Matrix:** Correlation of per-page HealthScore with GSC performance metrics categorises pages into a 2x2 matrix:
  - **Vulnerable Stars:** High performance / Low HealthScore. Top priority for structural remediation.
  - **Hidden Gems:** Low performance / High HealthScore. Structurally sound but potentially mismatched for search intent.
- **Performance Ledger:** A persistent record (`PerformanceRecord`) of per-page metrics over time, including lifecycle dates:
  - `page_created_at`: Discovery date.
  - `last_technical_improvement_at`: Set when a WP fix is applied or page is re-scanned with an improved score.
- **Refresh Triggers:** Automated "Review for Improvements" flags based on:
  - **Staleness:** >180 days since the last technical improvement.
  - **Traffic Decay:** >20% drop in clicks compared to the 3-month average.

**Performance Bundle ingestion (2026-08-06, Phase 1 — PB1/PB2/PB6/PB8).** In
addition to the in-app OAuth `GSCClient`, the same Performance Ledger can be fed
by a **source-agnostic `PerformanceBundle` (v1)** pushed from a sibling reporting
app that already owns GSC/GA4/GTM OAuth — so TalkingToad gains GA4 (sessions,
engagement, **conversions**, AI-referral) and GSC index-state per URL **without
adding any Google OAuth or unparking the multi-tenant identity model** (Option A;
`docs/TODO-MULTITENANT.md`). TalkingToad owns *consumption*; the sibling app owns
*acquisition*. The existing `/api/gsc/ingest` is just one producer of the same ledger.

- **Contract:** one bundle = one site + one `period` (YYYY-MM). Every field except
  `bundle_version`, `site_url`, `generated_at`, `period`, and `pages[].url` is
  optional; **absence means "unknown", never zero** (P2) — GA4 fields on
  `PerformanceRecord` are nullable and never coerced to 0.
- **Endpoint:** `POST /api/performance/ingest?job_id=…` (`api/routers/performance.py`,
  `require_auth`). **PB6 domain guard:** `bundle.site_url` must be the same site as
  the job's `target_url` (`is_same_domain`) or the call returns 403 `DOMAIN_MISMATCH`
  with zero rows written (a scheme/host-less `site_url` is a distinct 400
  `INVALID_SITE_URL`). Returns `{ingested, sources, period, unmatched_urls,
  invalid_urls, stale, deferred}`.
- **One join key (P11):** a matched row is stored under the **crawled page's** URL —
  the same key the page-priority consumer reads by — so a bundle/crawl difference of
  only a trailing slash / `www` / scheme still lands on the right row (storage, diff,
  and lookup share one key). Bundle URLs matching no crawled page are **held out** in
  `unmatched_urls`, not persisted under an orphan key; unparseable URLs go to
  `invalid_urls` without aborting the ingest (P2).
- **Merge (P8):** a bundle is authoritative only for the fields it carries — the
  router read-merges and the store COALESCE-merges so a GA4-only bundle never zeroes
  prior GSC and a GSC-only producer never wipes GA4. Re-ingest updates, never
  duplicates. A row that carries fields forward from an older bundle is stamped with
  the **oldest** contributing source's date, so freshness is never over-reported.
- **`deferred`** (query-level / site-level payloads accepted but persisted in a later
  phase) is surfaced, not dropped (P2).
- **Freshness (PB8):** `source_generated_at` is stored; `is_stale()`
  (`performance_freshness.py`, default 35-day window) drives a staleness signal so
  bundle-derived numbers are never shown as current when old.
- **Not yet (Phase 2/3):** striking-distance→rewriter (PB3), coverage/cross-signal
  diff (PB7), conversion-weighted priority (PB4), index reconciliation (PB5), GTM-audit
  surface (PB9). Spec: `docs/pending/2026-08-06_performance-bundle-ingestion.md`.

### 4.9 Agent-readiness checks (Phase 1)

A coherent set of checks describing how findable, parseable, and operable a
site is to AI crawlers (citation agents) and basic task-executing agents.
Phase 1 reuses shipped codes where they already cover the intent and adds
task-side codes for the gaps.

**New categories:** `rendering`, `semantic_html` (joining `ai_readiness`).

| Code | Category | Scope | Fires when |
|---|---|---|---|
| `JS_DEPENDENT_NAVIGATION` | rendering | per page | A navigation region exists but contains no usable links in the raw HTML (menu built client-side). In-page `#section` anchors count as links and do not fire. |
| `NON_SEMANTIC_BUTTON` | semantic_html | per page | A `<div>`/`<span>` is used as a clickable control (inline `onclick`, or button class + `tabindex`) without an interactive ARIA role. |
| `INTERACTIVE_NO_ACCESSIBLE_NAME` | semantic_html | per page | A `<button>` or text-style form field has no accessible name (text, `aria-label`, `title`, `<label>`, or placeholder). |
| `LANDMARK_MAIN_MISSING` | semantic_html | per page | No `<main>` / `role="main"` landmark. |
| `LANDMARK_NAV_MISSING` | semantic_html | homepage | No `<nav>` / `role="navigation"` landmark. |
| `PLACEHOLDER_LINK` | broken_link | per page | A navigational CTA's href is `#` / `javascript:void(0)`. JS toggles (accordions/tabs) and in-page anchors are excluded. |
| `WRONG_PLACEHOLDER_LINK` | broken_link | per page | A link points at a placeholder domain (example.com, localhost, a bare search-engine homepage). |
| `SCHEMA_ORG_MISSING` | ai_readiness | homepage | Homepage has no Organization/LocalBusiness JSON-LD. Confidence: Reasonable proxy. |
| `CONTACT_INFO_NOT_IN_HTML` | ai_readiness | homepage | Homepage exposes no machine-readable contact info (mailto/tel link, email, or phone in text). Confidence: Heuristic. |

**Reused (not duplicated):** AI-crawler access is the shipped `AI_BOT_*`
family (`check_ai_bot_access`, job-level — GPTBot/ClaudeBot/PerplexityBot/
Google-Extended, blanket-disallow, Allow overrides, 5xx/404). JS-content
absence is `RAW_HTML_JS_DEPENDENT`; FAQ-schema gap is `FAQ_SCHEMA_MISSING`;
content date is `DATE_PUBLISHED_MISSING`.

**FAQ detection (accordion-aware + AI-visibility, 2026-07-04).** FAQ questions
are extracted at parse time by `_extract_faq_blocks` (`parser.py` → `page.faq_blocks`)
from native `<details>/<summary>`, Elementor nested accordions
(`.e-n-accordion-item-title-text`), legacy toggle/tab widgets, and `<h?>` headings —
any title ending in `?`, deduped by normalized text (Elementor emits mobile+desktop
copies). This fixed a silent false-negative where `FAQ_SCHEMA_MISSING` only counted
`<h?>` questions and missed accordion FAQs with no literal "FAQ" heading; its `extra`
now reports an accurate `question_count` + per-container `sources` (was a misleading
`question_headings: 0`). Because the crawler reads raw HTML with no JS — exactly what a
non-rendering AI crawler sees — a new check **`FAQ_ANSWERS_NOT_IN_HTML`** (ai_readiness,
impact 4) fires when FAQ question titles are present but ≥ 2 (and ≥ 50%) of their answer
bodies are absent from source (< 40 chars), i.e. JS-injected on click and invisible to
AI. It is cluster-suppressed under `RAW_HTML_JS_DEPENDENT` when the whole page is a JS
shell (same root cause). Per the never-fabricate rule, it only reports absence.

#### Agent Health score

A second headline number alongside the SEO Health Score, surfaced in the
Results summary (`SummaryPanel`), the PDF report, and the Excel export. It
reuses the v1.5 Health-Score model — Page = `max(0, 100 − Σ impact)`, Site =
mean of page scores — but restricts the impact sum to **agent-relevant**
issues: categories `ai_readiness` / `rendering` / `semantic_html` plus the
two placeholder-link codes. Serialised as `summary.agent_health_score` (int
0–100) and `summary.agent_readiness.breakdown[]` (per-category counts and
impact). More failing agent checks never raise the score (monotonic
non-increasing).

### 4.10 Citation source parsing (R6, engine step 7b)

Real citations are extracted from each parsed page by `build_page_citations`
(`issue_checker.py`): an external body link to a non-social source, with the
anchor text captured as context (a bare-URL link becomes an orphan citation)
and the attribution style (`footnote` / `inline` / `mixed` / `none`) inferred
from the visible text. Post-crawl, `check_source_accessibility`
(`api/services/citation_model.py`, capped at 30 URLs) probes the cited source
URLs, and `citation_source_issues` emits **`CITATIONS_SOURCES_INACCESSIBLE`**
for pages whose cited sources cannot be reached. Per the never-fabricate rule
only real, parsed citations are considered. → `tests/test_r6_citations.py`

### 4.11 JS-render / cloaking checks (R7, engine step 7c, Playwright-gated)

`js_render_issues` (`issue_checker.py`) maps a `JSRenderResult` from the
optional Playwright renderer to issues, gated on `HAS_PLAYWRIGHT`: the step is
silently skipped when Playwright is absent and emits nothing on a render error
(a failed render is never reported as a finding). It can fire
**`JS_RENDERED_CONTENT_DIFFERS`** (significant content only appears after JS
runs), **`CONTENT_CLOAKING_DETECTED`** (rendered topic diverges from raw HTML),
and **`UA_CONTENT_DIFFERS`** (content served to AI-crawler user agents differs
from the rendered page). → `tests/test_r7_js_render.py`

### 4.12 GEO-LLM checks (R8, `POST /api/ai/geo-llm-checks`)

Opt-in, LLM-driven GEO checks for a single page (one LLM call). The endpoint
re-fetches and parses the page for its body text (the store does not persist
it), then `classify_geo_llm`/`parse_geo_verdict` (`api/services/geo_llm.py`)
classify it. `geo_llm_issues` maps the verdict to three codes —
**`CENTRAL_CLAIM_BURIED`**, **`CHUNKS_NOT_SELF_CONTAINED`**, and
**`PROMOTIONAL_CONTENT_INTERRUPTS`**. A failed or refused LLM response yields an
empty verdict, never a spurious finding (P14); pages under 200 words are
short-circuited with a `note`. Request `{page_url, job_id?}` → `{verdict,
issues: [{code, severity, priority_rank}]}`. → `tests/test_r8_geo_llm.py`

### 4.9 Scan content-type scoping (partial scan)

Lets the user restrict a crawl to a chosen subset of content types instead of
the whole site. Flow: enter a URL → choose **Full** (the existing whole-site
crawl, unchanged) or **Partial** → the app reads the site to discover its
content types → the user ticks one or more (Pages, Posts, Custom Post Types,
and/or Posts-by-category) → the crawl runs scoped to exactly that selection.

**Why an authoritative allowlist, not a URL guess.** A URL string cannot
distinguish a Page from a Post — WordPress permalinks are configurable, so
`/about/` (Page) and `/our-recap/` (Post) are structurally identical. Scope is
therefore an explicit URL set built from an authoritative source, never a
pattern match applied mid-crawl. `tests/test_crawl_scope.py::test_pages_only_excludes_lookalike_post`
is the adversarial guard: a Post whose permalink mimics a Page is excluded under
a Pages-only scope (P7).

**Discovery — `POST /api/crawl/discover-scope`** (`api/crawler/content_discovery.py`).
Read-only, no credentials, degrades across tiers and returns
`{is_wordpress, discovery_tier, types[], categories[], category_scope_supported, retryable, notes}`:
- **`rest`** — `/wp-json/` responds → enumerate public content types via
  `/wp/v2/types` (built-in non-content types excluded, all public CPTs kept) and
  categories via `/wp/v2/categories`; per-type counts from `X-WP-Total`.
  Category-by-post scoping supported here.
- **`sitemap`** — no REST but a typed `<sitemapindex>` exists → classify by child
  sitemap filename (`page-sitemap.xml`, `wp-sitemap-posts-post-1.xml`, etc. —
  Yoast/Rank Math and WP-core conventions). Pages/Posts/CPT scoping works;
  `category_scope_supported=false` (category sitemaps list archives, not member
  posts).
- **`none`** — the site was **reached** and definitively exposes neither REST nor
  a typed sitemap → only a full crawl is offered, with a note explaining why.
  `retryable=false`.
- **`unreachable`** (CLN0/SD, 2026-08-07) — the probes could **not reach** the
  site (network error, timeout, or 5xx after retries), so REST/typed-sitemap
  absence is *unproven*. Returns `retryable=true` with a "usually temporary — try
  again" note instead of the definitive dead-end; the frontend renders a **Try
  again** affordance rather than stripping the scoping option. A transient failure
  on *either* the REST probe (`_probe_wp_rest` → `"rest"`/`"absent"`/`"unreachable"`)
  or the sitemap tier (`SitemapResult.reachable`) yields this outcome — absence is
  only "none" when REST was definitively absent **and** the sitemap tier reached
  the site (P1/P2). All positive/definitive payloads carry `retryable=false`.

**Resolution + enforcement.** `POST /api/crawl/start` accepts
`settings.content_scope = {mode, type_keys[], category_ids[]}`. When
`mode="types"`, the server resolves the selection to a normalised, same-domain
URL allowlist (`resolve_scope_urls`) — REST collections per type / per category,
or classified sitemap URLs in the sitemap tier. An empty selection returns 422
`INVALID_SCOPE`; a selection that resolves to nothing returns 422 `SCOPE_EMPTY`
(never a silent full crawl — P2/P6). The engine
(`api/crawler/engine.py`) visits only allowlisted URLs plus the start URL
(always crawled so the homepage/summary resolves), filtering at both the
sitemap-seed and link-follow sites; distinct out-of-scope URLs are counted
(`CrawlResult.scope_skipped`) rather than dropped silently. `mode="full"` (the
default) reproduces the prior whole-site crawl byte-for-byte
(`tests/test_crawl_scope.py::test_full_mode_crawls_everything`).

**Security & robustness.** Discovery/resolution use an SSRF-guarded httpx client
(`make_ssrf_guarded_client`) that re-checks every request and redirect hop —
extending `fetch_page`'s per-hop SSRF guarantee to these auxiliary fetches
(P5). `_get_json` retries transient failures (network/5xx) with backoff, and
paginated collection reads use `X-WP-TotalPages` so a mid-pagination failure is
surfaced as a truncation note (returned as `scope_notes` on `/start`), never
mistaken for the end of the collection (P1/P9). The resolved allowlist is
computed server-side and never trusted from the client.
→ `tests/test_content_discovery.py`, `tests/test_crawl_scope.py`,
`tests/test_discover_scope_integration.py`,
`frontend/src/pages/__tests__/Home.scope.test.jsx`

### 4.10 "Search Everywhere" GEO — brand-entity + body-uniqueness (P1)

First phase of the GEO/AI-citability initiative (`PLAN-SEARCH-EVERYWHERE.md`,
derived from the "Search Everywhere Optimization" review). Five cross-page
`ai_readiness` codes, all detected post-crawl in
`api/crawler/checkers/cross_page.py` — crawl-only, no new external calls, no WP
calls. ⚠︎ Scores are provisional pending the R3→R5 refactor (`R5-REWORK`).

**Brand-entity consistency** (the technical underpinning of "be recognised by
name" — so AI reliably attributes content to one entity):
- `ENTITY_NAME_INCONSISTENT` (site) — the Organization name in JSON-LD differs
  across pages *after* casing + legal-suffix normalisation. Normalisation is the
  false-positive guard: "Living Systems Counselling Society" and "Living Systems
  Counselling" are one entity, not flagged. Emits one site-scoped issue listing
  the variants.
- `ENTITY_SAMEAS_MISSING` (page) — an Organization/Person block has no `sameAs`
  links to authoritative profiles (Wikipedia/Wikidata/socials). Does not fire on
  pages with no entity block.
- `AUTHOR_IDENTITY_INCONSISTENT` (site) — one author name under differing URLs
  (or vice-versa) across article schema. Heuristic tier (two real people can
  share a name).

**Body uniqueness** (find the thin, generic pages most exposed to AI
absorption). One shared pass shingles each page's lead content
(`first_1500_words`, 5-word n-grams), then computes a **site-wide boilerplate
set** = shingles appearing on ≥ max(3, 20% of eligible) pages:
- `NEAR_DUPLICATE_BODY` (site) — pages whose content-shingle Jaccard ≥ 0.80
  *after boilerplate removal* (nav/footer stripped — the false-positive guard).
  Clustered via union-find; one issue per cluster naming the members. Exact
  all-pairs Jaccard ≤ 400 eligible pages; MinHash prefilter above (announced in
  logs, P9).
- `BOILERPLATE_RATIO_HIGH` (page) — ≥ 60% of a page's shingles are the shared
  template — mostly boilerplate, low citability.

All thresholds are config (env-overridable, `docs/thresholds.md`); old crawls
missing `schema_blocks`/`first_1500_words` degrade to no findings, never a crash
(P8); site-scoped checks skip sites under 3 pages. Adversarial guards written
first (P10): `test_entity_consistency.py::test_e1_2_normalised_no_false_positive`,
`test_near_duplicate_body.py::test_e2_2_boilerplate_excluded`.
→ `tests/test_entity_consistency.py`, `tests/test_near_duplicate_body.py`,
`tests/test_p1_serialization.py`

**P2 — schema completeness + author E-E-A-T** (`api/crawler/checkers/ai_readiness.py`).
All three are **page-type-gated on the relevant schema `@type` being present** —
they flag *incomplete* markup, never *absent* markup, so pages without the schema
stay silent (P7, no false positives at scale):
- `HOWTO_SCHEMA_INCOMPLETE` (page) — a `HowTo` block with no `step` list.
- `PRODUCT_REVIEW_SCHEMA_MISSING` (page) — a `Product` block with neither
  `review` nor `aggregateRating`.
- `AUTHOR_CREDENTIALS_MISSING` (page) — an article's author `Person` schema is
  bare (name only, no jobTitle/description/sameAs/url). A plain text byline with
  no author schema does **not** fire (that is `AUTHOR_BYLINE_MISSING`'s remit and
  would otherwise flood every blog post). `@graph` is descended.
→ `tests/test_schema_completeness_eeat.py`

**P3 — citability grade** (`api/services/job_store_base.py::compute_citability_grade`).
A per-page 0–100 GEO/AI-citability lens: cluster suppression applied first (so
co-firing signals aren't double-counted), then `100 − Σ(impact of charged
ai_readiness rows)`. Unlike overall page health it does **not** apply the
per-category cap (ai_readiness *is* the whole score here). A pure rollup of
already-emitted signals — no new detection. Returned as `citability_grade` per
page on both `GET /api/crawl/{job_id}/page-priority` and
`GET /api/crawl/{job_id}/pages`, and surfaced in the UI (owner-approved) as a
colour-graded badge (`CitabilityBadge`, green ≥ 70 / amber ≥ 40 / red) — a column
on the Page Priority work queue (`PagePriorityPanel`) and on the By-Page view
(`ByPagePanel`). → `tests/test_citability_grade.py`,
`tests/test_api.py::TestGetPages::test_pages_includes_citability_grade`,
`frontend/.../PagePriorityPanel.test.jsx`, `frontend/.../ByPagePanel.test.jsx`

---

### 4.13 Analytics & Measurement category (2026-08-06)

A crawl-time category answering *"is your measurement working, and is your traffic
attributable?"* — decided entirely from page HTML, with **no GSC/GA4/GTM API,
OAuth, or per-site credentials** (distinct from §4.8, which consumes the GSC API).
Tag signatures/vocabulary live in `api/crawler/analytics_patterns.py` (config, not
code); per-page checks in `api/crawler/checkers/analytics.py`, the site-level check
in `checkers/cross_page.py`. Surfaced via a dedicated "Analytics & Measurement"
analysis toggle (default on). Detection is **markup-only** — a pass means the tag is
present on the page, not that it fires.

| Code | Scope | Sev | Fires when |
|---|---|---|---|
| `ANALYTICS_TAG_MISSING` | per page | warning | No current measurement tag on the page — GA4 (`G-…`), the unified **Google tag** (`GT-…`, 2026-08-08), or GTM (`GTM-…`). A Google Ads-only (`AW-…`/`DC-…`) page still counts as untagged (`require_id` gate). |
| `ANALYTICS_TAG_DUPLICATE` | per page | warning | GA4 configured in two+ separate `<script>` blocks, or a direct GA4 tag co-existing with a GTM container (double-count risk). Ads/Floodlight gtag calls are excluded (no `G-` id). |
| `ANALYTICS_ID_INCONSISTENT` | site | info | GA4/GTM measurement IDs differ across pages, or the tag is present on some pages and absent on others. Attributed to the first offending page. |
| `CONSENT_MODE_MISSING` | per page | info | A tag is present but no Google Consent Mode v2 signal (`gtag('consent',…)`) is detected. Suppressed when `ANALYTICS_TAG_MISSING` fires. Advisory (EU/UK). |
| `SELF_REFERENCING_UTM` | per page | info | An internal link carries `utm_*` (blank/upper-case included) or a click-id (`gclid`, `fbclid`, …), restarting the GA4 session source. External links excluded. |
| `OUTBOUND_LINK_UNTRACKABLE` | per page | info | An external image/icon link has no text, `aria-label`, `title`, or image `alt` — GA4's outbound-click event records an empty `link_text`. |
| `CTA_TRACKING_MISSING` | per page | info | The page **uses a click-tracking marker convention** (≥1 CTA carries a `track-`/`track_` (or `data-track*`/inline `gtag(`) marker — detected on the button **or an ancestor wrapper**, since page builders put the class on the widget and listeners use `closest()`), but a **conversion CTA** (button text matching donate/book/contact/register/counselling/intake/consultation/…) is **missing** it. Fires only with a measurement tag present; silent when no convention is detected (GTM-only sites — GTM click triggers aren't visible in HTML) or when every conversion CTA is tracked. Markup-only, advisory. (MI7, 2026-08-09) |

Scoring is derived through the R5/R3 calibration model (`_CALIBRATION` →
`_IMPACT_MATRIX`): tag-missing/duplicate → impact 4 (warning, quick wins), the rest
→ impact 1–2 (info). → `tests/test_analytics_checks.py`, `tests/test_parser_analytics.py`.

**Recognised measurement tags** (`api/crawler/analytics_patterns.py`, editorial
config): GA4 `G-…`, the unified Google tag `GT-…` (`google_tag` — Google's newer
default; added 2026-08-08 after a false `ANALYTICS_TAG_MISSING` on a `GT-`-tagged
site), GTM `GTM-…`, and legacy UA `UA-…` (recorded but never satisfies MI1). GA4
and the Google tag are the *direct* measurement tags for the MI2 duplicate check;
Google Ads `AW-…`/Floodlight `DC-…` gtag calls are excluded via the `require_id`
gate. Detection is markup-only — a JS-injected tag absent from the raw HTML is not
seen (by design).

Micro-spec: `docs/pending/2026-08-06_measurement-integrity-checks.md` (folded in on
completion, 2026-08-06).

### 4.14 Technical-debt cleanup batch (2026-08-08, CLN0–CLN8)

A batch of correctness/robustness cleanups (micro-spec
`docs/pending/2026-08-08_debt-cleanup-batch.md`, folded in on completion). The
user-facing behaviour change is CLN0 (scope-discovery retryable outcome, §4.9).
The rest are internal but affect documented invariants:

- **CLN2 — single source of truth for the category list.** The category set +
  labels + order live once in `registry.CATEGORY_DISPLAY`, projected to
  `frontend/src/data/categories.generated.json` (imported by Results.jsx /
  SummaryPanel.jsx via `scripts/generate_categories_json.py`) and read directly by
  the PDF report. A parity test requires `CATEGORY_DISPLAY`'s key set to equal the
  `_CATALOGUE` category set (no missing, no dead) — replacing the former
  hand-mirrored lists that had silently dropped categories from surfaces.
- **CLN3 — analysis-toggle completeness.** Every issue category is reachable via
  some `_ANALYSIS_CATEGORY_MAP` group or the always-emitted `security`; a partial
  `enabled_analyses` can no longer silently exclude `image`/`rendering`/
  `semantic_html` (enforced by `tests/test_engine_analysis_map.py`).
- **CLN4 — one performance-ledger join key.** `api/services/perf_join.py:match_key`
  (www/scheme/trailing-slash tolerant) is used by BOTH `/api/gsc/ingest` and the
  Performance Bundle ingest, and GSC rows are stored under the crawled-page key
  (what the page-priority consumer reads) with `source_generated_at` stamped —
  fixing GSC rows that previously landed under an orphan key.
- Also: CLN1 (dropped the dead `duplicate` category tile), CLN5 (per-page
  citability/health honour user-suppressed codes), CLN6 (`TITLE_H1_MISMATCH` is
  genuinely WP-fixable), CLN7 (`/pages` scopes its citability issue-load to the
  shown URLs), CLN8 (internal broken-page `occurrence_urls` populated).

### 4.15 Crawl-fidelity fixes and new checks (E1–E2, E5–E6, 2026-08-29)

Folded from the E-series micro-specs, written after comparing a TalkingToad
report for livingsystems.ca against an independent Semrush + GSC + GA4 +
WordPress audit of the same site. Both agreed on the nine internal 4xx targets,
the multiple-H1 count and the duplicate-description count; the items below are
where TalkingToad was wrong or silent.

**E1 — lazy-loaded image extraction.** `_extract_image_data`,
`_extract_image_urls` and `_find_img_missing_alt_srcs` required a literal `src`
and skipped `data:` placeholders, so on any lazy-loading site (Smush, Elementor,
WP Rocket) the parser saw **no images at all**: 9 of 9 on one live page, 11 of 11
on the homepage, 13 images stored across a 272-page crawl behind a "97% Image
Health" score. All three now resolve through `_resolve_img_src`
(`src` → `data-src` / `data-lazy-src` / `data-original` / `data-lazy` /
`data-echo` → `srcset` / `data-srcset`). The empty URL list no longer silences a
non-zero `img_missing_alt_count` (P2/P13) — the homepage has 10 of 11 images
without alt text and TalkingToad reported `IMG_ALT_MISSING` on 1 page of 272.
The per-job image cap is `TT_IMAGE_URL_CAP_PER_JOB` and its effect is disclosed
via `images_seen_total` / `images_collected` on the job.
→ `tests/test_parser_lazy_images.py`, `tests/test_image_cap_disclosure.py`,
real fixtures in `tests/fixtures/lazy_images/`.

**IM1 — pixel dimensions are measured, not inferred.** The scan was HEAD-only,
so no image had a width, a height or a content hash, and four checks —
`IMG_OVERSCALED`, `IMG_NO_SRCSET`, `IMG_DUPLICATE_CONTENT`, `IMG_SLOW_LOAD` —
had no data and did not fire in 156 jobs, while every image stored a technical
score of 0. A dimension pass now downloads images after the HEAD pass and reads
width/height/format with Pillow plus an MD5 content hash. Any failure measures
**nothing** rather than guessing: an unmeasured image is *not checked*, never
*clean* (P31), and `images_measured` / `images_measurable` carry the shortfall
the way `images_collected` / `images_seen_total` carry the image cap.

The pass is bounded by a **total byte budget** (`TT_IMAGE_DIMENSION_TOTAL_BYTES`,
48 MB) with a per-image skip (`TT_IMAGE_DIMENSION_MAX_BYTES`, 12 MB), a count
cap (250) and time budgets (45 s overall, 8 s per image) — **not** by a minimum
image size. A 100 KB floor was the first design and was wrong: the only two
overscaled images on the reference site are 30 KB and 9 KB, so the floor skipped
both and left `IMG_OVERSCALED` dead on exactly the cases it exists to catch
(P9). Overscaling is a ratio of intrinsic to display width and has no lower
bound in bytes. On the reference site the pass measures 32 of 34 images for
1.7 MB and `IMG_OVERSCALED` and `IMG_NO_SRCSET` now fire on the two images an
independent probe identified.
→ `tests/test_image_dimensions.py`, § IM1 above.

**V1 — every scored code declares what it rests on.** TalkingToad scores 170
codes and stated all of them in one voice, so a user could not tell a finding
backed by a W3C success criterion from one resting on a number we chose. Worse,
several checks cite a real source for the *subject* while firing on a
*threshold* that source does not publish: Google documents the title link and
publishes no length limit, so our 60 characters read as Google's rule.

`api/crawler/checkers/data/authority.yaml` now records, for each of the 170
codes, one of three bases:

| Basis | Meaning | Required fields | Count |
|---|---|---|---|
| `citation` | a published source states the claim | source, source_type, url, claim | 107 |
| `heuristic` | no source states it; this is our judgement | rationale saying what we believe and what it is not | 57 |
| `observation` | a fact measured during this crawl, not a claim about the world | method, saying what was measured and what it does not establish | 6 |

`threshold_note` is required on any citation whose check fires on a number the
cited source does not publish, and `docs/issue-codes.md` renders it under
**What the source does not say**. `source_type` is vendor / standard /
research / industry, which keeps a research finding from being read as vendor
confirmation — the one published GEO study backs several signals no engine
operator has confirmed, and those stay `Heuristic`.

Every cited URL was fetched, not asserted: `scripts/verify_authority_urls.py`
records the status of all 56 in `data/url_verification.yaml`, and a test fails
on any citation not recorded as 200. Three URLs in the first draft were
plausible and did not exist.

The record reconciles with the AI-readiness confidence label in both
directions: a code labelled `Established` must carry a vendor or standards
citation, and one labelled `Heuristic` may not cite a vendor without a
threshold_note. That check found `ENTITY_HOURS_DEFAULT` labelled `Established`
for an inference nobody has confirmed; relabelling it `Heuristic` dropped its
impact 6 → 2 and its severity warning → info, because `derive_impact` reads the
confidence tier. A finding we cannot support now costs a site less.
→ `tests/test_authority.py`, `api/crawler/checkers/authority.py`.

**V1.1 — the confidence label is derived, not duplicated.** The label existed in
three places: an `_IssueSpec.confidence_label` override field, the
`_AI_READINESS_CONFIDENCE` dict, and `_CALIBRATION[code][0]`, which is what
`derive_impact` actually scores from. `make_issue` read `spec.confidence_label
or dict`, so the override won silently and had drifted on two codes — the API
and `docs/issue-codes.md` published different labels for the same finding. The
override field and all seven of its uses are gone, and
`_AI_READINESS_CONFIDENCE` is now derived from `_CALIBRATION` rather than
maintained beside it, so the two cannot disagree.
→ `tests/test_confidence_single_source.py`.

**E1 — an error page is not content, on every path that can reach it.** A scoped
scan reported an unpublished post's URL as a regular page carrying
`NOINDEX_META`, `UNSAFE_CROSS_ORIGIN_LINK` and `CONSENT_MODE_MISSING`. The URL
returns 404, and every finding described WordPress's **404 template** — the
"unsafe cross-origin links" were the site footer's social icons, and the
`noindex` was the 404 template's own, which is correct for a 404. All of them
charged the health score for a page that does not exist.

`run_crawl` had always guarded this. `_fetch_and_check_page` — the rescan and
single-page path behind `scan_single_page` and the per-page rescan button —
guarded only `status_code == 0` (a network failure) and then ran `check_page`
unconditionally, so the same URL was audited or not depending on which button
reached it. It now returns the `BROKEN_LINK_*` finding alone for any response
`>= 400`, matching the crawl. The repo already pinned the two paths to agree on
*broken links*; nothing had pinned them to agree on *the page itself*.
→ `tests/test_error_pages_not_audited.py`.

**D1 — scanning a draft on purpose.** An unpublished page returns 404 to anyone
not signed in, so auditing one before publication needs an authenticated fetch:
`POST /api/crawl/scan-page?url=…&authenticated=true`. It reuses the existing
`WPClient` cookie login and copies the session cookies onto an SSRF-guarded
client, so the fetch keeps start-and-every-hop protection.
`_validate_wp_domain_for_url` is mandatory — the credentials belong to one site
and must never be sent to another.

Single page only, and deliberately not available for a whole-site crawl: the
architecture test forbids WP API calls during a scan, and a site-wide
authenticated crawl would audit content no search engine can see, silently
changing what the health score means.

The response says what the scan was — `authenticated_scan: true`,
`visibility: "not-public"`, and a caveat that the findings are pre-publication
advice rather than a measurement of live SEO. `ORPHAN_PAGE`, `NOT_IN_SITEMAP`
and `NOINDEX_META` are suppressed and listed as suppressed: a draft has no
inbound links, is not in the sitemap, and WordPress marks preview output
noindex, so reporting them would be noise the owner must learn to ignore.
→ `tests/test_draft_scanning.py`.

**D2 — a single-page scan declares the checks it could not run.**
`_fetch_and_check_page`, behind `POST /api/crawl/scan-page` and the per-page
rescan, never calls `check_cross_page` and passes `sitemap_urls=None` to
`check_page`. **Fourteen codes are therefore unreachable on that path**, and a
scan returning few or no findings was indistinguishable from a page that had
passed them. Only one of the fourteen — `ORPHAN_PAGE` — was disclosed, by the
2026-08-29 `orphan_detection: skipped_single_page` record; the other thirteen
sat behind the same uncalled function and said nothing.

`/scan-page` and the rescan response now carry `checks_not_run` (sorted) and
`checks_not_run_reason`. The list is **derived** from the registry's
`needs_full_crawl` flag on `_IssueSpec` — never mirrored in the router, which
would recreate the hand-mirrored enumeration the disclosure exists to prevent.

`needs_full_crawl` means *this code can only be produced by a full crawl*, which
is deliberately not the same claim as "the check needs several pages": some
entity checks read a single page and are listed only because of where they are
wired. It is also distinct from `scope`, which governs how a finding is charged
once found rather than whether it can be found.

Membership is computed as cross-page emitters **minus any code another checker
on the single-page path can also raise**, plus `NOT_IN_SITEMAP`. That subtraction
is load-bearing: `CANONICAL_MISSING` is emitted by both `cross_page.py` and
`metadata.py`, and `metadata.py` does run on this path, so declaring it un-run
would send the operator to run a full crawl for a check already performed. A
false disclosure is worse than a missing one.

`checks_not_run` and the draft scan's `suppressed_codes` stay separate: *not run
because of the code path* and *suppressed because pre-publication* are different
claims, and merging them would let one justify the other.

**Not yet rendered.** No frontend surface reads `checks_not_run`; the field is in
the API contract only. Recorded here rather than described as integrated —
shipping a disclosure nothing displays is the unwired-disclosure failure of
2026-08-30.
→ `tests/test_single_page_scan_discloses_inert_checks.py`.

**D3 — the app must import on the Python and dependency set it ships on.** The
suite passed on the dev interpreter (3.14) while `api.main` could not import at
all on the pinned one (`Dockerfile`: `python:3.11-slim`), for two independent
reasons.

`api/routers/advisor.py` annotated `store: SQLiteJobStore` without importing the
name. Annotations evaluate at def-time before Python 3.14; PEP 649 made them
lazy in 3.14, so the dev box sees nothing and 3.11 raises `NameError` at import.
Same class as the 2026-08-13 production bug, whose fix added
`test_checker_modules_import_before_any_def` — scoped to *checker* modules, so
routers were never covered.

`api/services/gsc_client.py` imported `google-*` at module level while those
packages are in neither `requirements.txt` nor the `Dockerfile`, so an optional
feature's missing library stopped the whole application from starting. **GSC is
opt-in and local-only** (owner's decision, 2026-08-31): the libraries are
deliberately not shipped. `gsc_client` now imports them lazily and
`_require_gsc_configured()` returns the same 503 for an absent library as for an
absent setting, making the module's stated promise — *"TalkingToad behaves
exactly as before"* — true for both. `pydantic` is now declared explicitly
rather than relied on transitively through FastAPI.

Guarded by `tests/test_shipping_runtime_imports.py`, which is **static AST, not
an import sweep**: a sweep passes on 3.14 and is blind to the entire annotation
class, so it would have certified this app healthy on the morning it could not
boot. All 124 modules now import under 3.11 with pinned requirements.

**Still open (not this item):** 28 tests fail under the pinned dependency set.
`requirements.txt` pins `fastapi~=0.115.0` while development runs 0.136; under
0.115, `from __future__ import annotations` makes `background_tasks:
BackgroundTasks` an unresolvable string, so FastAPI treats it as a required
query parameter and `POST /api/crawl/start` returns 422. Fourteen of eighteen
pins are violated by the dev venv. Tracked for the CI cycle.
→ `tests/test_shipping_runtime_imports.py`.

**E2 — broken-link source attribution.** `external_targets_seen` and
`discovered_from.setdefault` retained only the first page linking to each broken
target, so 120 broken internal links reported as 10. `external_target_sources`
and `discovered_from_all` now retain every source while the target is still
fetched once; `discovered_from` keeps its depth/parent semantics untouched (P12).
Issues carry `occurrences`, `occurrence_urls` and the uncapped
`occurrence_urls_total`, capped by `TT_BROKEN_LINK_SOURCE_CAP` and disclosed on
every surface. `collapse_per_target_occurrences` sums members' own occurrence
counts rather than resetting to `len(group)`. `CrawlResult.broken_link_sources`
is now `list[BrokenLinkRef]`: `link_type` is derived (a same-host 404 was always
stored "external") and `status_code` is persisted, so a transient 503 stays
distinguishable from a permanent 404 (P1). A P22 guard test forbids the legacy
3-tuple unpack. → `tests/test_broken_link_attribution.py`.

**E5 — entity value checks.** `SCHEMA_ORG_MISSING` only asked whether the node
exists. Four site-scoped codes now ask whether what it says is true:
`ENTITY_HOURS_DEFAULT`, `ENTITY_NAP_INCOMPLETE`, `ENTITY_FIELD_EMPTY`,
`ENTITY_VALUE_PLACEHOLDER`. Verified against the live homepage, which a
third-party tool rated "100% markup health": `description: "site logo"`,
`telephone: []`, seven-day 09:00–17:00 default hours, and a node typed `Place`
with no address. Placeholder vocabularies and default-value patterns live in
`api/config/entity_values.json`. `_self_entity_nodes` restricts NAP checking to
nodes whose `url` shares the page host, so a partners or funders page is not
flagged for third-party gaps (P7). All four are `developer_needed` — they are
SEO-plugin settings, and the WordPress-safety constraint forbids writing them.
→ `tests/test_entity_values.py`.

**E6 — stacked overlay links.** `LINK_EMPTY_ANCHOR` correctly excludes any anchor
with an accessible name from any source, so it cannot see a card emitting an
overlay link, a title link and an image link to one destination. The new
`LINK_STACKED_DUPLICATE` (category `metadata`) groups 2+ anchors resolving to the
same href inside one card container; card-class patterns live in
`api/config/link_patterns.json`. The container requirement is load-bearing: a
header logo link plus a "Home" link point at `/` on nearly every site.
`LINK_STACKED_DUPLICATE` cluster-suppresses `LINK_EMPTY_ANCHOR` so one template
defect is charged once. `docs/issue-codes.md` records that TalkingToad measures
accessible **name**, not visible text — a third-party tool reporting a much
higher "links without anchor text" count is measuring something else.
→ `tests/test_stacked_links.py`.

### 4.16 Issue evidence — WHICH element is wrong (EV, 2026-08-29)

Owner-reported: *"you report issues like 'Unsafe External Link' but you don't
provide the link, so it's not easy to find and fix."* Two independent faults.

**Three checks counted without capturing.** `UNSAFE_CROSS_ORIGIN_LINK`,
`MIXED_CONTENT` and `INTERNAL_NOFOLLOW` stored only a count, while their siblings
`IMG_ALT_MISSING` and `LINK_EMPTY_ANCHOR` had always returned an evidence list
(P5). `_find_unsafe_cross_origin`, `_find_mixed_content` and
`_find_internal_nofollow` now return the offending elements and the `_count_*`
helpers are `len()` of those, so a count cannot drift from its evidence.
Mixed-content rows carry `severity: active|passive` — a blocked `<script>` and an
auto-upgraded `<img>` are different problems.

**The report rendered no evidence at all.** Most codes already carried it —
`ANCHOR_TEXT_GENERIC` the anchor text and href, `SEMANTIC_DENSITY_LOW` a written
diagnosis, `SCHEMA_VISIBLE_MISMATCH` the exact off-page value — and the PDF showed
only affected page URLs. On the real 2,137-issue job, **34 codes** were carrying
usable evidence the report discarded (P25).

`api/services/issue_evidence.py` renders any code's `extra` from the ~15 recurring
shapes it actually uses, enumerated from a real job. A per-code formatter table was
rejected: 167 entries, and it would silently omit the next code added. Pure
measurements are skipped (the description states them); unknown keys are skipped
rather than dumped, because raw JSON in a client report is worse than nothing.
Surfaced as **"What to look for:"** in the PDF and a matching Excel column that is
genuinely uncapped, since the PDF points the reader there.

`PAGE_IS_THE_EVIDENCE` records the codes whose fix is "edit this page" with no
sub-element to name. A test asserts every entry is a real code and that every
high-volume code renders evidence — so a silent finding is a decision, not an
oversight.

**One implementation, server-side.** `_issue_dict` — the single serialiser all
seven list endpoints use — ships the rendered lines as `evidence` /
`evidence_total`, so the Results category panel, the By-Page view, the PDF and the
Excel export cannot disagree. A JS port of a 15-shape renderer was rejected: a
second implementation in another language is a drift waiting to happen (P19),
and the category panel's `IssueEvidence` component only formats what the server
already rendered. On job 05cd2496 that is 1,212 of 2,137 issues across 34 codes.

**Exempt anchors reach the evidence too.** `_apply_exempt_anchors` previously
rewrote only the description, leaving the raw hrefs in `extra`. Harmless while
nothing rendered them — the moment `evidence` did, the UI would have shown the
very anchors the user exempted. It now filters `extra` and recomputes the
evidence for the issues it modifies.
→ `tests/test_issue_evidence.py` (51 tests), `frontend`:
`CategoryPanelFocus.test.jsx`.

**Existing crawls:** the renderer works on stored data immediately; the three
capture fixes need a re-crawl, because those hrefs were never written.

**Configuration.** E4–E7 introduced `api/config/*.json` with a loader
(`api.config.load_config`) that validates required keys and raises at import on
a malformed file, so editorial content lives outside Python source (rule 9) and a
broken config fails loudly rather than silently defaulting (P2).

---

## 5. Fix capabilities

Fixes are organised into routers; all WP-touching endpoints validate domain credentials.

### 5.1 Title fixes (`title_router.py`)
- `GET /api/fixes/predefined-codes`
- `POST /api/fixes/bulk-trim-titles`
- `POST /api/fixes/trim-title-one`

### 5.2 Heading fixes (`heading_router.py`, 6 endpoints)
- `GET /find-heading`
- `GET /analyze-heading-sources`
- `POST /change-heading-level`
- `POST /change-heading-text`
- `POST /bulk-replace-heading`
- `POST /heading-to-bold`

### 5.3 Image metadata fix (`image_router.py`)
- `GET /image-info`
- `POST /update-image-meta`
- `POST /refresh-image-from-wp`

### 5.4 Image optimization — single
Workflow A (WP existing) and Workflow B (upload local). Generates WebP formats with optional SEO keywords and GPS EXIF metadata.

### 5.5 Batch image optimization (`batch_optimizer_router.py`)
Parallel batch processing with status polling and cancel/resume capabilities.

### 5.6 Orphaned media (`orphaned_media_router.py`)
Identifies WP media library entries not referenced on any crawled page.

### 5.7 Broken-link verification & replacement (`link_router.py`)
Re-checks broken targets and auto-clears resolved issues.

### 5.8 Mark-fixed actions
Clear target URLs, surgical anchor removal, and issue resolution marking.

### 5.9 Generic inline fix
Generic single-fix dispatcher (`/apply-one`) for any fixable issue code.

### 5.10 Verified links (`/api/verified-links`)
Mark external URLs as known-good to bypass bot-blocking skipped lists.

### 5.11 llms.txt generation
Generate or retrieve curated `/llms.txt` content from crawl data.

### 5.12 Schema Generation & Suggestions
**Generate-and-suggest features (No direct WP mutation):**
- **FAQ Generator (`POST /api/ai/geo-faq`):** Produces Schema.org `FAQPage` JSON-LD to capture long-tail, high-intent queries. Uses a hybrid engine with a deterministic template default and an opt-in `AIRouter` enrichment mode. Enforces a ≥6-word rule for all generated queries.
- **Entity Schema Factory (`POST /api/geo/entity-schema`):** Deterministically constructs a nested `Organization -> Service -> FAQPage` JSON-LD block linking the organisation to its authoritative entity via `sameAs` (e.g. Wikipedia URL sourced from `GeoConfig`).
- **Page FAQ Schema Generator (`POST /api/ai/faq-schema`):** Generates ready-to-paste Schema.org `FAQPage` JSON-LD for a single crawled page from its actual on-page Q&A. `generate_faqpage_schema` (`api/services/faq_schema_generator.py`) builds the schema only from answers present in the HTML — the page is re-fetched (SSRF-safe) and re-extracted via `_extract_faq_blocks` because answer text is not persisted in the crawl. Copy/export only; never writes to WordPress; refuses (`refused: true`) rather than fabricating when answers are JS-only. Request `{job_id, page_url}` → `{jsonld, question_count, refused, reason}`. → `tests/test_faq_schema_generator.py`

---

## 6. AI capabilities

All AI provider calls execute strictly through the centralized **`AIRouter` singleton** (`api/services/ai_router.py`), ensuring unified identity-based key resolution, usage tracking, and multi-provider fallback.

### 6.1 Content Quality Advisor (`/api/ai/advisor`)

Routes via `AIRouter.call_text` to evaluate a page across 6 properties:
1. Source Fidelity
2. Factual Grounding
3. Self-Containment
4. Structural Fitness
5. Authority Signals
6. Honest Placeholder Use

**Acceptance criteria:**
- Every finding cites specific page text.
- No scoring, qualitative findings only.
- Returns a markdown report rendered deterministically from the JSON response.
- **Entity Validation:** If a `GeoConfig` is injected into the payload, an `ENTITY VALIDATION CONTEXT` block automatically prepends to the LLM system prompt. The LLM validates `org_name`, `primary_location`, `location_pool`, and `topic_entities` against the page content.

### 6.2 Content Rewriter (`/api/ai/rewriter`, `/api/ai/rewrite-url`)

Takes `content` + `prompt`, returns one rewrite via a single `AIRouter.call_text` execution with temperature 0.2.

### 6.3 Image AI analysis

- `POST /api/ai/image/analyze-geo` — GEO-optimized alt-text + long description using `AIRouter.call_vision`. Securely fetches image bytes internally using an SSRF-safe client.
- `POST /api/ai/image/apply-geo-metadata` — applies GEO metadata to WP.

### 6.4 Executive summary (`GET /api/crawl/{id}/executive-summary`)

3–5 sentence plain-language narrative for the PDF report.

### 6.5 Citation ingestion (`POST /api/jobs/{job_id}/ai-citations`)

Receiving endpoint for a sibling tool that produces per-URL AI citation data. Normalizes URLs to safely match crawler outputs, records `ai_citation_count_30d` and `ai_citation_engines` directly to `CrawledPage` models. Powers the `AI_CITED_PAGE` and `AI_HIGH_VALUE_UNCITED` heuristics.

### 6.6 Token usage tracking & Aggregation (`/api/ai/usage/stats`)

- **Persistence:** Every successful or failed AIRouter call is reliably tracked via the async `UsageLogger`, which records task types, execution status, input/output tokens, and cost estimates to the `ai_usage` SQLite table.
- **Pricing Service:** `PriceLookup` (`api/services/ai_pricing.py`) computes execution costs deterministically using `decimal.Decimal` per 1M-token pricing tables, protecting upstream drivers from float inaccuracy.
- **Aggregation API:** `GET /api/ai/stats` provides time-bounded (max 90-day) usage summaries, aggregating total spend, call successes vs. failures, and detailed provider/model breakdowns.

### 6.7 Issue-aware AI Suggestion (`/api/ai/analyze` — `issue_advisor` type)

Per-issue AI text suggestion button in the Page Audit. Only appears on issue codes where AI can write improved text (26 codes: title, meta, OG, headings, alt text, anchors, thin content, schema, and select AI-readiness codes).

**Analysis type:** `issue_advisor` — added to `PROMPT_LIBRARY` in `api/services/ai_analyzer.py`. Takes `issue_code`, `issue_description`, and `extra_context` (image URL, current alt, link URL, H2 list, H1 topic — forwarded from issue `extra` fields). Returns `{suggested_text, why, where_to_apply}` JSON.

**Eligibility set:** `_AI_TEXT_SUGGESTION_CODES` in `api/routers/ai.py` — 26 codes. Requests with out-of-scope codes are rejected immediately with an error response.

**Frontend:** `AI_TEXT_SUGGESTION_CODES` set in `Results.jsx` gates the `✨ AI Suggestion` button per issue card. On response, renders three labelled fields (Suggested text + Copy, Why, Where to apply) instead of a raw blob.

**AI Readiness codes included:** `SCHEMA_ORG_MISSING`, `CONVERSATIONAL_H2_MISSING`, `QUERY_COVERAGE_WEAK`. `CITATIONS_MISSING_SUBSTANTIAL_CONTENT` is excluded (AI cannot invent real citations).

### 6.8 Contextual help icons — Page Audit

Every section header and every issue card in the Page Audit panel shows a visible `?` icon.

**Section-level help:** `CollapsibleSection` accepts a `helpContent` prop `{what, why, how}`. A `?` button after the section title toggles an inline blue panel. Content lives in `frontend/src/data/sectionHelp.js` (four entries: `page_metadata`, `headings_structure`, `issues_found`, `ai_recommendations`). `AIRecommendationsPanel` has its own inline `?` button using the same pattern.

**Issue-level help:** `?` button added to the IssueCard header row (between Fix button and `···`), always visible when help content exists for the code. Clicking toggles `showHelp` — same state used by the "Show Help" action in `···`. Source content: `issueHelp.js` (140 entries, unchanged).

### 6.9 Page-priority work queue (`GET /api/crawl/{job_id}/page-priority`)

Ranks a job's crawled pages into a prioritised work queue by the Authority
Matrix (§4.8): Vulnerable Stars first, then Traffic Decay / Staleness, then
worst-health, with Hidden Gems surfaced as opportunities. Per-page health is
computed via the canonical capped-and-suppressed model (`compute_page_health`,
R5.0) rather than a raw impact sum. `refresh_trigger.rank_pages` performs the
ordering, and `evaluate_refresh` produces each page's review flag; the queue
works with **or without** GSC data — a page with no Performance Ledger records
is ranked by health alone. Returns `{pages: [{url, health_score, gsc,
review_flag: {flagged, reasons}}], total}`, where `gsc` carries
`{clicks, impressions, ctr, position, conversions}` (conversions `None` when
unknown). → `tests/test_page_priority.py`

**Within-bucket ordering (PW, 2026-08-14).** The Authority-Matrix bucket is the primary key
(needs-work-first). WITHIN a bucket, pages are ordered by descending **clicks**, then descending
**conversions** (tiebreak), then worst health, then url — the full key is
`(bucket, −clicks, −conversions, health, url)`. Clicks lead (PW-D1): a high-click page is
high-value whether a journey entry point or an underperformer. With no GSC data every traffic key
is `(0, 0)`, so the order collapses to the prior health-only ordering — unchanged for non-GSC
scans. Conversions come from `ga4_conversions_mo` (the GSC upload's `inquiries`, §6.12);
`None`→`0` for the sort only (the stored/displayed value keeps `None`). Surfaced as a **Conv.**
column in the panel. → `tests/test_refresh_trigger.py::TestRankPagesPW`,
`tests/test_crawl_router_contracts.py::TestPagePriorityConversions`, `frontend`:
`PagePriorityPanel.test.jsx`. *(Spec: supersedes pending `2026-08-14_traffic-conversion-weighted-priority.md`.)*

**Frontend — Hide control.** The Page Priority panel's loaded-state action is a **Hide**
button that collapses and clears the ranked table; re-opening the panel re-ranks from the
current crawl. (It replaced a misleading "Refresh" button that only re-displayed the same
crawl's numbers without re-scanning.) → `frontend`: `PagePriority.test.jsx` "Hide collapses".

### 6.10 AI-error contract (P14) and Connections panel

**Error contract.** `analyze_with_ai` (`api/services/ai_analyzer.py`) and `geo_llm._call_llm`
**raise a typed `AIAnalysisError`** on any provider failure (auth error, API error, missing
prompt-context key) — they never return an error-sentinel string as content. Every caller
catches it and routes to its error channel: `/api/ai/analyze` → 503, `/page-advisor` /
`/site-advisor` → `{error}` field, and the `crawl.py` executive-summary path skips (never caches
the error onto the job). The former `str.startswith` sentinel checks and
`geo_llm._is_ai_error`/`_ERROR_PREFIXES` were deleted. → `tests/test_ai_test_endpoint.py`,
adversarial "provider error never appears as content" tests. *(Spec:
`docs/pending/OLD/2026-07-06_p14-ai-error-contract.md`.)*

**Connections panel.** A `ConnectionsPanel` modal (opened from the Results header, alongside
Display Settings / GEO) lets the operator verify the two external integrations without leaving
the results view. No new endpoints were added; both reuse existing bearer-auth GET routes.

- **Test LLM — `GET /api/ai/test`.** Runs a real round-trip against the configured provider.
  Response contract: `{success: bool, message: str}` plus `{sample}` on success. The former
  `api_key_read` diagnostic field was **dropped** from the response. → `tests/test_ai_test_endpoint.py`.
- **Test GSC — `GET /api/gsc/status`.** Reports connection state. Response contract:
  `{connected: bool, properties: [...], configured: bool}`. `configured: true` is returned on all
  three 200 paths (no-creds, success, except-fallback); the `_require_gsc_configured()` 503 path
  (GSC env not configured) maps to `configured: false` on the client, so the panel distinguishes
  configured-but-unlinked (shows **Connect**) from genuinely-not-configured (quiet empty state).
  GSC is linked **app-wide, one-time** via the OAuth `Connect` flow (§4.8). →
  `tests/test_gsc_integration.py::TestGscStatus::test_status_response_contract_fields`.
  *(Spec: `docs/pending/OLD/2026-07-06_connections-panel.md`,
  `docs/pending/OLD/2026-07-06_ui-and-detection-fixes.md`.)*

### 6.11 Fix Focus — curated priority-fix checklist (2026-08-13)

A finite, tickable worklist distinct from the read-only Top-10-Pages / Top-Priority summaries.
Built from the job's **already-stored** issues (no re-crawl), split into two focuses — **SEO**
and **AI/GEO** — grouped by page and capped at **10 pages per focus**, ordered by summed
`priority_rank`. It is **saved with the crawl** (a `fix_focus` JSON blob on the job, mirroring
`geo_report`) so it returns without re-scanning, and each page can be re-scanned to verify.

- **Bucketing (FF1).** `focus_bucket(category, code)` (`registry.py`) is the single source of
  truth: GEO = `AGENT_READINESS_CATEGORIES` (`ai_readiness`, `rendering`, `semantic_html`) ∪
  `AGENT_READINESS_EXTRA_CODES` (`PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK`); SEO is the
  complement. `job_store_base` **imports** the same set (Agent Health and Fix Focus can't drift —
  `test_ff1c_focus_bucket_single_source`).
- **Selection (FF2).** Only page-scoped issues at or above `FIX_FOCUS_MIN_IMPACT` (4, warning+);
  deduped by `(page_url, issue_code)`; the 10-page cap announces the drop
  (`pages_total`/`pages_shown`/`items_hidden` — no silent truncation).
- **Persistence (FF3).** The snapshot is frozen on first `GET` and persisted; each item carries a
  `status ∈ {open, checked, verified, still_present}`. `update_job` now JSON-encodes dict blobs on
  **both** SQLite and Redis (previously Redis `str()`-repr'd a dict — a latent bug fixed here).
- **Endpoints (FF4/FF5).** `GET /api/crawl/{id}/fix-focus` (generate+persist),
  `POST …/fix-focus/check` (reversible toggle), `POST …/fix-focus/regenerate` (rebuild,
  preserving checked/verified state for surviving items), `POST …/fix-focus/verify-page` (reuses
  the existing `rescan-url` path — one hardened fetch — then reconciles from the **absolute**
  current issue set: a code still seen → `still_present`, otherwise → `verified`; new codes →
  `newly_found`, surfaced but not injected into the frozen list). A page returning HTTP ≥ 400 is
  **not** reconciled (`reconciled:false`) so an erroring page never false-verifies.
- **Frontend.** A **Fix Focus** tab in Results renders both focuses with checkboxes, a per-page
  **Verify** button, and **Regenerate**; toggle/verify failures surface in the panel's error
  state. Fix Focus is **also** surfaced on the **Summary** dashboard, in a responsive row
  immediately after the Top 5 Priority Fixes panel, beside a **Fix Focus Items Help** panel
  (`FixFocusItemsHelp.jsx`) — a deduped glossary that explains each DISTINCT issue code on the
  list exactly once (across SEO+GEO and across pages). Each entry is **titled with the same
  label the checklist shows** (`human_description`) so it lines up with its checklist item, with
  the "what it is" + fix body from `issueHelp.js` keyed by code (title falls back to the
  `issueHelp` title, then the code); the list is ordered **A–Z** by that label for quick lookup.
  → `tests/test_fix_focus.py`,
  `tests/test_crawl_router_contracts.py::TestFixFocusEndpoints`, `frontend`:
  `FixFocusPanel.test.jsx`, `FixFocusItemsHelp.test.jsx`. *(Spec: this section supersedes the
  pending micro-specs `2026-08-13_fix-focus-checklist.md` and `2026-08-13_fix-focus-summary-and-help.md`.)*

### 6.12 GSC priority upload — seed the crawl + rank by Search Console (2026-08-14)

An **optional, user-uploaded** hand-off from the sibling GSC reporting app. On the scan-start
screen the user may attach that app's `priority_pages.json`; the browser reads and JSON-parses it
and embeds the object in the `POST /api/crawl/start` body as `gsc_priority` (the hosted server
never reads the user's disk). No file → a normal scan, unchanged. **ONE file drives both flows.**

- **Contract (reconciled to the real produced file).** Per page: `url` (absolute), `clicks`,
  `impressions`, `avg_position`, `inquiries`, `top_queries[]` (strings); top level `generated_for`,
  `site` (bare host). `api/services/gsc_priority.py::parse_priority_upload` domain-guards each URL
  against the scan target (`is_same_domain`), holds out off-domain/blank rows and **announces
  "seeded N of M"** (P2), coerces stringy numbers, rejects a file another tool stamped
  (`generated_for` ≠ "talkingtoad") or one with no in-domain page (422 `INVALID_PRIORITY_FILE`).
  `inquiries` is **nullable** → `ga4_conversions_mo` (absent ≠ measured zero, P2).
- **(ii) crawl seed.** The ranked `pages[].url` list is passed to the engine as `priority_urls`
  and **fronted in the frontier right after the homepage, before sitemap URLs** — advisory:
  same-domain, in-scope, deduped, subject to the identical robots/SSRF/`max_pages` guards as any
  URL; `single_page` skips it. A seed ≥ `max_pages` would silently restrict the crawl, so `/start`
  emits a loud scope note (D-N1: seed **orders**, never restricts).
- **(i) ranking.** After the crawl, `build_ledger_records` joins the seed's per-page metrics onto
  crawled pages (same `match_key`/`build_crawled_key_map` as `/api/performance/ingest`) → the
  Performance Ledger (`clicks`, `impressions`, `ctr` derived, `avg_position`→`position`,
  `inquiries`→`ga4_conversions_mo`), stamped from upload time (D-N4). Page Priority then ranks with
  Search Console data. The seed persists as a `priority_seed` job blob (SQLite + Redis).
- **Deferred (v1 out of scope):** the rich `PerformanceBundle` (GA4 sessions, `conversions_by_event`,
  URL-Inspection `index_state`, GTM) — the GSC app doesn't pull those; TT reads the flat file it
  already emits, so v1 needs **no GSC-app code**. → `tests/test_priority_upload.py`,
  `tests/test_priority_upload_ledger.py`, `tests/test_crawl_priority_seed.py`, `frontend`:
  `api.test.js`. *(Spec: supersedes pending `2026-08-14_gsc-performance-handoff-plan.md`.)*

---

## 7. Reporting and export

### 7.1 PDF audit (`GET /api/crawl/{id}/export/pdf`)

Letter (8.5×11), fpdf2-generated. Sections, in order:
- Cover page with domain, health score, summary counts
- (Optional) AI executive summary
- Dashboard Summary — Health, Agent Health, and **Site Hygiene** (§7.5) when prevalence was computed, with the distinction between them printed beneath
- **Search Performance** and **Priority Pages** (§7.4) — only when the Performance Ledger holds data for the domain
- Top 10 most-affected pages — ordered by the §6.9 work queue when ledger data exists, by issue count otherwise, with a subtitle naming which
- **Systemic Defects** (§7.5) — only when a defect crosses the systemic tier
- **Remediation Roadmap** (§7.6) — owner, phase, effort and a countable "done when" per finding
- "What to Do Next" checklist — prevalence-ordered when available
- llms.txt status, Image Health (omitted when no images were collected), category sections with help text and evidence tiers
- **Scope, Method and Caveats** (§7.7) — always rendered

**Acceptance criteria:**
- AI-readiness issues display a colour-coded evidence-tier pill (Established/Reasonable proxy/Heuristic) below the issue title, powered by the issue's `confidence_label`.
- Critical issues appear in red, warnings in amber, info in blue.
- Every section that is omitted for lack of data is **named in Caveats** (§7.7). A missing section must never read as a passed check. → `tests/test_report_roadmap.py::TestOmissionsAreDisclosed`

### 7.2 Excel export (`GET /api/crawl/{id}/export/excel`)

openpyxl-generated tabbed workbook:
- Summary tab, Pages tab, Citations tab
- **Performance**, **Priority Pages**, **Prevalence** and **Roadmap** tabs, mirroring the PDF sections and uncapped where the PDF is capped
- One tab per issue category
- The "AI Readiness" sheet features an explicit **Confidence** column mapping to the AI-readiness taxonomy.

### 7.4 Search Performance and Priority Pages (E3, 2026-08-29)

`api/services/page_priority.py` holds **one** assembly used by the
`/page-priority` endpoint, the PDF and the Excel export, so the ranking cannot
exist for one surface and be absent from another (P25). Before this, the ranking
was reachable only from the API and the GUI panel while the client-facing PDF
sorted "Top 10 Pages to Fix First" by raw issue count.

- `build_page_priority(store, job_id)` — the §6.9 Authority-Matrix queue.
- `build_performance_summary(store, job_id)` — site totals (impressions, clicks,
  CTR, GA4 sessions, conversions, AI-referral sessions), the top 15 pages by
  impressions **joined to each page's health score**, and a "seen but not
  clicked" list (above-median impressions, below-average CTR). Returns `None`
  when the ledger holds nothing, so the caller omits the section and records the
  omission rather than rendering zeros that read as "no traffic".
- **Freshness (P6):** age is derived from the data's own reporting period, or
  from the producer's `source_generated_at` when supplied — never from
  `recorded_at`, which the store stamps at write time, so a three-month-old
  bundle re-imported today would otherwise read as fresh. Clamped at 0, because
  the current month's period-end is in the future.
- **The join key (`ledger_key`).** Crawled URLs and ledger URLs disagree on
  trailing slashes — the crawler normalises them away, the ledger stores what
  Search Console reported, which on WordPress carries one. An exact match joined
  **11 of 272** pages on livingsystems.ca, lost the site's biggest page entirely,
  and reported 3,717 impressions instead of 27,284. Both sides now go through
  `ledger_key` (trailing slash, `www.`, and host case ignored; path case
  preserved), and the domain candidates are collected from **every** crawled
  host, not from `pages[0]`. A join that matches nothing, or under
  `TT_PERF_JOIN_WARN_RATIO`, logs a warning — "no ledger row for this page" and
  "the key didn't match" otherwise produce identical output (P19 + P2).
- **Unknown is not zero (P2).** GA4 totals sum only pages that reported a value
  and each carries its own `*_pages_with_data` denominator; the report prints
  "not measured" rather than 0. A page with no measured CTR is never listed as
  an underperformer.

→ `tests/test_performance_report.py`, fixture `tests/fixtures/performance/livingsystems_ledger.json` (a real 555-row export).

### 7.4b Core Web Vitals (D2, 2026-08-29)

`api/services/web_vitals.py`, surfaced by `POST /api/crawl/{id}/web-vitals` —
**opt-in, post-scan, never inside the crawl** (guarded by
`tests/test_web_vitals.py::test_d2_1b_scan_never_calls_web_vitals_apis`). The
binding CrUX/PSI constraint is 100 queries per 100 seconds, so a whole-site sweep
would add minutes to every run for data that only matters where traffic is. Scope
is the top N of the §6.9 priority queue (`default_top_n` 10, hard max 25).

**Why this does not cross the producer line.** The Performance Bundle contract
says "TalkingToad does not do OAuth to Google — the producer owns acquisition."
That rule is about *account-scoped* data: reading a Search Console property needs
the owner's authorisation. CrUX and PSI are API-key gated and callable for any
public URL without touching an account — a different class.

**Field and lab are never conflated.** CrUX field data (75th percentile across
real Chrome users, 28-day window) is the **only** source that raises a finding.
PSI lab data is one synthetic run and is diagnostic context only; every rendered
row states which it is. Google is discontinuing CrUX field data *inside* the PSI
response, so field data comes from the CrUX API directly. Lighthouse has no INP
audit, and Total Blocking Time is deliberately **not** mapped onto `inp_ms`.

Three codes, field-only, category `rendering`, `Established` confidence:
`CWV_LCP_POOR` (>4.0s), `CWV_INP_POOR` (>500ms), `CWV_CLS_POOR` (>0.25) —
Google's own "poor" boundaries, in `api/config/web_vitals.json`. Only the poor
band fires; "needs improvement" is reported as a number, because flagging two
thirds of the web is noise.

Findings are **persisted** so they reach the report, the summary and the health
score. A re-run clears the job's prior CWV rows first: the measurement is a
snapshot of a rolling window, so the newest run replaces the older one and a page
that improves loses its finding rather than keeping a stale negative (P8/P1).

A 429 is **retryable, never a terminal "no data"** — quota exhaustion on page 8
of 10 must not make pages 9 and 10 look fine. A page with no CrUX record is
reported "not measured", never "good". The API key is env-only and is **scrubbed**
from every error string: Google takes it as a query parameter, so an httpx
transport error carries it into the log and the 502 body without that.

No key → the section is omitted and named in Caveats, and the E7 "Core Web Vitals
not checked" line becomes conditional on whether the collection actually ran.

**Fixture caveat (P19/P20):** the checked-in CrUX/PSI payloads are **constructed
from the documented contracts, not recorded** — no key was available and the
shared keyless PSI pool returned 429. The parsers degrade to "not measured" on an
unrecognised shape, and `TestLiveApiContract` runs against the real API as soon as
`TT_PSI_API_KEY` is set. See `tests/fixtures/web_vitals/README.md`.
→ `tests/test_web_vitals.py` (46 tests).

### 7.5 Site prevalence and Site Hygiene (E4, 2026-08-29)

`api/services/prevalence.py` measures how much of the **indexable** estate each
code touches, as a second lens beside per-page severity.

**Scoring is not affected.** `_ISSUE_SCORING`, `_CATEGORY_IMPACT_CAP`,
`compute_page_health`, `compute_impact_health`, the R3/R5 calibration and every
`_IssueSpec.severity` are unchanged, and `tests/test_prevalence.py::TestScoringUnchanged`
asserts health is byte-identical.

- Denominator is indexable pages (crawled minus noindex/robots-blocked), so a
  large noindex'd archive cannot dilute a share.
- Site-scoped and job-level codes get no entry — a share for a once-per-job code
  would read as a 0.4% problem.
- Tiers need **both** a share and a page count (§thresholds).
- **Site Hygiene** = the percentage of indexable pages carrying **no** systemic
  defect, reported *alongside* Health with both meanings stated. Health is
  per-page quality averaged; Hygiene is breadth.

  A weighted penalty sum (`100 − Σ(tier weight × share)`) was tried first and
  discarded: on livingsystems.ca nine systemic defects produced a penalty of 135
  and the score clamped to 0, which distinguishes nothing from a site with
  twenty. The coverage measure is bounded by construction, needs no arbitrary
  per-tier weight, is monotonic, and states itself in one sentence — on that
  site it reads 34, i.e. 178 of 271 indexable pages carry at least one systemic
  defect, alongside a Health score of 89. That pair is the honest description:
  individually decent pages, all sharing the same template problems.
- **`always_systemic` bypasses the share gate** (broken links are a template fix
  however few pages show them), so a systemic code can have a small footprint.
  No surface quotes a threshold percentage; each states its actual footprint.

Surfaced on `GET /api/crawl/{id}/results` (`summary.prevalence`,
`summary.systemic_count`, `summary.site_hygiene_score`), in the Results summary
panel, and as PDF/Excel sections. → `tests/test_prevalence.py`,
`frontend`: `SystemicDefects.test.jsx`.

### 7.6 Remediation Roadmap (E7, 2026-08-29)

`api/services/remediation.py` groups deduplicated findings into three phases —
Stabilise (0–30d), Repair priority pages (31–60d), Expand (61–90d) — each row
carrying **Owner**, **Impact**, **Effort**, **pages affected** and a **"done
when"**. Phase membership is derived, not decorative: Phase 1 because the defect
is systemic (§7.5), Phase 2 because it lands on a top-quartile page of the §7.4
queue. With neither data source available the section says so rather than
implying a phasing it did not apply.

Every "done when" is written to be **re-crawl assertable** ("a re-crawl reports
0 indexable pages with a missing description"), with a countable fallback for
codes carrying no override — being verifiable by re-running the tool is the one
thing TalkingToad offers that a consultant's PDF cannot.
Owners and phase labels live in `api/config/remediation_owners.json`.

`build_roadmap` returns `(items, weighted, totals)` — `totals` is the **pre-cap**
count per phase, so the PDF can print "Showing the top 12 of 40". Returning only
the capped list made that disclosure impossible (rule 6). The Excel Roadmap sheet
is called uncapped, because both the PDF and the Results issue card point the
reader there for the full list.
→ `tests/test_report_roadmap.py`.

### 7.10 Off-site authority (D1, 2026-08-29)

`api/services/offsite.py`, fed by a new `links` section on the Performance
Bundle's `site` object (`api/routers/performance.py`).

**A vendor backlink index was declined.** Semrush/Ahrefs/Moz are a recurring cost
with a per-customer key, and a per-customer key is the parked multi-tenant work
(`docs/TODO-MULTITENANT.md`). But "we cannot buy the third-party estimate" was
never the same as "off-site is out of reach": Search Console reports referring
domains, top linking sites and top linked pages for free, inside the OAuth scope
the producer app already holds. So this is a **contract extension, not an
integration** — no new vendor, no new key, no multi-tenant prerequisite.

**The join is worth more than the number**, and these three need both halves:

- **External links pointing at broken pages.** Another site links to a URL that
  404s: the link exists and its value is being discarded, and a one-hop redirect
  recovers it. Neither a backlink tool nor an analytics export can find this
  alone — it needs the crawl's broken-link set. A broken target is reported once,
  not also as earned authority; "fix the redirect" is a different action from
  "improve the page".
- **Earned authority on pages with fixable problems.** Real incoming links AND a
  low health score: the hard part is already done. A single stray link does not
  qualify (`TT_OFFSITE_MIN_INCOMING`).
- **Linked pages the site does not link to internally.** Authority that is not
  circulating.

The join uses the same `ledger_key` as E3 — an exact match silently lost 96% of
the Performance Ledger before that fix, and repeating it here would be the same
bug in a new place (P5). `pages_in_report` vs `pages_matched` makes a join failure
visible rather than silent.

Absent section → `build_offsite` returns `None`, the report omits the section, and
the E7 caveat becomes precise: Search Console link data IS included when supplied;
third-party authority scores, full backlink graphs and directory-listing
consistency are not, and it says why. → `tests/test_offsite.py` (21 tests).

**Producer dependency:** TalkingToad's half is complete and the contract accepts
the section today. The data arrives once the sibling reporting app adds the GSC
links call. → also `docs/pending/2026-08-11_performance-bundle-producer-contract.md`.

### 7.9 Page blueprints (D4, 2026-08-29)

`api/services/blueprints.py`, surfaced by `POST /api/ai/blueprints/{job_id}`
(+ `/approve`, `/reject`). Drafts a title, meta description, H1 and answer-first
lead for one page, grounded in that page's own text.

**Built as a tool with a review gate, not as a report section.** Two independent
gates guard the export: the draft must be **approved by a person**, and the
caller must pass `include_blueprints=true` — which defaults to **off**. Reasoning
recorded because it is the shape of the whole item: the report is otherwise a
record of observations where every line traces to something measured, and
generated prose makes it partly a record and partly a draft with no way for the
reader to tell which. The site this was built against is a counselling charity,
where invented copy could imply a clinical outcome or soften crisis-resource
language. The external audit that inspired this required human review of its own
drafts before publication.

**The grounding check is the feature**, and it has two tiers:

- **Verbatim floor, never relaxed.** Proper nouns, numbers, dates and money in
  the draft must appear in the source page. A capitalised word in
  sentence-initial position is dropped from a candidate first — flagging "Explore
  Bowen family systems…" marks every faithful draft unverified, and a gate that
  fires on everything is one the operator learns to click through. The trade-off
  costs the leading word of a sentence-initial name and is asserted not to cost
  recall on a fabricated one.
- **Topical overlap** on the paraphrased lead, plus a marker list for fabricated
  **stances** ("clinically proven", "accredited by") that carry no proper noun and
  no number — the class P20 says a concrete-specific gold set always misses.

An `unverified` draft is **shown with its unsupported claims listed** and cannot
be approved until a human clears them; it is never silently discarded, because
the operator needs to see what the model tried to assert. A provider failure
raises (P14) — an error message must never become draft copy. Every call routes
through `AIRouter`, so usage and cost stay centralised, and nothing in the path
touches WordPress. → `tests/test_blueprints.py` (27 tests).

### 7.8 WordPress configuration audit (D3, 2026-08-29)

`api/services/wp_audit.py`, surfaced by `POST /api/wp-audit/{job_id}`.
**Read-only, opt-in, post-scan.** It reports the operational facts no crawler can
reach — inactive plugins, pending updates, two plugins claiming the same job,
and WordPress's own Site Health recommendations.

**It cannot write, and that is enforced.**
`tests/test_wp_audit.py::TestReadOnly` asserts the module and its router contain
no `post(` / `patch(` / `put(` / `delete(` call, and a behavioural test confirms
the client saw nothing but reads. This holds admin credentials to a live client
site; intent is not a property.

**It is not part of the crawl.** `engine.py`'s constraint — the scan uses HTML
and HEAD requests only, never the WordPress API — is untouched and still enforced.
That constraint is what keeps the crawl fast and keeps TalkingToad working on
non-WordPress sites.

Order of operations: domain validation → capability probe → plugin read. A
capability failure returns 403 with a named code rather than an empty audit,
because "we could not look" must never render as "nothing to report" (P2).
Themes and Site Health are best-effort — absent on some installs, and their
absence degrades the report rather than failing it.

Plugin-overlap detection collapses free/premium pairs of one product first
(`families` in `api/config/wp_plugin_advice.json`): flagging Yoast against Yoast
Premium, or Duplicator against Duplicator Pro, is noise that would make the whole
section easy to dismiss (P7). Only **active** plugins can overlap.

**The boundary is declared in the output.** "Duplicator is active but has never
taken a backup" needs Duplicator's own tables; there is no generic REST surface
for plugin-internal state, and a bespoke probe per plugin is open-ended. The
report lists what it did **not** inspect, and the E7 "CMS and plugin
configuration not checked" caveat flips to a precise statement of that boundary
once the audit has run. → `tests/test_wp_audit.py` (27 tests).

### 7.7 Scope, Method and Caveats (E7, 2026-08-29)

Always rendered, including on a clean site. Records what was covered; **every
cap that actually bit**, with both numbers; **every section omitted, by name**;
the data sources and periods behind any performance figures; and what the audit
did **not** check — off-site authority, Core Web Vitals, server logs, CMS/plugin
configuration, WCAG conformance, and anything behind a login. Closes with what
each score means and the statement that none of them forecasts rankings,
traffic or revenue. A cap that did not bite is not mentioned.
→ `tests/test_report_roadmap.py::TestOmissionsAreDisclosed`.

### 7.3 CSV export

- `GET /api/crawl/{id}/export/csv` — full CSV (all issues)

---

## 8. Non-functional requirements

### 8.1 Security

- **Bearer token auth** strictly enforced on every single `/api/*` endpoint (including all AI routers and GSC).
- **Production-environment fail-closed:** app refuses to start if deployed and `AUTH_TOKEN` is empty.
- **SSRF protection:** `is_ssrf_safe()` blocks RFC1918, loopback, and link-local.
- **AIRouter Isolation:** Drivers do not contain explicit arithmetic; modules cannot bypass `AIRouter` bounds.
- **Encrypted Secrets:** OAuth tokens (GSC) and AI credentials are encrypted at rest using Fernet.

### 8.2 Performance

- Async crawl engine with concurrent fetches.
- Crawl delay configurable per job.
- `UsageLogger` utilizes an async task queue and lifespan `await_pending()` hooks so that telemetry database writes never stall critical LLM responses.
- Batch upserts for the Performance Ledger to ensure high-throughput writes.

### 8.3 Reliability

- **Test suite:** Over 1380 passing tests on `main` as of v2.6.0 baseline.
- Parity tests enforce structural synchronization among the `_CATALOGUE`, numeric scores, `issueHelp.js` metadata, and dynamically generated documentation (`issue-codes.md`).
- Contract coverage for `AIRouter` fallback configurations and multi-provider models.

### 8.4 Configurability

- **Suppressed codes:** global setting to exclude specific codes from health-score.
- **Exempt anchor URLs:** specific hrefs that should not trigger `LINK_EMPTY_ANCHOR`.
- **Ignored image patterns:** substring patterns to exclude theme images.

### 8.5 Deployment

- Backend container (Railway, Fly.io, Render, or self-hosted Docker).
- Frontend on Vercel; proxies `/api/*` to backend.
- SQLite (dev) or Upstash Redis (optional prod).
- Health check endpoint returns `{"status": "ok", "version": "2.6.0"}`.

### 8.6 Stabilization & adversarial hardening (Cycles J-U, v2.6 M9.1)

Consolidated 19 vulnerabilities across the audit engine into robust regression-guards. Defenses standard across the codebase include:
- None-tolerant dict reads.
- Case-insensitive semantic equality.
- Whitespace-tolerant parsing.
- Self-link filtering in cross-page graphs.

---

## 9. Verification matrix

For each major feature, the test file(s) that prove it works:

| Feature | Primary test file(s) | Coverage notes |
|---|---|---|
| URL normalization | `tests/test_normaliser.py` | Trailing slash, fragments, UTM stripping |
| robots.txt parsing | `tests/test_robots.py` | Disallow rules, wildcards, crawl-delay |
| Sitemap discovery | `tests/test_sitemap.py` | Standard, index, gzip |
| HTML parsing | `tests/test_parser.py` | Extractors, no-mutation invariant |
| Page-level issue checks | `tests/test_issue_checker.py` | 140+ codes; per-issue trigger conditions |
| Crawl engine flow | `tests/test_crawl_engine.py` | Domain boundary, external link caps |
| Job store | `tests/test_job_store.py`, `test_redis_job_store.py` | CRUD, pagination |
| API contract (core) | `tests/test_api.py` | Health, start, results |
| API contract (fixes) | `tests/test_title_router.py`, `test_heading_router.py`, `test_image_router.py`, `test_batch_optimizer.py`, `test_link_router.py` | Auth, validation, WP safeguards |
| Advisor service | `tests/test_advisor.py`, `test_advisor_routing.py`, `test_advisor_geo_injection.py` | Report rendering, GeoConfig LLM prompt injection |
| AIRouter & Pricing | `tests/test_ai_router.py`, `test_ai_pricing.py` | Singleton fallback, auth mapping, float safety |
| AI Usage Aggregation | `tests/test_usage_aggregation.py`, `test_usage_logger.py` | Token/cost math, isolation, time boundaries |
| GSC Integration | `tests/test_gsc_integration.py` | OAuth flow, API ingest, data mapping |
| Performance Ledger | `tests/test_performance_ledger.py` | Model persistence, batch upsert, lifecycle dates |
| Refresh Trigger | `tests/test_refresh_trigger.py` | Staleness and traffic decay algorithms |
| Schema Generators | `tests/test_geo_faq.py`, `test_geo_schema_integration.py` | Deterministic Schema.org builders, AI-enrichment filters |
| SSRF guards | `tests/test_fetcher.py` | 50 adversarial tests: private IPs, IPv6 mapped |
| WP fixer | `tests/test_wp_fixer.py` | Gutenberg blocks, post discovery |
| Architecture parity | `tests/test_architecture_constraints.py` | issueHelp.js ↔ _CATALOGUE; confidence labels |
| Production safety | `tests/test_production_safety.py` | _is_production detection; fail-closed |

To run the full suite locally:

```bash
./talkingtoad.sh test
```

---

## 10. Known limitations

Features either not shipped, partially working, or with documented caveats.

### 10.1 In-flight work (uncommitted on a feature branch)

- **Multi-page GEO report** — On `feature/multi-page-geo` branch.
  Frontend selects multiple pages, calls
  `GET /api/ai/geo-report/pages` (exists) and
  `POST /api/ai/geo-report` (exists, multi-page payload supported).
  Branch contains additional UI work to render results.

### 10.2 Functional but with caveats

- **AI Bot reference table is a snapshot.** Vendor user agents change.
  Table is reviewed every 6 months.
- **llms.txt has no confirmed retrieval effect.** Labelled **Heuristic** confidence.
- **PDF non-Latin character rendering.** Current Latin-1 encoding
  mangles Chinese, Arabic, Hebrew, etc. Planned upgrade to DejaVu in v3.0.
- **Batch optimizer state is in-memory.** Pauses/resumes survive within
  one backend process but not across restarts.
- **CONTENT_CLOAKING_DETECTED requires Playwright.** Silently skipped if missing.
- **STATISTICS_COUNT_LOW** and **QUOTATIONS_MISSING** evaluate a bounded 1500-word window to prevent unbounded over-counting from long footers or appendices.

### 10.3 Planned for v4.0 & Deferred Infrastructure

- **Multi-tenant Identity Model:** Currently, the system runs safely as a single-tenant deployment for nonprofits using a universal `SYSTEM_CONTEXT_ID`. Per-customer billing, session JWTs, and tenant logical isolation are explicitly **deferred** until a paid-customer launch is imminent.
- **Frontend infrastructure**: toast notification system to replace
  ~54 `alert()` calls; accessibility baseline; code-splitting for
  heavy modals.

---

## Document maintenance

- **Owner:** the development team is the canonical author; this doc is
  updated whenever shipped behaviour changes.
- **Review cadence:** at every release (each `v2.x` increment or v3.0
  release should include a doc review).
- **Source-of-truth precedence:** when this doc and code disagree, the
  code wins — file a discrepancy issue. Acceptance criteria here that
  the code violates are bugs.
- **Related docs:** see `docs/README.md` for the full documentation
  index.

*Last updated: 2026-06-01. Reflects `main` at tag `v2.6.0`.*
