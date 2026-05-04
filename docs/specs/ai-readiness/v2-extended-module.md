# AI-Readiness Module v2.0 — Extension Spec

**Status:** Draft for implementation review
**Target repo:** talking-toad
**Author:** specification dialogue, 2 May 2026
**Builds on:** AI-Readiness Module v1.7 (already in `architecture.md`)

---

## 1. Purpose and scope

This spec extends the existing AI-Readiness Module (v1.7) with checks that audit a site's readiness to be discovered, crawled, and cited by AI search and retrieval engines (ChatGPT, Google AI Overviews / Gemini, Perplexity, Claude, Copilot, etc.).

It is **additive**. Nothing in v1.7 is replaced. Existing checks (llms.txt presence, semantic density, JSON-LD presence as `SCHEMA_MISSING`, conversational headings, image AI analysis with the GEO master prompt) remain.

**Out of scope (explicitly):**
- Server log analysis. talking-toad runs admin-free against a target URL and does not have access to access logs. Detection of whether AI bots are *actually* crawling a site is therefore out of scope. The spec instead checks whether bots are *permitted* to crawl, which is what an external auditor can determine.
- Live AI engine query testing ("does ChatGPT cite this page?"). That belongs to the sibling SERP-side tool, not talking-toad. Hooks for receiving citation data from that tool are included (§5) but the data collection itself is not in scope.
- JavaScript-rendered DOM analysis. talking-toad fetches raw HTML via httpx; this spec respects that constraint. Checks that would require a headless browser are explicitly omitted or implemented as raw-HTML proxies.

**Scope summary:**
- §3: Site-level checks for AI crawler access (robots.txt directives, deprecated user agents, user-fetch bot misconfigurations)
- §4: Per-page schema typing checks (extends existing `SCHEMA_MISSING`)
- §5: Per-page content extractability and passage-quality heuristics
- §6: Citation hooks (data-model fields for SERP-tool integration)
- §7: New issue codes, scoring, and help content
- §8: Implementation notes
- §9: Calibration and reliability disclaimers

---

## 2. Confidence labelling for new checks

Every new check declared in this spec carries one of three confidence labels. These must be surfaced in `issueHelp.js` so users understand what they're seeing.

| Label | Meaning |
|---|---|
| **Established** | The check measures something with public, vendor-confirmed effect on AI crawling, indexing, or citation. Robots.txt directives for declared AI bots fall here. |
| **Reasonable proxy** | The check measures something the GEO/AEO industry consistently treats as influential, but vendor confirmation is partial or absent. JSON-LD typing falls here. |
| **Heuristic** | The check measures something believed to influence AI extraction or citation by industry consensus but with no vendor confirmation. Passage-level structure checks fall here. Issue text must include the phrase "heuristic, not a measured signal." |

This labelling is non-optional. Without it the module overstates its own authority.

---

## 3. AI crawler access checks (site-level)

These run once per crawl, alongside the existing site-level checks (`robots.txt` parse, `llms.txt` presence, HTTPS redirect). They consume the already-fetched `robots.txt` and do not add HTTP requests.

### 3.1 Background context (for implementer)

Major AI providers in 2026 operate three-bot architectures separating training, search-indexing, and user-fetch traffic:

| Provider | Training bot | Search/index bot | User-fetch bot |
|---|---|---|---|
| OpenAI | GPTBot | OAI-SearchBot | ChatGPT-User |
| Anthropic | ClaudeBot | Claude-SearchBot | Claude-User |
| Perplexity | PerplexityBot | (combined) | Perplexity-User |
| Google | (Google-Extended opts out of Gemini training) | Googlebot covers AI Overviews | Google-Agent, Google-NotebookLM |
| Apple | Applebot-Extended (training opt-out) | Applebot | — |
| Common Crawl | CCBot (training corpus) | — | — |

**Key facts for the checker:**

