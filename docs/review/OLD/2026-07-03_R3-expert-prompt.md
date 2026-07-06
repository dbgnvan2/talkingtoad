# Expert evaluation request — TalkingToad SEO/GEO issue-scoring calibration

> **How to use (from the repo owner):** Paste this entire document into a capable LLM agent
> (e.g. GPT-5, Gemini, or a fresh Claude session) and ask it to complete the task. I am running
> this by **two independent agents** and will compare their answers, so please be decisive, show
> your reasoning, and flag where you are uncertain. You do NOT have repo access — everything you
> need is in this brief, including a one-line description of every check.

## Who you are
You are a senior technical-SEO **and** generative-engine-optimization (GEO/AI-search) expert with
hands-on knowledge, **as of mid-2026**, of how Google ranking and how AI answer engines (ChatGPT,
Claude, Perplexity, Google AI Overviews) select and cite web content. You are calibrating the
issue-severity scoring for an automated SEO/GEO auditing tool.

## The tool and its audience
**TalkingToad** crawls a website, runs 151 checks, and produces a per-page and site-wide "health
score" plus a prioritized issue list. **Typical target site:** a **nonprofit**, **20–100 pages**
(some up to ~500), **WordPress with a page builder** (Elementor/Divi/Gutenberg), **no developer on
staff**, maintained part-time by a volunteer or non-technical staffer on a small budget. Calibrate
"effort" and priority with that maintainer in mind; scores must be **trustworthy and defensible**,
not inflated.

## The exact scoring model (this is how it works — do not assume)
- Every **code** has **impact** (integer 0–10) and **effort** (integer 0–5).
- **Page Health = max(0, 100 − Σ(impact of every issue row on that page))**. Additive, uncapped
  until the 0 floor.
- **Site Health = mean of all pages' Page Health** (a page with no issues scores 100).
- **priority_rank = impact×10 − effort×2** — orders the issue list only. On the 0–10/0–5 scales,
  impact×10 spans 0–100 and effort×2 spans 0–10, so effort can move an item's rank by at most 10
  points while impact dominates.
- **severity** (critical / warning / info) exists per code (shown in the table) but is **NOT
  currently part of the health score** — it only affects sort order.

### Counting rule (critical for judging the formula — task 4)
Most checks emit **one issue per page**, carrying an occurrence count in their data (e.g.
`IMG_ALT_MISSING` is a single issue with `missing_alt_count=12`; the impact is deducted **once**).
BUT the **per-target** checks — `BROKEN_LINK_404/410/503/5XX`, `REDIRECT_*`, `EXTERNAL_LINK_TIMEOUT`
— emit **one issue per offending link**, all attributed to the source page, and the score sums
every issue row on a page with **no dedup by code**. So a page with **five** broken 404 links loses
**5 × 10 = 50 points** from that one check alone. Factor this into whether the additive formula is
sound and whether per-occurrence checks need per-page caps.

### Informational-by-design codes (do NOT assign nonzero impact)
Three codes are intentionally **impact 0** — they are positive/informational findings, not problems:
`AI_CITED_PAGE`, `AI_BOT_TRAINING_DISALLOWED` (blocking training bots is a legitimate owner choice),
`AI_BOT_TABLE_STALE` (a maintenance reminder). Keep them at 0; do not "fix" them.

### On the impact-10 ceiling
Current data uses impact **10** for page-fatal / indexing-blocking issues (`BROKEN_LINK_404`,
`NOINDEX_META`, `NOINDEX_HEADER`, `REDIRECT_LOOP`). State whether your model keeps a distinct **10**
tier (e.g. "removes the page from search entirely") or folds the ceiling to 9 — and apply your choice
consistently.

## The problem you are solving
The 151 impact values were **hand-set over time** and are inconsistent. Only **62 of 151** codes
currently carry an evidence-**confidence** tier (shown in the table; the other 89 show `—`). The
tiers:
- **Established** — vendor-confirmed effect (Google/OpenAI/Anthropic documented behavior).
- **Reasonable proxy** — strong industry consensus / partial vendor confirmation.
- **Heuristic** — best-practice consensus only, no vendor confirmation.

