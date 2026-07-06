---
status: draft-review
proposed: 2026-07-02
author: Hermes Agent
type: review
scope: GEO Analyzer (Aggarwal, Mechanistic, Conventional) + Tier 1 GEO heuristics + Content Freshness + AI Citation + Agent-readiness (part 5 of 5)
---

# Scoring Weight Review — Part 5: GEO Analyzer, Freshness, AI Citation, Agent-Readiness

> Each entry shows current weight, assessment, and recommendation. These are the newest checks in the system (v2.1+) and the least validated.

---

## Current Scoring Reference

| Code | Current (impact, effort) | Priority rank | Confidence label | Severity |
|------|--------------------------|---------------|------------------|----------|
| STATISTICS_COUNT_LOW | (7, 2) | 66 | Heuristic | warning |
| EXTERNAL_CITATIONS_LOW | (7, 2) | 66 | Reasonable proxy | warning |
| QUOTATIONS_MISSING | (6, 2) | 56 | Heuristic | warning |
| ORPHAN_CLAIM_TECHNICAL | (6, 2) | 56 | Heuristic | warning |
| RAW_HTML_JS_DEPENDENT | (6, 3) | 54 | Reasonable proxy | warning |
| JS_RENDERED_CONTENT_DIFFERS | (6, 4) | 52 | Reasonable proxy | warning |
| CONTENT_CLOAKING_DETECTED | (8, 4) | 72 | Reasonable proxy | error |
| UA_CONTENT_DIFFERS | (7, 3) | 64 | Reasonable proxy | warning |
| FIRST_VIEWPORT_NO_ANSWER | (5, 2) | 46 | Heuristic | warning |
| AUTHOR_BYLINE_MISSING | (4, 2) | 36 | Reasonable proxy | warning |
| DATE_PUBLISHED_MISSING | (3, 1) | 28 | Reasonable proxy | info |
| DATE_MODIFIED_MISSING | (2, 1) | 18 | Reasonable proxy | info |
| CODE_BLOCK_MISSING_TECHNICAL | (4, 2) | 36 | Heuristic | warning |
| COMPARISON_TABLE_MISSING | (3, 2) | 26 | Heuristic | info |
| CHUNKS_NOT_SELF_CONTAINED | (5, 4) | 42 | Heuristic | warning |
| CENTRAL_CLAIM_BURIED | (5, 3) | 44 | Heuristic | warning |
| GEO_SUMMARY_BURIED | (7, 3) | 64 | Heuristic | warning |
| LINK_PROFILE_PROMOTIONAL | (4, 2) | 36 | Heuristic | info |
| STRUCTURED_ELEMENTS_LOW | (3, 2) | 26 | Heuristic | info |
| JSON_LD_INVALID | (4, 2) | 36 | Reasonable proxy | warning |
| FAQ_SCHEMA_MISSING | (3, 2) | 26 | Reasonable proxy | info |
| PROMOTIONAL_CONTENT_INTERRUPTS | (3, 3) | 24 | Heuristic | info |
| AI_TXT_MISSING | (1, 1) | 8 | Heuristic | info |
| QUERY_COVERAGE_WEAK | (7, 2) | 66 | Heuristic | warning |
| SECTION_VAGUE_OPENER | (5, 2) | 46 | Heuristic | warning |
| SECTION_CROSS_REFERENCES | (6, 2) | 56 | Heuristic | warning |
| PARAS_TOO_LONG | (4, 2) | 36 | (none — crawlability) | info |
| CONTENT_DATE_STALE_VISIBLE | (4, 2) | 36 | Reasonable proxy | warning |
| CONTENT_STAT_OUTDATED | (2, 1) | 18 | Heuristic | info |
| AI_CITED_PAGE | (0, 0) | 0 | Established | info |
| AI_HIGH_VALUE_UNCITED | (4, 2) | 36 | Reasonable proxy | warning |
| JS_DEPENDENT_NAVIGATION | (5, 3) | 44 | (none — rendering) | warning |
| NON_SEMANTIC_BUTTON | (4, 3) | 34 | (none — semantic_html) | warning |
| LANDMARK_MAIN_MISSING | (2, 2) | 16 | (none — semantic_html) | info |
| LANDMARK_NAV_MISSING | (2, 2) | 16 | (none — semantic_html) | info |
| INTERACTIVE_NO_ACCESSIBLE_NAME | (4, 2) | 36 | (none — semantic_html) | warning |
| PLACEHOLDER_LINK | (7, 2) | 66 | (none — broken_link) | critical |
| WRONG_PLACEHOLDER_LINK | (7, 2) | 66 | (none — broken_link) | critical |
| SCHEMA_ORG_MISSING | (5, 2) | 46 | Reasonable proxy | warning |
| CONTACT_INFO_NOT_IN_HTML | (4, 2) | 36 | Heuristic | warning |

