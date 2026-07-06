# TalkingToad issue-scoring calibration — expert evaluation (Response R3)

Reviewer role: senior technical-SEO / GEO calibration review, mid-2026 knowledge base. Independent run; no repo access; judgments made per-code against the brief's effect_size ruler and verified vendor facts.

---

## 1. Methodology (model recommendation and derivation)

**Recommendation: a synthesis — Model B's two axes, hard-capped by Model A's confidence ceilings, with a discrete (not numeric) effect scale.**

Model B's stated weakness is manufacturing false precision by multiplying two uncertain numbers. I neutralize that in three ways: (1) effect_size is **categorical, not numeric** — the judgment required is only "could this mechanically gate indexing/citation, measurably move it, or is it marginal?" That mechanism question is answerable even for Heuristic-tier checks (you can know a check's *ceiling* without knowing its measured size). (2) The confidence tier acts as a **hard cap**, so an unproven claim can never score high regardless of claimed effect — this is Model A's anti-gaming property retained intact. (3) At effect = small, all tiers converge to 1–2, because tiny effects are tiny whatever the evidence; confidence only differentiates as claimed magnitude grows. Pure Model A's weakness (collapsing "measured once" with "pure guess") is handled by a fourth row: **Heuristic-measured** — Heuristic checks backed by ≥1 controlled study (in practice, the Aggarwal et al. lane: citations, quotations, statistics).

**Derivation matrix (impact integers):**

| confidence \ effect | none | small | moderate | large |
|---|---|---|---|---|
| Heuristic | 0 | 1 | 2 | 3 |
| Heuristic-measured | 0 | 2 | 3 | 4 |
| Reasonable proxy | 0 | 2 | 4 | 6 |
| Established | 0 | 2 | 6 | 9 (**10** if page-fatal) |

I added a **none** effect level for findings with no defect (positive/informational findings, auto-handled redirects, unverified links). The brief's three anchors have no home for these; forcing them to "small" would penalize non-problems.

**10-tier: keep it**, strictly for "removes the page from search/AI eligibility outright by documented mechanism": `NOINDEX_META`, `NOINDEX_HEADER`, `REDIRECT_LOOP`. `ROBOTS_BLOCKED` stays 9 (URL-only indexing remains possible). `BROKEN_LINK_404` at 10 is indefensible — a link *on* a page is not page-fatal.

**Severity: do not feed it into the health score.** Two independent knobs (impact, severity) guarantee drift — the current data already shows it (`NOINDEX_META` impact 10 labeled "warning"). Derive severity from derived_impact: ≥8 critical, 4–7 warning, ≤3 info. One source of truth.

**Page formula (task 4): the additive uncapped formula is unsound as-is.** Two fixes: (a) **normalize per-target checks to one issue row per page** carrying an occurrence count, like every other check, with an occurrence multiplier `min(1 + 0.25×(n−1), 2.0)` — five 404s costs 2×impact, not 5×; (b) add a **per-category cap of 25 points per page** so no single category can floor a page. Keep additivity otherwise — it stays explainable to a volunteer maintainer. Diminishing-returns curves across all issues would obscure "fix X, gain Y."

**Priority (task 5): yes, effort should weigh more.** Propose `priority_rank = impact×10 − effort×6` (effort now spans 0–30, enough to reorder within an impact tier, never across two tiers) **plus** a separate flagged "Quick wins" list: `impact ≥ 4 AND effort ≤ 1`. The badge does more for a non-technical maintainer than any formula tweak.

---

## 2. Full table — all 151 codes

Notes: `-` in current_confidence = no tier previously assigned. `Heuristic-measured` = exception lane (≥1 controlled study). Rationales use semicolons, no commas.

