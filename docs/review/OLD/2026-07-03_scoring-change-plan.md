---
status: proposed-change-plan
audit_date: 2026-07-03
auditor: Claude Code (Opus 4.8)
companion: 2026-07-03_code-audit-report.md (Phases 1-3), 2026-07-03_remediation-plan.md
governance: REPORT-ONLY — do not apply to registry.py until owner approves
---

# Phase 4 — Scoring Change Plan (all 151 codes)

Generated from `api/crawler/checkers/registry.py` (extracted grid) with the auditor's
adjudicated decisions applied as config. Every impact change carries a rationale and states
which prior reviewer it sides with; every effort change cites a scope reason; fixability
corrections are explicit.

**Method corrections vs the prior reviews:**
- **Effort is a scope/work-size rubric, INDEPENDENT of fixability.** (My first pass wrongly
  derived effort from fixability and inflated ~60 trivial `developer_needed` one-liners — see
  audit report §3.4 revision. Corrected: current efforts are the baseline; only the specific
  miscalibrations below change.)
- **Confidence-cap violations are FLAGGED, not force-applied.** 15 `ai_readiness` codes carry a
  Heuristic label but impact 4-7. Slamming them to ≤3 would gut the GEO checks. They are marked
  `⚠ …exceeds cap` and resolved by the **confidence × effect_size model migration** (remediation
  R5), which assigns each an `effect_size` so its impact is derived, not capped away.

**Tally: 20 value changes · 121 keep · 1 deprecate · 8 pending-impl · 1 fix-misfire.**

