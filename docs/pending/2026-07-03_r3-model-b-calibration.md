---
status: pending-approval
proposed: 2026-07-03
author: Claude Code (Opus 4.8) — validated merge of the Gemini R3 report + audit findings
sources: docs/Gemini TakingToad Scoring Revision2.md ; docs/review/2026-07-03_code-audit-report.md
governance: SPEC ONLY — no code until approved; scoring change, needs owner sign-off
---

# R3 — Model B scoring calibration (validated merge)

> **Partial implementation status (2026-07-03):** the **structural, low-regret** pieces are
> IMPLEMENTED and shipped — §2 page-health model (per-category cap = 20 + page-fatal bypass) and the
> §4 cluster merge (added `JS_DEPENDENT_NAVIGATION`; the two mutually-exclusive Gemini clusters and
> the cross-scope `HTTPS_REDIRECT_MISSING⊳HTTP_PAGE` were dropped). STILL PENDING owner sign-off:
> **§5 the 151-value impact recalibration** (the high-variance Model B numbers) and **§3 the
> priority-ordering formula** — hold until the second expert opinion is folded in or a real-crawl
> validation is run.

This folds the **Gemini R3 expert report** (Model B: two-axis matrix + exception lane) together
with the audit's own findings into one implementable calibration. It is a **validated merge**, not a
verbatim adoption: Gemini's methodology is adopted; its per-code output was re-checked against the
matrix, the live registry, and the verified vendor facts, and corrected where it was wrong. Every
divergence from Gemini is listed in §6.

> **Scale of change:** this recalibrates all 151 impacts and changes the page-health formula. It is
> the largest single scoring change in the audit and **must be validated on a real crawl of
> livingsystems.ca (before/after) before it ships to production.**

## 1. Methodology — Model B (adopted from Gemini)

**1.1 Impact derivation matrix** (confidence × effect_size → impact):

| | small | moderate | large |
|---|---|---|---|
| **Established** | 2 | 6 | 10 |
| **Reasonable proxy** | 1 | 4 | 8 |
| **Heuristic** | 0→**1** | 2 | 4 |

- **Established** = vendor-documented behavior, protocol response codes, or hard indexation blocks.
- **Reasonable proxy** = strong multi-platform consensus / partial vendor confirmation.
- **Heuristic** = style/layout/semantic best practice without direct engine-weight proof.

**1.2 Exception lane** — a `Heuristic` check backed by a controlled study (the Aggarwal GEO work)
maps to the **Reasonable proxy** row (S=1, M=4, L=8) so measured tactics aren't zeroed. Applies to:
`STATISTICS_COUNT_LOW`, `EXTERNAL_CITATIONS_LOW`, `CENTRAL_CLAIM_BURIED`, `GEO_SUMMARY_BURIED`,
`FIRST_VIEWPORT_NO_ANSWER`, `COMPARISON_TABLE_MISSING`, `CONTENT_STAT_OUTDATED`,
`CITATIONS_MISSING_SUBSTANTIAL_CONTENT`.

**1.3 Auditor divergences baked into the matrix (see §6):**
- **Heuristic×small = 1, not 0.** Gemini's 0 silently zeroed 28 real checks (they'd still display but
  never affect the score — worse than not checking). Floored to **1** so every real finding carries
  minimal weight. `impact 0` is reserved for the 3 **informational-by-design** codes only
  (`AI_CITED_PAGE`, `AI_BOT_TRAINING_DISALLOWED`, `AI_BOT_TABLE_STALE`).
  *(Future UX option, needs GUI approval: move impact-1 advisory checks into a separate
  "Advisory / not scored" list instead of flooring — cleaner for non-technical users.)*

## 2. Page Health formula — combined model (audit R4 + Gemini caps + per-occurrence cap)

Gemini's per-category cap is adopted, **combined** with the already-shipped R4 cluster suppression
and a new per-occurrence guard (Gemini's model left broken-link stacking unsolved — with all broken
links at 10 and `broken_link` uncapped, five dead links would still zero a page):

```
Page Health = max(0, 100 − Σ_category min( Cap_c , Σ impact of CHARGED issues in c ))
```
where "charged" = after R4 cluster suppression (parent charged once; children dropped).

