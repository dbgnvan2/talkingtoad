---
status: current
last_reviewed: 2026-05-27
---
# TalkingToad — Functional Specification

> **Status:** v2.3 (rock-solid baseline). Reflects shipped behaviour on
> `main` as of 2026-05-27.
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

### 1.4 Out of scope (today)

- Server log analysis (no admin access to target sites)
- Live AI engine query testing ("does ChatGPT cite this page?") — that's
  a sibling tool's job per v3.0 plan
- Headless browser DOM analysis beyond the optional JS-renderer service
- AI-engine-specific user-agent crawling (only declared bot table is
  used, not actual bot impersonation)
- Multi-tenant / multi-customer (planned for v3.0)

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
- The health score equals `max(0, 100 − Σ impact)` across all issues.
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
  taxonomy.
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

**Steps (Workflow A — existing WP image):**
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
- Health score appears prominently on the cover page.
- The full URL is shown for every flagged page (not truncated).
- A category page break is inserted before each issue title to avoid
  orphaning help text.
- Excel export (alternate to PDF) produces a tabbed workbook with one
  sheet per category.

### Journey F — Run AI-assisted content advisor

**Goal:** User wants AI feedback on a page's content quality for AI
search retrieval.

**Pre-conditions:** `GEMINI_API_KEY` or `OPENAI_API_KEY` is configured.

**Steps:**
1. From the Results page, user opens the GEO Report panel.
2. User selects one or more pages to analyze.
3. User clicks "Generate Report".
4. **Observable:** the AI advisor returns a structured analysis covering
   six properties: source fidelity, factual grounding,
   self-containment, structural fitness, authority signals, honest
   placeholder use.
5. (Optional) User clicks "Generate Rewrite Prompt" → "Apply Rewrite"
   to receive a faithful rewritten version.

**Acceptance criteria:**
- Every finding cites specific page text (no findings without
  evidence).
- The advisor does not score or rank — it provides qualitative
  findings only.
- The rewriter is a single LLM call with low temperature (0.2) and no
  variants.
- If both `OPENAI_API_KEY` and `GEMINI_API_KEY` are set, OpenAI is
  preferred.
- AI usage is logged.

---

## 3. Feature catalogue

High-level inventory. Each row maps to detailed sections later.

| Feature | Capability | Status | Detail section |
|---|---|---|---|
| Async crawl engine | Crawls up to 500 pages with rate limiting + robots.txt respect | ✅ Shipped | §4 |
| 133 issue codes | 130+ SEO and AI-readiness issue checks | ✅ Shipped | §4 |
| Cross-page duplicate detection | Title / meta / title+meta duplicates across pages | ✅ Shipped | §4 |
| Confidence labelling | All 49 AI-readiness codes labelled Established/Reasonable-proxy/Heuristic | ✅ Shipped (M0.2) | §4.6 |
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
| Content Quality Advisor | Structured AI critique with 6 evaluation properties | ✅ Shipped (v2.2) | §6.1 |
| Content Rewriter | Single LLM call rewrite with low temperature | ✅ Shipped (v2.2) | §6.2 |
| Image AI analysis (basic) | Vision-model alt-text suggestion + accuracy scores | ✅ Shipped | §6.3 |
| Image AI analysis (GEO) | Geographic + topic entity-rich alt text and long description | ✅ Shipped | §6.3 |
| Executive summary (AI) | Plain-language 3–5 sentence narrative for PDF report | ✅ Shipped | §6.4 |
| PDF report | 8.5×11 audit report with category sections, action checklist | ✅ Shipped | §7.1 |
| Excel report | Tabbed workbook, one tab per category | ✅ Shipped | §7.2 |
| CSV export | Full or per-category CSV download | ✅ Shipped | §7.3 |
| Verified links | Mark external URLs as known-good to suppress `EXTERNAL_LINK_SKIPPED` | ✅ Shipped | §5.10 |
| Suppressed issue codes | Globally exclude specific codes from health-score calc | ✅ Shipped | §8.4 |
| Exempt anchor URLs | Exclude specific anchor hrefs from `LINK_EMPTY_ANCHOR` flagging | ✅ Shipped | §8.4 |
| Ignored image patterns | Substring patterns to exclude theme SVGs from image checks | ✅ Shipped | §8.4 |
| llms.txt validation | Detect presence and validate `/llms.txt` at site root | ✅ Shipped | §4.6 |
| llms.txt generation | Curated `/llms.txt` from high-value crawled pages | ✅ Shipped | §5.11 |
| AI bot reference table | Robots.txt audit for GPTBot / ClaudeBot / etc. | ✅ Shipped | §4.6 |
| Schema typing per page | JSON-LD type match for inferred page type | ✅ Shipped | §4.6 |
| Citation ingestion endpoint | Receive per-URL AI citation data from sibling tool | ✅ Endpoint exists | §6.5 |
| Multi-page GEO report | Generate GEO report across selected pages | 🟡 On feature/multi-page-geo branch | §10 |
| GSC OAuth integration | Pull AI Overview / AI Mode performance data | ❌ Planned (v3.0 M6) | §10 |
| Multi-provider AI routing | Per-customer keys, DeepSeek/Gemini/OpenAI/Anthropic | ❌ Planned (v3.0 M2) | §10 |
| Token usage tracking | Per-customer billing-ready usage data | ❌ Planned (v3.0 M2) | §10 |