| Category | Code | Cur (i,e) | Cur fix | Conf | Final (i,e) | Final fix | Status | Rationale / adjudication |
|---|---|---|---|---|---|---|---|---|
| ai_readiness | `AI_BOT_BLANKET_DISALLOW` | (9,1) | developer_needed | Established | (9,1) | developer_needed | keep | — |
| ai_readiness | `AI_BOT_DEPRECATED_DIRECTIVE` | (2,1) | developer_needed | Established | (2,1) | developer_needed | keep | — |
| ai_readiness | `AI_BOT_NO_AI_DIRECTIVES` | (1,1) | developer_needed | Reasonable proxy | (1,1) | developer_needed | keep | — |
| ai_readiness | `AI_BOT_SEARCH_BLOCKED` | (8,1) | developer_needed | Established | (8,1) | developer_needed | keep | — |
| ai_readiness | `AI_BOT_TABLE_STALE` | (0,1) | developer_needed | Heuristic | (0,1) | developer_needed | keep | — |
| ai_readiness | `AI_BOT_TRAINING_DISALLOWED` | (0,1) | developer_needed | Established | (0,1) | developer_needed | keep | — |
| ai_readiness | `AI_BOT_USER_FETCH_BLOCKED` | (4,1) | developer_needed | Established | (4,1) | developer_needed | keep | KEEP 4 — Claude-User honors robots.txt (vendor-confirmed 2026); block has real cost. Claude>Hermes(drop-to-2). |
| ai_readiness | `AI_CITED_PAGE` | (0,0) | content_edit | Established | (0,0) | content_edit | keep | — |
| ai_readiness | `AI_CONTENT_NOT_IN_TEXT` | (4,2) | content_edit | Reasonable proxy | (4,2) | content_edit | keep | — |
| ai_readiness | `AI_HIGH_VALUE_UNCITED` | (4,2) | content_edit | Reasonable proxy | (4,2) | content_edit | keep | — |
| ai_readiness | `AI_MAIN_CONTENT_LOW_RATIO` | (2,1) | content_edit | Heuristic | (2,1) | content_edit | keep | — |
| ai_readiness | `AI_NO_VISUAL_COMPANION` | (1,1) | content_edit | Reasonable proxy | (1,1) | content_edit | keep | — |
| ai_readiness | `AI_PREVIEW_BLOCKED_AT_BOT` | (3,1) | developer_needed | Established | (3,1) | developer_needed | keep | — |
| ai_readiness | `AI_PREVIEW_SUPPRESSED` | (3,1) | developer_needed | Established | (3,1) | developer_needed | keep | — |
| ai_readiness | `AI_TXT_MISSING` | (1,1) | developer_needed | Heuristic | (1,1) | developer_needed | keep | — |
| ai_readiness | `AUTHOR_BYLINE_MISSING` | (4,2) | content_edit | Reasonable proxy | (4,2) | content_edit | keep | — |
| ai_readiness | `BLOG_SECTIONS_MISSING` | (5,2) | content_edit | Heuristic | (5,2) | content_edit | keep | ⚠ impact 5 exceeds Heuristic cap 3 — review |
| ai_readiness | `CENTRAL_CLAIM_BURIED` | (5,3) | content_edit | Heuristic | (5,3) | content_edit | PENDING | PENDING-IMPL: implement LLM classifier — remediation R8; ⚠ impact 5 exceeds Heuristic cap 3 — review |
| ai_readiness | `CHUNKS_NOT_SELF_CONTAINED` | (5,4) | content_edit | Heuristic | (5,4) | content_edit | PENDING | PENDING-IMPL: implement LLM classifier — remediation R8; ⚠ impact 5 exceeds Heuristic cap 3 — review |
| ai_readiness | `CITATIONS_MISSING_SUBSTANTIAL_CONTENT` | (3,2) | content_edit | Reasonable proxy | (3,2) | content_edit | FIX | FIX-MISFIRE: fires on EVERY >200-word page (hardcoded empty citations). Fix input or fold into EXTERNAL_CITATIONS_LOW — remediation R6. |
| ai_readiness | `CITATIONS_ORPHANED` | (2,1) | content_edit | Heuristic | (2,1) | content_edit | PENDING | PENDING-IMPL: fix citation model to parse real citations — remediation R6 |
| ai_readiness | `CITATIONS_SOURCES_INACCESSIBLE` | (4,3) | content_edit | Heuristic | (4,3) | content_edit | PENDING | PENDING-IMPL: implement source-accessibility HTTP check — remediation R6; ⚠ impact 4 exceeds Heuristic cap 3 — review |
| ai_readiness | `CODE_BLOCK_MISSING_TECHNICAL` | (4,2) | content_edit | Heuristic | (4,2) | content_edit | keep | ⚠ impact 4 exceeds Heuristic cap 3 — review |
| ai_readiness | `COMPARISON_TABLE_MISSING` | (3,2) | content_edit | Heuristic | (3,2) | content_edit | keep | — |
| ai_readiness | `CONTACT_INFO_NOT_IN_HTML` | (4,2) | content_edit | Heuristic | (4,2) | content_edit | keep | ⚠ impact 4 exceeds Heuristic cap 3 — review |
| ai_readiness | `CONTENT_CLOAKING_DETECTED` | (8,4) | developer_needed | Reasonable proxy | (8,4) | developer_needed | PENDING | PENDING-IMPL: wire in js_renderer (Playwright) — remediation R7; also fix severity 'error'→'warning'; ⚠ impact 8 exceeds Reasonable proxy cap 6 — review |
| ai_readiness | `CONTENT_DATE_STALE_VISIBLE` | (4,2) | content_edit | Reasonable proxy | (4,2) | content_edit | keep | — |
| ai_readiness | `CONTENT_IMAGE_HEAVY` | (2,3) | content_edit | Heuristic | (2,3) | content_edit | keep | — |
| ai_readiness | `CONTENT_NOT_EXTRACTABLE_NO_TEXT` | (6,4) | content_edit | Reasonable proxy | (6,4) | content_edit | keep | — |
| ai_readiness | `CONTENT_STAT_OUTDATED` | (2,1) | content_edit | Heuristic | (2,1) | content_edit | keep | — |
| ai_readiness | `CONTENT_THIN` | (4,3) | content_edit | Reasonable proxy | (4,3) | content_edit | keep | — |
| ai_readiness | `CONTENT_UNSTRUCTURED` | (3,2) | content_edit | Heuristic | (3,2) | content_edit | keep | — |
| ai_readiness | `CONVERSATIONAL_H2_MISSING` | (4,2) | content_edit | Heuristic | (4,2) | content_edit | keep | ⚠ impact 4 exceeds Heuristic cap 3 — review |
| ai_readiness | `DATE_MODIFIED_MISSING` | (2,1) | developer_needed | Reasonable proxy | (2,1) | developer_needed | keep | — |
| ai_readiness | `DATE_PUBLISHED_MISSING` | (3,1) | developer_needed | Reasonable proxy | (3,1) | developer_needed | keep | — |
| ai_readiness | `DOCUMENT_PROPS_MISSING` | (4,2) | content_edit | Reasonable proxy | (4,2) | content_edit | keep | — |
| ai_readiness | `EXTERNAL_CITATIONS_LOW` | (7,2) | content_edit | Reasonable proxy | (5,2) | content_edit | CHANGE | overlaps E-E-A-T; both reviews converge on 5. |
| ai_readiness | `FAQ_SCHEMA_MISSING` | (3,2) | developer_needed | Reasonable proxy | (2,2) | developer_needed | CHANGE | FAQ rich results fully removed 2026-05-07; schema still aids understanding but yields no rich result. Claude>Hermes. |
| ai_readiness | `FIRST_VIEWPORT_NO_ANSWER` | (5,2) | content_edit | Heuristic | (5,2) | content_edit | keep | ⚠ impact 5 exceeds Heuristic cap 3 — review |
| ai_readiness | `GEO_SUMMARY_BURIED` | (7,3) | content_edit | Heuristic | (5,3) | content_edit | CHANGE | was 7 via Cycle-GG penalty=20 translation artifact, not evidence; align to answer-first peers (5). |
| ai_readiness | `JSON_LD_INVALID` | (4,2) | developer_needed | Reasonable proxy | (4,2) | developer_needed | keep | — |
| ai_readiness | `JSON_LD_MISSING` | (7,2) | developer_needed | Reasonable proxy | (7,2) | developer_needed | keep | ⚠ impact 7 exceeds Reasonable proxy cap 6 — review |
| ai_readiness | `JS_RENDERED_CONTENT_DIFFERS` | (6,4) | developer_needed | Reasonable proxy | (6,4) | developer_needed | PENDING | PENDING-IMPL: wire in js_renderer (Playwright) — remediation R7 |
| ai_readiness | `LINK_PROFILE_PROMOTIONAL` | (4,2) | content_edit | Heuristic | (4,2) | content_edit | keep | ⚠ impact 4 exceeds Heuristic cap 3 — review |
| ai_readiness | `LLMS_TXT_INVALID` | (4,2) | content_edit | Heuristic | (2,2) | content_edit | CHANGE | Heuristic; low. Cap→2. |
| ai_readiness | `LLMS_TXT_MISSING` | (6,1) | content_edit | Heuristic | (3,1) | content_edit | CHANGE | Heuristic; no measured citation lift, Google declined support. Cap→3. |
| ai_readiness | `ORPHAN_CLAIM_TECHNICAL` | (6,2) | content_edit | Heuristic | (6,2) | content_edit | keep | ⚠ impact 6 exceeds Heuristic cap 3 — review |
| ai_readiness | `PROMOTIONAL_CONTENT_INTERRUPTS` | (3,3) | content_edit | Heuristic | (3,3) | content_edit | PENDING | PENDING-IMPL: implement LLM classifier — remediation R8 |
| ai_readiness | `QUERY_COVERAGE_WEAK` | (7,2) | content_edit | Heuristic | (5,2) | content_edit | CHANGE | Heuristic at impact 7 violates confidence cap; no study — reduce to effect-based 5 (calibrate). |
| ai_readiness | `QUOTATIONS_MISSING` | (6,2) | content_edit | Heuristic | (4,2) | content_edit | CHANGE | Heuristic, single-study; moderate effect. Hermes(4)=Claude(4-5). |
| ai_readiness | `RAW_HTML_JS_DEPENDENT` | (6,3) | developer_needed | Reasonable proxy | (6,3) | developer_needed | keep | — |
| ai_readiness | `SCHEMA_DEPRECATED_TYPE` | (2,1) | content_edit | Reasonable proxy | (2,1) | content_edit | keep | — |
| ai_readiness | `SCHEMA_ORG_MISSING` | (5,2) | wp_fixable | Reasonable proxy | (5,2) | wp_fixable | keep | — |
| ai_readiness | `SCHEMA_TYPE_CONFLICT` | (3,2) | content_edit | Reasonable proxy | (3,2) | content_edit | keep | — |
| ai_readiness | `SCHEMA_TYPE_MISMATCH` | (4,2) | content_edit | Reasonable proxy | (4,2) | content_edit | keep | — |
| ai_readiness | `SCHEMA_VISIBLE_MISMATCH` | (5,2) | content_edit | Established | (5,2) | content_edit | keep | — |
| ai_readiness | `SECTION_CROSS_REFERENCES` | (6,2) | content_edit | Heuristic | (6,2) | content_edit | keep | ⚠ impact 6 exceeds Heuristic cap 3 — review |
| ai_readiness | `SECTION_VAGUE_OPENER` | (5,2) | content_edit | Heuristic | (5,2) | content_edit | keep | ⚠ impact 5 exceeds Heuristic cap 3 — review |
| ai_readiness | `SEMANTIC_DENSITY_LOW` | (5,3) | developer_needed | Heuristic | (3,3) | developer_needed | CHANGE | page-builder false-positive magnet; deweight now, deprecate once AI_MAIN_CONTENT_LOW_RATIO covers it. |
| ai_readiness | `STATISTICS_COUNT_LOW` | (7,2) | content_edit | Heuristic | (5,2) | content_edit | CHANGE | Heuristic tier but measured (Aggarwal) — exception lane; don't floor. Claude(4-5). |
| ai_readiness | `STRUCTURED_ELEMENTS_LOW` | (3,2) | content_edit | Heuristic | (3,2) | content_edit | keep | — |
| ai_readiness | `UA_CONTENT_DIFFERS` | (7,3) | developer_needed | Reasonable proxy | (7,3) | developer_needed | PENDING | PENDING-IMPL: wire in js_renderer (Playwright) — remediation R7; ⚠ impact 7 exceeds Reasonable proxy cap 6 — review |
| broken_link | `BROKEN_LINK_404` | (10,2) | wp_fixable | — | (10,2) | wp_fixable | keep | — |
| broken_link | `BROKEN_LINK_410` | (8,2) | wp_fixable | — | (8,2) | wp_fixable | keep | — |
| broken_link | `BROKEN_LINK_503` | (4,3) | developer_needed | — | (4,3) | developer_needed | keep | — |
| broken_link | `BROKEN_LINK_5XX` | (7,3) | wp_fixable | — | (7,2) | content_edit | CHANGE | fixability→content_edit: 5xx is on the remote server; author removes/replaces link — not WP-fixable; effort 3→2: author removes/replaces the offending link — content edit |
| broken_link | `EXTERNAL_LINK_SKIPPED` | (2,1) | developer_needed | — | (2,1) | developer_needed | keep | — |
| broken_link | `EXTERNAL_LINK_TIMEOUT` | (3,1) | developer_needed | — | (3,1) | developer_needed | keep | — |
| broken_link | `PLACEHOLDER_LINK` | (7,2) | developer_needed | — | (7,2) | developer_needed | keep | — |
| broken_link | `WRONG_PLACEHOLDER_LINK` | (7,2) | content_edit | — | (7,2) | content_edit | keep | — |
| crawlability | `AMPHTML_BROKEN` | (4,3) | developer_needed | — | (4,3) | developer_needed | keep | — |
| crawlability | `CONTENT_STALE` | (3,4) | content_edit | — | (3,3) | content_edit | CHANGE | effort 4→3: content refresh is moderate, not 4 |
| crawlability | `HIGH_CRAWL_DEPTH` | (5,3) | developer_needed | — | (5,3) | developer_needed | keep | — |
| crawlability | `INTERNAL_NOFOLLOW` | (5,2) | developer_needed | — | (5,2) | developer_needed | keep | — |
| crawlability | `LOGIN_REDIRECT` | (2,1) | developer_needed | — | (2,1) | developer_needed | keep | — |
| crawlability | `MISSING_VIEWPORT_META` | (6,1) | developer_needed | — | (6,1) | developer_needed | keep | — |
| crawlability | `NOINDEX_HEADER` | (10,2) | developer_needed | — | (10,2) | developer_needed | keep | — |
| crawlability | `NOINDEX_META` | (10,1) | wp_fixable | — | (10,1) | wp_fixable | keep | — |
| crawlability | `NOT_IN_SITEMAP` | (4,1) | wp_fixable | — | (4,1) | wp_fixable | keep | — |
| crawlability | `ORPHAN_PAGE` | (6,4) | developer_needed | — | (6,2) | content_edit | CHANGE | fixability→content_edit: adding internal links is content work, not dev; effort 4→2: add internal links — single-page content work, not 4 |
| crawlability | `PAGE_SIZE_LARGE` | (5,3) | developer_needed | — | (5,3) | developer_needed | keep | — |
| crawlability | `PAGE_TIMEOUT` | (6,3) | developer_needed | — | (6,3) | developer_needed | keep | — |
| crawlability | `PAGINATION_LINKS_PRESENT` | (2,2) | developer_needed | — | (2,2) | developer_needed | keep | — |
| crawlability | `PARA_TOO_LONG` | (4,2) | content_edit | — | (4,2) | content_edit | keep | — |
| crawlability | `PDF_TOO_LARGE` | (4,2) | developer_needed | — | (4,2) | developer_needed | keep | — |
| crawlability | `ROBOTS_BLOCKED` | (9,2) | developer_needed | — | (9,2) | developer_needed | keep | — |
| crawlability | `SCHEMA_MISSING` | (5,2) | wp_fixable | — | (5,2) | wp_fixable | DEPRECATE | DEPRECATE: overlaps JSON_LD_MISSING + SCHEMA_ORG_MISSING; make those the graded pair. Historical audits keep the code label (read-only). |
| crawlability | `THIN_CONTENT` | (6,4) | content_edit | — | (6,3) | content_edit | CHANGE | effort 4→3: writing ~300 words is moderate, not 4 |
| duplicate | `TITLE_META_DUPLICATE_PAIR` | (6,2) | content_edit | — | (6,2) | content_edit | keep | — |
| heading | `H1_MISSING` | (8,1) | content_edit | — | (6,1) | content_edit | CHANGE | not an SEO crisis, but AI-extraction + a11y argue against <5. Claude(5-6)>Hermes(5). |
| heading | `H1_MULTIPLE` | (6,2) | content_edit | — | (5,2) | content_edit | CHANGE | HTML5 outline algorithm is dead; Google tolerates. Slight deweight. |
| heading | `HEADING_EMPTY` | (4,1) | content_edit | — | (4,1) | content_edit | keep | — |
| heading | `HEADING_SKIP` | (4,3) | content_edit | — | (4,3) | content_edit | keep | — |
| image | `IMG_ALT_DUP_FILENAME` | (3,1) | wp_fixable | — | (3,1) | wp_fixable | keep | — |
| image | `IMG_ALT_GENERIC` | (4,1) | wp_fixable | — | (4,1) | wp_fixable | keep | — |
| image | `IMG_ALT_MISSING` | (5,2) | wp_fixable | — | (5,2) | wp_fixable | keep | — |
| image | `IMG_ALT_MISUSED` | (3,2) | content_edit | — | (3,2) | content_edit | keep | — |
| image | `IMG_ALT_TOO_LONG` | (2,1) | wp_fixable | — | (2,1) | wp_fixable | keep | — |
| image | `IMG_ALT_TOO_SHORT` | (3,1) | wp_fixable | — | (3,1) | wp_fixable | keep | — |
| image | `IMG_BROKEN` | (8,2) | developer_needed | — | (8,2) | developer_needed | keep | — |
| image | `IMG_DUPLICATE_CONTENT` | (2,2) | developer_needed | — | (2,2) | developer_needed | keep | — |
| image | `IMG_FORMAT_LEGACY` | (2,2) | content_edit | — | (2,2) | content_edit | keep | — |
| image | `IMG_NO_SRCSET` | (2,3) | developer_needed | — | (2,3) | developer_needed | keep | — |
| image | `IMG_OVERSCALED` | (4,3) | content_edit | — | (4,3) | content_edit | keep | — |
| image | `IMG_OVERSIZED` | (5,2) | content_edit | — | (5,2) | content_edit | keep | — |
| image | `IMG_POOR_COMPRESSION` | (4,2) | content_edit | — | (4,2) | content_edit | keep | — |
| image | `IMG_SLOW_LOAD` | (4,2) | developer_needed | — | (4,2) | developer_needed | keep | — |
| metadata | `ANCHOR_TEXT_GENERIC` | (4,2) | content_edit | — | (4,2) | content_edit | keep | — |
| metadata | `CANONICAL_EXTERNAL` | (5,2) | developer_needed | — | (5,3) | developer_needed | CHANGE | effort 2→3: server/template canonical change — raise 2→3 (part0 conceded Hermes) |
| metadata | `CANONICAL_MISSING` | (6,2) | developer_needed | — | (6,2) | developer_needed | keep | — |
| metadata | `CANONICAL_SELF_MISSING` | (5,1) | developer_needed | — | (5,1) | developer_needed | keep | — |
| metadata | `FAVICON_MISSING` | (3,2) | content_edit | — | (3,2) | content_edit | keep | — |
| metadata | `LANG_MISSING` | (6,1) | developer_needed | — | (6,1) | developer_needed | keep | — |
| metadata | `LINK_EMPTY_ANCHOR` | (7,2) | content_edit | — | (7,2) | content_edit | keep | — |
| metadata | `META_DESC_DUPLICATE` | (4,2) | content_edit | — | (4,2) | content_edit | keep | — |
| metadata | `META_DESC_MISSING` | (7,1) | wp_fixable | — | (7,1) | wp_fixable | keep | — |
| metadata | `META_DESC_TOO_LONG` | (3,1) | wp_fixable | — | (3,1) | wp_fixable | keep | — |
| metadata | `META_DESC_TOO_SHORT` | (4,1) | wp_fixable | — | (4,1) | wp_fixable | keep | — |
| metadata | `OG_DESC_MISSING` | (3,1) | wp_fixable | — | (3,1) | wp_fixable | keep | — |
| metadata | `OG_IMAGE_MISSING` | (3,1) | content_edit | — | (3,1) | content_edit | keep | — |
| metadata | `OG_TITLE_MISSING` | (4,1) | wp_fixable | — | (4,1) | wp_fixable | keep | — |
| metadata | `TITLE_DUPLICATE` | (5,2) | content_edit | — | (5,2) | content_edit | keep | — |
| metadata | `TITLE_H1_MISMATCH` | (6,2) | wp_fixable | — | (6,2) | wp_fixable | keep | — |
| metadata | `TITLE_MISSING` | (9,1) | wp_fixable | — | (9,1) | wp_fixable | keep | — |
| metadata | `TITLE_TOO_LONG` | (4,1) | wp_fixable | — | (4,1) | wp_fixable | keep | — |
| metadata | `TITLE_TOO_SHORT` | (5,1) | wp_fixable | — | (5,1) | wp_fixable | keep | — |
| metadata | `TWITTER_CARD_MISSING` | (3,1) | content_edit | — | (3,1) | content_edit | keep | — |
| redirect | `INTERNAL_REDIRECT_301` | (4,1) | developer_needed | — | (4,1) | developer_needed | keep | — |
| redirect | `META_REFRESH_REDIRECT` | (5,2) | developer_needed | — | (5,2) | developer_needed | keep | — |
| redirect | `REDIRECT_301` | (3,2) | developer_needed | — | (3,2) | developer_needed | keep | — |
| redirect | `REDIRECT_302` | (5,2) | developer_needed | — | (4,2) | developer_needed | CHANGE | PageRank-loss premise is a myth (Illyes; re-verified 2026); real issue is canonicalization only. Claude>Hermes. |
| redirect | `REDIRECT_CASE_NORMALISE` | (2,1) | developer_needed | — | (2,1) | developer_needed | keep | — |
| redirect | `REDIRECT_CHAIN` | (6,3) | developer_needed | — | (6,3) | developer_needed | keep | — |
| redirect | `REDIRECT_LOOP` | (10,4) | developer_needed | — | (10,4) | developer_needed | keep | — |
| redirect | `REDIRECT_TRAILING_SLASH` | (2,1) | developer_needed | — | (2,1) | developer_needed | keep | — |
| rendering | `JS_DEPENDENT_NAVIGATION` | (5,3) | developer_needed | — | (5,3) | developer_needed | keep | — |
| security | `HTTPS_REDIRECT_MISSING` | (9,2) | developer_needed | — | (9,2) | developer_needed | keep | — |
| security | `HTTP_PAGE` | (9,2) | developer_needed | — | (9,2) | developer_needed | keep | — |
| security | `MISSING_HSTS` | (4,2) | developer_needed | — | (4,2) | developer_needed | keep | — |
| security | `MIXED_CONTENT` | (6,2) | developer_needed | — | (6,2) | developer_needed | keep | — |
| security | `UNSAFE_CROSS_ORIGIN_LINK` | (3,1) | developer_needed | — | (3,1) | developer_needed | keep | — |
| security | `WWW_CANONICALIZATION` | (5,2) | developer_needed | — | (5,2) | developer_needed | keep | — |
| semantic_html | `INTERACTIVE_NO_ACCESSIBLE_NAME` | (4,2) | developer_needed | — | (4,2) | developer_needed | keep | — |
| semantic_html | `LANDMARK_MAIN_MISSING` | (2,2) | developer_needed | — | (2,2) | developer_needed | keep | — |
| semantic_html | `LANDMARK_NAV_MISSING` | (2,2) | developer_needed | — | (2,2) | developer_needed | keep | — |
| semantic_html | `NON_SEMANTIC_BUTTON` | (4,3) | developer_needed | — | (4,3) | developer_needed | keep | — |
| sitemap | `SITEMAP_MISSING` | (6,2) | developer_needed | — | (6,2) | developer_needed | keep | — |
| url_structure | `URL_HAS_SPACES` | (5,3) | content_edit | — | (5,2) | content_edit | CHANGE | effort 3→2: single-page slug edit, align with sibling URL codes |
| url_structure | `URL_HAS_UNDERSCORES` | (2,4) | content_edit | — | (2,2) | content_edit | CHANGE | effort 4→2: single-page slug edit, not 4 |
| url_structure | `URL_TOO_LONG` | (2,4) | content_edit | — | (2,2) | content_edit | CHANGE | effort 4→2: single-page slug/text edit, not 4 |
| url_structure | `URL_UPPERCASE` | (3,2) | content_edit | — | (3,2) | content_edit | keep | — |

