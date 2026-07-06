---
status: pending-approval (implementation plan)
proposed: 2026-07-03
author: Claude Code (Opus 4.8) — triangulation of TWO independent expert opinions + audit
sources: Gemini R3 report ; Fable/Claude R3 report ; docs/review/OLD/2026-07-03_code-audit-report.md
supersedes: docs/pending/2026-07-03_r3-model-b-calibration.md (single-opinion draft)
governance: SPEC ONLY — changes every score; owner sign-off required before code
---

# R3 — FINAL scoring calibration (two-opinion triangulation) + implementation plan

> **IMPLEMENTED 2026-07-03.** R3.1 (impact recalibration + `_CALIBRATION`/`derive_impact`),
> R3.2 (severity derived from impact), R3.3 (priority `impact×10−effort×6` + `quick_win`) shipped.
> Tests: `tests/test_r3_calibration.py`; full suite 1790 passed (only 3 pre-existing unrelated
> failures). R3.4 (extra suppression clusters) deferred/optional. **Next: validate on a real
> before/after crawl of livingsystems.ca before deploy** (scores will rise — intended).

Both independent experts have reported. This reconciles **Gemini** (Model B, aggressive) and
**Fable/Claude** (Model B *hard-capped by confidence ceilings*, the better-reasoned synthesis) with
the audit's own findings, and lays out the implementation.

## 1. Triangulation result
- **130 / 151 codes converge** (the two experts land ≤2 impact apart) → high confidence, adopted.
- **21 diverge** (>2 apart) → adjudicated individually (§3), basis shown per row in §4.
- **Adopted framework: Fable's synthesis.** It is stronger than Gemini's: it hard-caps impact by
  confidence tier (retains Model A's anti-gaming), uses a **discrete** effect scale (avoids Model B's
  false-precision), adds a **none** tier for non-defects, a **Heuristic-measured** lane for the
  Aggarwal GEO checks, and — critically — **derives severity from impact** (one source of truth,
  fixing the impact/severity drift the audit flagged, e.g. NOINDEX_META impact 10 labelled "warning").

## 2. The model (Fable, adopted)
**Impact matrix** (confidence × discrete effect):

| confidence \ effect | none | small | moderate | large |
|---|---|---|---|---|
| Heuristic | 0 | 1 | 2 | 3 |
| Heuristic-measured (Aggarwal lane) | 0 | 2 | 3 | 4 |
| Reasonable proxy | 0 | 2 | 4 | 6 |
| Established | 0 | 2 | 6 | 9 (**10** iff page-fatal) |

- **10-tier** only for documented page-removal: `NOINDEX_META`, `NOINDEX_HEADER`, `REDIRECT_LOOP`.
  `ROBOTS_BLOCKED` = 9 (URL-only indexing still possible).
- **Severity derived:** `impact ≥ 8 → critical`, `4–7 → warning`, `≤3 → info`. Result: 8 critical /
  32 warning / 111 info. (Most checks are honestly minor — fewer false alarms for volunteers.)
- **Page-health model:** already shipped (per-category cap 20 + page-fatal bypass). With these lower
  impacts, per-occurrence stacking is largely moot (a broken link is now 2, not 10); the cap remains
  a backstop. Fable's occurrence-multiplier is noted as an optional future refinement, not required.
- **Priority (Fable):** `priority_rank = impact×10 − effort×6` (effort reorders within an impact tier,
  never across two) **plus a "Quick wins" list**: `impact ≥ 4 AND effort ≤ 1`.

## 3. Divergence adjudications (the 21) + judgment calls
Most resolved in **Fable's** favor — its low values are vendor-grounded (Google statements) where
Gemini kept audit-flagged over-scores. Notable resolutions:
- **Broken links** `BROKEN_LINK_404/410` 10/8 → **2**, `5XX` → **3**, `503` → **1**: Google confirms
  broken *outbound* links are not a ranking factor; with per-page counting the old 10s were the
  single biggest distortion. *(Follow-up: distinguish a page's OWN 404 from an outbound 404 — the
  code is currently overloaded; the self-404 case deserves higher weight.)*