1. The three bot categories represent independent decisions. A site can rationally allow search bots while blocking training bots. The checker must evaluate each category, not roll them up.
2. `anthropic-ai` and `claude-web` were deprecated in July 2024 in favour of the three-bot system. Robots.txt files still listing them are using stale configuration.
3. User-fetch bots (ChatGPT-User, Claude-User, Perplexity-User, Google-Agent, Google-NotebookLM) often do not honour robots.txt by design, because the user is the entity making the request. Blocking them in robots.txt is therefore a misconfiguration: it does nothing useful and signals the site owner misunderstands the protocol.
4. `Bytespider` (ByteDance) has a documented history of ignoring robots.txt. This is informational, not actionable.

### 3.2 Bot reference table

The implementation must include a versioned table of AI user agents. Suggested location: `api/services/ai_bots.py`.

```python
# ai_bots.py — version this and date the file
AI_BOTS = {
    # category: training | search | user_fetch | training_optout
    # honors_robots: True | False | "documented_violations"
    # current: True | False  (False = deprecated string, flag if seen)
    "GPTBot":            {"vendor": "OpenAI",     "category": "training",   "honors_robots": True,  "current": True},
    "OAI-SearchBot":     {"vendor": "OpenAI",     "category": "search",     "honors_robots": True,  "current": True},
    "ChatGPT-User":      {"vendor": "OpenAI",     "category": "user_fetch", "honors_robots": False, "current": True},

    "ClaudeBot":         {"vendor": "Anthropic",  "category": "training",   "honors_robots": True,  "current": True},
    "Claude-SearchBot":  {"vendor": "Anthropic",  "category": "search",     "honors_robots": True,  "current": True},
    "Claude-User":       {"vendor": "Anthropic",  "category": "user_fetch", "honors_robots": False, "current": True},
    "anthropic-ai":      {"vendor": "Anthropic",  "category": "training",   "honors_robots": True,  "current": False},  # deprecated
    "claude-web":        {"vendor": "Anthropic",  "category": "training",   "honors_robots": True,  "current": False},  # deprecated

    "PerplexityBot":     {"vendor": "Perplexity", "category": "search",     "honors_robots": "documented_violations", "current": True},
    "Perplexity-User":   {"vendor": "Perplexity", "category": "user_fetch", "honors_robots": False, "current": True},

    "Google-Extended":   {"vendor": "Google",     "category": "training_optout", "honors_robots": True,  "current": True},
    "Google-Agent":      {"vendor": "Google",     "category": "user_fetch", "honors_robots": False, "current": True},
    "Google-NotebookLM": {"vendor": "Google",     "category": "user_fetch", "honors_robots": False, "current": True},

    "Applebot-Extended": {"vendor": "Apple",      "category": "training_optout", "honors_robots": True,  "current": True},
    "Applebot":          {"vendor": "Apple",      "category": "search",     "honors_robots": True,  "current": True},

    "CCBot":             {"vendor": "CommonCrawl","category": "training",   "honors_robots": True,  "current": True},
    "Bytespider":        {"vendor": "ByteDance",  "category": "training",   "honors_robots": "documented_violations", "current": True},
    "Amazonbot":         {"vendor": "Amazon",     "category": "training",   "honors_robots": True,  "current": True},
    "Meta-ExternalAgent":{"vendor": "Meta",       "category": "training",   "honors_robots": True,  "current": True},
    "MistralAI-User":    {"vendor": "Mistral",    "category": "user_fetch", "honors_robots": False, "current": True},
    "DuckAssistBot":     {"vendor": "DuckDuckGo", "category": "search",     "honors_robots": True,  "current": True},
}
```

Update cadence: this table needs review every 6 months. Add a `LAST_REVIEWED` constant at the top of the file. Surface its age in the audit report so users know how stale the reference is.

### 3.3 New site-level issue codes

