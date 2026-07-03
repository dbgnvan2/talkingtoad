---
status: draft-review
proposed: 2026-07-02
author: Hermes Agent
type: review
scope: AI-readiness core — ai_readiness + AI Bot Access + Schema Typing + Content Extractability + Citations (part 4 of 5)
---

# Scoring Weight Review — Part 4: AI-Readiness Core

> Each entry shows current weight, assessment, and recommendation. Also includes the confidence_label from `_AI_READINESS_CONFIDENCE` — this is a key factor in whether the weight is appropriate.

---

## Current Scoring Reference

| Code | Current (impact, effort) | Priority rank | Confidence label | Severity |
|------|--------------------------|---------------|------------------|----------|
| LLMS_TXT_MISSING | (6, 1) | 58 | Heuristic | info |
| LLMS_TXT_INVALID | (4, 2) | 36 | Heuristic | warning |
| SEMANTIC_DENSITY_LOW | (5, 3) | 44 | Heuristic | warning |
| DOCUMENT_PROPS_MISSING | (4, 2) | 36 | Reasonable proxy | warning |
| JSON_LD_MISSING | (7, 2) | 66 | Reasonable proxy | warning |
| CONVERSATIONAL_H2_MISSING | (4, 2) | 36 | Heuristic | info |
| BLOG_SECTIONS_MISSING | (5, 2) | 46 | Heuristic | warning |
| AI_BOT_SEARCH_BLOCKED | (8, 1) | 78 | Established | warning |
| AI_BOT_TRAINING_DISALLOWED | (0, 1) | -2 | Established | info |
| AI_BOT_USER_FETCH_BLOCKED | (4, 1) | 38 | Established | warning |
| AI_BOT_DEPRECATED_DIRECTIVE | (2, 1) | 18 | Established | warning |
| AI_BOT_NO_AI_DIRECTIVES | (1, 1) | 8 | Reasonable proxy | info |
| AI_BOT_BLANKET_DISALLOW | (9, 1) | 88 | Established | critical |
| AI_BOT_TABLE_STALE | (0, 1) | -2 | Heuristic | info |
| SCHEMA_TYPE_MISMATCH | (4, 2) | 36 | Reasonable proxy | warning |
| SCHEMA_DEPRECATED_TYPE | (2, 1) | 18 | Reasonable proxy | info |
| SCHEMA_TYPE_CONFLICT | (3, 2) | 26 | Reasonable proxy | warning |
| SCHEMA_VISIBLE_MISMATCH | (5, 2) | 46 | Established | warning |
| AI_CONTENT_NOT_IN_TEXT | (4, 2) | 36 | Reasonable proxy | warning |
| AI_PREVIEW_SUPPRESSED | (3, 1) | 28 | Established | info |
| AI_PREVIEW_BLOCKED_AT_BOT | (3, 1) | 28 | Established | info |
| AI_NO_VISUAL_COMPANION | (1, 1) | 8 | Reasonable proxy | info |
| AI_MAIN_CONTENT_LOW_RATIO | (2, 1) | 18 | Heuristic | warning |
| CONTENT_NOT_EXTRACTABLE_NO_TEXT | (6, 4) | 52 | Reasonable proxy | warning |
| CONTENT_THIN | (4, 3) | 34 | Reasonable proxy | warning |
| CONTENT_UNSTRUCTURED | (3, 2) | 26 | Heuristic | warning |
| CONTENT_IMAGE_HEAVY | (2, 3) | 14 | Heuristic | info |
| CITATIONS_MISSING_SUBSTANTIAL_CONTENT | (3, 2) | 26 | Reasonable proxy | info |
| CITATIONS_ORPHANED | (2, 1) | 18 | Heuristic | info |
| CITATIONS_SOURCES_INACCESSIBLE | (4, 3) | 34 | Heuristic | warning |

---

## General Observation

A pattern emerges in this section: **several codes with "Heuristic" confidence are weighted higher than codes with "Reasonable proxy" or even "Established" confidence.** The confidence labels were introduced precisely to track certainty, but the impact scores don't follow them. Heuristic checks should generally have lower impact scores to reflect that we're guessing.