- **Default category cap = 20.** Applied to metadata, image, broken_link, redirect, ai_readiness,
  heading, url_structure, semantic_html, sitemap, duplicate, rendering.
- **Uncapped (page-fatal allowed to reach 0): `crawlability`, `security`.** These hold the true
  kill-switches (NOINDEX, ROBOTS_BLOCKED, HTTP_PAGE, HTTPS_REDIRECT_MISSING, PAGE_TIMEOUT) — a page
  carrying one of those *should* be able to drop to 0.
- The `broken_link` cap (20) is the per-occurrence guard: 2 dead links hurt, but no number of them
  alone zeroes an otherwise-healthy page.
- Site Health = mean of page scores (unchanged). Computed in the shared `compute_impact_health`
  (both stores), extended with the category-cap step.

## 3. Priority ordering — quick-win weighted (moderated from Gemini)

Gemini proposed `Impact×7 − Effort×6`. That over-weights effort: it lets a trivial impact-3/effort-0
item (21) outrank an important impact-5/effort-3 item (17) — inverting importance. **Proposed:**
```
priority_rank = Impact×10 − Effort×4          # effort matters ~2× more than today, impact still leads
quick_win = (impact >= 5 and effort <= 2)      # boolean badge the UI can surface first
```
Ordering only — does not affect scores. **Tunable; flag for owner preference** (if you want Gemini's
stronger quick-win bias, we set the coefficients accordingly).

## 4. Deduplication / co-firing clusters (merged + validated)

Merging the R4 suppression rules (already shipped) with Gemini's C1–C4. Two of Gemini's are **dropped
as already impossible** — a validation catch:

**Active suppression rules** (parent charged once; children excluded from score, still shown):
1. `SCHEMA_MISSING` ⊳ `JSON_LD_MISSING`, `SCHEMA_ORG_MISSING`  *(R4)*
2. `TITLE_META_DUPLICATE_PAIR` ⊳ `TITLE_DUPLICATE`, `META_DESC_DUPLICATE`  *(R4)*
3. `RAW_HTML_JS_DEPENDENT` ⊳ `AI_CONTENT_NOT_IN_TEXT`, `CONTENT_NOT_EXTRACTABLE_NO_TEXT`,
   `CONTACT_INFO_NOT_IN_HTML`, **`JS_DEPENDENT_NAVIGATION`**  *(R4 + Gemini C3)*
4. `THIN_CONTENT` ⊳ `CONTENT_THIN`  *(R4)*
5. `HTTPS_REDIRECT_MISSING` ⊳ `HTTP_PAGE`  *(Gemini C1 — verify scope at build: site-level parent vs
   per-page child)*

**Dropped (Gemini C2, C4) — already mutually exclusive in the checkers, so no dedup needed:**
- `NOINDEX_META` vs `NOINDEX_HEADER`: `crawlability.py` emits exactly one (header-source branch).
- `META_DESC_MISSING` vs `META_DESC_TOO_SHORT`: metadata checker emits one (missing XOR too-short).

## 5. The reconciled 151-code calibration