---

## GEO Analyzer: Aggarwal et al. Checks (Empirical)

These checks are based on Aggarwal et al. (2023) — a single academic paper studying factors that correlate with AI citation. Confidence for all of these is Heuristic (one paper, no vendor confirmation).

### STATISTICS_COUNT_LOW — (7, 2) → 66 (Heuristic)

**Assessment:** Impact 7 is TOO HIGH. This is a check based on ONE academic paper. Impact 7 ties it with JSON_LD_MISSING (which has "Reasonable proxy" confidence). A single-paper Heuristic check should not outrank established SEO signals. Impact 4 is more appropriate for a non-validated hypothesis.

**Recommendation:** LOWER impact from 7 to 4. (4, 2) → 36

---

### EXTERNAL_CITATIONS_LOW — (7, 2) → 66 (Reasonable proxy)

**Assessment:** Impact 7 is too high. While this has "Reasonable proxy" confidence (wider industry consensus that external citations build authority), impact 7 is still too high for a signal that's a pattern, not a direct ranking factor. Google has confirmed that links to authoritative external sources are useful but not a direct signal. Impact 5 is more appropriate.

**Recommendation:** LOWER impact from 7 to 5. (5, 2) → 46

---

### QUOTATIONS_MISSING — (6, 2) → 56 (Heuristic)

**Assessment:** Impact 6 is too high. A Heuristic check from a single paper suggesting that direct quotations help AI citation. There's zero vendor confirmation. Impact 3-4 is more appropriate.

**Recommendation:** LOWER impact from 6 to 4. (4, 2) → 36

---

### ORPHAN_CLAIM_TECHNICAL — (6, 2) → 56 (Heuristic)

**Assessment:** Impact 6 is too high for a Heuristic check. Technical claims without source links is a content quality concern, and the Aggarwal paper suggests it matters for AI citation credibility. But again, validation is thin. Impact 4 is more appropriate.

**Recommendation:** LOWER impact from 6 to 4. (4, 2) → 36

---

## GEO Analyzer: Mechanistic Checks

### RAW_HTML_JS_DEPENDENT — (6, 3) → 54 (Reasonable proxy)

**Assessment:** Impact 6 is reasonable. If the raw HTML is a JS shell with near-zero text, AI crawlers and Googlebot both see an empty page. This is a real technical barrier. "Reasonable proxy" is appropriate (Google has confirmed JS-rendering issues for some bots). Keep.

**Recommendation:** KEEP AS-IS (6, 3)

---

### JS_RENDERED_CONTENT_DIFFERS — (6, 4) → 52 (Reasonable proxy)

**Assessment:** Impact 6 is reasonable. When rendered content is substantially more than raw HTML (>20% more tokens), the page is JS-gated — real content is invisible to non-JS crawlers. This is a genuine extraction barrier. However, effort 4 (major dev work) is correct — fixing requires SSR or SSG.

**Recommendation:** KEEP AS-IS (6, 4)

---

### CONTENT_CLOAKING_DETECTED — (8, 4) → 72 (Reasonable proxy)

**Assessment:** Impact 8 is reasonable. Content cloaking — serving different content to AI crawlers than to users — violates Google's Webmaster Guidelines and can result in manual actions. This is the most severe GEO issue. "Error" severity level is appropriate (unique in the codebase). Keep.

**Recommendation:** KEEP AS-IS (8, 4)

---

### UA_CONTENT_DIFFERS — (7, 3) → 64 (Reasonable proxy)

**Assessment:** Impact 7 is reasonable but slightly high. AI crawlers receiving stripped content is a real visibility problem, but it's less severe than cloaking (which is deliberate deception). Impact 6 might be more appropriate.

**Recommendation:** LOWER impact from 7 to 6. (6, 3) → 54

---

### FIRST_VIEWPORT_NO_ANSWER — (5, 2) → 46 (Heuristic)