---

## AI-Readiness Checks

### LLMS_TXT_MISSING — (6, 1) → 58 (Heuristic)

**Assessment:** Impact 6 is TOO HIGH. `/llms.txt` is an emerging convention (proposed by AnswerThePublic's founder as a way to guide LLM crawlers). No major AI engine (Google, OpenAI, Anthropic, Perplexity) has confirmed using it. It's a "Heuristic" confidence check — industry consensus only. Impact 6 is tied with CANONICAL_MISSING (a well-established SEO requirement). This should be impact 3 at most.

**Recommendation:** LOWER impact from 6 to 3. (3, 1) → 28

---

### LLMS_TXT_INVALID — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is too high for a heuristic check that follows from the same uncertain premise. Having an invalid llms.txt is less harmful than missing it entirely. Impact 2 is more appropriate.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

---

### SEMANTIC_DENSITY_LOW — (5, 3) → 44 (Heuristic)

**Assessment:** Impact 5 is TOO HIGH. This checks text-to-HTML ratio (<10%). On a typical nonprofit WordPress site with bloated themes, this will flag nearly every page. The threshold is arbitrary and the SEO/AI impact is indirect at best. This is a Heuristic check — impact 3 is more honest. Effort 3 (template/theme work) is appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 3) → 24

---

### DOCUMENT_PROPS_MISSING — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is too high for a PDF-specific check. Missing Title/Subject metadata in PDFs affects AI citation labels but has zero SEO impact and only affects PDF content. Impact 2 is more appropriate for this niche check.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

---

### JSON_LD_MISSING — (7, 2) → 66 (Reasonable proxy)

**Assessment:** Impact 7 is well-calibrated. JSON-LD structured data is the primary way Google understands page content for rich results, and AI engines use schema heavily for entity extraction and citation. This is one of the most important AI-readiness signals. The "Reasonable proxy" label probably understates this — Google has confirmed schema's importance for rich results.

**Recommendation:** KEEP AS-IS (7, 2) — consider upgrading confidence to "Established"

---

### CONVERSATIONAL_H2_MISSING — (4, 2) → 36 (Heuristic)

**Assessment:** Impact 4 is too high for a Heuristic check with no vendor confirmation. This flags H2s that don't start with conversational interrogatives (How, What, Why). There's no evidence this affects AI citation. It's an experiment, not a weightable signal. Impact 2 is appropriate.

**Recommendation:** LOWER impact from 4 to 2. (2, 2) → 16

---

### BLOG_SECTIONS_MISSING — (5, 2) → 46 (Heuristic)

**Assessment:** Impact 5 is too high. This checks whether a blog/article page has sufficient heading structure for AI citation anchors. The concept is sound (headings do serve as citation anchors for AI engines), but the confidence is Heuristic and the threshold is arbitrary (fewer than 3 headings). Impact 3 is more realistic.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

---

## AI Bot Access Checks

### AI_BOT_SEARCH_BLOCKED — (8, 1) → 78 (Established)

**Assessment:** Impact 8 is correct. Blocking a major AI search bot (GPTBot, Google-Extended, ClaudeBot) in robots.txt has a confirmed, direct effect on whether your content appears in AI search results (ChatGPT, Gemini, Perplexity, etc.). The confidence label is "Established" — this is vendor-confirmed. Keep.

**Recommendation:** KEEP AS-IS (8, 1)

---

### AI_BOT_TRAINING_DISALLOWED — (0, 1) → -2 (Established)

**Assessment:** Impact 0 is correct. This is intentionally a zero-impact observation. Blocking training bots doesn't affect AI search visibility. This is correctly an info-level, zero-impact check.

**Recommendation:** KEEP AS-IS (0, 1)

---

### AI_BOT_USER_FETCH_BLOCKED — (4, 1) → 38 (Established)