## Migration patch

```python
# _ISSUE_SCORING migration — only changed rows (impact, effort)
    "BROKEN_LINK_5XX": (7, 2),
    "CANONICAL_EXTERNAL": (5, 3),
    "CONTENT_STALE": (3, 3),
    "EXTERNAL_CITATIONS_LOW": (5, 2),
    "FAQ_SCHEMA_MISSING": (2, 2),
    "GEO_SUMMARY_BURIED": (5, 3),
    "H1_MISSING": (6, 1),
    "H1_MULTIPLE": (5, 2),
    "LLMS_TXT_INVALID": (2, 2),
    "LLMS_TXT_MISSING": (3, 1),
    "ORPHAN_PAGE": (6, 2),
    "QUERY_COVERAGE_WEAK": (5, 2),
    "QUOTATIONS_MISSING": (4, 2),
    "REDIRECT_302": (4, 2),
    "SEMANTIC_DENSITY_LOW": (3, 3),
    "STATISTICS_COUNT_LOW": (5, 2),
    "THIN_CONTENT": (6, 3),
    "URL_HAS_SPACES": (5, 2),
    "URL_HAS_UNDERSCORES": (2, 2),
    "URL_TOO_LONG": (2, 2),
```


## Deprecations & lifecycle (listed separately, with compatibility note)