**Assessment:** Impact 5 is too high for a Heuristic check. "First 200 words don't contain a direct answer signal" is a stylistic/content observation with no confirmed SEO or AI impact. Many high-quality pages use an introductory paragraph before delivering the answer. Impact 3 is more appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

---

### AUTHOR_BYLINE_MISSING — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. Missing author byline is a credibility signal less for SEO (Google doesn't require it for ranking) than for AI citation (AI engines favor pages with clear authorship). The "Reasonable proxy" label fits. However, impact 3 is more honest.

**Recommendation:** LOWER impact from 4 to 3. (3, 2) → 26

---

### DATE_PUBLISHED_MISSING — (3, 1) → 28 (Reasonable proxy)

**Assessment:** Impact 3 is reasonable. Missing publication date is a minor content quality signal. Google uses dates for fresh content, and AI citation engines prefer dated content. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

---

### DATE_MODIFIED_MISSING — (2, 1) → 18 (Reasonable proxy)

**Assessment:** Impact 2 is reasonable. Less important than datePublished. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### CODE_BLOCK_MISSING_TECHNICAL — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is too high for a Heuristic check. The absence of `<code>`/`<pre>` blocks on a technical how-to page is a content-quality observation, not a problem. Impact 2 is more appropriate.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

---

### COMPARISON_TABLE_MISSING — (3, 2) → 26 (Heuristic)

**Assessment:** Impact 3 is reasonable for a Heuristic check. Using comparison language without a table is a missed opportunity for structured extraction. Low impact is correct.

**Recommendation:** KEEP AS-IS (3, 2)

---

### CHUNKS_NOT_SELF_CONTAINED — (5, 4) → 42 (Heuristic)

**Assessment:** Impact 5 is too high. Self-contained sections are good writing practice and help AI chunkers, but there's no evidence this directly affects citation rates. Impact 3 is more appropriate. Effort 4 is also too high — rewriting section openers is content editing, effort 2-3.

**Recommendation:** LOWER impact from 5 to 3, LOWER effort from 4 to 3. (3, 3) → 24

---

### CENTRAL_CLAIM_BURIED — (5, 3) → 44 (Heuristic)

**Assessment:** Impact 5 is too high. The main claim not appearing in the first 150 words is a content structure concern, but many legitimate articles warm up the reader before delivering the thesis. Impact 3 is more appropriate for a Heuristic check.

**Recommendation:** LOWER impact from 5 to 3. (3, 3) → 24

---

### GEO_SUMMARY_BURIED — (7, 3) → 64 (Heuristic)

**Assessment:** Impact 7 is TOO HIGH. This DOM-depth check (whether the first paragraph under each H2/H3 contains the core answer) is a Heuristic check with a single speculative code comment justifying its impact. Impact 7 ties it with core, well-established issues. For a Heuristic check with no vendor confirmation, impact 4 is more appropriate.

**Recommendation:** LOWER impact from 7 to 4. (4, 3) → 34

---

### LINK_PROFILE_PROMOTIONAL — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is too high. >80% of outbound links pointing to the same organization's own domains is a pattern observation, not a problem. Nonprofits naturally link to their own programs and services. Impact 2 is more appropriate for this info-level Heuristic check.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

---

### STRUCTURED_ELEMENTS_LOW — (3, 2) → 26 (Heuristic)

**Assessment:** Impact 3 is reasonable for a Heuristic observation. Few lists, tables, code blocks relative to content length is a content quality note. Correctly low-impact. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

## GEO Analyzer: Conventional Checks

### JSON_LD_INVALID — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is too low. This should be higher than JSON_LD_MISSING. An INVALID JSON-LD block that's missing @type/@context is actively harmful (search engines may ignore ALL schema on the page). Impact 6-7 is more appropriate. Effort 2 is right.

**Recommendation:** RAISE impact from 4 to 6. (6, 2) → 56

---

### FAQ_SCHEMA_MISSING — (3, 2) → 26 (Reasonable proxy)

**Assessment:** Impact 3 is reasonable. FAQPage schema is nice-to-have for Q&A sections. Absence doesn't harm anything. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

### PROMOTIONAL_CONTENT_INTERRUPTS — (3, 3) → 24 (Heuristic)

**Assessment:** Impact 3 is reasonable. Mid-article promotions interrupting content flow is a readability concern. Heuristic, low impact. Effort 3 is too high — moving promotional content is a drag-and-drop content edit, effort 1.

