---
status: current
last_reviewed: 2026-06-01
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

The crawler emits **152 distinct issue codes** organised into 13
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
| `cross_page.py` | Post-crawl `TITLE_DUPLICATE`, `META_DESC_DUPLICATE`, `CANONICAL_MISSING`, `ORPHAN_PAGE`. |
| `semantic_html.py` | Agent-readiness WP3 — `NON_SEMANTIC_BUTTON`, `INTERACTIVE_NO_ACCESSIBLE_NAME`, `LANDMARK_MAIN_MISSING`, `LANDMARK_NAV_MISSING`. |
| `__init__.py` | Package docstring. |

Agent-readiness WP4 (`PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK`) lives in
`links.py`, WP2 (`JS_DEPENDENT_NAVIGATION`) in `crawlability.py`, and WP5
(`SCHEMA_ORG_MISSING`, `CONTACT_INFO_NOT_IN_HTML`) in `metadata.py`. The
underlying signals are pre-computed on `ParsedPage` at parse time.

### 4.0.1 Scoring model R5 (2026-07-06)

The R5 scoring change (`scoring_model_version = "2026-07-06-r5"`) finished the safe remainder of the
external scoring spec on top of the R3/R4 calibration. It changes **how the health score is computed**,
not which codes exist — all 152 codes are retained (the spec's proposed merges/deletions were declined;
the former "merge" clusters are re-cast as suppress-children). Per-target occurrence counting (external §2)
and the proposed cap increase to 25 were both declined by the owner; the category cap stays **20**.

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

**Deploy note.** Site-scoping the TLS codes and the noindex reduction mean multi-page HTTP-site and
noindexed-page scores **rise once** under R5. A before/after crawl (per the R3 precedent) is the manual
deploy gate; monotonicity is preserved (`test_agent_score_monotonic_non_increasing` stays green).

### 4.1 Metadata category

Title, meta description, OG tags, canonical, favicon. Notable codes:
- `TITLE_MISSING` (critical) — page has no `<title>` tag
- `TITLE_TOO_LONG` (warning) — title >60 chars
- `TITLE_DUPLICATE` (warning) — same title on ≥2 pages
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
- `ORPHAN_PAGE` — no internal link points to this page
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
  - `SCHEMA_VISIBLE_MISMATCH` — A value declared in JSON-LD structured data does not appear in the page's visible text.
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

---

## 7. Reporting and export

### 7.1 PDF audit (`GET /api/crawl/{id}/export/pdf`)

Letter (8.5×11), fpdf2-generated. Sections:
- Cover page with domain, health score, summary counts
- (Optional) AI executive summary
- Top 10 most-affected pages
- Category sections with help text and evidence tiers
- "What to Do Next" checklist

**Acceptance criteria:**
- AI-readiness issues display a colour-coded evidence-tier pill (Established/Reasonable proxy/Heuristic) below the issue title, powered by the issue's `confidence_label`.
- Critical issues appear in red, warnings in amber, info in blue.

### 7.2 Excel export (`GET /api/crawl/{id}/export/excel`)

openpyxl-generated tabbed workbook:
- Summary tab, Pages tab, Citations tab
- One tab per issue category
- The "AI Readiness" sheet features an explicit **Confidence** column mapping to the AI-readiness taxonomy.

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