```csv
code,current_confidence,recommended_confidence,recommended_effect_size,derived_impact,current_impact,impact_changed,confidence_changed,reviewer_confidence,rationale
AI_BOT_BLANKET_DISALLOW,Established,Established,large,9,9,no,no,H,blanket disallow gates all crawling and citation
AI_BOT_DEPRECATED_DIRECTIVE,Established,Established,small,2,2,no,no,H,stale token is hygiene; no live effect
AI_BOT_NO_AI_DIRECTIVES,Reasonable proxy,Heuristic,small,1,1,no,yes,M,defaults already allow; advisory only
AI_BOT_SEARCH_BLOCKED,Established,Established,large,9,8,yes,no,H,gates citation eligibility for that AI engine
AI_BOT_TABLE_STALE,Heuristic,Heuristic,none,0,0,no,no,H,informational by design; keep zero
AI_BOT_TRAINING_DISALLOWED,Established,Established,none,0,0,no,no,H,legitimate owner choice; keep zero
AI_BOT_USER_FETCH_BLOCKED,Established,Established,small,2,4,yes,no,M,live fetch only; compliance vendor-specific
AI_CITED_PAGE,Established,Established,none,0,0,no,no,H,positive finding; keep zero
AI_CONTENT_NOT_IN_TEXT,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,non-text content impairs extraction; not gating
AI_HIGH_VALUE_UNCITED,Reasonable proxy,Heuristic,none,0,4,yes,yes,M,opportunity signal not a page defect
AI_MAIN_CONTENT_LOW_RATIO,Heuristic,Heuristic,moderate,2,2,no,no,M,boilerplate dilution plausibly hurts extraction
AI_NO_VISUAL_COMPANION,Reasonable proxy,Heuristic,small,1,1,no,yes,M,weak evidence visuals raise citation odds
AI_PREVIEW_BLOCKED_AT_BOT,Established,Established,moderate,6,3,yes,no,M,documented suppression; may be intentional though
AI_PREVIEW_SUPPRESSED,Established,Established,moderate,6,3,yes,no,M,nosnippet-class directives curb AI reuse
AI_TXT_MISSING,Heuristic,Heuristic,small,1,1,no,no,H,no vendor support; negligible adoption
AMPHTML_BROKEN,-,Reasonable proxy,small,2,4,yes,yes,H,AMP deprecated; broken variant largely ignored
ANCHOR_TEXT_GENERIC,-,Established,small,2,4,yes,yes,M,descriptive anchors documented; per-page effect small
AUTHOR_BYLINE_MISSING,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,EEAT authorship consensus; partially confirmed
BLOG_SECTIONS_MISSING,Heuristic,Heuristic,moderate,2,5,yes,no,M,citation-anchor theory plausible but unmeasured
BROKEN_LINK_404,-,Established,small,2,10,yes,yes,H,Google confirms broken links not ranking factor
BROKEN_LINK_410,-,Established,small,2,8,yes,yes,H,same as 404; UX and discovery only
BROKEN_LINK_503,-,Heuristic,small,1,4,yes,yes,M,often transient or bot blocking; verify
BROKEN_LINK_5XX,-,Reasonable proxy,small,2,7,yes,yes,M,may be transient; marginal ranking effect
CANONICAL_EXTERNAL,-,Established,moderate,6,5,yes,yes,M,honored hint can deindex the page
CANONICAL_MISSING,-,Established,moderate,6,6,no,yes,M,duplicate signals split without canonical
CANONICAL_SELF_MISSING,-,Established,small,2,5,yes,yes,H,self-canonical optional; Google infers
CENTRAL_CLAIM_BURIED,Heuristic,Heuristic,moderate,2,5,yes,no,M,answer-first is consensus advice; unmeasured
CHUNKS_NOT_SELF_CONTAINED,Heuristic,Heuristic,moderate,2,5,yes,no,M,chunk-retrieval logic plausible; unmeasured
CITATIONS_MISSING_SUBSTANTIAL_CONTENT,Reasonable proxy,Heuristic-measured,moderate,3,3,no,yes,M,cite-sources measured once in Aggarwal study
CITATIONS_ORPHANED,Heuristic,Heuristic,small,1,2,yes,no,L,vague condition; marginal effect
CITATIONS_SOURCES_INACCESSIBLE,Heuristic,Heuristic,small,1,4,yes,no,M,broken citations undermine trust marginally
CODE_BLOCK_MISSING_TECHNICAL,Heuristic,Heuristic,small,1,4,yes,no,M,formatting preference; no measured effect
COMPARISON_TABLE_MISSING,Heuristic,Heuristic,small,1,3,yes,no,M,table preference plausible; unmeasured
CONTACT_INFO_NOT_IN_HTML,Heuristic,Reasonable proxy,moderate,4,4,no,yes,M,NAP extractability strong local-SEO consensus
CONTENT_CLOAKING_DETECTED,Reasonable proxy,Reasonable proxy,large,6,8,yes,no,M,true cloaking penalized; detection uncertain
CONTENT_DATE_STALE_VISIBLE,Reasonable proxy,Reasonable proxy,small,2,4,yes,no,M,freshness matters query-dependently
CONTENT_IMAGE_HEAVY,Heuristic,Heuristic,small,1,2,yes,no,L,ratio heuristic; weak signal
CONTENT_NOT_EXTRACTABLE_NO_TEXT,Reasonable proxy,Established,large,9,6,yes,yes,H,no crawlable text gates citation outright
CONTENT_STALE,-,Heuristic,small,1,3,yes,yes,M,evergreen pages age fine
CONTENT_STAT_OUTDATED,Heuristic,Heuristic,small,1,2,yes,no,M,dated year reference marginal
CONTENT_THIN,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,thin pages rarely rank or get cited
CONTENT_UNSTRUCTURED,Heuristic,Reasonable proxy,moderate,4,3,yes,yes,M,headings aid chunking; broad consensus
CONVERSATIONAL_H2_MISSING,Heuristic,Heuristic,small,1,4,yes,no,M,question-heading fad; no measured lift
DATE_MODIFIED_MISSING,Reasonable proxy,Reasonable proxy,small,2,2,no,no,M,dates aid freshness assessment slightly
DATE_PUBLISHED_MISSING,Reasonable proxy,Reasonable proxy,small,2,3,yes,no,M,publication date minor freshness signal
DOCUMENT_PROPS_MISSING,Reasonable proxy,Established,small,2,4,yes,yes,M,Google documented use of PDF title metadata
EXTERNAL_CITATIONS_LOW,Reasonable proxy,Heuristic-measured,moderate,3,5,yes,yes,M,cite-sources measured once; narrow basis
EXTERNAL_LINK_SKIPPED,-,Heuristic,none,0,2,yes,yes,H,nothing verified wrong; informational
EXTERNAL_LINK_TIMEOUT,-,Heuristic,small,1,3,yes,yes,M,unverifiable; often transient
FAQ_SCHEMA_MISSING,Reasonable proxy,Established,small,2,2,no,yes,H,FAQ rich results removed 2026; understanding aid only
FAVICON_MISSING,-,Established,small,2,3,yes,yes,H,SERP favicon display documented; cosmetic
FIRST_VIEWPORT_NO_ANSWER,Heuristic,Heuristic,moderate,2,5,yes,no,M,answer-first plausible; pattern check unmeasured
GEO_SUMMARY_BURIED,Heuristic,Heuristic,moderate,2,5,yes,no,M,answer-first family duplicate; unmeasured
H1_MISSING,-,Reasonable proxy,moderate,4,6,yes,yes,M,Google says minor; aids extraction structure
H1_MULTIPLE,-,Established,small,2,5,yes,yes,H,Google confirms multiple H1s acceptable
HEADING_EMPTY,-,Heuristic,small,1,4,yes,yes,M,template junk; cosmetic
HEADING_SKIP,-,Heuristic,small,1,4,yes,yes,M,accessibility nicety; no ranking effect
HIGH_CRAWL_DEPTH,-,Reasonable proxy,moderate,4,5,yes,yes,M,deep pages crawled and weighted less
HTTPS_REDIRECT_MISSING,-,Established,moderate,6,9,yes,yes,M,duplicate HTTP host; small documented signal
HTTP_PAGE,-,Established,moderate,6,9,yes,yes,M,browser warnings plus documented lightweight signal
IMG_ALT_DUP_FILENAME,-,Heuristic,small,1,3,yes,yes,M,lazy alt text; marginal
IMG_ALT_GENERIC,-,Established,small,2,4,yes,yes,M,alt guidance documented; per-page effect small
IMG_ALT_MISSING,-,Established,small,2,5,yes,yes,M,image search and accessibility; page effect small
IMG_ALT_MISUSED,-,Heuristic,small,1,3,yes,yes,L,decorative alt convention; cosmetic
IMG_ALT_TOO_LONG,-,Heuristic,small,1,2,yes,yes,M,length threshold arbitrary
IMG_ALT_TOO_SHORT,-,Heuristic,small,1,3,yes,yes,M,length threshold arbitrary
IMG_BROKEN,-,Reasonable proxy,moderate,4,8,yes,yes,M,visible breakage; UX and image-search loss
IMG_DUPLICATE_CONTENT,-,Heuristic,small,1,2,yes,yes,L,duplicate images rarely matter
IMG_FORMAT_LEGACY,-,Reasonable proxy,small,2,2,no,yes,M,speed gain real; ranking effect small
IMG_NO_SRCSET,-,Reasonable proxy,small,2,2,no,yes,M,responsive delivery aids CWV slightly
IMG_OVERSCALED,-,Reasonable proxy,small,2,4,yes,yes,M,wasted bytes; CWV effect small
IMG_OVERSIZED,-,Established,small,2,5,yes,yes,M,CWV documented signal; effect small
IMG_POOR_COMPRESSION,-,Reasonable proxy,small,2,4,yes,yes,M,overlaps oversized; CWV small
IMG_SLOW_LOAD,-,Reasonable proxy,small,2,4,yes,yes,M,overlaps oversized; CWV small
INTERACTIVE_NO_ACCESSIBLE_NAME,-,Heuristic,small,1,4,yes,yes,M,accessibility issue; minimal search effect
INTERNAL_NOFOLLOW,-,Reasonable proxy,moderate,4,5,yes,yes,M,wastes internal discovery signals
INTERNAL_REDIRECT_301,-,Established,small,2,4,yes,yes,H,extra hop; equity passes regardless
JSON_LD_INVALID,Reasonable proxy,Reasonable proxy,moderate,4,4,no,no,M,invalid schema ignored; equivalent to missing
JSON_LD_MISSING,Reasonable proxy,Reasonable proxy,moderate,4,7,yes,no,M,schema aids eligibility; AI-citation evidence mixed
JS_DEPENDENT_NAVIGATION,-,Established,moderate,6,5,yes,yes,M,AI fetchers skip JS; nav links invisible
JS_RENDERED_CONTENT_DIFFERS,Reasonable proxy,Established,moderate,6,6,no,yes,M,AI fetchers read raw HTML only
LANDMARK_MAIN_MISSING,-,Heuristic,small,1,2,yes,yes,L,landmark absence marginal for extraction
LANDMARK_NAV_MISSING,-,Heuristic,small,1,2,yes,yes,L,landmark absence marginal
LANG_MISSING,-,Established,small,2,6,yes,yes,H,Google ignores lang attribute; accessibility only
LINK_EMPTY_ANCHOR,-,Reasonable proxy,small,2,7,yes,yes,M,accessibility plus lost anchor signal; small
LINK_PROFILE_PROMOTIONAL,Heuristic,Heuristic,small,1,4,yes,no,M,self-link ratio heuristic; unproven
LLMS_TXT_INVALID,Heuristic,Heuristic,small,1,2,yes,no,H,no measured lift; format detail
LLMS_TXT_MISSING,Heuristic,Heuristic,small,1,3,yes,no,H,no measured citation lift; low adoption
LOGIN_REDIRECT,-,Heuristic,none,0,2,yes,yes,M,usually intentional gating; informational
META_DESC_DUPLICATE,-,Established,small,2,4,yes,yes,H,descriptions not ranking factor; snippet only
META_DESC_MISSING,-,Established,small,2,7,yes,yes,H,not ranking factor; Google rewrites snippets
META_DESC_TOO_LONG,-,Established,small,2,3,yes,yes,H,truncation cosmetic
META_DESC_TOO_SHORT,-,Established,small,2,4,yes,yes,H,length guidance soft; snippet only
META_REFRESH_REDIRECT,-,Established,small,2,5,yes,yes,M,Google handles meta refresh; UX slow
MISSING_HSTS,-,Heuristic,small,1,4,yes,yes,H,security hardening; no search effect
MISSING_VIEWPORT_META,-,Established,moderate,6,6,no,yes,H,mobile-friendliness documented factor
MIXED_CONTENT,-,Reasonable proxy,moderate,4,6,yes,yes,M,blocked resources and warnings; modest effect
NOINDEX_HEADER,-,Established,large,10,10,no,yes,H,removes page from search entirely
NOINDEX_META,-,Established,large,10,10,no,yes,H,removes page from search entirely
NON_SEMANTIC_BUTTON,-,Heuristic,small,1,4,yes,yes,M,accessibility issue; minimal search effect
NOT_IN_SITEMAP,-,Established,small,2,4,yes,yes,H,sitemap optional for small linked sites
OG_DESC_MISSING,-,Heuristic,small,1,3,yes,yes,M,social preview only
OG_IMAGE_MISSING,-,Heuristic,small,1,3,yes,yes,M,social preview only
OG_TITLE_MISSING,-,Heuristic,small,1,4,yes,yes,M,social preview only
ORPHAN_CLAIM_TECHNICAL,Heuristic,Heuristic-measured,moderate,3,6,yes,yes,M,cite-sources measured once; narrow basis
ORPHAN_PAGE,-,Reasonable proxy,moderate,4,6,yes,yes,M,discovery impaired; sitemap may compensate
PAGE_SIZE_LARGE,-,Reasonable proxy,small,2,5,yes,yes,M,speed effect small on modern crawling
PAGE_TIMEOUT,-,Reasonable proxy,large,6,6,no,yes,M,unfetchable page gates everything if persistent
PAGINATION_LINKS_PRESENT,-,Established,none,0,2,yes,yes,H,Google ignores rel next prev since 2019
PARA_TOO_LONG,-,Heuristic,small,1,4,yes,yes,M,readability preference; threshold arbitrary
PDF_TOO_LARGE,-,Heuristic,small,1,4,yes,yes,M,large PDFs still indexed
PLACEHOLDER_LINK,-,Reasonable proxy,small,2,7,yes,yes,M,functional defect; ranking effect marginal
PROMOTIONAL_CONTENT_INTERRUPTS,Heuristic,Heuristic,small,1,3,yes,no,M,classifier-based; unproven effect
QUERY_COVERAGE_WEAK,Heuristic,Heuristic,moderate,2,5,yes,no,M,topical coverage proxy; crude measure
QUOTATIONS_MISSING,Heuristic,Heuristic-measured,moderate,3,4,yes,yes,M,quotation lift measured once in Aggarwal study
RAW_HTML_JS_DEPENDENT,Reasonable proxy,Established,large,9,6,yes,yes,H,app shell invisible to non-rendering AI fetchers
REDIRECT_301,-,Established,small,2,3,yes,yes,M,normal behavior; equity passes
REDIRECT_302,-,Established,small,2,4,yes,yes,H,PageRank passes; only canonicalization ambiguity
REDIRECT_CASE_NORMALISE,-,Established,none,0,2,yes,yes,H,automatic normalisation harmless
REDIRECT_CHAIN,-,Established,small,2,6,yes,yes,M,Google follows chains; latency only
REDIRECT_LOOP,-,Established,large,10,10,no,yes,H,page unreachable; fatal
REDIRECT_TRAILING_SLASH,-,Established,none,0,2,yes,yes,H,automatic normalisation harmless
ROBOTS_BLOCKED,-,Established,large,9,9,no,yes,H,blocks crawling; URL-only indexing still possible
SCHEMA_DEPRECATED_TYPE,Reasonable proxy,Established,small,2,2,no,yes,H,deprecations vendor-documented; low stakes
SCHEMA_MISSING,-,Reasonable proxy,moderate,4,5,yes,yes,M,duplicate of JSON_LD_MISSING; merge codes
SCHEMA_ORG_MISSING,Reasonable proxy,Reasonable proxy,moderate,4,5,yes,no,M,entity identification aids knowledge surfaces
SCHEMA_TYPE_CONFLICT,Reasonable proxy,Reasonable proxy,small,2,3,yes,no,M,conflicting types confuse parsing slightly
SCHEMA_TYPE_MISMATCH,Reasonable proxy,Reasonable proxy,small,2,4,yes,no,M,mismatch inference itself heuristic
SCHEMA_VISIBLE_MISMATCH,Established,Established,moderate,6,5,yes,no,H,violates documented structured-data policy
SECTION_CROSS_REFERENCES,Heuristic,Heuristic,small,1,6,yes,no,M,phrase detection; chunk theory unmeasured
SECTION_VAGUE_OPENER,Heuristic,Heuristic,small,1,5,yes,no,M,phrase detection; unmeasured
SEMANTIC_DENSITY_LOW,Heuristic,Heuristic,small,1,3,yes,no,M,text-HTML ratio crude proxy
SITEMAP_MISSING,-,Established,small,2,6,yes,yes,H,small well-linked sites need no sitemap
STATISTICS_COUNT_LOW,Heuristic,Heuristic-measured,moderate,3,5,yes,yes,M,statistics lift measured once in Aggarwal study
STRUCTURED_ELEMENTS_LOW,Heuristic,Heuristic,small,1,3,yes,no,M,element-count heuristic
THIN_CONTENT,-,Reasonable proxy,moderate,4,6,yes,yes,M,thin pages weak; 300-word threshold arbitrary
TITLE_DUPLICATE,-,Reasonable proxy,moderate,4,5,yes,yes,M,undifferentiated titles blur relevance
TITLE_H1_MISMATCH,-,Heuristic,small,1,6,yes,yes,M,mismatch often legitimate; no evidence of harm
TITLE_META_DUPLICATE_PAIR,-,Heuristic,small,1,6,yes,yes,M,double-counts two other codes; drop
TITLE_MISSING,-,Established,moderate,6,9,yes,yes,H,titles documented element; Google generates fallback
TITLE_TOO_LONG,-,Established,small,2,4,yes,yes,H,truncation cosmetic; rewrites common
TITLE_TOO_SHORT,-,Heuristic,small,1,5,yes,yes,M,short descriptive titles fine
TWITTER_CARD_MISSING,-,Heuristic,small,1,3,yes,yes,M,social preview only
UA_CONTENT_DIFFERS,Reasonable proxy,Reasonable proxy,large,6,7,yes,no,M,AI agents served less content; near-gating
UNSAFE_CROSS_ORIGIN_LINK,-,Established,none,0,3,yes,yes,H,browsers imply noopener since 2021
URL_HAS_SPACES,-,Established,small,2,5,yes,yes,M,encoded spaces ugly but functional
URL_HAS_UNDERSCORES,-,Established,small,2,2,no,yes,H,hyphens documented preference; effect tiny
URL_TOO_LONG,-,Heuristic,small,1,2,yes,yes,M,length threshold arbitrary
URL_UPPERCASE,-,Reasonable proxy,small,2,3,yes,yes,M,case variants risk duplicate URLs
WRONG_PLACEHOLDER_LINK,-,Reasonable proxy,small,2,7,yes,yes,M,functional defect; ranking effect marginal
WWW_CANONICALIZATION,-,Reasonable proxy,moderate,4,5,yes,yes,M,host duplication splits signals; usually auto-resolved
```