**Recommendation:** KEEP impact 3, LOWER effort from 3 to 1. (3, 1) → 28

---

### AI_TXT_MISSING — (1, 1) → 8 (Heuristic)

**Assessment:** Impact 1 is correct. This is the lowest-priority check for a reason — it's an emerging convention with no AI engine support confirmed. Keep.

**Recommendation:** KEEP AS-IS (1, 1)

---

## Tier 1 GEO Heuristics

### QUERY_COVERAGE_WEAK — (7, 2) → 66 (Heuristic)

**Assessment:** Impact 7 is TOO HIGH. This checks whether H1 topic terms appear in the intro and H2 headings. While the concept makes logical sense (AI systems score pages by query-content similarity), it's a Heuristic check with no vendor confirmation. Impact 4-5 is more appropriate.

**Recommendation:** LOWER impact from 7 to 5. (5, 2) → 46

---

### SECTION_VAGUE_OPENER — (5, 2) → 46 (Heuristic)

**Assessment:** Impact 5 is too high. Vague section openers ("This method…" with unclear antecedent) are a writing-quality concern. AI systems may struggle with section independence, but this is a minor Heuristic check. Impact 3 is more appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

---

### SECTION_CROSS_REFERENCES — (6, 2) → 56 (Heuristic)

**Assessment:** Impact 6 is too high. Phrases like "as mentioned above" break section independence for AI chunkers. The logic is sound but the impact is Heuristic. Impact 4 is more appropriate.

**Recommendation:** LOWER impact from 6 to 4. (4, 2) → 36

---

## Content Freshness (M4)

### CONTENT_DATE_STALE_VISIBLE — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. A visibly stale date for the page type (e.g., a 2021 date on a 2025 article) signals to users and AI that content may be outdated. Reasonable proxy confidence is fair (Google has discussed freshness signals). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### CONTENT_STAT_OUTDATED — (2, 1) → 18 (Heuristic)

**Assessment:** Impact 2 is reasonable. An outdated year reference is a minor content issue. Heuristic confidence, low impact. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

## AI Citation Ingestion (M5)

### AI_CITED_PAGE — (0, 0) → 0 (Established)

**Assessment:** Impact 0 is correct. This is an observation ("this page has been cited by AI engines") — it's not a problem to fix. Correctly zero-impact. Keep.

**Recommendation:** KEEP AS-IS (0, 0)

---

### AI_HIGH_VALUE_UNCITED — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. A healthy, content-rich page with zero AI citations represents a visibility gap. Reasonable proxy confidence is appropriate (we can check citation data but the reasons for non-citation are speculative). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

## Agent-Readiness Checks (Phase 1 — WP2–WP5)

These are the newest checks, targeting AI task-execution agents rather than search/citation bots.

### JS_DEPENDENT_NAVIGATION — (5, 3) → 44

**Assessment:** Impact 5 is reasonable. Navigation not present in server-rendered HTML means AI crawlers and agents that don't run JS cannot discover the rest of the site. This is a real structural barrier for agent-based traffic. No confidence label (category is "rendering", not "ai_readiness"). Keep.

**Recommendation:** KEEP AS-IS (5, 3)

---

### NON_SEMANTIC_BUTTON — (4, 3) → 34

**Assessment:** Impact 4 is reasonable. `<div>`/`<span>` clickable controls without button roles are invisible as clickable elements to agents reading the accessibility tree. Effort 3 is right — fixing requires template changes. Keep.

**Recommendation:** KEEP AS-IS (4, 3)

---

### LANDMARK_MAIN_MISSING — (2, 2) → 16

**Assessment:** Impact 2 is correct. Missing `<main>` landmark is a minor navigation issue for agents. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

---

### LANDMARK_NAV_MISSING — (2, 2) → 16

**Assessment:** Impact 2 is correct. Same as above — minor for agents. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

---

### INTERACTIVE_NO_ACCESSIBLE_NAME — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Controls without accessible names are unusable for agents operating via the accessibility tree. Effort 2 is right (add aria-label). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### PLACEHOLDER_LINK — (7, 2) → 66

**Assessment:** Impact 7 is reasonable. A navigation CTA whose href is "#" or "javascript:void(0)" is a dead end for any agent following links. This is a genuine broken-navigation problem. Severity "critical" is appropriate. Keep.