**Assessment:** Impact 4 is too high. This flag fires when a user-fetch bot (ChatGPT-User, Claude-User) is blocked in robots.txt — which has no effect because these bots don't honor robots.txt by design. The check itself tells the user their block is ineffective. Impact 2 is more appropriate (it's a misconfiguration, not a problem).

**Recommendation:** LOWER impact from 4 to 2. (2, 1) → 18

---

### AI_BOT_DEPRECATED_DIRECTIVE — (2, 1) → 18 (Established)

**Assessment:** Impact 2 is about right. Using old bot names (anthropic-ai, claude-web) means the rules don't apply to the current bots. Minor — confirmed fact but low impact. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### AI_BOT_NO_AI_DIRECTIVES — (1, 1) → 8 (Reasonable proxy)

**Assessment:** Impact 1 is correct. Not having explicit AI bot rules doesn't harm anything — by default, they're allowed. This is an info-level observation. Keep.

**Recommendation:** KEEP AS-IS (1, 1)

---

### AI_BOT_BLANKET_DISALLOW — (9, 1) → 88 (Established)

**Assessment:** Impact 9 is correct. `User-agent: * Disallow: /` blocks ALL bots, including Googlebot. This is catastrophic for a site's SEO and AI visibility. The only reason it's not 10 is that it's usually intentional (dev/staging). Keep.

**Recommendation:** KEEP AS-IS (9, 1)

---

### AI_BOT_TABLE_STALE — (0, 1) → -2 (Heuristic)

**Assessment:** Impact 0 is correct. Internal documentation check only. Keep.

**Recommendation:** KEEP AS-IS (0, 1)

---

## Schema Typing Checks

### SCHEMA_TYPE_MISMATCH — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. Using the wrong schema type (e.g., Product instead of Article) means Google's rich results may not apply and AI engines may misinterpret the content. This is a real quality signal. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### SCHEMA_DEPRECATED_TYPE — (2, 1) → 18 (Reasonable proxy)

**Assessment:** Impact 2 is correct. Using deprecated schema types is a minor hygiene issue — they still work but may not be supported forever. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### SCHEMA_TYPE_CONFLICT — (3, 2) → 26 (Reasonable proxy)

**Assessment:** Impact 3 is reasonable. Conflicting schema types (e.g., declaring both Product and Article on the same page) create ambiguity for parsers. Google may ignore the conflicting data. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

### SCHEMA_VISIBLE_MISMATCH — (5, 2) → 46 (Established)

**Assessment:** Impact 5 is reasonable. Google's own guidelines state that schema values should match visible page content. Mismatch can trigger manual actions or rich result loss. "Established" confidence is correct. Keep.

**Recommendation:** KEEP AS-IS (5, 2)

---

### AI_CONTENT_NOT_IN_TEXT — (4, 2) → 36 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable. Critical content in images/video/embeds that AI systems can't read as text is a real barrier to AI extraction. Impact 4 is appropriate for a "Reasonable proxy" signal.

**Recommendation:** KEEP AS-IS (4, 2)

---

### AI_PREVIEW_SUPPRESSED — (3, 1) → 28 (Established)

**Assessment:** Impact 3 is reasonable. Suppressing search/AI previews (nosnippet) is a deliberate choice — this flag informs the user that their content won't appear in AI Overviews. Impact 3 is appropriate for info level.

**Recommendation:** KEEP AS-IS (3, 1)

---

### AI_PREVIEW_BLOCKED_AT_BOT — (3, 1) → 28 (Established)

**Assessment:** Impact 3 is reasonable. Same as above — deliberate choice. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

---

### AI_NO_VISUAL_COMPANION — (1, 1) → 8 (Reasonable proxy)

**Assessment:** Impact 1 is correct. Text pages without images are fine — adding images is a nice improvement but not a problem. Keep.

**Recommendation:** KEEP AS-IS (1, 1)

---

### AI_MAIN_CONTENT_LOW_RATIO — (2, 1) → 18 (Heuristic)