---

## 4. Audit capabilities

The crawler emits **131 distinct issue codes** organised into 11
categories. Each code has: severity (`critical` / `warning` / `info`),
impact (0–10), effort (0–5), priority rank `(impact × 10) − (effort × 2)`,
fixability (`wp_fixable` / `content_edit` / `developer_needed`), and —
for ai_readiness codes — a confidence label.

### 4.0 Audit engine architecture (Cycle K, v2.6 M9.1)

The single canonical list lives in
`api/crawler/checkers/registry.py` under `_CATALOGUE`, with scoring in
`_ISSUE_SCORING` and confidence labels in `_AI_READINESS_CONFIDENCE`. The
top-level module `api/crawler/issue_checker.py` is now a **thin facade**
that re-exports every historically importable name and orchestrates the
per-page checks across a `checkers/` package — every caller
(`engine.py`, the routers, the docs generator, every test) continues to
`from api.crawler.issue_checker import …` unchanged.

`docs/issue-codes.md` is **auto-generated** from `_CATALOGUE` by
`scripts/generate_issue_codes_doc.py`; the CI parity test
`test_issue_codes_doc_matches_catalogue` fails if the generated file
drifts from the registry.

The `checkers/` package contains eleven modules:

| Module | Responsibility |
|---|---|
| `registry.py` | Issue dataclasses, `_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`, `_STOP_WORDS`, size constants, `make_issue()` factory, `_sig_words` / `_titles_mismatch` helpers — single source of truth, ~1,430 lines (mostly the catalogue itself). |
| `metadata.py` | Canonical tag validation (`CANONICAL_*`). |
| `headings.py` | H1 presence, multiple H1s, empty headings, level skips. |
| `links.py` | Broken-link status mapping (`BROKEN_LINK_*`), redirect classification (`REDIRECT_*`), auto-redirect heuristics (trailing-slash, case-normalise). |
| `images.py` | Per-asset file-size limits (`IMG_OVERSIZED`, `PDF_TOO_LARGE`). |
| `security.py` | HTTP-page, mixed content, HSTS, unsafe cross-origin. |
| `crawlability.py` | `NOINDEX_*`, long-paragraph signal, post-crawl AMP HEAD result mapping. |
| `url_structure.py` | URL hygiene — length, casing, embedded spaces, underscores. |
| `ai_readiness.py` | `_run_geo_checks` + every GEO regex/counter helper (statistics, citations, quotations, orphan claims, answer signal, numbered steps). |
| `cross_page.py` | Post-crawl `TITLE_DUPLICATE`, `META_DESC_DUPLICATE`, `TITLE_META_DUPLICATE_PAIR`, `CANONICAL_MISSING` (near-duplicate), `ORPHAN_PAGE`. |
| `__init__.py` | Package docstring. |

The per-page orchestrator (`check_page`) stays in the facade. Future
extraction of its inline blocks into per-domain helpers is tracked
follow-up work; the current shape preserves the existing emission
order, which several tests are coupled to.

**Structural integrity** is locked down by five CI invariants
(`tests/test_class1_invariants.py::TestCatalogueScoringParity`,
`tests/test_architecture_constraints.py::TestAIReadinessConfidenceLabels`):
every scored code has a catalogue entry, every catalogue code has a
score, every `ai_readiness` code has a confidence label, no orphan
confidence label exists for a non-catalogue code, and no confidence
label is attached to a non-`ai_readiness` code.

### 4.1 Metadata category

Title, meta description, OG tags, canonical, favicon. Notable codes:
- `TITLE_MISSING` (critical) — page has no `<title>` tag
- `TITLE_TOO_LONG` (warning) — title >60 chars
- `TITLE_DUPLICATE` (warning) — same title on ≥2 pages
- `META_DESC_MISSING`, `META_DESC_TOO_LONG`
- `OG_TITLE_MISSING`, `OG_DESC_MISSING`, `OG_IMAGE_MISSING`
- `TWITTER_CARD_MISSING` (v1.9.5)
- `CANONICAL_MISSING` — only fires when (a) page has query string, OR
  (b) page is a near-duplicate (same title+meta_desc as another page),
  OR (c) canonical points externally (`CANONICAL_EXTERNAL`)