- **`SCHEMA_MISSING` — DEPRECATE.** Overlaps `JSON_LD_MISSING` (page-level rich-result
  eligibility) + `SCHEMA_ORG_MISSING` (homepage identity). Make those two the graded pair; stop
  emitting `SCHEMA_MISSING`.
- **`SEMANTIC_DENSITY_LOW` — deweight now (5→3), deprecate later** once `AI_MAIN_CONTENT_LOW_RATIO`
  demonstrably covers the "content buried in chrome" case on page-builder markup.
- **8 PENDING-IMPL codes** stay in the catalogue but are excluded from the *active* score until
  their implementation ships (remediation R6-R8): the JS-render trio, the 3 LLM-driven checks, and
  2 citation codes. Until then they must not contribute phantom impact.
- **1 FIX-MISFIRE code** (`CITATIONS_MISSING_SUBSTANTIAL_CONTENT`) must be corrected or folded into
  `EXTERNAL_CITATIONS_LOW` before its −3 is trusted (remediation R6).

**Compatibility note (historical audit data).** Deprecated/renamed codes must remain resolvable in
`_CATALOGUE` (read-only) so past audits that reference `SCHEMA_MISSING` still render. Do NOT delete
catalogue entries; mark them `deprecated=True` and stop emitting them. Health scores for *new*
crawls change; historical scores are recomputed only if the owner explicitly re-runs aggregation.

## Suppression rules (from audit report §2.3 — apply at aggregation time, keep issues visible)

These change *scores*, not the issue list: schema parent-suppress, duplicate-metadata merge,
not-in-text precedence, thin-content pick-one, image-performance precedence, per-category page cap.
See remediation R4.