**Assessment:** Impact 2 is reasonable. Main content <40% of visible text is a usability/extraction concern, not a direct harm. Heuristic confidence, low impact — correct calibration.

**Recommendation:** KEEP AS-IS (2, 1)

---

## Content Extractability

### CONTENT_NOT_EXTRACTABLE_NO_TEXT — (6, 4) → 52 (Reasonable proxy)

**Assessment:** Impact 6 is reasonable. A page with no visible text at all (images-only or JS-shell) is completely invisible to AI extractors. This is a significant barrier. However, effort 4 is too high — adding text to a page is a content-edit task, not "major dev work." Effort 2.

**Recommendation:** KEEP impact 6, LOWER effort from 4 to 2. (6, 2) → 56

---

### CONTENT_THIN — (4, 3) → 34 (Reasonable proxy)

**Assessment:** Impact 4 is reasonable for thin content (<100 words). Similar to the crawlability THIN_CONTENT check but at a stricter threshold and in the AI-readiness category. Effort 3 is too high — adding content is a wordpress-fixable content edit, effort 1-2.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 2. (4, 2) → 36

---

### CONTENT_UNSTRUCTURED — (3, 2) → 26 (Heuristic)

**Assessment:** Impact 3 is reasonable. No heading structure on a long page makes AI extraction harder. Heuristic confidence, moderate impact. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

### CONTENT_IMAGE_HEAVY — (2, 3) → 14 (Heuristic)

**Assessment:** Impact 2 is reasonable. Image-heavy pages (more images than text sections) are harder for AI to extract, but this is a heuristic observation. Effort 3 is too high — adding text alongside images is content work, effort 1-2.

**Recommendation:** KEEP impact 2, LOWER effort from 3 to 2. (2, 2) → 16

---

## Citation & Attribution

### CITATIONS_MISSING_SUBSTANTIAL_CONTENT — (3, 2) → 26 (Reasonable proxy)

**Assessment:** Impact 3 is reasonable. Pages with 200+ words but no citations are harder for AI to verify and cite authoritatively. This is a content quality signal. Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

### CITATIONS_ORPHANED — (2, 1) → 18 (Heuristic)

**Assessment:** Impact 2 is reasonable. Citations without surrounding context are less useful, but this is a minor content quality concern. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### CITATIONS_SOURCES_INACCESSIBLE — (4, 3) → 34 (Heuristic)

**Assessment:** Impact 4 is reasonable. Broken citation sources undermine the page's claims. For AI citation engines, a page citing broken sources is less quotable. However, effort 3 is too high — fixing a link is a trivial content-edit task, effort 1.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 1. (4, 1) → 38

---

## Part 4 Summary

| Code | Current | Proposed | Delta |
|------|---------|----------|-------|
| LLMS_TXT_MISSING | (6, 1) | (3, 1) | -3 impact |
| LLMS_TXT_INVALID | (4, 2) | (2, 2) | -2 impact |
| SEMANTIC_DENSITY_LOW | (5, 3) | (3, 3) | -2 impact |
| DOCUMENT_PROPS_MISSING | (4, 2) | (2, 2) | -2 impact |
| CONVERSATIONAL_H2_MISSING | (4, 2) | (2, 2) | -2 impact |
| BLOG_SECTIONS_MISSING | (5, 2) | (3, 2) | -2 impact |
| AI_BOT_USER_FETCH_BLOCKED | (4, 1) | (2, 1) | -2 impact |
| CONTENT_NOT_EXTRACTABLE_NO_TEXT | (6, 4) | (6, 2) | -2 effort |
| CONTENT_THIN | (4, 3) | (4, 2) | -1 effort |
| CONTENT_IMAGE_HEAVY | (2, 3) | (2, 2) | -1 effort |
| CITATIONS_SOURCES_INACCESSIBLE | (4, 3) | (4, 1) | -2 effort |

**Confidence–impact alignment:** After these changes, Heuristic checks would have a max impact of 3, Reasonable proxy max of 6, and Established max of 9 — a natural mapping that makes the scoring system internally consistent.