**Recommendation:** KEEP AS-IS (7, 2)

---

### WRONG_PLACEHOLDER_LINK — (7, 2) → 66

**Assessment:** Impact 7 is reasonable. Links to example.com, localhost, or bare search engine URLs are usually template leftovers — they're broken destinations. Same severity as PLACEHOLDER_LINK and correctly weighted. Keep.

**Recommendation:** KEEP AS-IS (7, 2)

---

### SCHEMA_ORG_MISSING — (5, 2) → 46 (Reasonable proxy)

**Assessment:** Impact 5 is reasonable. Missing Organization schema on the homepage means AI systems lack a machine-readable identity anchor for the entire site. Reasonable proxy confidence is appropriate. Keep.

**Recommendation:** KEEP AS-IS (5, 2)

---

### CONTACT_INFO_NOT_IN_HTML — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is reasonable but slightly high. Contact info only in images/JS is a practical accessibility concern for users and agents, but Heuristic confidence suggests this is speculative for AI citation. Impact 3 is more appropriate.

**Recommendation:** LOWER impact from 4 to 3. (3, 2) → 26

---

## Part 5 Summary

| Code | Current | Proposed | Delta |
|------|---------|----------|-------|
| STATISTICS_COUNT_LOW | (7, 2) | (4, 2) | -3 impact |
| EXTERNAL_CITATIONS_LOW | (7, 2) | (5, 2) | -2 impact |
| QUOTATIONS_MISSING | (6, 2) | (4, 2) | -2 impact |
| ORPHAN_CLAIM_TECHNICAL | (6, 2) | (4, 2) | -2 impact |
| UA_CONTENT_DIFFERS | (7, 3) | (6, 3) | -1 impact |
| FIRST_VIEWPORT_NO_ANSWER | (5, 2) | (3, 2) | -2 impact |
| AUTHOR_BYLINE_MISSING | (4, 2) | (3, 2) | -1 impact |
| CODE_BLOCK_MISSING_TECHNICAL | (4, 2) | (2, 2) | -2 impact |
| CHUNKS_NOT_SELF_CONTAINED | (5, 4) | (3, 3) | -2 impact, -1 effort |
| CENTRAL_CLAIM_BURIED | (5, 3) | (3, 3) | -2 impact |
| GEO_SUMMARY_BURIED | (7, 3) | (4, 3) | -3 impact |
| LINK_PROFILE_PROMOTIONAL | (4, 2) | (2, 2) | -2 impact |
| JSON_LD_INVALID | (4, 2) | (6, 2) | +2 impact |
| PROMOTIONAL_CONTENT_INTERRUPTS | (3, 3) | (3, 1) | -2 effort |
| QUERY_COVERAGE_WEAK | (7, 2) | (5, 2) | -2 impact |
| SECTION_VAGUE_OPENER | (5, 2) | (3, 2) | -2 impact |
| SECTION_CROSS_REFERENCES | (6, 2) | (4, 2) | -2 impact |
| CONTACT_INFO_NOT_IN_HTML | (4, 2) | (3, 2) | -1 impact |

---

## Overall Summary: All 5 Parts

**Total codes reviewed:** ~130 in _ISSUE_SCORING

**Codes recommended to KEEP AS-IS:** ~65 (majority of established SEO checks)

**Codes recommended to CHANGE:** ~65

**Largest changes (priority rank drops of 30+):**
- H1_MULTIPLE: 56 → 16 (Google confirmed multiple H1s are fine)
- META_DESC_MISSING: 68 → 48 (not a ranking factor, only CTR impact)
- LLMS_TXT_MISSING: 58 → 28 (emerging convention, zero vendor confirmation)
- STATISTICS_COUNT_LOW: 66 → 36 (single paper, Heuristic confidence)
- GEO_SUMMARY_BURIED: 64 → 34 (Heuristic, DOM-depth speculation)
- H1_MISSING: 78 → 48 (no H1 is not an SEO penalty)

**Largest increase:**
- JSON_LD_INVALID: 36 → 56 (broken schema is more harmful than missing schema)

**Theme of the review:** The scoring system has been built incrementally over versions, and many older weights reflect outdated SEO assumptions (H1 dogma, meta description importance) while newer GEO weights were assigned high values prematurely (before real-world validation). The confidence_label system already tracks this tension — but the impact scores haven't been aligned with it.