| Code | Confidence | Description | Default impact |
|---|---|---|---|
| `AI_BOT_SEARCH_BLOCKED` | Established | A search/retrieval bot (OAI-SearchBot, Claude-SearchBot, PerplexityBot) is disallowed in robots.txt. This removes the site from that AI's answers. | 8 |
| `AI_BOT_TRAINING_DISALLOWED` | Established | A training bot (GPTBot, ClaudeBot, CCBot) is disallowed. **Informational only — this may be intentional.** Surface as a warning, not a defect. | 0 (info) |
| `AI_BOT_USER_FETCH_BLOCKED` | Established | A user-fetch bot (ChatGPT-User, Claude-User, Perplexity-User) is disallowed in robots.txt. The block is ineffective (these bots ignore robots.txt) and signals misconfiguration. | 4 |
| `AI_BOT_DEPRECATED_DIRECTIVE` | Established | Robots.txt references a deprecated user agent (`anthropic-ai`, `claude-web`). | 2 |
| `AI_BOT_NO_AI_DIRECTIVES` | Reasonable proxy | Robots.txt has no AI-bot directives at all. Default `User-agent: *` rules apply. Surface as informational with recommended starter config. | 1 (info) |
| `AI_BOT_BLANKET_DISALLOW` | Established | Robots.txt contains `User-agent: *` with `Disallow: /`. All AI bots blocked. | 9 |
| `AI_BOT_TABLE_STALE` | Heuristic | Internal AI bot reference table has not been reviewed in >12 months. Output a single audit-level warning, not a per-issue flag. | 0 (system warning) |

**Implementation notes:**
- All robots.txt checks must use case-insensitive user-agent matching per RFC 9309.
- The check for `AI_BOT_USER_FETCH_BLOCKED` must include explanatory help text: blocking these bots does nothing protective and breaks user-initiated AI access to the page.
- For `AI_BOT_TRAINING_DISALLOWED`, the help text must explicitly say "this may be intentional and is not a defect" so users opting out of training aren't told they have a bug.

### 3.4 X-Robots-Tag header (optional, defer)

X-Robots-Tag headers can also block AI bots (e.g., `X-Robots-Tag: GPTBot: noindex`). Detecting these requires inspecting response headers per page. Defer to a v2.1 increment. If implemented later, mirror the categories above.

### 3.5 llms.txt status (already in v1.7)

Existing llms.txt check stays. **Update its help text** to reflect 2026 reality: as of writing, no major AI vendor has confirmed that llms.txt affects retrieval. Recommend it as low-cost, low-evidence; do not claim it improves AI citation. Confidence: Heuristic.

---

## 4. Schema typing checks (per-page)

Extends the existing `SCHEMA_MISSING` check (which fires when `schema_types` is empty) to evaluate *which* types are present and whether they fit the page.

### 4.1 Page-type inference

Before evaluating schema appropriateness, the checker must classify the page. Use a simple rule chain on URL pattern + visible content cues. The classifier returns one of: `home`, `service`, `about`, `team_member`, `article`, `faq`, `contact`, `unknown`.

Suggested rules (refine in implementation):

| Inferred type | Cue |
|---|---|
| `home` | URL path is `/` or domain root |
| `article` | URL contains `/blog/`, `/news/`, `/articles/`, `/posts/`; OR HTML has `<article>` containing `<time>` with `datetime` |
| `team_member` | URL contains `/team/`, `/about/staff/`, `/practitioners/`, `/our-team/`; OR page has a single `<h1>` matching person-name pattern |
| `service` | URL contains `/services/`, `/counselling/`, `/training/`, or talking-toad's existing nav-detection identifies a service section |
| `faq` | URL contains `/faq/`, `/faqs/`, `/questions/`; OR page has ≥3 `<h2>`/`<h3>` ending in `?` |
| `contact` | URL contains `/contact`; OR page has a `<form>` with email field |
| `about` | URL contains `/about` |
| `unknown` | none of the above match |

For `unknown`, skip schema appropriateness checks — only `SCHEMA_MISSING` from v1.7 still applies.

### 4.2 Expected schema by page type