Two competing calibration models — **stated with their weaknesses symmetrically**:
- **Model A — single cap:** impact capped by confidence tier (Heuristic ≤3, Reasonable proxy ≤6,
  Established ≤9). *Strength:* simple, hard to game. *Weakness:* collapses two different things —
  a single-study-but-**measured** effect gets floored alongside a pure guess, losing information.
- **Model B — two axes:** impact derived from **confidence** × **effect_size**, with an exception
  lane for heuristics backed by ≥1 controlled study. *Strength:* expressive; separates "is it real"
  from "how big." *Weakness:* for Heuristic-tier checks the effect_size is itself a guess, so you
  multiply two uncertain numbers and risk **manufacturing false precision**.

Pick A, B, or a concrete synthesis — and defend it against its own weakness.

### effect_size scale (use THIS common ruler so answers are comparable)
Do not invent your own scale. Rate each check's effect **when the problem is present**:
- **large** — can gate the page's indexing or AI-citation eligibility outright (e.g. noindex, no
  crawlable content).
- **moderate** — a measurable effect on ranking or citation probability, but not gating.
- **small** — marginal, indirect, or cosmetic.
You may argue the anchors are wrong, but fill the table against them.

## Your task
1. **Recommend a model** (A / B / synthesis) and define the exact **derivation** (e.g. a 3×3
   confidence×effect_size → impact matrix with the integer each cell yields, plus how the exception
   lane and any 10-tier work).
2. **Assign to ALL 151 codes** a **recommended_confidence** and **recommended_effect_size**, then the
   **derived_impact** your model produces. **Every one of the 89 `—` rows must get a tier — none
   blank.** Also correct any of the 62 existing tiers you believe are mislabeled (that's why the CSV
   has both current and recommended confidence columns).
3. **Flag every code whose current impact you consider indefensible**, with the corrected value.
4. **Formula soundness:** should **severity** feed the health score? Is the **additive, uncapped**
   page formula sound given the counting rule above? Concretely: a page with ten moderate (impact-4)
   issues and a page with two critical (impact-10) issues can both floor near the same score — and a
   page with five 404s loses 50 from one check. Recommend keep / per-category caps / diminishing
   returns / per-occurrence caps / severity-weighting.
5. **Priority ordering:** for the non-technical nonprofit maintainer, should **effort** weigh more so
   real "quick wins" surface first (today it moves rank ≤10 points vs impact's 100)? Propose a
   formula if so.
6. **Overlap / double-counting (distinct deliverable):** the additive formula stacks penalties when
   one underlying condition trips multiple codes. Scan the table and list every **cluster of codes
   that would co-fire on the same page for a single root cause** (there are several). For each,
   recommend how to avoid double-counting (suppress a child, merge, or graded parent).
7. Note where an answer **depends on fast-moving vendor behavior**; give a per-row
   **reviewer_confidence** (H/M/L) in the CSV.

## Verified vendor facts (mid-2026) — use these; do not contradict without a source
- **AI-bot robots.txt compliance is vendor-specific:** Anthropic honors robots.txt on **all** its
  bots incl. **Claude-User**; OpenAI says robots.txt "may not apply" to **ChatGPT-User**;
  **Perplexity-User** ignores it. Search bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot) vs
  training bots (GPTBot, ClaudeBot, CCBot) vs user-fetch agents are distinct categories.
- **301 and 302 both pass PageRank** (Google, since 2016). A 302's only real downside is
  **canonicalization ambiguity** — Google may keep the *source* URL canonical, leaving link equity
  split across both URLs rather than consolidated on the target; not outright equity loss.
- **Google FAQ rich results were fully removed 2026-05-07** (restricted to gov/health since 2023).
  FAQ structured data still helps Google *understand* a page but yields no rich result. **HowTo**
  rich results were deprecated in 2023.