- `SITEMAP_MISSING` 6 → **2** (small linked sites — the tool's audience — need no sitemap);
  `REDIRECT_CHAIN` 6 → **2**; `META_REFRESH_REDIRECT` 5 → **2**; `LANG_MISSING` 6 → **2**;
  `TITLE_H1_MISMATCH` 6 → **1**; `META_DESC_MISSING` 7 → **2** (both experts; Google rewrites snippets).
- Raised where both experts agree GEO is under-scored: `RAW_HTML_JS_DEPENDENT` 6 → **9**,
  `CONTENT_NOT_EXTRACTABLE_NO_TEXT` 6 → **9**, `JS_DEPENDENT_NAVIGATION` 5 → **6**.
- `TITLE_META_DUPLICATE_PAIR` → **4** (override both experts): it is the R4 suppression *parent*, so
  it must carry the "page is a duplicate" weight, not be dropped.

**Genuine judgment calls flagged for the owner (I picked a default; easy to change):**
1. **`AI_PREVIEW_SUPPRESSED` / `AI_PREVIEW_BLOCKED_AT_BOT`** — Gemini 2 vs Fable 6. These control
   whether content appears in AI answer surfaces. For a GEO-differentiated tool Fable's "mid-tier"
   view is compelling, but they are often unintentional plugin residue. **Default: 4.**
2. **Broken links → 2** is factually right but the most *visible* drop (a page full of dead links now
   scores well). Confirm you're comfortable presenting broken links as minor. **Default: adopt.**
3. **Severity becomes mostly "info" (111/151).** Honest, but changes the dashboard's feel. **Default:
   adopt derived severity.**

## 4. Reconciled 151-code calibration
`cur` = live impact; `Gem`/`Fable` = each expert's derived impact; **FINAL** = adopted; `sev` =
derived severity; `basis` = converge / diverge→Fable / override.

| code | cur | Gem | Fable | FINAL | sev | Δ | basis |
|---|---|---|---|---|---|---|---|
| AI_BOT_BLANKET_DISALLOW | 9 | 10 | 9 | **9** | critical | +0 | converge |
| AI_BOT_DEPRECATED_DIRECTIVE | 2 | 2 | 2 | **2** | info | +0 | converge |
| AI_BOT_NO_AI_DIRECTIVES | 1 | 1 | 1 | **1** | info | +0 | converge |
| AI_BOT_SEARCH_BLOCKED | 8 | 10 | 9 | **9** | critical | +1 | converge |
| AI_BOT_TABLE_STALE | 0 | 0 | 0 | **0** | info | +0 | converge |
| AI_BOT_TRAINING_DISALLOWED | 0 | 0 | 0 | **0** | info | +0 | converge |
| AI_BOT_USER_FETCH_BLOCKED | 4 | 6 | 2 | **3** | info | -1 | override |
| AI_CITED_PAGE | 0 | 0 | 0 | **0** | info | +0 | converge |
| AI_CONTENT_NOT_IN_TEXT | 4 | 4 | 4 | **4** | warning | +0 | converge |
| AI_HIGH_VALUE_UNCITED | 4 | 4 | 0 | **2** | info | -2 | override |
| AI_MAIN_CONTENT_LOW_RATIO | 2 | 0 | 2 | **2** | info | +0 | converge |
| AI_NO_VISUAL_COMPANION | 1 | 1 | 1 | **1** | info | +0 | converge |
| AI_PREVIEW_BLOCKED_AT_BOT | 3 | 2 | 6 | **4** | warning | +1 | override |
| AI_PREVIEW_SUPPRESSED | 3 | 2 | 6 | **4** | warning | +1 | override |
| AI_TXT_MISSING | 1 | 0 | 1 | **1** | info | +0 | converge |
| AMPHTML_BROKEN | 4 | 2 | 2 | **2** | info | -2 | converge |
| ANCHOR_TEXT_GENERIC | 4 | 4 | 2 | **2** | info | -2 | converge |
| AUTHOR_BYLINE_MISSING | 4 | 4 | 4 | **4** | warning | +0 | converge |
| BLOG_SECTIONS_MISSING | 5 | 2 | 2 | **2** | info | -3 | converge |
| BROKEN_LINK_404 | 10 | 10 | 2 | **2** | info | -8 | diverge→Fable |
| BROKEN_LINK_410 | 8 | 10 | 2 | **2** | info | -6 | diverge→Fable |
| BROKEN_LINK_503 | 4 | 6 | 1 | **1** | info | -3 | diverge→Fable |
| BROKEN_LINK_5XX | 7 | 10 | 2 | **3** | info | -4 | override |
| CANONICAL_EXTERNAL | 5 | 6 | 6 | **6** | warning | +1 | converge |
| CANONICAL_MISSING | 6 | 6 | 6 | **6** | warning | +0 | converge |
| CANONICAL_SELF_MISSING | 5 | 2 | 2 | **2** | info | -3 | converge |
| CENTRAL_CLAIM_BURIED | 5 | 4 | 2 | **2** | info | -3 | converge |
| CHUNKS_NOT_SELF_CONTAINED | 5 | 2 | 2 | **2** | info | -3 | converge |
| CITATIONS_MISSING_SUBSTANTIAL_CONTENT | 3 | 1 | 3 | **3** | info | +0 | converge |
| CITATIONS_ORPHANED | 2 | 0 | 1 | **1** | info | -1 | converge |
| CITATIONS_SOURCES_INACCESSIBLE | 4 | 2 | 1 | **1** | info | -3 | converge |
| CODE_BLOCK_MISSING_TECHNICAL | 4 | 0 | 1 | **1** | info | -3 | converge |
| COMPARISON_TABLE_MISSING | 3 | 1 | 1 | **1** | info | -2 | converge |
| CONTACT_INFO_NOT_IN_HTML | 4 | 2 | 4 | **4** | warning | +0 | converge |
| CONTENT_CLOAKING_DETECTED | 8 | 8 | 6 | **6** | warning | -2 | converge |
| CONTENT_DATE_STALE_VISIBLE | 4 | 4 | 2 | **2** | info | -2 | converge |
| CONTENT_IMAGE_HEAVY | 2 | 0 | 1 | **1** | info | -1 | converge |
| CONTENT_NOT_EXTRACTABLE_NO_TEXT | 6 | 8 | 9 | **9** | critical | +3 | converge |
| CONTENT_STALE | 3 | 1 | 1 | **1** | info | -2 | converge |
| CONTENT_STAT_OUTDATED | 2 | 0 | 1 | **1** | info | -1 | converge |
| CONTENT_THIN | 4 | 4 | 4 | **4** | warning | +0 | converge |
| CONTENT_UNSTRUCTURED | 3 | 0 | 4 | **3** | info | +0 | override |
| CONVERSATIONAL_H2_MISSING | 4 | 2 | 1 | **1** | info | -3 | converge |
| DATE_MODIFIED_MISSING | 2 | 1 | 2 | **2** | info | +0 | converge |
| DATE_PUBLISHED_MISSING | 3 | 1 | 2 | **2** | info | -1 | converge |
| DOCUMENT_PROPS_MISSING | 4 | 4 | 2 | **2** | info | -2 | converge |
| EXTERNAL_CITATIONS_LOW | 5 | 4 | 3 | **3** | info | -2 | converge |
| EXTERNAL_LINK_SKIPPED | 2 | 1 | 0 | **0** | info | -2 | converge |
| EXTERNAL_LINK_TIMEOUT | 3 | 1 | 1 | **1** | info | -2 | converge |
| FAQ_SCHEMA_MISSING | 2 | 1 | 2 | **2** | info | +0 | converge |
| FAVICON_MISSING | 3 | 2 | 2 | **2** | info | -1 | converge |
| FIRST_VIEWPORT_NO_ANSWER | 5 | 4 | 2 | **2** | info | -3 | converge |
| GEO_SUMMARY_BURIED | 5 | 4 | 2 | **2** | info | -3 | converge |
| H1_MISSING | 6 | 6 | 4 | **4** | warning | -2 | converge |
| H1_MULTIPLE | 5 | 1 | 2 | **2** | info | -3 | converge |
| HEADING_EMPTY | 4 | 1 | 1 | **1** | info | -3 | converge |
| HEADING_SKIP | 4 | 0 | 1 | **1** | info | -3 | converge |
| HIGH_CRAWL_DEPTH | 5 | 4 | 4 | **4** | warning | -1 | converge |
| HTTPS_REDIRECT_MISSING | 9 | 10 | 6 | **6** | warning | -3 | diverge→Fable |
| HTTP_PAGE | 9 | 10 | 6 | **6** | warning | -3 | diverge→Fable |
| IMG_ALT_DUP_FILENAME | 3 | 1 | 1 | **1** | info | -2 | converge |
| IMG_ALT_GENERIC | 4 | 1 | 2 | **2** | info | -2 | converge |
| IMG_ALT_MISSING | 5 | 6 | 2 | **3** | info | -2 | override |
| IMG_ALT_MISUSED | 3 | 1 | 1 | **1** | info | -2 | converge |
| IMG_ALT_TOO_LONG | 2 | 1 | 1 | **1** | info | -1 | converge |
| IMG_ALT_TOO_SHORT | 3 | 1 | 1 | **1** | info | -2 | converge |
| IMG_BROKEN | 8 | 6 | 4 | **4** | warning | -4 | converge |
| IMG_DUPLICATE_CONTENT | 2 | 0 | 1 | **1** | info | -1 | converge |
| IMG_FORMAT_LEGACY | 2 | 1 | 2 | **2** | info | +0 | converge |
| IMG_NO_SRCSET | 2 | 1 | 2 | **2** | info | +0 | converge |
| IMG_OVERSCALED | 4 | 1 | 2 | **2** | info | -2 | converge |
| IMG_OVERSIZED | 5 | 1 | 2 | **2** | info | -3 | converge |
| IMG_POOR_COMPRESSION | 4 | 1 | 2 | **2** | info | -2 | converge |
| IMG_SLOW_LOAD | 4 | 4 | 2 | **2** | info | -2 | converge |
| INTERACTIVE_NO_ACCESSIBLE_NAME | 4 | 1 | 1 | **1** | info | -3 | converge |
| INTERNAL_NOFOLLOW | 5 | 6 | 4 | **4** | warning | -1 | converge |
| INTERNAL_REDIRECT_301 | 4 | 2 | 2 | **2** | info | -2 | converge |
| JSON_LD_INVALID | 4 | 4 | 4 | **4** | warning | +0 | converge |
| JSON_LD_MISSING | 7 | 4 | 4 | **4** | warning | -3 | converge |
| JS_DEPENDENT_NAVIGATION | 5 | 8 | 6 | **6** | warning | +1 | converge |
| JS_RENDERED_CONTENT_DIFFERS | 6 | 8 | 6 | **6** | warning | +0 | converge |
| LANDMARK_MAIN_MISSING | 2 | 0 | 1 | **1** | info | -1 | converge |
| LANDMARK_NAV_MISSING | 2 | 0 | 1 | **1** | info | -1 | converge |
| LANG_MISSING | 6 | 2 | 2 | **2** | info | -4 | converge |
| LINK_EMPTY_ANCHOR | 7 | 1 | 2 | **2** | info | -5 | converge |
| LINK_PROFILE_PROMOTIONAL | 4 | 2 | 1 | **1** | info | -3 | converge |
| LLMS_TXT_INVALID | 2 | 0 | 1 | **1** | info | -1 | converge |
| LLMS_TXT_MISSING | 3 | 0 | 1 | **1** | info | -2 | converge |
| LOGIN_REDIRECT | 2 | 10 | 0 | **2** | info | +0 | override |
| META_DESC_DUPLICATE | 4 | 1 | 2 | **2** | info | -2 | converge |
| META_DESC_MISSING | 7 | 1 | 2 | **2** | info | -5 | converge |
| META_DESC_TOO_LONG | 3 | 1 | 2 | **2** | info | -1 | converge |
| META_DESC_TOO_SHORT | 4 | 1 | 2 | **2** | info | -2 | converge |
| META_REFRESH_REDIRECT | 5 | 10 | 2 | **2** | info | -3 | diverge→Fable |
| MISSING_HSTS | 4 | 2 | 1 | **1** | info | -3 | converge |
| MISSING_VIEWPORT_META | 6 | 10 | 6 | **6** | warning | +0 | diverge→Fable |
| MIXED_CONTENT | 6 | 6 | 4 | **4** | warning | -2 | converge |
| NOINDEX_HEADER | 10 | 10 | 10 | **10** | critical | +0 | converge |
| NOINDEX_META | 10 | 10 | 10 | **10** | critical | +0 | converge |
| NON_SEMANTIC_BUTTON | 4 | 0 | 1 | **1** | info | -3 | converge |
| NOT_IN_SITEMAP | 4 | 1 | 2 | **2** | info | -2 | converge |
| OG_DESC_MISSING | 3 | 0 | 1 | **1** | info | -2 | converge |
| OG_IMAGE_MISSING | 3 | 0 | 1 | **1** | info | -2 | converge |
| OG_TITLE_MISSING | 4 | 0 | 1 | **1** | info | -3 | converge |
| ORPHAN_CLAIM_TECHNICAL | 6 | 2 | 3 | **3** | info | -3 | converge |
| ORPHAN_PAGE | 6 | 6 | 4 | **4** | warning | -2 | converge |
| PAGE_SIZE_LARGE | 5 | 1 | 2 | **2** | info | -3 | converge |
| PAGE_TIMEOUT | 6 | 10 | 6 | **6** | warning | +0 | diverge→Fable |
| PAGINATION_LINKS_PRESENT | 2 | 1 | 0 | **0** | info | -2 | converge |
| PARA_TOO_LONG | 4 | 0 | 1 | **1** | info | -3 | converge |
| PDF_TOO_LARGE | 4 | 1 | 1 | **1** | info | -3 | converge |
| PLACEHOLDER_LINK | 7 | 1 | 2 | **2** | info | -5 | converge |
| PROMOTIONAL_CONTENT_INTERRUPTS | 3 | 0 | 1 | **1** | info | -2 | converge |
| QUERY_COVERAGE_WEAK | 5 | 2 | 2 | **2** | info | -3 | converge |
| QUOTATIONS_MISSING | 4 | 0 | 3 | **3** | info | -1 | diverge→Fable |
| RAW_HTML_JS_DEPENDENT | 6 | 8 | 9 | **9** | critical | +3 | converge |
| REDIRECT_301 | 3 | 2 | 2 | **2** | info | -1 | converge |
| REDIRECT_302 | 4 | 2 | 2 | **2** | info | -2 | converge |
| REDIRECT_CASE_NORMALISE | 2 | 1 | 0 | **0** | info | -2 | converge |
| REDIRECT_CHAIN | 6 | 6 | 2 | **2** | info | -4 | diverge→Fable |
| REDIRECT_LOOP | 10 | 10 | 10 | **10** | critical | +0 | converge |
| REDIRECT_TRAILING_SLASH | 2 | 1 | 0 | **0** | info | -2 | converge |
| ROBOTS_BLOCKED | 9 | 10 | 9 | **9** | critical | +0 | converge |
| SCHEMA_DEPRECATED_TYPE | 2 | 1 | 2 | **2** | info | +0 | converge |
| SCHEMA_MISSING | 5 | 4 | 4 | **4** | warning | -1 | converge |
| SCHEMA_ORG_MISSING | 5 | 4 | 4 | **4** | warning | -1 | converge |
| SCHEMA_TYPE_CONFLICT | 3 | 1 | 2 | **2** | info | -1 | converge |
| SCHEMA_TYPE_MISMATCH | 4 | 1 | 2 | **2** | info | -2 | converge |
| SCHEMA_VISIBLE_MISMATCH | 5 | 6 | 6 | **6** | warning | +1 | converge |
| SECTION_CROSS_REFERENCES | 6 | 0 | 1 | **1** | info | -5 | converge |
| SECTION_VAGUE_OPENER | 5 | 0 | 1 | **1** | info | -4 | converge |
| SEMANTIC_DENSITY_LOW | 3 | 0 | 1 | **1** | info | -2 | converge |
| SITEMAP_MISSING | 6 | 6 | 2 | **2** | info | -4 | diverge→Fable |
| STATISTICS_COUNT_LOW | 5 | 4 | 3 | **3** | info | -2 | converge |
| STRUCTURED_ELEMENTS_LOW | 3 | 0 | 1 | **1** | info | -2 | converge |
| THIN_CONTENT | 6 | 6 | 4 | **4** | warning | -2 | converge |
| TITLE_DUPLICATE | 5 | 6 | 4 | **4** | warning | -1 | converge |
| TITLE_H1_MISMATCH | 6 | 1 | 1 | **1** | info | -5 | converge |
| TITLE_META_DUPLICATE_PAIR | 6 | 6 | 1 | **4** | warning | -2 | override |
| TITLE_MISSING | 9 | 10 | 6 | **6** | warning | -3 | override |
| TITLE_TOO_LONG | 4 | 1 | 2 | **2** | info | -2 | converge |
| TITLE_TOO_SHORT | 5 | 1 | 1 | **1** | info | -4 | converge |
| TWITTER_CARD_MISSING | 3 | 0 | 1 | **1** | info | -2 | converge |
| UA_CONTENT_DIFFERS | 7 | 8 | 6 | **6** | warning | -1 | converge |
| UNSAFE_CROSS_ORIGIN_LINK | 3 | 0 | 0 | **0** | info | -3 | converge |
| URL_HAS_SPACES | 5 | 1 | 2 | **2** | info | -3 | converge |
| URL_HAS_UNDERSCORES | 2 | 0 | 2 | **2** | info | +0 | converge |
| URL_TOO_LONG | 2 | 1 | 1 | **1** | info | -1 | converge |
| URL_UPPERCASE | 3 | 0 | 2 | **2** | info | -1 | converge |
| WRONG_PLACEHOLDER_LINK | 7 | 1 | 2 | **2** | info | -5 | converge |
| WWW_CANONICALIZATION | 5 | 6 | 4 | **4** | warning | -1 | converge |

```python
# _ISSUE_SCORING impact migration (effort unchanged)
    "AI_BOT_SEARCH_BLOCKED": (9, 1),
    "AI_BOT_USER_FETCH_BLOCKED": (3, 1),
    "AI_HIGH_VALUE_UNCITED": (2, 2),
    "AI_PREVIEW_BLOCKED_AT_BOT": (4, 1),
    "AI_PREVIEW_SUPPRESSED": (4, 1),
    "AMPHTML_BROKEN": (2, 3),
    "ANCHOR_TEXT_GENERIC": (2, 2),
    "BLOG_SECTIONS_MISSING": (2, 2),
    "BROKEN_LINK_404": (2, 2),
    "BROKEN_LINK_410": (2, 2),
    "BROKEN_LINK_503": (1, 3),
    "BROKEN_LINK_5XX": (3, 2),
    "CANONICAL_EXTERNAL": (6, 3),
    "CANONICAL_SELF_MISSING": (2, 1),
    "CENTRAL_CLAIM_BURIED": (2, 3),
    "CHUNKS_NOT_SELF_CONTAINED": (2, 4),
    "CITATIONS_ORPHANED": (1, 1),
    "CITATIONS_SOURCES_INACCESSIBLE": (1, 3),
    "CODE_BLOCK_MISSING_TECHNICAL": (1, 2),
    "COMPARISON_TABLE_MISSING": (1, 2),
    "CONTENT_CLOAKING_DETECTED": (6, 4),
    "CONTENT_DATE_STALE_VISIBLE": (2, 2),
    "CONTENT_IMAGE_HEAVY": (1, 3),
    "CONTENT_NOT_EXTRACTABLE_NO_TEXT": (9, 4),
    "CONTENT_STALE": (1, 3),
    "CONTENT_STAT_OUTDATED": (1, 1),
    "CONVERSATIONAL_H2_MISSING": (1, 2),
    "DATE_PUBLISHED_MISSING": (2, 1),
    "DOCUMENT_PROPS_MISSING": (2, 2),
    "EXTERNAL_CITATIONS_LOW": (3, 2),
    "EXTERNAL_LINK_SKIPPED": (0, 1),
    "EXTERNAL_LINK_TIMEOUT": (1, 1),
    "FAVICON_MISSING": (2, 2),
    "FIRST_VIEWPORT_NO_ANSWER": (2, 2),
    "GEO_SUMMARY_BURIED": (2, 3),
    "H1_MISSING": (4, 1),
    "H1_MULTIPLE": (2, 2),
    "HEADING_EMPTY": (1, 1),
    "HEADING_SKIP": (1, 3),
    "HIGH_CRAWL_DEPTH": (4, 3),
    "HTTPS_REDIRECT_MISSING": (6, 2),
    "HTTP_PAGE": (6, 2),
    "IMG_ALT_DUP_FILENAME": (1, 1),
    "IMG_ALT_GENERIC": (2, 1),
    "IMG_ALT_MISSING": (3, 2),
    "IMG_ALT_MISUSED": (1, 2),
    "IMG_ALT_TOO_LONG": (1, 1),
    "IMG_ALT_TOO_SHORT": (1, 1),
    "IMG_BROKEN": (4, 2),
    "IMG_DUPLICATE_CONTENT": (1, 2),
    "IMG_OVERSCALED": (2, 3),
    "IMG_OVERSIZED": (2, 2),
    "IMG_POOR_COMPRESSION": (2, 2),
    "IMG_SLOW_LOAD": (2, 2),
    "INTERACTIVE_NO_ACCESSIBLE_NAME": (1, 2),
    "INTERNAL_NOFOLLOW": (4, 2),
    "INTERNAL_REDIRECT_301": (2, 1),
    "JSON_LD_MISSING": (4, 2),
    "JS_DEPENDENT_NAVIGATION": (6, 3),
    "LANDMARK_MAIN_MISSING": (1, 2),
    "LANDMARK_NAV_MISSING": (1, 2),
    "LANG_MISSING": (2, 1),
    "LINK_EMPTY_ANCHOR": (2, 2),
    "LINK_PROFILE_PROMOTIONAL": (1, 2),
    "LLMS_TXT_INVALID": (1, 2),
    "LLMS_TXT_MISSING": (1, 1),
    "META_DESC_DUPLICATE": (2, 2),
    "META_DESC_MISSING": (2, 1),
    "META_DESC_TOO_LONG": (2, 1),
    "META_DESC_TOO_SHORT": (2, 1),
    "META_REFRESH_REDIRECT": (2, 2),
    "MISSING_HSTS": (1, 2),
    "MIXED_CONTENT": (4, 2),
    "NON_SEMANTIC_BUTTON": (1, 3),
    "NOT_IN_SITEMAP": (2, 1),
    "OG_DESC_MISSING": (1, 1),
    "OG_IMAGE_MISSING": (1, 1),
    "OG_TITLE_MISSING": (1, 1),
    "ORPHAN_CLAIM_TECHNICAL": (3, 2),
    "ORPHAN_PAGE": (4, 2),
    "PAGE_SIZE_LARGE": (2, 3),
    "PAGINATION_LINKS_PRESENT": (0, 2),
    "PARA_TOO_LONG": (1, 2),
    "PDF_TOO_LARGE": (1, 2),
    "PLACEHOLDER_LINK": (2, 2),
    "PROMOTIONAL_CONTENT_INTERRUPTS": (1, 3),
    "QUERY_COVERAGE_WEAK": (2, 2),
    "QUOTATIONS_MISSING": (3, 2),
    "RAW_HTML_JS_DEPENDENT": (9, 3),
    "REDIRECT_301": (2, 2),
    "REDIRECT_302": (2, 2),
    "REDIRECT_CASE_NORMALISE": (0, 1),
    "REDIRECT_CHAIN": (2, 3),
    "REDIRECT_TRAILING_SLASH": (0, 1),
    "SCHEMA_MISSING": (4, 2),
    "SCHEMA_ORG_MISSING": (4, 2),
    "SCHEMA_TYPE_CONFLICT": (2, 2),
    "SCHEMA_TYPE_MISMATCH": (2, 2),
    "SCHEMA_VISIBLE_MISMATCH": (6, 2),
    "SECTION_CROSS_REFERENCES": (1, 2),
    "SECTION_VAGUE_OPENER": (1, 2),
    "SEMANTIC_DENSITY_LOW": (1, 3),
    "SITEMAP_MISSING": (2, 2),
    "STATISTICS_COUNT_LOW": (3, 2),
    "STRUCTURED_ELEMENTS_LOW": (1, 2),
    "THIN_CONTENT": (4, 3),
    "TITLE_DUPLICATE": (4, 2),
    "TITLE_H1_MISMATCH": (1, 2),
    "TITLE_META_DUPLICATE_PAIR": (4, 2),
    "TITLE_MISSING": (6, 1),
    "TITLE_TOO_LONG": (2, 1),
    "TITLE_TOO_SHORT": (1, 1),
    "TWITTER_CARD_MISSING": (1, 1),
    "UA_CONTENT_DIFFERS": (6, 3),
    "UNSAFE_CROSS_ORIGIN_LINK": (0, 1),
    "URL_HAS_SPACES": (2, 2),
    "URL_TOO_LONG": (1, 2),
    "URL_UPPERCASE": (2, 2),
    "WRONG_PLACEHOLDER_LINK": (2, 2),
    "WWW_CANONICALIZATION": (4, 2),
```


## 5. Implementation plan (phased; each phase its own tested commit)
- **R3.1 — Impact recalibration.** Apply the FINAL migration patch (§4) to `_ISSUE_SCORING` (120
  codes; effort unchanged). Add `confidence` + `effect_size` to every `_IssueSpec` and a parity test
  `impact == matrix(confidence, effect_size)` (allow a documented override set for the §3 overrides).
- **R3.2 — Derived severity.** Replace hardcoded `_IssueSpec.severity` with `severity_from_impact()`
  in `make_issue`; update the ~N severity-assertion tests; regenerate `issue-codes.md`.
- **R3.3 — Priority + quick-wins.** `priority_rank = impact×10 − effort×6`; add a `quick_win`
  boolean (impact≥4 and effort≤1) — surface as an issue-list flag (no GUI restructure).
- **R3.4 (optional) — extra suppression clusters** from Fable §3 that are safe as scoring-time
  suppressions: blanket-robots suppresses per-bot children; a `NOINDEX_*` page suppresses
  discoverability/content checks. Lower urgency now that impacts are low.

### Acceptance criteria → tests
- `test_impact_matches_matrix` — every non-override code's impact == matrix(confidence, effect_size).
- `test_scoring_matches_r3_final` — `_ISSUE_SCORING` matches §4 FINAL (×151).
- `test_severity_derived_from_impact` — every emitted severity == severity_from_impact(impact).
- `test_priority_rank_formula` + `test_quick_win_flag`.
- `test_broken_links_low_impact` (regression: a page with many dead links no longer craters).
- Real-crawl before/after on livingsystems.ca (manual gate before deploy).

## 6. Rollout / compatibility
- Typical site scores will **rise** (current scores were deflated by inflated cosmetic penalties).
  Re-baseline any historical comparisons; note the one-time shift in the changelog.
- No codes deleted. `confidence`/`effect_size` become the source of truth; impact derived from them.
- Update `functional-specification.md`, `thresholds.md`, `issue-codes.md`, `issueHelp.js` severities.
- Re-run this calibration semi-annually (both experts flag fast-moving vendor behavior); use the GSC
  Authority-Matrix correlation as the empirical validator (no A/B needed).