**Indefensible current impacts (task 3, headline items):** `BROKEN_LINK_404` (10 → 2), `BROKEN_LINK_410` (8 → 2), `META_DESC_MISSING` (7 → 2), `LINK_EMPTY_ANCHOR` (7 → 2), `LANG_MISSING` (6 → 2), `SECTION_CROSS_REFERENCES` (6 → 1), `TITLE_H1_MISMATCH` (6 → 1), `SITEMAP_MISSING` (6 → 2), `H1_MULTIPLE` (5 → 2), `REDIRECT_CHAIN` (6 → 2), plus the systematic *under*-scoring of JS-shell/no-text pages (6 → 9). Full detail in the CSV and section 4.

---

## 3. Overlap clusters (task 6)

Clusters where one root cause fires multiple codes and the additive formula stacks penalties:

1. **JS app shell** — `RAW_HTML_JS_DEPENDENT` + `JS_RENDERED_CONTENT_DIFFERS` + `JS_DEPENDENT_NAVIGATION` + `SEMANTIC_DENSITY_LOW` + potentially `THIN_CONTENT`/`CONTENT_UNSTRUCTURED` (raw HTML is empty). A single Elementor/JS-heavy page could lose 25–35 points for one architectural cause. **Fix:** make `RAW_HTML_JS_DEPENDENT` a graded parent; suppress all children when it fires.
2. **No JSON-LD at all** — `JSON_LD_MISSING` + `SCHEMA_MISSING` (these two are the *same condition* in two categories — merge them into one code) + `SCHEMA_ORG_MISSING` + `FAQ_SCHEMA_MISSING` + `DATE_PUBLISHED_MISSING` + `DATE_MODIFIED_MISSING`. A schema-less blog post loses ~20 points for one absent block. **Fix:** merge the two "missing" codes; suppress all field-level schema children when no JSON-LD exists.
3. **No TLS configuration** — `HTTP_PAGE` + `HTTPS_REDIRECT_MISSING` + `MIXED_CONTENT` + `MISSING_HSTS` (+ often `WWW_CANONICALIZATION`). One server-config root cause, up to 4 codes on every page. **Fix:** promote to a single site-level finding; charge each page once (the worst code only).
4. **Answer-first trio** — `CENTRAL_CLAIM_BURIED` + `FIRST_VIEWPORT_NO_ANSWER` + `GEO_SUMMARY_BURIED` measure nearly the same heuristic three ways (−15 currently for one editorial style). **Fix:** merge into one graded "answer placement" check.
5. **Sourcing/citations family** — `CITATIONS_MISSING_SUBSTANTIAL_CONTENT` + `EXTERNAL_CITATIONS_LOW` + `ORPHAN_CLAIM_TECHNICAL` + `QUOTATIONS_MISSING` (+ `LINK_PROFILE_PROMOTIONAL`) all fire on a page with zero outbound sourcing. **Fix:** one graded "external sourcing" parent; children become detail annotations.
6. **Section self-containment** — `CHUNKS_NOT_SELF_CONTAINED` + `SECTION_CROSS_REFERENCES` + `SECTION_VAGUE_OPENER`: same chunk-independence theory, three detectors. **Fix:** merge into one graded check.
7. **Title/meta duplication triple-count** — `TITLE_META_DUPLICATE_PAIR` fires exactly when `TITLE_DUPLICATE` and `META_DESC_DUPLICATE` both fire. **Fix:** drop the pair code (or suppress the two children when it fires).
8. **Heavy image** — `IMG_OVERSIZED` + `IMG_POOR_COMPRESSION` + `IMG_OVERSCALED` + `IMG_FORMAT_LEGACY` + `IMG_SLOW_LOAD` + `IMG_NO_SRCSET`: one unoptimized hero image can trip five or six codes. **Fix:** one graded "image weight" issue per page; individual codes as annotations.
9. **Alt-text family** — `IMG_ALT_MISSING`/`GENERIC`/`TOO_SHORT`/`TOO_LONG`/`DUP_FILENAME`/`MISUSED`: a site with no alt discipline trips several per page (and "photo" trips GENERIC and TOO_SHORT simultaneously). **Fix:** one graded "alt-text quality" issue per page.
10. **Social meta** — `OG_TITLE_MISSING` + `OG_DESC_MISSING` + `OG_IMAGE_MISSING` + `TWITTER_CARD_MISSING`: absence of one plugin setting = 4 codes (−13 currently). **Fix:** merge into one "social preview metadata" check.
11. **Blanket robots disallow** — `AI_BOT_BLANKET_DISALLOW` implies `AI_BOT_SEARCH_BLOCKED`, `AI_BOT_USER_FETCH_BLOCKED`, and `ROBOTS_BLOCKED` on every page. **Fix:** suppress children when the blanket code fires.
12. **Noindexed page** — a deliberately noindexed page will also trip `NOT_IN_SITEMAP`, `ORPHAN_PAGE`, content and metadata checks. **Fix:** when `NOINDEX_*` fires, suppress all discoverability/content checks on that page (they are out of scope for a page excluded from search).
13. **Redirect chain** — `REDIRECT_CHAIN` co-fires with `REDIRECT_301`/`REDIRECT_302` per hop and overlaps `INTERNAL_REDIRECT_301`. **Fix:** chain suppresses single-hop codes for the same URL path.
14. **Poorly linked page** — `ORPHAN_PAGE` + `NOT_IN_SITEMAP` + `HIGH_CRAWL_DEPTH` stack on the same neglected page. Legitimate partial overlap; **fix** via the per-category cap rather than suppression.
15. **Thin page** — `CONTENT_THIN` (<100 words) is a strict subset of `THIN_CONTENT` (<300 words); both fire on very short pages, plus `CONTENT_UNSTRUCTURED`/`STRUCTURED_ELEMENTS_LOW`. **Fix:** keep only the most severe of the word-count pair; cap the cluster.