- **llms.txt**: ~5-10% adoption; Google declined to support it; Anthropic/Perplexity signaled
  support; **no measured citation lift** to date.
- **rel=noopener** is implied by browsers for `target="_blank"` since ~2021 (reverse-tabnabbing
  largely neutralized regardless of markup).
- GEO "answer-first / statistics / cite-your-sources" guidance traces largely to the **Aggarwal
  et al. GEO study** — one paper, ~1,000 queries on a single LLM generation. Measured effects (a
  genuine signal) but a **narrow evidentiary basis**: measured-but-limited, not established consensus.

## Required output format
1. **Methodology** (≤500 words): model recommendation defended against its own weakness; the exact
   derivation/matrix; your stance on severity, the page formula + counting rule (task 4), and
   priority ordering (task 5).
2. **Full table of all 151 codes as a CSV code block** (```csv fenced) — NOT a markdown table.
   Exact header:
   `code,current_confidence,recommended_confidence,recommended_effect_size,derived_impact,current_impact,impact_changed,confidence_changed,reviewer_confidence,rationale`
   Rules: all 151 rows; no blank `recommended_confidence`; `impact_changed`/`confidence_changed` =
   yes/no; `reviewer_confidence` = H/M/L; `rationale` ≤ 12 words with **no commas** (use semicolons).
   **Process the codes in the order given; do NOT batch-assign tiers by category — judge each check
   on its own.** (Splitting into two turns — methodology + first ~75 rows, then the rest — is fine
   if it improves quality; keep the same CSV header.)
3. **Overlap clusters** (task 6): each cluster + its de-duplication recommendation.
4. **Top 20 most-consequential changes**, ranked, each with a 1–2 sentence justification.
5. **Open questions / where I'd want more data** — be honest about the limits of your judgment.

## The 151 codes (current values + what each checks)
`impact`/`effort`/`severity` are current; `confidence` is `—` for the 89 codes with no tier yet.

| code | category | severity | impact | effort | confidence | what it checks |
|---|---|---|---|---|---|---|
| AI_BOT_BLANKET_DISALLOW | ai_readiness | critical | 9 | 1 | Established | robots.txt blocks all bots with User-agent: * / Disallow: / |
| AI_BOT_DEPRECATED_DIRECTIVE | ai_readiness | warning | 2 | 1 | Established | robots.txt references a deprecated AI bot user agent |
| AI_BOT_NO_AI_DIRECTIVES | ai_readiness | info | 1 | 1 | Reasonable proxy | robots.txt has no explicit directives for known AI bots |
| AI_BOT_SEARCH_BLOCKED | ai_readiness | warning | 8 | 1 | Established | A major AI search bot is disallowed in robots.txt |
| AI_BOT_TABLE_STALE | ai_readiness | info | 0 | 1 | Heuristic | Internal AI bot reference table has not been reviewed in >12 months |
| AI_BOT_TRAINING_DISALLOWED | ai_readiness | info | 0 | 1 | Established | An AI training bot is disallowed in robots.txt |
| AI_BOT_USER_FETCH_BLOCKED | ai_readiness | warning | 4 | 1 | Established | An AI user-fetch bot is disallowed in robots.txt |
| AI_CITED_PAGE | ai_readiness | info | 0 | 0 | Established | This page has been cited by AI engines in the last 30 days, indicating established AI v... |
| AI_CONTENT_NOT_IN_TEXT | ai_readiness | warning | 4 | 2 | Reasonable proxy | Important content on this page is not in textual form — it is carried by |
| AI_HIGH_VALUE_UNCITED | ai_readiness | warning | 4 | 2 | Reasonable proxy | This healthy, content-rich page has zero AI citations despite recent data, suggesting a... |
| AI_MAIN_CONTENT_LOW_RATIO | ai_readiness | warning | 2 | 1 | Heuristic | The main content area contains less than 40% of the page's visible text. |
| AI_NO_VISUAL_COMPANION | ai_readiness | info | 1 | 1 | Reasonable proxy | A substantial text page (article/service/FAQ) has no images or video to |
| AI_PREVIEW_BLOCKED_AT_BOT | ai_readiness | info | 3 | 1 | Established | An X-Robots-Tag directive specifically blocks an AI crawler |
| AI_PREVIEW_SUPPRESSED | ai_readiness | info | 3 | 1 | Established | An X-Robots-Tag response header suppresses this page's search/AI preview |
| AI_TXT_MISSING | ai_readiness | info | 1 | 1 | Heuristic | No /ai.txt file found at site root |
| AMPHTML_BROKEN | crawlability | warning | 4 | 3 | — | Page declares an AMP version via <link rel="amphtml"> but the AMP URL is not reachable |
| ANCHOR_TEXT_GENERIC | metadata | warning | 4 | 2 | — | Links use non-descriptive anchor text like 'click here' or 'read more' |
| AUTHOR_BYLINE_MISSING | ai_readiness | warning | 4 | 2 | Reasonable proxy | Blog or article page has no author byline, rel=author, or JSON-LD author field |
| BLOG_SECTIONS_MISSING | ai_readiness | warning | 5 | 2 | Heuristic | Blog or article page lacks sufficient heading structure for AI citation anchors |
| BROKEN_LINK_404 | broken_link | critical | 10 | 2 | — | Link destination returns 404 Not Found |
| BROKEN_LINK_410 | broken_link | critical | 8 | 2 | — | Link destination returns 410 Gone |
| BROKEN_LINK_503 | broken_link | warning | 4 | 3 | — | Link destination returns 503 — may be temporarily down or blocking automated checks |
| BROKEN_LINK_5XX | broken_link | critical | 7 | 2 | — | Link destination returns a server error |
| CANONICAL_EXTERNAL | metadata | warning | 5 | 3 | — | Canonical points to a different domain |
| CANONICAL_MISSING | metadata | warning | 6 | 2 | — | No canonical tag — page has query strings or is a near-duplicate |
| CANONICAL_SELF_MISSING | metadata | info | 5 | 1 | — | Indexable page has no canonical tag — consider adding a self-referencing canonical |
| CENTRAL_CLAIM_BURIED | ai_readiness | warning | 5 | 3 | Heuristic | The page's main claim or answer does not appear in the first 150 words |
| CHUNKS_NOT_SELF_CONTAINED | ai_readiness | warning | 5 | 4 | Heuristic | More than half of the page's H2/H3 sections are not understandable in isolation |
| CITATIONS_MISSING_SUBSTANTIAL_CONTENT | ai_readiness | info | 3 | 2 | Reasonable proxy | Page has 200+ words but no citations or source attribution |
| CITATIONS_ORPHANED | ai_readiness | info | 2 | 1 | Heuristic | Page has citations without surrounding context |
| CITATIONS_SOURCES_INACCESSIBLE | ai_readiness | warning | 4 | 3 | Heuristic | Page cites sources that are broken or inaccessible |
| CODE_BLOCK_MISSING_TECHNICAL | ai_readiness | warning | 4 | 2 | Heuristic | Technical how-to/guide page with numbered steps has no <pre> or <code> blocks |
| COMPARISON_TABLE_MISSING | ai_readiness | info | 3 | 2 | Heuristic | Page contains comparison language ('vs', 'versus', 'compared to') but no table |
| CONTACT_INFO_NOT_IN_HTML | ai_readiness | warning | 4 | 2 | Heuristic | The homepage's contact details (address, phone, or email) appear only inside |
| CONTENT_CLOAKING_DETECTED | ai_readiness | warning | 8 | 4 | Reasonable proxy | Rendered content appears to shift the page's topic versus raw HTML — possible cloaking |
| CONTENT_DATE_STALE_VISIBLE | ai_readiness | warning | 4 | 2 | Reasonable proxy | Visible/declared modified date is old enough to read as stale for its page type |
| CONTENT_IMAGE_HEAVY | ai_readiness | info | 2 | 3 | Heuristic | Page has significantly more images than text sections |
| CONTENT_NOT_EXTRACTABLE_NO_TEXT | ai_readiness | warning | 6 | 4 | Reasonable proxy | Page has no visible text — only images, video, or interactive media |
| CONTENT_STALE | crawlability | info | 3 | 3 | — | Page content has not been modified in over 12 months |
| CONTENT_STAT_OUTDATED | ai_readiness | info | 2 | 1 | Heuristic | Body text references a year that is ≥24 months old without mentioning the current year. |
| CONTENT_THIN | ai_readiness | warning | 4 | 3 | Reasonable proxy | Page has very little text (under 100 words) |
| CONTENT_UNSTRUCTURED | ai_readiness | warning | 3 | 2 | Heuristic | Page has substantial text but no heading structure |
| CONVERSATIONAL_H2_MISSING | ai_readiness | info | 4 | 2 | Heuristic | H2 headings do not use conversational interrogatives (How, What, Why) |
| DATE_MODIFIED_MISSING | ai_readiness | info | 2 | 1 | Reasonable proxy | Blog or article page has no last-modified date in JSON-LD |
| DATE_PUBLISHED_MISSING | ai_readiness | info | 3 | 1 | Reasonable proxy | Blog or article page has no publication date in JSON-LD or meta tags |
| DOCUMENT_PROPS_MISSING | ai_readiness | warning | 4 | 2 | Reasonable proxy | PDF is missing internal Title or Subject metadata |
| EXTERNAL_CITATIONS_LOW | ai_readiness | warning | 5 | 2 | Reasonable proxy | 500+ word page has no outbound links to external authoritative sources in body text |
| EXTERNAL_LINK_SKIPPED | broken_link | info | 2 | 1 | — | Link not verified — social media platforms block automated checks |
| EXTERNAL_LINK_TIMEOUT | broken_link | info | 3 | 1 | — | External link did not respond — destination may be slow or unavailable |
| FAQ_SCHEMA_MISSING | ai_readiness | info | 2 | 2 | Reasonable proxy | Page has an FAQ section but no FAQPage JSON-LD schema |
| FAVICON_MISSING | metadata | info | 3 | 2 | — | No favicon found (homepage only) |
| FIRST_VIEWPORT_NO_ANSWER | ai_readiness | warning | 5 | 2 | Heuristic | First 200 words contain no direct answer signal (definition, TL;DR, summary phrase) |
| GEO_SUMMARY_BURIED | ai_readiness | warning | 5 | 3 | Heuristic | The first paragraph or list does not lead its H2 or H3 section — the core |
| H1_MISSING | heading | critical | 6 | 1 | — | No H1 tag found on page |
| H1_MULTIPLE | heading | warning | 5 | 2 | — | More than one H1 on the page |
| HEADING_EMPTY | heading | warning | 4 | 1 | — | One or more heading tags have no text content |
| HEADING_SKIP | heading | warning | 4 | 3 | — | Heading levels skip (e.g., H1 → H3) |
| HIGH_CRAWL_DEPTH | crawlability | warning | 5 | 3 | — | Page is more than 4 clicks from the homepage |
| HTTPS_REDIRECT_MISSING | security | critical | 9 | 2 | — | HTTP version of the site does not redirect to HTTPS |
| HTTP_PAGE | security | critical | 9 | 2 | — | Page is served over HTTP, not HTTPS |
| IMG_ALT_DUP_FILENAME | image | warning | 3 | 1 | — | Image alt text matches the filename |
| IMG_ALT_GENERIC | image | warning | 4 | 1 | — | Image alt text uses a generic term like 'image', 'photo', or 'picture' |
| IMG_ALT_MISSING | image | warning | 5 | 2 | — | One or more images are missing an alt attribute or have empty/blank alt text |
| IMG_ALT_MISUSED | image | warning | 3 | 2 | — | Alt text usage is incorrect for image type (decorative image has alt text) |
| IMG_ALT_TOO_LONG | image | warning | 2 | 1 | — | Image alt text is too long (over 125 characters) |
| IMG_ALT_TOO_SHORT | image | warning | 3 | 1 | — | Image alt text is too short (under 5 characters) |
| IMG_BROKEN | image | critical | 8 | 2 | — | Image src URL returns an error response (4xx/5xx) |
| IMG_DUPLICATE_CONTENT | image | info | 2 | 2 | — | Same image content used under multiple URLs |
| IMG_FORMAT_LEGACY | image | info | 2 | 2 | — | Image uses legacy format (JPEG/PNG/GIF) where WebP would save significant space |
| IMG_NO_SRCSET | image | info | 2 | 3 | — | Large image lacks srcset for responsive delivery |
| IMG_OVERSCALED | image | warning | 4 | 3 | — | Image intrinsic size is more than 2x its display size (wasted bandwidth) |
| IMG_OVERSIZED | image | warning | 5 | 2 | — | Image file exceeds 200 KB |
| IMG_POOR_COMPRESSION | image | warning | 4 | 2 | — | Image has poor compression efficiency (high bytes per pixel) |
| IMG_SLOW_LOAD | image | warning | 4 | 2 | — | Image takes too long to load (over 1 second) |
| INTERACTIVE_NO_ACCESSIBLE_NAME | semantic_html | warning | 4 | 2 | — | An interactive element (button, link, or form field) has no accessible name — |
| INTERNAL_NOFOLLOW | crawlability | warning | 5 | 2 | — | Blocked Internal Link |
| INTERNAL_REDIRECT_301 | redirect | info | 4 | 1 | — | Internal page URL redirects with a 301 — links should point to the final URL |
| JSON_LD_INVALID | ai_readiness | warning | 4 | 2 | Reasonable proxy | A JSON-LD block is present but missing @type or @context (invalid schema) |
| JSON_LD_MISSING | ai_readiness | warning | 7 | 2 | Reasonable proxy | No JSON-LD structured data found on this indexable page |
| JS_DEPENDENT_NAVIGATION | rendering | warning | 5 | 3 | — | The page's primary navigation links are not present in the server-rendered |
| JS_RENDERED_CONTENT_DIFFERS | ai_readiness | warning | 6 | 4 | Reasonable proxy | Rendered page contains substantially more content than raw HTML (>20% more tokens) |
| LANDMARK_MAIN_MISSING | semantic_html | info | 2 | 2 | — | Page has no <main> landmark (or role="main") identifying its primary content |
| LANDMARK_NAV_MISSING | semantic_html | info | 2 | 2 | — | Page has no <nav> landmark (or role="navigation") identifying its navigation |
| LANG_MISSING | metadata | warning | 6 | 1 | — | Page is missing the lang attribute on the <html> element |
| LINK_EMPTY_ANCHOR | metadata | warning | 7 | 2 | — | Link has no visible anchor text — screen readers and search engines cannot describe its... |
| LINK_PROFILE_PROMOTIONAL | ai_readiness | info | 4 | 2 | Heuristic | Over 80% of outbound body-text links point to the same organisation's own domains |
| LLMS_TXT_INVALID | ai_readiness | warning | 2 | 2 | Heuristic | /llms.txt format is invalid |
| LLMS_TXT_MISSING | ai_readiness | info | 3 | 1 | Heuristic | No llms.txt found at root |
| LOGIN_REDIRECT | crawlability | info | 2 | 1 | — | Page redirects to a login screen |
| META_DESC_DUPLICATE | metadata | warning | 4 | 2 | — | Same meta description on multiple pages |
| META_DESC_MISSING | metadata | critical | 7 | 1 | — | No meta description |
| META_DESC_TOO_LONG | metadata | warning | 3 | 1 | — | Meta description over 160 characters |
| META_DESC_TOO_SHORT | metadata | warning | 4 | 1 | — | Meta description under 70 characters |
| META_REFRESH_REDIRECT | redirect | warning | 5 | 2 | — | Page uses a <meta http-equiv="refresh"> tag to redirect users |
| MISSING_HSTS | security | info | 4 | 2 | — | HTTPS page is missing the Strict-Transport-Security header |
| MISSING_VIEWPORT_META | crawlability | warning | 6 | 1 | — | Page is missing the viewport meta tag |
| MIXED_CONTENT | security | warning | 6 | 2 | — | HTTPS page loads resources over HTTP |
| NOINDEX_HEADER | crawlability | warning | 10 | 2 | — | Page has a noindex HTTP header |
| NOINDEX_META | crawlability | warning | 10 | 1 | — | Page has a noindex meta tag |
| NON_SEMANTIC_BUTTON | semantic_html | warning | 4 | 3 | — | A clickable control is built from a <div> or <span> with no button/link role |
| NOT_IN_SITEMAP | crawlability | info | 4 | 1 | — | Crawlable page not listed in sitemap |
| OG_DESC_MISSING | metadata | info | 3 | 1 | — | Open Graph description tag missing |
| OG_IMAGE_MISSING | metadata | info | 3 | 1 | — | Open Graph image tag (og:image) is missing |
| OG_TITLE_MISSING | metadata | info | 4 | 1 | — | Open Graph title tag missing |
| ORPHAN_CLAIM_TECHNICAL | ai_readiness | warning | 6 | 2 | Heuristic | Technical/how-to page has 3+ factual claims not paired with a source link or attribution |
| ORPHAN_PAGE | crawlability | warning | 6 | 2 | — | Page has no internal links pointing to it — search engines may not discover it |
| PAGE_SIZE_LARGE | crawlability | warning | 5 | 3 | — | HTML page response is unusually large — slower to load, especially on mobile connections |
| PAGE_TIMEOUT | crawlability | warning | 6 | 3 | — | Page did not respond within the timeout period |
| PAGINATION_LINKS_PRESENT | crawlability | info | 2 | 2 | — | Page declares rel="next" or rel="prev" pagination link elements |
| PARA_TOO_LONG | crawlability | info | 4 | 2 | — | One or more paragraphs exceed 150 words, making content harder to scan and extract |
| PDF_TOO_LARGE | crawlability | warning | 4 | 2 | — | PDF file exceeds 10 MB |
| PLACEHOLDER_LINK | broken_link | critical | 7 | 2 | — | A navigational call-to-action links nowhere — its href is "#" or |
| PROMOTIONAL_CONTENT_INTERRUPTS | ai_readiness | info | 3 | 3 | Heuristic | Mid-article sections classified as promotional interrupt the content flow |
| QUERY_COVERAGE_WEAK | ai_readiness | warning | 5 | 2 | Heuristic | Page H1 topic terms are under-represented in the intro or section headings — |
| QUOTATIONS_MISSING | ai_readiness | warning | 4 | 2 | Heuristic | 500+ word page contains no direct quotations from named sources |
| RAW_HTML_JS_DEPENDENT | ai_readiness | warning | 6 | 3 | Reasonable proxy | Page raw HTML is a JavaScript app shell with near-zero visible text |
| REDIRECT_301 | redirect | info | 3 | 2 | — | Page returns a permanent redirect |
| REDIRECT_302 | redirect | warning | 4 | 2 | — | Page returns a temporary redirect |
| REDIRECT_CASE_NORMALISE | redirect | info | 2 | 1 | — | Redirect normalises URL case — your web server handles this automatically |
| REDIRECT_CHAIN | redirect | warning | 6 | 3 | — | Page involves a multi-hop redirect chain |
| REDIRECT_LOOP | redirect | critical | 10 | 4 | — | Redirect loop detected |
| REDIRECT_TRAILING_SLASH | redirect | info | 2 | 1 | — | Redirect adds or removes a trailing slash — your CMS handles this automatically |
| ROBOTS_BLOCKED | crawlability | warning | 9 | 2 | — | Page blocked by robots.txt |
| SCHEMA_DEPRECATED_TYPE | ai_readiness | info | 2 | 1 | Reasonable proxy | Page uses deprecated schema.org types |
| SCHEMA_MISSING | crawlability | info | 5 | 2 | — | No structured data (schema markup) found on this page |
| SCHEMA_ORG_MISSING | ai_readiness | warning | 5 | 2 | Reasonable proxy | The homepage has no Organization (or LocalBusiness) JSON-LD schema identifying |
| SCHEMA_TYPE_CONFLICT | ai_readiness | warning | 3 | 2 | Reasonable proxy | Page declares multiple conflicting schema types |
| SCHEMA_TYPE_MISMATCH | ai_readiness | warning | 4 | 2 | Reasonable proxy | Page schema type does not match inferred page type |
| SCHEMA_VISIBLE_MISMATCH | ai_readiness | warning | 5 | 2 | Established | A value declared in JSON-LD structured data does not appear in the page's visible text |
| SECTION_CROSS_REFERENCES | ai_readiness | warning | 6 | 2 | Heuristic | Page contains backward-reference phrases ('as mentioned above', 'as discussed earlier') |
| SECTION_VAGUE_OPENER | ai_readiness | warning | 5 | 2 | Heuristic | One or more H2/H3 sections begin with a vague demonstrative reference |
| SEMANTIC_DENSITY_LOW | ai_readiness | warning | 3 | 3 | Heuristic | Text-to-HTML ratio is below 10% |
| SITEMAP_MISSING | sitemap | info | 6 | 2 | — | No sitemap found for this domain |
| STATISTICS_COUNT_LOW | ai_readiness | warning | 5 | 2 | Heuristic | 500+ word page contains no statistics (numbers paired with units, percentages, or dates) |
| STRUCTURED_ELEMENTS_LOW | ai_readiness | info | 3 | 2 | Heuristic | Page has very few structured elements (lists, tables, code blocks) relative to content ... |
| THIN_CONTENT | crawlability | warning | 6 | 3 | — | Page has fewer than 300 words of body content |
| TITLE_DUPLICATE | metadata | warning | 5 | 2 | — | Same title used on multiple pages |
| TITLE_H1_MISMATCH | metadata | warning | 6 | 2 | — | The page title and the H1 heading share no significant words |
| TITLE_META_DUPLICATE_PAIR | duplicate | warning | 6 | 2 | — | Both title and meta description duplicated on another page |
| TITLE_MISSING | metadata | critical | 9 | 1 | — | Page has no <title> tag |
| TITLE_TOO_LONG | metadata | warning | 4 | 1 | — | Title over 60 characters |
| TITLE_TOO_SHORT | metadata | warning | 5 | 1 | — | Title under 30 characters |
| TWITTER_CARD_MISSING | metadata | info | 3 | 1 | — | Missing Twitter/X Card meta tag |
| UA_CONTENT_DIFFERS | ai_readiness | warning | 7 | 3 | Reasonable proxy | AI crawler user agents (GPTBot, ClaudeBot) receive substantially less content than a br... |
| UNSAFE_CROSS_ORIGIN_LINK | security | info | 3 | 1 | — | External link opens in a new tab without rel="noopener" or rel="noreferrer" |
| URL_HAS_SPACES | url_structure | warning | 5 | 2 | — | URL contains encoded spaces (%20) |
| URL_HAS_UNDERSCORES | url_structure | info | 2 | 2 | — | URL path uses underscores instead of hyphens |
| URL_TOO_LONG | url_structure | info | 2 | 2 | — | URL exceeds 200 characters |
| URL_UPPERCASE | url_structure | warning | 3 | 2 | — | URL path contains uppercase characters |
| WRONG_PLACEHOLDER_LINK | broken_link | critical | 7 | 2 | — | A link points at a placeholder or example domain (example.com, localhost, or |
| WWW_CANONICALIZATION | security | warning | 5 | 2 | — | Both www and non-www versions of the site resolve without redirecting to each other |