- `TITLE_H1_MISMATCH` — title and H1 differ significantly

**Verification:** every metadata code is exercised in
`tests/test_issue_checker.py`. Run `pytest tests/test_issue_checker.py -k metadata`.

### 4.2 Heading category

H1 / hierarchy / banner-suppression handling. Notable codes:
- `H1_MISSING` (critical) — no H1 found on the page
- `H1_MULTIPLE` — more than one H1 (excluding banner-detected ones)
- `HEADING_SKIP` — heading hierarchy skips a level (h2 → h4)
- `HEADING_EMPTY` (v1.9.5) — heading tag with no text
- `CONVERSATIONAL_H2_MISSING` — no question-shaped H2 headings (AI-readiness)

The banner-suppression logic (v1.9.2) detects theme-injected banner H1s
via CSS classes (`entry-title`, `page-title`, etc.) and excludes them
from `H1_MULTIPLE` calculations. Suppression is **on** by default and
applies to "first H1" only; single-H1 pages are never modified.

### 4.3 Broken-link / redirect category

External link checking, redirect chain detection, login redirects.
- `BROKEN_LINK_404` (critical), `_410`, `_5XX`, `_503`
- `REDIRECT_LOOP` (critical), `_CHAIN`, `_301`, `_302`
- `EXTERNAL_LINK_TIMEOUT`, `EXTERNAL_LINK_SKIPPED` (the latter for
  domains in the bot-blocking list — can be cleared via "Verify"
  workflow)
- `LINK_EMPTY_ANCHOR` — `<a>` tag with no link text and no
  `aria-label` (fires once per page; extras list every offending href)
- `ANCHOR_TEXT_GENERIC` (v1.9.5) — anchor text is "click here",
  "read more", etc. (15 patterns)

Per-page broken-link source tracking: when a broken link is found, the
crawler records which page discovered it (`discovered_from` dict).
Issues include `source_url` in `extra` for UI display.

### 4.4 Crawlability category

- `ROBOTS_BLOCKED` (critical) — page blocked by robots.txt but still
  reachable
- `NOINDEX_META`, `NOINDEX_HEADER` — distinguishes meta-set noindex
  from header-set noindex (uses `parsed_page.robots_source`)
- `THIN_CONTENT` — fewer than 300 words; suppressed for noindex pages
- `ORPHAN_PAGE` — no internal link points to this page (v1.5)
- `HIGH_CRAWL_DEPTH` — page is >4 clicks from the homepage

### 4.5 Security and URL structure

- `HTTP_PAGE` — page served over HTTP (not HTTPS)
- `MIXED_CONTENT` — HTTPS page loads HTTP resources
- `MISSING_HSTS` — site doesn't send Strict-Transport-Security (one
  emit per host, not per page)
- `UNSAFE_CROSS_ORIGIN_LINK` — `target="_blank"` without rel=noopener
- `WWW_CANONICALIZATION` (v1.9.5) — both www and non-www resolve
  without redirecting
- `URL_UPPERCASE`, `URL_HAS_SPACES`, `URL_HAS_UNDERSCORES`, `URL_TOO_LONG`

### 4.6 AI-readiness category (49 codes)

All ai_readiness codes carry a confidence label per the v2.0 spec:

- **Established** (5 codes) — robots.txt / AI bot directives:
  `AI_BOT_SEARCH_BLOCKED`, `AI_BOT_TRAINING_DISALLOWED`,
  `AI_BOT_USER_FETCH_BLOCKED`, `AI_BOT_DEPRECATED_DIRECTIVE`,
  `AI_BOT_BLANKET_DISALLOW`
- **Reasonable proxy** (17 codes) — schema typing, JSON-LD,
  date metadata, cloaking detection, etc.
- **Heuristic** (27 codes) — llms.txt, passage-quality, content-thinness
  micro-checks

The AI bot reference table (`api/services/ai_bots.py`) is versioned with
a `LAST_REVIEWED` constant. Reports flag if the table is >12 months stale.

### 4.7 Other categories

- **Duplicate** — cross-page title/meta_desc detection
- **Sitemap** — `SITEMAP_MISSING`, `NOT_IN_SITEMAP`
- **Image** — see §5 for fix; the audit identifies oversized
  (>200 KB), oversized intrinsic (>2× rendered), missing alt text, etc.
- **Performance** — page size limit (default 300 KB), excessive
  external script/stylesheet count

---

## 5. Fix capabilities

Fixes are organised into 6 router modules; all WP-touching endpoints
validate that `wp-credentials.json` domain matches the target site.

### 5.1 Title fixes (`title_router.py`)

- `GET /api/fixes/predefined-codes` — list of issue codes the WP
  automation engine knows how to fix
- `POST /api/fixes/bulk-trim-titles?job_id=...` — strip site-name
  suffix from every title in a job using Yoast or Rank Math