---

## 4. Top 20 most-consequential changes (ranked)

1. **BROKEN_LINK_404: 10 → 2, plus per-occurrence normalization.** The single largest distortion in the tool. Google has repeatedly confirmed broken outbound links are not a ranking factor; combined with per-link emission, one page with five dead links currently loses 50 points — more than a noindexed page ever could.
2. **Per-target counting rule: convert to one issue per page with count and a 2× occurrence cap.** Not a code change, but without it no impact value for the link family is defensible.
3. **RAW_HTML_JS_DEPENDENT: 6 → 9.** GPTBot/ClaudeBot/PerplexityBot do not execute JavaScript; an app shell with near-zero raw text is invisible to AI engines. This is the most under-scored GEO issue in the registry.
4. **CONTENT_NOT_EXTRACTABLE_NO_TEXT: 6 → 9.** "No crawlable content" is the brief's own definitional example of a large/gating effect; it should sit with the 9-tier, not mid-pack.
5. **META_DESC_MISSING: 7 → 2.** Vendor-documented: not a ranking factor, and Google rewrites the majority of descriptions anyway. Current value near TITLE_MISSING territory is indefensible.
6. **BROKEN_LINK_410: 8 → 2** and **BROKEN_LINK_5XX: 7 → 2.** Same mechanism as 404; 5XX additionally suffers transient false positives.
7. **TITLE_MISSING: 9 → 6.** Titles matter and are documented, but a missing title does not deindex a page — Google generates one. 9 conflates "important" with "fatal."
8. **HTTP_PAGE and HTTPS_REDIRECT_MISSING: 9 → 6 each, charged once as a cluster.** The HTTPS ranking signal is documented but lightweight; the current 9+9 stacking (often plus MIXED_CONTENT) can floor a page for one server setting.
9. **LANG_MISSING: 6 → 2.** Google explicitly ignores the lang attribute for language detection; this is an accessibility item, not an SEO one.
10. **LINK_EMPTY_ANCHOR: 7 → 2.** Accessibility-significant, search-marginal; 7 puts it above real indexing issues.
11. **SECTION_CROSS_REFERENCES: 6 → 1 and SECTION_VAGUE_OPENER: 5 → 1.** Pure phrase-detection heuristics with no measured effect were carrying warning-tier weight; the confidence cap exists precisely for these.
12. **JSON_LD_MISSING: 7 → 4 (and merge with SCHEMA_MISSING).** Schema's effect on LLM citation is a reasonable proxy at best, and the same absence currently fires two codes in two categories.
13. **SITEMAP_MISSING: 6 → 2.** Google's own documentation says small, well-linked sites (the tool's entire audience) generally don't need a sitemap.
14. **TITLE_H1_MISMATCH: 6 → 1.** Deliberate title/H1 divergence is a legitimate, common practice; no evidence of harm.
15. **TITLE_META_DUPLICATE_PAIR: 6 → 1 and drop the code.** It is pure double-counting of two codes that already fire.
16. **AI_PREVIEW_SUPPRESSED / AI_PREVIEW_BLOCKED_AT_BOT: 3 → 6.** nosnippet-class directives are documented to remove content from AI answer surfaces — for a GEO tool this is a mid-tier finding, not trivia. For non-technical WordPress users these headers are usually plugin residue, not intent.
17. **IMG_BROKEN: 8 → 4.** A broken image is visible and worth fixing but is not near-fatal; 8 placed it above robots-level issues in practice.
18. **H1_MULTIPLE: 5 → 2 and H1_MISSING: 6 → 4.** Google has directly stated multiple H1s are fine and H1s are not critical; the structure argument justifies moderate at most.
19. **Aggarwal lane normalization: STATISTICS_COUNT_LOW 5 → 3, EXTERNAL_CITATIONS_LOW 5 → 3, ORPHAN_CLAIM_TECHNICAL 6 → 3, QUOTATIONS_MISSING 4 → 3.** All four rest on one measured study; the Heuristic-measured lane gives them uniform, honest weight instead of scattered hand-set values.
20. **REDIRECT_CHAIN: 6 → 2 and REDIRECT_302: 4 → 2.** Per the given vendor facts, both redirect types pass PageRank and chains are followed; residual cost is latency and canonicalization ambiguity only.