| Page type | Expected schema types (any one is sufficient unless noted) |
|---|---|
| `home` | `Organization` or `LocalBusiness` (LocalBusiness preferred for service businesses) |
| `service` | `Service` AND (`Organization` or `LocalBusiness`) |
| `about` | `Organization` or `AboutPage` |
| `team_member` | `Person` (preferred with `worksFor` linking to `Organization`) |
| `article` | `Article`, `BlogPosting`, or `NewsArticle` (with `author`, `datePublished`, `headline`) |
| `faq` | `FAQPage` |
| `contact` | `ContactPage` or `Organization` with `contactPoint` |

### 4.3 New per-page issue codes

| Code | Confidence | Description |
|---|---|---|
| `SCHEMA_TYPE_MISMATCH` | Reasonable proxy | Page has JSON-LD but the type doesn't match the inferred page type (e.g., a team member page has only `WebPage`, not `Person`). |
| `SCHEMA_INCOMPLETE_PERSON` | Reasonable proxy | `Person` schema is present but missing `name`, `jobTitle`, or `worksFor`. |
| `SCHEMA_INCOMPLETE_ARTICLE` | Reasonable proxy | `Article`/`BlogPosting` is present but missing `author`, `datePublished`, or `headline`. |
| `SCHEMA_INCOMPLETE_LOCALBUSINESS` | Reasonable proxy | `LocalBusiness` present but missing `address`, `telephone`, or `areaServed`. |
| `SCHEMA_INCOMPLETE_FAQPAGE` | Reasonable proxy | `FAQPage` present but `mainEntity` is empty or has fewer than 2 `Question` items. |
| `SCHEMA_DUPLICATE_TYPES` | Heuristic | Same schema type declared in multiple JSON-LD blocks with conflicting properties. |

**Default impact:** 4 for all `SCHEMA_*` codes. **Default effort:** 2 (most are CMS-edit fixes).

### 4.4 Implementation notes

- Use the existing JSON-LD parser. If the project doesn't have one beyond extracting `schema_types`, add a minimal `extract_schema_blocks()` returning `List[Dict]` of full parsed JSON-LD objects, not just type strings.
- `SCHEMA_INCOMPLETE_*` checks should validate property *presence*, not value correctness (validating addresses, phone numbers, dates is out of scope and brittle).
- Microdata and RDFa are out of scope. JSON-LD only. This matches the existing `schema_types` field semantics.

---

## 5. Content extractability and passage-quality heuristics (per-page)

This section is the most speculative. **Every check here is labelled Heuristic.** The signals are plausible-but-unconfirmed proxies for "is this content easy for an AI engine to extract a coherent answer from."

### 5.1 Structural extractability

These check raw-HTML structure. They are reliably measurable and modestly informative.

| Code | Confidence | Description |
|---|---|---|
| `AI_NO_MAIN_LANDMARK` | Heuristic | Page has no `<main>`, `<article>`, or `role="main"` element. AI extractors fall back to heuristic content detection. |
| `AI_HEADING_HIERARCHY_BROKEN` | Reasonable proxy | Heading levels skip (e.g., `<h1>` → `<h3>` with no `<h2>`). Already partially covered in standard SEO checks; if talking-toad already has this check, do not duplicate — instead, surface it under the AI-Readiness category as well. |
| `AI_HEADING_PARAGRAPH_RATIO_LOW` | Heuristic | Page has fewer than 1 heading per ~400 words of body text. AI extractors prefer chunked content. |

### 5.2 Passage self-containedness (heuristic)

These are pure heuristics. Implementation should be conservative — flag only obvious cases — and help text must be explicit about uncertainty.

| Code | Confidence | Description |
|---|---|---|
| `AI_PARAGRAPH_TOO_LONG` | Heuristic | Paragraphs over ~150 words. Long paragraphs are harder for AI engines to chunk and cite. Threshold configurable; default flag if >25% of paragraphs exceed limit. |
| `AI_NO_DEFINITIONS` | Heuristic | Article-type pages with no detectable definitional sentence (heuristic: first paragraph contains no copular sentence with the page topic, e.g., "X is..."). Likely too noisy on first version; ship as opt-in only. |
| `AI_FIRST_PARAGRAPH_BOILERPLATE` | Heuristic | First content paragraph after the H1 is shorter than 30 words OR contains primarily marketing/CTA language (heuristic: ratio of imperative verbs and brand-name occurrences). High false-positive risk; ship behind a feature flag. |