`cur` = live registry impact (post-R2); `conf`/`effect` = Gemini's recommendation; `gem` = Gemini's
derived impact; **FINAL** = this spec's value after corrections; `Δ` = FINAL − cur; `note` = why
FINAL differs from `gem` (FLOOR = 0→1 floor; OVERRIDE = §6; informational = kept 0; MATRIX≠ = Gemini
value didn't match its own matrix, recomputed).

| code | cur | conf | effect | gem | FINAL | Δ | note |
|---|---|---|---|---|---|---|---|
| AI_BOT_BLANKET_DISALLOW | 9 | Established | large | 10 | **10** | +1 |  |
| AI_BOT_DEPRECATED_DIRECTIVE | 2 | Established | small | 2 | **2** | +0 |  |
| AI_BOT_NO_AI_DIRECTIVES | 1 | Reasonable proxy | small | 1 | **1** | +0 |  |
| AI_BOT_SEARCH_BLOCKED | 8 | Established | large | 10 | **10** | +2 |  |
| AI_BOT_TABLE_STALE | 0 | Heuristic | small | 0 | **0** | +0 | informational |
| AI_BOT_TRAINING_DISALLOWED | 0 | Established | small | 0 | **0** | +0 | MATRIX≠ (exp 2) |
| AI_BOT_USER_FETCH_BLOCKED | 4 | Established | moderate | 6 | **6** | +2 |  |
| AI_CITED_PAGE | 0 | Established | small | 0 | **0** | +0 | MATRIX≠ (exp 2) |
| AI_CONTENT_NOT_IN_TEXT | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| AI_HIGH_VALUE_UNCITED | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| AI_MAIN_CONTENT_LOW_RATIO | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| AI_NO_VISUAL_COMPANION | 1 | Reasonable proxy | small | 1 | **1** | +0 |  |
| AI_PREVIEW_BLOCKED_AT_BOT | 3 | Established | small | 2 | **2** | -1 |  |
| AI_PREVIEW_SUPPRESSED | 3 | Established | small | 2 | **2** | -1 |  |
| AI_TXT_MISSING | 1 | Heuristic | small | 0 | **1** | +0 | FLOOR |
| AMPHTML_BROKEN | 4 | Heuristic | moderate | 2 | **2** | -2 |  |
| ANCHOR_TEXT_GENERIC | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| AUTHOR_BYLINE_MISSING | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| BLOG_SECTIONS_MISSING | 5 | Heuristic | moderate | 2 | **2** | -3 |  |
| BROKEN_LINK_404 | 10 | Established | large | 10 | **10** | +0 |  |
| BROKEN_LINK_410 | 8 | Established | large | 10 | **10** | +2 |  |
| BROKEN_LINK_503 | 4 | Established | moderate | 6 | **6** | +2 |  |
| BROKEN_LINK_5XX | 7 | Established | large | 10 | **6** | -1 | OVERRIDE |
| CANONICAL_EXTERNAL | 5 | Established | moderate | 6 | **6** | +1 |  |
| CANONICAL_MISSING | 6 | Established | moderate | 6 | **6** | +0 |  |
| CANONICAL_SELF_MISSING | 5 | Established | small | 2 | **2** | -3 |  |
| CENTRAL_CLAIM_BURIED | 5 | Heuristic | moderate | 4 | **4** | -1 |  |
| CHUNKS_NOT_SELF_CONTAINED | 5 | Heuristic | moderate | 2 | **2** | -3 |  |
| CITATIONS_MISSING_SUBSTANTIAL_CONTENT | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| CITATIONS_ORPHANED | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| CITATIONS_SOURCES_INACCESSIBLE | 4 | Heuristic | moderate | 2 | **2** | -2 |  |
| CODE_BLOCK_MISSING_TECHNICAL | 4 | Heuristic | small | 0 | **1** | -3 | FLOOR |
| COMPARISON_TABLE_MISSING | 3 | Heuristic | small | 1 | **1** | -2 |  |
| CONTACT_INFO_NOT_IN_HTML | 4 | Heuristic | moderate | 2 | **2** | -2 |  |
| CONTENT_CLOAKING_DETECTED | 8 | Reasonable proxy | large | 8 | **8** | +0 |  |
| CONTENT_DATE_STALE_VISIBLE | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| CONTENT_IMAGE_HEAVY | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| CONTENT_NOT_EXTRACTABLE_NO_TEXT | 6 | Reasonable proxy | large | 8 | **8** | +2 |  |
| CONTENT_STALE | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| CONTENT_STAT_OUTDATED | 2 | Heuristic | small | 0 | **1** | -1 | MATRIX≠ (exp 1) |
| CONTENT_THIN | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| CONTENT_UNSTRUCTURED | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| CONVERSATIONAL_H2_MISSING | 4 | Heuristic | moderate | 2 | **2** | -2 |  |
| DATE_MODIFIED_MISSING | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| DATE_PUBLISHED_MISSING | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| DOCUMENT_PROPS_MISSING | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| EXTERNAL_CITATIONS_LOW | 5 | Reasonable proxy | moderate | 4 | **4** | -1 |  |
| EXTERNAL_LINK_SKIPPED | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| EXTERNAL_LINK_TIMEOUT | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| FAQ_SCHEMA_MISSING | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| FAVICON_MISSING | 3 | Established | small | 2 | **2** | -1 |  |
| FIRST_VIEWPORT_NO_ANSWER | 5 | Heuristic | moderate | 4 | **4** | -1 |  |
| GEO_SUMMARY_BURIED | 5 | Heuristic | moderate | 4 | **4** | -1 |  |
| H1_MISSING | 6 | Established | moderate | 6 | **6** | +0 |  |
| H1_MULTIPLE | 5 | Reasonable proxy | small | 1 | **1** | -4 |  |
| HEADING_EMPTY | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| HEADING_SKIP | 4 | Heuristic | small | 0 | **1** | -3 | FLOOR |
| HIGH_CRAWL_DEPTH | 5 | Reasonable proxy | moderate | 4 | **4** | -1 |  |
| HTTPS_REDIRECT_MISSING | 9 | Established | large | 10 | **10** | +1 |  |
| HTTP_PAGE | 9 | Established | large | 10 | **10** | +1 |  |
| IMG_ALT_DUP_FILENAME | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| IMG_ALT_GENERIC | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| IMG_ALT_MISSING | 5 | Established | moderate | 6 | **6** | +1 |  |
| IMG_ALT_MISUSED | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| IMG_ALT_TOO_LONG | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| IMG_ALT_TOO_SHORT | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| IMG_BROKEN | 8 | Established | moderate | 6 | **6** | -2 |  |
| IMG_DUPLICATE_CONTENT | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| IMG_FORMAT_LEGACY | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| IMG_NO_SRCSET | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| IMG_OVERSCALED | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| IMG_OVERSIZED | 5 | Reasonable proxy | small | 1 | **1** | -4 |  |
| IMG_POOR_COMPRESSION | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| IMG_SLOW_LOAD | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| INTERACTIVE_NO_ACCESSIBLE_NAME | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| INTERNAL_NOFOLLOW | 5 | Established | moderate | 6 | **6** | +1 |  |
| INTERNAL_REDIRECT_301 | 4 | Established | small | 2 | **2** | -2 |  |
| JSON_LD_INVALID | 4 | Reasonable proxy | moderate | 4 | **4** | +0 |  |
| JSON_LD_MISSING | 7 | Reasonable proxy | moderate | 4 | **4** | -3 |  |
| JS_DEPENDENT_NAVIGATION | 5 | Reasonable proxy | large | 8 | **8** | +3 |  |
| JS_RENDERED_CONTENT_DIFFERS | 6 | Reasonable proxy | large | 8 | **8** | +2 |  |
| LANDMARK_MAIN_MISSING | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| LANDMARK_NAV_MISSING | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| LANG_MISSING | 6 | Established | small | 2 | **2** | -4 |  |
| LINK_EMPTY_ANCHOR | 7 | Reasonable proxy | small | 1 | **1** | -6 |  |
| LINK_PROFILE_PROMOTIONAL | 4 | Heuristic | moderate | 2 | **2** | -2 |  |
| LLMS_TXT_INVALID | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| LLMS_TXT_MISSING | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| LOGIN_REDIRECT | 2 | Established | large | 10 | **10** | +8 |  |
| META_DESC_DUPLICATE | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| META_DESC_MISSING | 7 | Reasonable proxy | small | 1 | **1** | -6 |  |
| META_DESC_TOO_LONG | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| META_DESC_TOO_SHORT | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| META_REFRESH_REDIRECT | 5 | Established | large | 10 | **6** | +1 | OVERRIDE |
| MISSING_HSTS | 4 | Established | small | 2 | **2** | -2 |  |
| MISSING_VIEWPORT_META | 6 | Established | large | 10 | **6** | +0 | OVERRIDE |
| MIXED_CONTENT | 6 | Established | moderate | 6 | **6** | +0 |  |
| NOINDEX_HEADER | 10 | Established | large | 10 | **10** | +0 |  |
| NOINDEX_META | 10 | Established | large | 10 | **10** | +0 |  |
| NON_SEMANTIC_BUTTON | 4 | Heuristic | small | 0 | **1** | -3 | FLOOR |
| NOT_IN_SITEMAP | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| OG_DESC_MISSING | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| OG_IMAGE_MISSING | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| OG_TITLE_MISSING | 4 | Heuristic | small | 0 | **1** | -3 | FLOOR |
| ORPHAN_CLAIM_TECHNICAL | 6 | Heuristic | moderate | 2 | **2** | -4 |  |
| ORPHAN_PAGE | 6 | Established | moderate | 6 | **6** | +0 |  |
| PAGE_SIZE_LARGE | 5 | Reasonable proxy | small | 1 | **1** | -4 |  |
| PAGE_TIMEOUT | 6 | Established | large | 10 | **10** | +4 |  |
| PAGINATION_LINKS_PRESENT | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| PARA_TOO_LONG | 4 | Heuristic | small | 0 | **1** | -3 | FLOOR |
| PDF_TOO_LARGE | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| PLACEHOLDER_LINK | 7 | Reasonable proxy | small | 1 | **1** | -6 |  |
| PROMOTIONAL_CONTENT_INTERRUPTS | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| QUERY_COVERAGE_WEAK | 5 | Heuristic | moderate | 2 | **2** | -3 |  |
| QUOTATIONS_MISSING | 4 | Heuristic | small | 0 | **1** | -3 | FLOOR |
| RAW_HTML_JS_DEPENDENT | 6 | Reasonable proxy | large | 8 | **8** | +2 |  |
| REDIRECT_301 | 3 | Established | small | 2 | **2** | -1 |  |
| REDIRECT_302 | 4 | Established | small | 2 | **2** | -2 |  |
| REDIRECT_CASE_NORMALISE | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| REDIRECT_CHAIN | 6 | Established | moderate | 6 | **6** | +0 |  |
| REDIRECT_LOOP | 10 | Established | large | 10 | **10** | +0 |  |
| REDIRECT_TRAILING_SLASH | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| ROBOTS_BLOCKED | 9 | Established | large | 10 | **10** | +1 |  |
| SCHEMA_DEPRECATED_TYPE | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| SCHEMA_MISSING | 5 | Reasonable proxy | moderate | 4 | **4** | -1 |  |
| SCHEMA_ORG_MISSING | 5 | Reasonable proxy | moderate | 4 | **4** | -1 |  |
| SCHEMA_TYPE_CONFLICT | 3 | Reasonable proxy | small | 1 | **1** | -2 |  |
| SCHEMA_TYPE_MISMATCH | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| SCHEMA_VISIBLE_MISMATCH | 5 | Established | moderate | 6 | **6** | +1 |  |
| SECTION_CROSS_REFERENCES | 6 | Heuristic | small | 0 | **1** | -5 | FLOOR |
| SECTION_VAGUE_OPENER | 5 | Heuristic | small | 0 | **1** | -4 | FLOOR |
| SEMANTIC_DENSITY_LOW | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| SITEMAP_MISSING | 6 | Established | moderate | 6 | **6** | +0 |  |
| STATISTICS_COUNT_LOW | 5 | Heuristic | moderate | 4 | **4** | -1 |  |
| STRUCTURED_ELEMENTS_LOW | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| THIN_CONTENT | 6 | Established | moderate | 6 | **6** | +0 |  |
| TITLE_DUPLICATE | 5 | Established | moderate | 6 | **6** | +1 |  |
| TITLE_H1_MISMATCH | 6 | Reasonable proxy | small | 1 | **1** | -5 |  |
| TITLE_META_DUPLICATE_PAIR | 6 | Established | moderate | 6 | **6** | +0 |  |
| TITLE_MISSING | 9 | Established | large | 10 | **10** | +1 |  |
| TITLE_TOO_LONG | 4 | Reasonable proxy | small | 1 | **1** | -3 |  |
| TITLE_TOO_SHORT | 5 | Reasonable proxy | small | 1 | **1** | -4 |  |
| TWITTER_CARD_MISSING | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| UA_CONTENT_DIFFERS | 7 | Reasonable proxy | large | 8 | **8** | +1 |  |
| UNSAFE_CROSS_ORIGIN_LINK | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| URL_HAS_SPACES | 5 | Reasonable proxy | small | 1 | **1** | -4 |  |
| URL_HAS_UNDERSCORES | 2 | Heuristic | small | 0 | **1** | -1 | FLOOR |
| URL_TOO_LONG | 2 | Reasonable proxy | small | 1 | **1** | -1 |  |
| URL_UPPERCASE | 3 | Heuristic | small | 0 | **1** | -2 | FLOOR |
| WRONG_PLACEHOLDER_LINK | 7 | Reasonable proxy | small | 1 | **1** | -6 |  |
| WWW_CANONICALIZATION | 5 | Established | moderate | 6 | **6** | +1 |  |

## 6. Divergences from the Gemini report (explicit)

1. **Heuristic×small floored 0→1** — 28 checks Gemini zeroed now carry impact 1 (real issues aren't
   weightless). 3 informational codes stay 0.
2. **Overrides** (Gemini value → FINAL, with reason):
   - `META_REFRESH_REDIRECT` 10 → **6**: a poor redirect pattern, not de-indexing / page-fatal.
   - `MISSING_VIEWPORT_META` 10 → **6**: mobile-friendliness signal, not total de-indexing.
   - `BROKEN_LINK_5XX` 10 → **6**: destination server error, transient/retryable (see audit R0.3);
     not the source page's fatal flaw.
3. **3 matrix inconsistencies corrected** — Gemini's derived integer didn't match its own matrix
   (e.g. `CONTENT_STAT_OUTDATED`, `AI_BOT_TRAINING_DISALLOWED`); FINAL is recomputed so the table is
   internally consistent.
4. **2 dedup clusters dropped** (§4) as already mutually exclusive.
5. **Priority formula moderated** (§3) to avoid rank inversions.
6. **Per-occurrence cap added** (§2) — Gemini's model didn't bound broken-link stacking.

**Notable calls worth a second look** (kept per Gemini's methodology but flagged): `META_DESC_MISSING`
7→1, `LINK_EMPTY_ANCHOR` 7→1, `TITLE_H1_MISMATCH` 6→1, all broken links at/near 10. These are
defensible under Model B but are the rows most likely to warrant the second expert opinion.

## 7. Acceptance criteria → tests
- `test_model_b_matrix` — derived impact == matrix(confidence, effect_size), exception lane honored.
- `test_impact_floor_and_informational` — every non-informational code impact ≥ 1; the 3
  informational codes == 0.
- `test_scoring_matches_calibration` — `_ISSUE_SCORING` matches this spec's FINAL column (×151).
- `test_category_caps` — a category's deduction never exceeds its cap; crawlability/security uncapped.
- `test_broken_link_per_occurrence_capped` — 10 × BROKEN_LINK_404 on one page deducts ≤ 20, not 100.
- `test_page_fatal_still_zeroes` — a single NOINDEX/ROBOTS_BLOCKED can still floor a page to 0.
- `test_priority_no_inversion` — an important-but-harder item outranks a trivial quick win at chosen coefficients.
- `test_merged_suppression_clusters` — the 5 rules fire; the 2 dropped ones are asserted mutually exclusive.
- Dirty-state (P8): re-aggregating an existing job applies caps+suppression without double-counting.

## 8. Rollout / compatibility
- Confidence + effect_size become real per-code fields (extends `_IssueSpec`); impact derived from
  them via the matrix (audit R3 goal — impact stops being hand-set).
- **One-time production score shift** (on top of the Path-A impact-model move). Document in changelog;
  historical scores recompute only on re-aggregation. No codes deleted.
- Update `docs/issue-codes.md`, `docs/thresholds.md` (caps + coefficients), `functional-specification.md`.

## 9. Open items
- Second expert opinion not yet incorporated — the §6 "notable calls" are the rows to reconcile when
  it arrives.
- `HTTPS_REDIRECT_MISSING ⊳ HTTP_PAGE` scope to confirm at build.
- Volatility monitor (Gemini §4 YAML): optional; the existing `AI_BOT_TABLE_STALE` cadence covers the
  AI-bot rows. Defer unless wanted.