---

## 5. Open questions / limits of this judgment

- **AI-citation mechanics are largely unobservable.** Nobody outside the vendors knows how ChatGPT/Perplexity/AI Overviews weight schema, headings, or answer placement in retrieval and citation selection. Every `ai_readiness` moderate rating here is a mechanism argument, not a measurement. Reviewer_confidence M throughout that category reflects this honestly.
- **Aggarwal generalizability.** The Heuristic-measured lane rests on one study, ~1,000 queries, one generation model, in a pre-2024 retrieval setup. If replication fails on 2026-era engines, that lane collapses back to plain Heuristic (impact 1–2). I would want TalkingToad's own citation-tracking data (`AI_CITED_PAGE`) correlated against these checks before trusting the lane further.
- **Intentionality ambiguity.** `AI_PREVIEW_*`, `AI_BOT_SEARCH_BLOCKED`, `LOGIN_REDIRECT`, and noindex directives may be deliberate owner choices. The tool already recognizes this for training bots (impact 0); a per-site "acknowledge as intentional" mechanism would resolve the tension better than any impact value can.
- **Fast-moving vendor behavior** (flagged per-row via reviewer_confidence): AI-bot robots.txt compliance policies, nosnippet↔AI Overviews coupling, llms.txt adoption, and schema's role in LLM grounding could all shift within 6–12 months. I would re-run this calibration semi-annually.
- **Effect thresholds inside checks** (150-word paragraphs, 125-char alt text, 300-word thin content, 40% main-content ratio) are arbitrary and I could not evaluate their false-positive rates without crawl data. Several "small/1" ratings would drop to informational if false-positive rates are high.
- **The none-tier is a deliberate deviation** from the brief's three-anchor ruler. If the comparison agent forced those codes into "small," expect systematic +1/+2 differences on ~8 rows; that is a scale disagreement, not a substantive one.
- **Health-score semantics.** With these recalibrated (generally lower) impacts, typical site scores will rise. That is correct behavior — the current scores are deflated by inflated cosmetic penalties — but you may want to re-baseline any historical score comparisons after adoption.