**Strong recommendation:** Ship §5.1 in the first release. Hold §5.2 behind a config flag (`enable_passage_heuristics: false` by default) until calibrated against a corpus of real sites. Shipping noisy heuristic checks erodes trust in the whole module.

### 5.3 Anchor and reference checks (defer)

Several promising heuristics — anaphoric reference density, presence of TL;DR/summary blocks, claim-attribution density — are not specified here. They require more design work and corpus calibration before they can be implemented without unacceptable false-positive rates. Track as v2.2 candidates.

---

## 6. Citation hooks (integration with sibling SERP tool)

The sibling tool (the AI-SERP analog of talking-toad's existing SERP tool) will eventually produce per-URL citation data: "this URL was cited N times in engine X for query Y over period Z." talking-toad should be able to surface that data without depending on the sibling tool existing yet.

### 6.1 Data model additions

Add to the `crawled_pages` table (and the Redis equivalent):

| Column | Type | Default | Description |
|---|---|---|---|
| `ai_citation_count_30d` | INTEGER | NULL | Citations in the past 30 days, summed across engines. NULL = no data ingested. |
| `ai_citation_engines` | TEXT (JSON) | NULL | JSON array of `{engine, count, last_seen}` objects. |
| `ai_citation_last_updated` | TIMESTAMP | NULL | When the citation data was last ingested. |

These are populated only by an explicit ingestion endpoint (§6.2). All checks must treat NULL as "no data," not "zero citations." This distinction matters for reports.

### 6.2 Ingestion endpoint

Add to the FastAPI router:

```
POST /api/jobs/{job_id}/ai-citations
Authorization: Bearer <AUTH_TOKEN>
Content-Type: application/json

{
  "ingested_at": "2026-05-02T12:00:00Z",
  "data": [
    {
      "url": "https://example.com/services/counselling/",
      "engines": [
        {"engine": "chatgpt", "count": 4, "last_seen": "2026-05-01T..."},
        {"engine": "google_ai_overview", "count": 1, "last_seen": "2026-04-29T..."}
      ]
    }
  ]
}
```

URL matching uses the same normalisation as the existing crawler (§2.7 of `architecture.md`). URLs in the payload that don't match any crawled page are recorded but not surfaced.

### 6.3 Issue codes (populated only when citation data is present)

| Code | Confidence | Description |
|---|---|---|
| `AI_CITED_PAGE` | Established (when data present) | Informational. Page has been cited ≥1 time in the last 30 days. Surface as a positive signal in the report, not as an issue. Impact 0. |
| `AI_HIGH_VALUE_UNCITED` | Reasonable proxy | Page is structurally healthy (low issue count, in sitemap, indexable, has appropriate schema) but has zero citations. Suggests content/visibility gap rather than technical defect. Only fires when citation data has been ingested in the last 60 days. |

### 6.4 What this is not

This section explicitly does not implement the SERP-side data collection. talking-toad receives data; it does not query AI engines. Keep that boundary clean — the SERP tool can change vendors, query strategies, or pricing without touching talking-toad.

---

## 7. Issue-code summary, scoring, and help content

### 7.1 Issue codes added

Site-level: `AI_BOT_SEARCH_BLOCKED`, `AI_BOT_TRAINING_DISALLOWED`, `AI_BOT_USER_FETCH_BLOCKED`, `AI_BOT_DEPRECATED_DIRECTIVE`, `AI_BOT_NO_AI_DIRECTIVES`, `AI_BOT_BLANKET_DISALLOW`, `AI_BOT_TABLE_STALE`.

Per-page: `SCHEMA_TYPE_MISMATCH`, `SCHEMA_INCOMPLETE_PERSON`, `SCHEMA_INCOMPLETE_ARTICLE`, `SCHEMA_INCOMPLETE_LOCALBUSINESS`, `SCHEMA_INCOMPLETE_FAQPAGE`, `SCHEMA_DUPLICATE_TYPES`, `AI_NO_MAIN_LANDMARK`, `AI_HEADING_HIERARCHY_BROKEN` (or shared with existing), `AI_HEADING_PARAGRAPH_RATIO_LOW`, `AI_PARAGRAPH_TOO_LONG`, `AI_NO_DEFINITIONS` (opt-in), `AI_FIRST_PARAGRAPH_BOILERPLATE` (opt-in), `AI_CITED_PAGE` (data-driven), `AI_HIGH_VALUE_UNCITED` (data-driven).

### 7.2 Help content requirements

Each new code requires entries in `frontend/src/data/issueHelp.js` (and the auto-generated `api/services/issue_help_data.py`). Each entry must include:

1. **`what_it_is`** — one or two sentences explaining the check.
2. **`why_it_matters`** — must include the confidence label verbatim ("Established", "Reasonable proxy", or "Heuristic, not a measured signal").
3. **`how_to_fix`** — concrete steps. For robots.txt issues, include exact directive lines.
4. **`vendor_references`** — for Established checks, link to the vendor's published bot documentation. For Reasonable-proxy and Heuristic checks, omit or link to industry references (do not invent vendor confirmations).

### 7.3 Scoring philosophy

Default impact values are suggestions. The principle:
- Established checks affecting AI search visibility (search bots blocked, blanket disallow): impact 8–9
- Established checks affecting only training (GPTBot disallow, etc.): impact 0 (informational; may be intentional)
- Reasonable-proxy checks (schema typing): impact 3–5
- Heuristic checks (passage-level): impact 1–3 max
- Configuration-error checks (user-fetch bots blocked, deprecated directives): impact 2–4

The point is that no single check in this module should ever dominate the health score. The existing technical SEO checks remain the larger contributors. AI-readiness should add signal, not noise.

---

## 8. Implementation notes

### 8.1 Code organisation

Suggested file structure (matching existing patterns):

```
api/
  services/
    ai_bots.py             # bot reference table (§3.2)
    ai_readiness.py        # site-level checks (§3, llms.txt already lives elsewhere; coordinate)
    schema_typing.py       # §4 schema appropriateness logic
    page_classifier.py     # §4.1 page-type inference
    passage_heuristics.py  # §5 heuristic checks (gated by config flag)
  routers/
    citations.py           # §6.2 ingestion endpoint
```

Per-page checks are added to `check_page()`'s existing call chain. Site-level checks fit alongside the existing pipeline steps 4–5 in `architecture.md` ("HTTPS redirect check," "llms.txt check").

### 8.2 ParsedPage additions

Add to the `ParsedPage` dataclass:

```python
@dataclass
class ParsedPage:
    # ... existing fields ...
    schema_blocks: List[Dict]          # full JSON-LD objects, not just type names
    inferred_page_type: str            # from page_classifier
    main_landmark_present: bool
    paragraph_word_counts: List[int]   # for §5.2 heuristics
    heading_count: int
    body_word_count: int
```

### 8.3 Configuration

Add to crawl-job config:

```python
{
  "enable_ai_readiness_v2": True,
  "enable_passage_heuristics": False,   # opt-in until calibrated
  "ai_bot_table_max_age_days": 365,
  "passage_heuristic_thresholds": {
    "long_paragraph_words": 150,
    "long_paragraph_ratio_threshold": 0.25,
    "headings_per_n_words": 400
  }
}
```

### 8.4 Reporting

PDF and Excel reports must group AI-Readiness v2 issues under a clearly labelled "AI Search Readiness" section, distinct from technical SEO. Each grouped section's intro paragraph must state the confidence labels in plain language. This is non-negotiable: the module is useful only if users know what they're being told.

### 8.5 Testing

Required test coverage for v2.0:
- Unit tests for the bot reference table (table integrity, no duplicate strings, all entries have all required fields).
- Unit tests for robots.txt parsing against a fixture set including: clean allow, blanket disallow, deprecated directives, mixed permissions, malformed files.
- Unit tests for page-type inference against a fixture set of representative URL+HTML pairs.
- Unit tests for schema-block extraction against fixtures with: single block, multiple blocks, malformed JSON-LD, nested `@graph`, microdata-only (should be ignored).
- Integration test for the citation ingestion endpoint, including URL normalisation matching.
- Snapshot test for a complete crawl against a fixture site producing the expected v2.0 issues.

The existing test gap noted in `REVIEW_SPEC.md` (no real WP integration tests, zero Redis-store tests) is not made worse by this spec. New v2.0 logic is testable in isolation against HTML/JSON fixtures without a live site.

### 8.6 Frontend additions

`Results.jsx` (already 2700+ lines per `REVIEW_SPEC.md`) should not absorb the new UI directly. Extract a new `AIReadinessPanel.jsx` component that:
- Lists v2.0 issues grouped by site-level vs. per-page
- Displays the confidence label as a coloured pill on each issue (e.g., green for Established, yellow for Reasonable proxy, grey for Heuristic)
- Surfaces the bot table's `LAST_REVIEWED` date and warns if stale

This is also a partial answer to the broader code-quality concern about `Results.jsx` size — adding to it would worsen an already-flagged issue.

---

## 9. Calibration and reliability disclaimers

This module is shipping into a fast-moving domain. Three disclosures must appear in the user-facing documentation:

1. **The AI bot reference table is a snapshot.** Vendor user agents change. The table needs review at least every 6 months. The module surfaces the table's last-reviewed date so users can judge currency.

2. **Heuristic checks are not measured signals.** The industry's understanding of what makes content AI-citable is preliminary and dominated by vendor-side opinion rather than independent measurement. Heuristic checks reflect industry consensus, not vendor confirmation.

3. **llms.txt has no confirmed retrieval effect as of writing.** The existing v1.7 check stays because the file is cheap to add, but help text must not claim it improves AI visibility.

These disclaimers belong in `docs/ai-readiness.md` (new file) and in the AI Search Readiness section header of every report.

---

## 10. Out of scope, deferred, and rejected

**Out of scope (won't do):**
- Server log analysis (no admin access)
- Live AI engine querying (sibling tool's job)
- JavaScript-rendered DOM analysis (talking-toad architecture)
- Fact-checking of page claims

**Deferred to v2.1 or later:**
- X-Robots-Tag header analysis (§3.4)
- Anaphoric reference and TL;DR-block heuristics (§5.3)
- Microdata/RDFa schema analysis
- Content freshness checks (last-modified vs. AI engine recrawl cadence)

**Rejected:**
- Schema value validation (addresses, phone numbers): brittle, high false-positive rate.
- Sentiment/tone analysis of content: outside the scope of a technical auditor.
- Aggregated "AI-readiness score" as a single number: would obscure the established/proxy/heuristic distinction the module is trying to preserve. Use the existing health-score machinery; do not create a parallel score.

---

## 11. Open questions for implementation

These were flagged during specification and remain unresolved. Claude Code (or implementer) should clarify against the actual codebase before implementation:

1. Does the existing crawler already extract full JSON-LD blocks (not just type names), or does §8.2's `schema_blocks` field require new parsing logic?
2. Does the existing heading-hierarchy check (if any) belong under standard SEO, AI-readiness, or both? §5.1 lists it under AI but a duplicate would be confusing.
3. Is the GEO image-AI prompt (in `geo_image_ai_prompt.md`) already wired into the Level 3 Image Analysis flow, or is it pending integration? This spec assumes it is wired; if not, it remains an open task but is independent of v2.0.
4. Is the existing "Conversational Headings" check (v1.7) calibrated to a confidence level? If not, it should adopt the §2 scheme retroactively for consistency.

---

## End of specification