- `POST /api/fixes/trim-title-one?page_url=...` — same for one page

**Acceptance criteria:**
- Trim only works if Yoast or Rank Math is detected.
- When the per-page SEO title is empty (Yoast template default), the
  app writes the SEO variable (`%%title%%`) so the title stays correct
  if the page is later renamed.
- Empty proposed values are rejected by the apply layer (data-loss
  guard, verified Defect #5).

### 5.2 Heading fixes (`heading_router.py`, 6 endpoints)

- `GET /find-heading?job_id=...&heading_text=...&level=...` — search
  job pages for matching heading (no WP call)
- `GET /analyze-heading-sources?page_url=...` — diagnose where each
  heading on a page lives (post_content / reusable_block / widget /
  template_part / theme_php)
- `POST /change-heading-level?page_url=...&heading_text=...&from_level=N&to_level=M`
- `POST /change-heading-text?page_url=...&old_text=...&new_text=...&level=N`
  — HTML-escapes the new text to prevent stored XSS
- `POST /bulk-replace-heading?job_id=...&heading_text=...&from_level=N&to_level=M`
  — `to_level=None` is preview mode (returns matched pages without
  touching WP)
- `POST /heading-to-bold?page_url=...&heading_text=...&level=N` —
  converts `<h{N}>X</h{N}>` to `<p><strong>X</strong></p>`

**Acceptance criteria:**
- Gutenberg block headings (`<!-- wp:heading -->` style) are matched
  and modified correctly (verified by 3 tests added in M0.9 P4).
- Heading text comparison uses normalised matching (smart quotes,
  whitespace, dashes equalised).
- `bulk_replace_heading` with `from_level == to_level` is a no-op
  guard, returns matches without changes.

### 5.3 Image metadata fix (`image_router.py`)

- `GET /image-info?image_url=...` — live WP metadata
- `POST /update-image-meta?image_url=...&alt_text=...&title=...&caption=...&description=...`
- `POST /refresh-image-from-wp?image_url=...&job_id=...` — cache-busted
  re-fetch

**Acceptance criteria:**
- Only updates the image's WP attachment if `source_url` matches
  exactly (no fuzzy match — prevents updating wrong image).
- Domain validation enforced (creds for `othersite.com` cannot touch
  `example.com` images).

### 5.4 Image optimization — single

**Workflow A — Existing WP image:**
- `POST /optimize-existing-preview` — preview savings
- `POST /optimize-existing` — full Workflow A
- `POST /optimize-image` — simple wrapper (sane defaults)

**Workflow B — Upload local file:**
- `POST /optimize-upload-preview` (multipart) — preview
- `POST /optimize-upload` (multipart) — full Workflow B

**Acceptance criteria for both workflows:**
- Target file size <200 KB whenever the original was larger.
- WebP format output by default; original format preserved as archive.
- GPS EXIF coordinates injected when `apply_gps=true` and GeoConfig has
  coordinates configured.
- SEO filename generation: `{keyword}-{city}-small.webp` pattern when
  `seo_keyword` provided.
- Workflow A leaves the original WP file untouched (creates new entry).
- Workflow B uploads one file to WP.
- SSRF guard rejects image URLs resolving to private/internal IPs.

### 5.5 Batch image optimization (`batch_optimizer_router.py`)

- `POST /batch-optimize/start` — kick off batch with configurable
  parallel limit (1–10)
- `GET /batch-optimize/{batch_id}/status` — poll progress
- `POST /batch-optimize/{batch_id}/pause` — pause queue
- `POST /batch-optimize/{batch_id}/resume` — resume
- `POST /batch-optimize/{batch_id}/cancel` — stop processing remaining
- `GET /batch-optimize/list` — list recent batches

**Acceptance criteria:**
- Batches survive backend restarts? **No — in-memory** (documented
  limitation). Fine for the single-process container model.
- Parallel limit capped at 10 (Pydantic `le=10`).
- `image_urls` capped at 500 per batch (Pydantic `max_length=500`).
- Already-completed images stay applied after a cancel.

### 5.6 Orphaned media (`orphaned_media_router.py`)

- `GET /orphaned-media/{job_id}` — WP media library entries not
  referenced on any crawled page

**Acceptance criteria:**
- Handles WP size-variants in both directions (crawled URL references
  `image-600x403.jpg`, WP stores `image.jpg`, and vice versa).
- `{job_id}` constrained to UUID4 pattern (catches typos as 422).

### 5.7 Broken-link verification & replacement (`link_router.py`)

- `GET /link-sources?job_id=...&target_url=...` — find pages linking
  to a URL
- `POST /verify-broken-links/{job_id}` — re-check broken targets;
  auto-clear issues for URLs that now return 200
- `POST /replace-link` — swap `old_url` for `new_url` in a WP post
  (works for both classic-editor HTML and Gutenberg blocks)

**Acceptance criteria for verify:**
- Each target URL is checked via `fetch_page` (which has SSRF guard).
- Issues for cleared URLs are deleted from the store.
- Counts returned: `checked`, `still_broken`, `now_ok`, `cleared`,
  `issues_deleted`.

### 5.8 Mark-fixed actions

- `POST /mark-broken-link-fixed` — mark a target URL as resolved
- `POST /mark-anchor-fixed` — surgically remove one href from
  `LINK_EMPTY_ANCHOR.extra.empty_anchor_hrefs` (deletes issue if
  list becomes empty)
- `POST /mark-issue-fixed` — mark issues by code+URL as resolved

### 5.9 Generic inline fix

- `POST /apply-one` — generic single-fix dispatcher for any fixable
  issue code; used by `FixInlinePanel`
- `GET /wp-value?page_url=...&field=...` — current value of a WP field
  for inline comparison

### 5.10 Verified links (`/api/verified-links`)

- `GET` — list all verified URLs
- `POST { url, job_id? }` — mark URL as verified (idempotent); if
  `job_id` provided, also clears matching `EXTERNAL_LINK_SKIPPED`
- `DELETE ?url=...` — unverify

### 5.11 llms.txt generation

- `GET /api/utility/generate-llms-txt?job_id=...` — generate or
  retrieve curated `/llms.txt` content from crawl data
- `POST /api/utility/save-llms-txt { job_id, content }` — persist
  custom content

---

## 6. AI capabilities

All AI calls require either `GEMINI_API_KEY` or `OPENAI_API_KEY`
configured. When both are set, OpenAI is preferred.

### 6.1 Content Quality Advisor (`/api/ai/advisor`)

Single LLM call with structured JSON response. Evaluates a page across
6 properties:
1. **Source Fidelity** — when comparing a rewrite to original, identify
   fabrications, losses, degradations, preserved strengths.
2. **Factual Grounding** — specific facts vs generalities; verdict:
   `grounded` / `weak` / `minimal`.
3. **Self-Containment** — per H2/H3 section: can stand alone or
   requires prior context?
4. **Structural Fitness** — prose vs structure mismatches (e.g.
   enumerates but not in `<ul>`).
5. **Authority Signals** — real citations, missing citations, placeholder
   citations.
6. **Honest Placeholder Use** — placeholders at real gaps vs decorative.

**Acceptance criteria:**
- Every finding cites specific page text (citation required).
- No scoring, no weighting, no metrics — qualitative only.
- Decision flags: `should_generate_prompt = true` if grounded AND has
  issues; `should_generate_diagnosis = true` if minimal.
- Returns a markdown report rendered deterministically from the JSON
  response.

### 6.2 Content Rewriter (`/api/ai/rewriter`, `/api/ai/rewrite-url`)

- `rewriter`: takes `content` + `prompt`, returns one rewrite.
- `rewrite-url`: fetches URL, then rewrites. SSRF-guarded.

**Acceptance criteria:**
- Single LLM call with temperature 0.2.
- No iteration, no variants, no scoring.
- `stopped_by_limit` flag set if token limit hit.

### 6.3 Image AI analysis

- `POST /api/ai/image/analyze-geo` — GEO-optimized alt-text + long
  description with triple-context packet (image bytes + page H1 +
  surrounding text + global GEO settings)
- `POST /api/ai/image/apply-geo-metadata` — applies GEO metadata to WP

**Acceptance criteria for GEO analysis:**
- Alt text 80–125 chars with geographic + topic entities.
- Long description 150–300 words.
- Image URL rejected with SSRF guard if private/internal.
- Either Gemini Vision or OpenAI Vision (GPT-4o) used.

### 6.4 Executive summary (`GET /api/crawl/{id}/executive-summary`)

3–5 sentence plain-language narrative for the PDF report. Cached on the
job record after first generation. Gracefully skipped if no AI key is
configured.

### 6.5 Citation ingestion (`POST /api/jobs/{job_id}/ai-citations`)

Receiving endpoint for a sibling tool that produces per-URL AI citation
data. **Endpoint stubbed; sibling tool not implemented.** Documented in
v3.0 plan M5.

---

## 7. Reporting and export

### 7.1 PDF audit (`GET /api/crawl/{id}/export/pdf`)

Letter (8.5×11), fpdf2-generated. Sections:
- Cover page with domain, health score, summary counts
- (Optional) AI executive summary (1 page)
- Top 10 most-affected pages with severity-coloured issue counts
- One section per issue category with help text
- "What to Do Next" prioritized checklist (top 15 actions, checkboxes)

**Acceptance criteria:**
- Filename includes domain: `TalkingToad-Audit-{domain}.pdf`
- 1-inch margins
- Critical issues red, warnings amber, info blue
- Section breaks prevent orphan titles
- Latin-1 text cleaning (non-Latin chars currently render as `?` —
  known limitation, planned upgrade to DejaVu font in v3.0)

### 7.2 Excel export (`GET /api/crawl/{id}/export/excel`)

openpyxl-generated tabbed workbook:
- Summary tab
- One tab per issue category
- Pages tab with per-page issue counts
- (When citation data present) Citations tab

### 7.3 CSV export

- `GET /api/crawl/{id}/export/csv` — full CSV (all issues)
- `GET /api/crawl/{id}/export/csv/{category}` — category CSV

---

## 8. Non-functional requirements

### 8.1 Security

- **Bearer token auth** on every `/api/*` endpoint except `/api/health`.
- **Production-environment fail-closed:** app refuses to start if
  `VERCEL=1`/`RAILWAY_ENVIRONMENT`/`RENDER=true`/`ENV=production` is
  set and `AUTH_TOKEN` is empty.
- **CORS:** rejects `ALLOWED_ORIGINS=*` with `allow_credentials=True`
  in production.
- **SSRF protection:** every HTTP fetch goes through (or first checks
  via) `is_ssrf_safe()` which rejects private/internal IPs (RFC1918,
  loopback, link-local, IPv6-mapped, AWS metadata `169.254.169.254`).
  Defence-in-depth: `fetch_page()` pre-checks the initial URL AND every
  redirect hop.
- **WP cross-site protection:** every WP-touching endpoint validates
  the credentials file's domain against the request's target domain
  (returns 403 `DOMAIN_MISMATCH`).
- **XSS prevention:** heading text changes HTML-escape user input
  before insertion into WP content.

### 8.2 Performance

- Async crawl engine with concurrent fetches.
- External link checking caps: 50 unique external domains per crawl,
  HEAD with GET fallback on 405.
- 5 MB HTML size cap (responses larger are not parsed).
- Crawl delay configurable per job (default 500 ms, min 200 ms).
- Query variant cap: 50 unique query variants per path before flagging.

### 8.3 Reliability

- **Test suite:** 1240 passing on `main` as of v2.x rock-solid
  baseline. Includes:
  - 105 router contract tests (across 6 fix-domain routers)
  - 50 SSRF adversarial tests
  - 14 production-safety tests
  - Architecture parity tests for catalogue ↔ help ↔ confidence labels
  - CI guard that fails the build if any `/api/*` endpoint has no test
- **Endpoint coverage guard:** `tests/test_endpoint_coverage.py`
  inspects every registered API path; fails build if any path has zero
  test references.

### 8.4 Configurability

- **Suppressed codes:** global setting to exclude specific codes from
  health-score and issue counts.
- **Exempt anchor URLs:** specific hrefs that should not trigger
  `LINK_EMPTY_ANCHOR`.
- **Ignored image patterns:** substring patterns (e.g. `/icon.svg`) to
  exclude theme images from `IMG_ALT_MISSING`.
- **Crawl settings per job:** max pages, crawl delay, sitemap URL
  override.

### 8.5 Deployment

- Backend container (Railway, Fly.io, Render, or self-hosted Docker).
- Frontend on Vercel (or any static host); proxies `/api/*` to backend.
- SQLite (dev) or Upstash Redis (prod). SQLite needs a persistent
  volume for production.
- Health check endpoint `/api/health` returns `{"status": "ok", "version": "2.3"}`.

### 8.6 Stabilization & adversarial hardening (Cycles J-U, v2.6 M9.1)

The v2.6 stabilization phase consolidated 19 distinct vulnerabilities
across the audit engine, found by a multi-round external adversarial
QA. Every vulnerability now has a regression-guard test in
`tests/test_issue_checker.py` (per-domain `Test*Adversarial` classes)
or `tests/test_architecture_constraints.py`.

**Cycles and their scope:**

| Cycle | Module(s) | Vulnerabilities patched |
|---|---|---|
| J | `issue_checker.py` (pre-split) | 3 — banner-H1 None classes; anchor dict missing href; whitespace-only duplicate titles (with `.strip()` semantic upgrade) |
| K | full split into `api/crawler/checkers/` | structural — zero logic change, 11-module split, facade preserved back-compat |
| L | `checkers/ai_readiness.py` | 4 — `_count_statistics` None text; `_ANSWER_SIGNAL_RE` case-insensitivity defeating `[A-Z]`; list-valued `schema_blocks`; whitespace-prefixed external links |
| N | `checkers/crawlability.py` | 2 — None `long_paragraph_count` crash; case-sensitive `robots_source` misdiagnosing NOINDEX_HEADER as NOINDEX_META |
| O | `checkers/cross_page.py` | 2 — self-link evasion of ORPHAN_PAGE; case-sensitive title/desc bucketing evading TITLE_DUPLICATE/META_DESC_DUPLICATE |
| P | `checkers/headings.py` | 2 — `None.strip()` in HEADING_EMPTY; `KeyError: 'text'` in H1_MISSING / HEADING_SKIP diagnostic formatters |
| Q | `checkers/images.py`, `checkers/metadata.py` | 3 — None `content_type` crash; empty `href=""` misclassified as CANONICAL_EXTERNAL; defensive whitespace strip on canonical URL (V3 was not actually exploitable under cpython urlparse but the fix landed as a regression guard) |
| R | `checkers/links.py`, `checkers/url_structure.py`, `checkers/security.py` | 3 — 2-hop redirect chain hiding as trailing-slash fix; literal-space URL paths evading URL_HAS_SPACES; case-sensitive `http://` scheme check missing `HTTP://` |
| S | `tests/test_architecture_constraints.py` | belt-and-braces parity guards (invariants 4 & 5 — orphan confidence labels, confidence labels on wrong-category codes) |
| M | `tests/test_geo_apply_end_to_end.py` | quarantined live-WP integration test to restore deterministic green baseline |
| T | `docs/functional-specification.md`, `docs/thresholds.md` | doc namespace cleanup — stripped stale line numbers, re-routed references to post-split module locations, added §4.0 architecture description |
| U | this section | final compilation sync |

**Defensive patterns now standard across the codebase:**

- **None-tolerant dict reads.** Every `dict.get(key, default)` followed
  by a string operation now uses `(d.get(key) or fallback)` to handle
  the case where the key is present with an explicit `None` value
  (parser artifact for malformed input). The default kwarg only fires
  for missing keys, not None values — easy to miss.
- **Case-insensitive equality where semantics demand it.** Title
  duplicate detection casefolds; HTTP/HTTPS scheme detection
  lowercases; X-Robots-Tag source matching normalises case+whitespace.
- **Whitespace-tolerant parsing.** Empty-string and whitespace-only
  inputs are treated equivalently to missing inputs (title, meta
  description, canonical URL). External-link `href` values are
  stripped before `startswith()` scheme checks.
- **Single-pass list normalisation.** Mixed-type collections (legacy
  strings vs. new dicts in `empty_anchor_hrefs`, list-vs-dict in
  `schema_blocks`) are normalised in one explicit loop that drops
  malformed entries silently rather than crashing the crawl.
- **Self-link filtering in cross-page graphs.** A page linking to
  itself does not contribute to its own discoverability.

**Five CI parity invariants enforced** (see `tests/test_class1_invariants.py::TestCatalogueScoringParity`,
`tests/test_architecture_constraints.py::TestAIReadinessConfidenceLabels`):

1. Every code in `_ISSUE_SCORING` has a `_CATALOGUE` entry.
2. Every `_CATALOGUE` code has an `_ISSUE_SCORING` entry.
3. Every `_CATALOGUE` code with `category=="ai_readiness"` has an
   `_AI_READINESS_CONFIDENCE` entry.
4. Every `_AI_READINESS_CONFIDENCE` code exists in `_CATALOGUE`.
5. Every `_AI_READINESS_CONFIDENCE` code has
   `_CATALOGUE[code].category == "ai_readiness"`.

**Baseline snapshot at end of stabilization:** 1,276 tests passing,
12 skipped, 0 failed. 131 issue codes across 11 categories. 49
ai_readiness codes with confidence labels. Tagged `v2.6-stabilized`.

---

## 9. Verification matrix

For each major feature, the test file(s) that prove it works:

| Feature | Primary test file(s) | Coverage notes |
|---|---|---|
| URL normalization | `tests/test_normaliser.py` | Trailing slash, fragments, UTM stripping, domain boundary |
| robots.txt parsing | `tests/test_robots.py` | Disallow rules, wildcards, crawl-delay |
| Sitemap discovery | `tests/test_sitemap.py` | Standard, sitemap index, gzip, auto-discovery |
| HTML parsing | `tests/test_parser.py` | All extractors, no-mutation invariant (recommended addition per docs-review) |
| Page-level issue checks | `tests/test_issue_checker.py` | 130+ codes; per-issue trigger conditions |
| Crawl engine flow | `tests/test_crawl_engine.py` | Domain boundary, admin skip, external link caps |
| Job store (SQLite) | `tests/test_job_store.py` | CRUD, pagination, deletions |
| Job store (Redis) | `tests/test_redis_job_store.py` | Serialization, summary, fixes |
| API contract (core) | `tests/test_api.py` | Health, start, status, results, pages, cancel |
| API contract (crawl extras) | `tests/test_crawl_router_contracts.py` | rescan, scan-page, mark-fixed, exports, comparison, executive-summary, images |
| API contract (fixes) | `tests/test_title_router.py`, `test_heading_router.py`, `test_image_router.py`, `test_orphaned_media_router.py`, `test_batch_optimizer_router.py`, `test_link_router.py` | All 6 fix-domain routers — auth, validation, NO_CREDENTIALS, DOMAIN_MISMATCH, architecture |
| API contract (misc) | `tests/test_misc_router_contracts.py` | ai, verified, utility extras, geo |
| Endpoint coverage guard | `tests/test_endpoint_coverage.py` | CI fails if any /api/* path has zero test references |
| Advisor auth | `tests/test_advisor_auth.py` | All 6 advisor endpoints reject unauth (19 tests) |
| Advisor service logic | `tests/test_advisor.py`, `test_advisor_calibration.py` | Report rendering, decision flags |
| Rewriter | `tests/test_rewriter.py` | LLM call, token limit, error handling |
| SSRF guards | `tests/test_fetcher.py` | 50 adversarial tests: private IPs, IPv6 mapped, DNS rebinding, redirect chains |
| WP fixer | `tests/test_wp_fixer.py` | change_heading_text (incl. 3 Gutenberg block tests added in M0.9 P4), find_post_by_url, find_attachment_by_url |
| WP domain validation | `tests/test_wp_domain_validation.py` | Helpers + endpoint-level (5 skipped for endpoints implemented in M0.12) |
| Image optimization | `tests/test_image_optimization.py` | EXIF injection, SEO filename, validation |
| Batch optimizer | `tests/test_batch_optimizer.py` | Create, controls, status, cleanup (30 tests) |
| GEO image analysis | `tests/test_geo_image_*.py` | Multi-file coverage of GEO prompt workflow |
| Architecture parity | `tests/test_architecture_constraints.py` | issueHelp.js ↔ _CATALOGUE; AI-readiness confidence labels |
| Production safety | `tests/test_production_safety.py` | _is_production detection; AUTH_TOKEN + CORS fail-closed |

Total: **1240 passing tests** on `main` as of v2.3 baseline.

To run the full suite locally:

```bash
./talkingtoad.sh test
```

To run a specific verification scope:

```bash
./talkingtoad.sh test -k auth        # auth-related tests only
./talkingtoad.sh test tests/test_fetcher.py  # SSRF tests
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
- **Frontend defects #7, #8, #10** (FixManager confirmations, silent
  load errors, silent CSV export errors) — fold into the v2.7 M10
  toast/dialog system when those land.

### 10.2 Functional but with caveats

- **AI Bot reference table is a snapshot.** Vendor user agents change.
  Table is reviewed every 6 months; reports surface the
  `LAST_REVIEWED` date.
- **llms.txt has no confirmed retrieval effect.** Per Google's own
  documentation, no AI vendor has publicly confirmed it affects
  citation. The check is shipped because the file is cheap to add, but
  the issue is labelled **Heuristic** confidence.
- **PDF non-Latin character rendering.** Current Latin-1 encoding
  mangles Chinese, Arabic, Hebrew, etc. Planned upgrade to DejaVu in v3.0.
- **Batch optimizer state is in-memory.** Pauses/resumes survive within
  one backend process but not across restarts.
- **Vercel serverless deployment is deprecated.** v2.3 uses Railway for
  the backend because Vercel's `BackgroundTasks` freezes when the
  function returns. See `deployment-railway.md`.
- **CONTENT_CLOAKING_DETECTED requires Playwright.** When Playwright
  isn't installed, the check silently does not fire — but it does NOT
  emit a skip marker (known issue, docs-review Section 2 item).
- **STATISTICS_COUNT_LOW** scans only the first ~150 words + headings
  (known limitation, docs-review Section 2 item).

### 10.3 Planned for v3.0 (not shipped)

See `PLAN-V3.0.md` for the full plan; high points:

- **AI multi-provider routing** with per-customer keys (DeepSeek for
  text, Gemini Flash for vision, GPT-4o/Sonnet for premium tier)
- **Token usage tracking** for billing
- **GSC OAuth integration** (pull AI Overview / AI Mode performance
  data into reports)
- **Sibling phrase tool integration** — citation data ingestion is
  ready (endpoint exists), sibling tool not built
- **Content freshness suite** (visible-on-page date extraction, aged-
  stat detection, page-type-aware recommendations)
- **Schema-visible-content alignment check** (Google-stated
  requirement)
- **Refactor work** — `issue_checker.py` was split into the
  `api/crawler/checkers/` package in v2.6 M9.1 (Cycle K); the top-level
  module is now a 518-line facade. `Results.jsx` (1,831) and `crawl.py`
  (1,859) remain known refactor candidates; code works as-is.
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

*Last updated: 2026-05-28. Reflects `main` at tag `v2.6-stabilized` (post-Cycle-U). The 19 vulnerability fixes and structural split landed in Cycles J-U; see §8.6 for the consolidated summary and `git log` for per-cycle detail.*
