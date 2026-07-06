# TalkingToad — scoring/ranking change specification

Derived from the R3 expert evaluation (2026-07-03). This document specifies **what to change** in TalkingToad's scoring, ranking, and issue-emission pipeline. It does not re-litigate the analysis; consult the R3 response for justification.

Scope: scoring model, counting rule, formulas, code merges/suppressions, data model, migration. Individual per-code impact values are in the R3 CSV (`derived_impact` column) — this spec references that CSV as the authoritative per-code table rather than duplicating 151 rows.

Confidence flags are called out inline: **[High]** where the change is mechanically forced by vendor facts or the R3 model; **[Judgment]** where reasonable engineers could disagree on the exact threshold.

---

## 1. Scoring model — replace the hand-set impact table

### 1.1 Derivation matrix

Impact is derived, not stored per-code as a free-form integer. Two inputs: `confidence` and `effect_size`.

| confidence \ effect | none | small | moderate | large |
|---|---|---|---|---|
| Heuristic | 0 | 1 | 2 | 3 |
| Heuristic-measured | 0 | 2 | 3 | 4 |
| Reasonable proxy | 0 | 2 | 4 | 6 |
| Established | 0 | 2 | 6 | 9 |

**10-tier exception:** a small allowlist of codes may carry impact 10 when the mechanism is "removes the page from search/AI eligibility outright." Current allowlist: `NOINDEX_META`, `NOINDEX_HEADER`, `REDIRECT_LOOP`. All other codes are capped at 9.

**None-tier addition [Judgment]:** effect_size gains a fourth level `none` (impact 0) for findings that are informational, are auto-handled by the platform, or reflect a legitimate owner choice. Without this level such codes would either be forced to `small` (falsely penalizing non-defects) or require ad-hoc impact-0 overrides. Codes in the current registry that should use `none`: `AI_BOT_TABLE_STALE`, `AI_BOT_TRAINING_DISALLOWED`, `AI_CITED_PAGE`, `AI_HIGH_VALUE_UNCITED`, `EXTERNAL_LINK_SKIPPED`, `LOGIN_REDIRECT`, `PAGINATION_LINKS_PRESENT`, `REDIRECT_CASE_NORMALISE`, `REDIRECT_TRAILING_SLASH`, `UNSAFE_CROSS_ORIGIN_LINK`.

### 1.2 Code registry — schema change

Each code definition changes from `(impact, effort, severity, confidence)` to:

```
code:
  effort: 0–5                        # unchanged, still hand-set
  confidence: enum                   # Heuristic | Heuristic-measured | Reasonable proxy | Established
  effect_size: enum                  # none | small | moderate | large
  fatal_override: bool               # true only for the 10-tier allowlist
  # impact and severity are DERIVED, not stored
```

Derived at load time:
- `impact = fatal_override ? 10 : matrix[confidence][effect_size]`
- `severity = impact >= 8 ? "critical" : impact >= 4 ? "warning" : "info"`

**Rationale:** the current data has severity drifting from impact (e.g. `NOINDEX_META` impact 10 labeled "warning"). Derivation eliminates the drift by construction.

### 1.3 Per-code values

Load `confidence` and `effect_size` for all 151 codes from the R3 CSV columns `recommended_confidence` and `recommended_effect_size`. The `derived_impact` column is the expected result of running these through the matrix — use it as a test fixture, not as stored data.

---

## 2. Counting rule — normalize per-target checks **[High]**

**Current behavior:** `BROKEN_LINK_404/410/503/5XX`, `REDIRECT_*`, `EXTERNAL_LINK_TIMEOUT` emit one issue row per offending link. Each row's full impact is deducted. A page with five 404s loses `5 × impact`.

**Change:** these checks emit **one issue row per page**, matching the rest of the registry. The row carries an `occurrences` field (list of offending URLs). Impact is deducted **once**, multiplied by an occurrence factor:

```
occurrence_multiplier = min(1 + 0.25 * (n - 1), 2.0)
page_deduction = impact * occurrence_multiplier
```

Where `n` = number of occurrences. Effect: 1 broken link → 1.0×; 2 → 1.25×; 5 → 2.0×; 20 → 2.0×.

**[Judgment]** on the specific curve. The `0.25` step and `2.0` ceiling are defensible defaults; you may want to tune after seeing distributional impact on your existing crawl corpus. What is **not** a judgment call is that unbounded per-target multiplication must go.

Report UI: the single row shows the count and lists offending targets in a detail panel. Priority ranking uses the effective (multiplied) deduction, not the base impact.

---

## 3. Page-health formula — add a per-category cap **[Judgment]**

**Current:** `page_health = max(0, 100 − Σ(impact of every issue row))`

**Change:** apply a per-category cap before summing:

```
per_category_deduction = min(Σ(deductions in category), CATEGORY_CAP)
page_health = max(0, 100 − Σ(per_category_deduction))
```

Recommended `CATEGORY_CAP = 25`. Categories are the existing `category` field (`ai_readiness`, `crawlability`, `image`, `metadata`, `redirect`, `broken_link`, `security`, `semantic_html`, `heading`, `url_structure`, `sitemap`, `duplicate`, `rendering`).

**Rationale:** one architectural root cause (JS app shell, no HTTPS, no schema) currently trips 4–8 codes in a single category and can floor a page from one underlying condition. The cap prevents monocausal flooring while preserving additivity across independent problems.

**Do not adopt:** diminishing-returns curves across all issues, or a global site-wide cap. Both make "fix X, gain Y" unexplainable to a non-technical maintainer, which is the tool's primary audience.

---

## 4. Priority-ranking formula **[Judgment]**

**Current:** `priority_rank = impact × 10 − effort × 2` (effort can move rank ≤10 points; impact spans 0–100).

**Change:**
```
priority_rank = impact × 10 − effort × 6
```

Effort now spans 0–30, which reorders within an impact tier but cannot cross two impact tiers.

**Additional deliverable — Quick Wins list:** a separately-surfaced list, independent of overall priority ordering, of every issue satisfying `impact >= 4 AND effort <= 1`. For the target audience (non-technical volunteer maintainer), this UI badge does more useful work than any formula tweak. Recommend showing it as the default landing view of the issues panel.

---

## 5. Severity — remove from scoring pipeline **[High]**

Severity is currently a stored per-code field that "exists but is NOT part of the health score." Under section 1.2 it becomes a derived value from impact. Remove it from the code registry as a source of truth. It remains a display attribute in the UI.

---

## 6. Overlap suppression rules — 15 clusters

Each cluster below specifies a root cause and the deduplication mechanism. Three mechanisms are used:

- **suppress-children:** when the parent code fires, children are still detected and shown in the report (for diagnostics) but contribute 0 to the health score
- **merge:** delete one or more codes; the surviving code covers the union
- **cap-only:** rely on the per-category cap (section 3) rather than an explicit suppression

Implementation: add a `suppresses: [code, code, ...]` field to code definitions, evaluated after all detectors run and before score computation.

### 6.1 JS app shell → suppress-children
`RAW_HTML_JS_DEPENDENT` suppresses: `JS_RENDERED_CONTENT_DIFFERS`, `JS_DEPENDENT_NAVIGATION`, `SEMANTIC_DENSITY_LOW`, `CONTENT_UNSTRUCTURED`, `THIN_CONTENT`, `CONTENT_THIN`.

### 6.2 No JSON-LD → merge + suppress-children
- **Merge:** delete `SCHEMA_MISSING`; keep `JSON_LD_MISSING` (they detect the same condition in two categories).
- **Suppress-children:** `JSON_LD_MISSING` suppresses `SCHEMA_ORG_MISSING`, `FAQ_SCHEMA_MISSING`, `DATE_PUBLISHED_MISSING`, `DATE_MODIFIED_MISSING`, `SCHEMA_TYPE_CONFLICT`, `SCHEMA_TYPE_MISMATCH`, `SCHEMA_VISIBLE_MISMATCH`, `SCHEMA_DEPRECATED_TYPE`, `JSON_LD_INVALID`.

### 6.3 No TLS → promote to site-level
`HTTP_PAGE`, `HTTPS_REDIRECT_MISSING`, `MIXED_CONTENT`, `MISSING_HSTS`, `WWW_CANONICALIZATION` are site-configuration issues that currently charge every page. Change: emit each **once per site** at the worst-affected representative page. Do not deduct from other pages for the same finding. Requires a new issue-scope enum (`page` | `site`) on code definitions.

### 6.4 Answer-first family → merge
Merge `CENTRAL_CLAIM_BURIED`, `FIRST_VIEWPORT_NO_ANSWER`, `GEO_SUMMARY_BURIED` into one code — proposed name `ANSWER_PLACEMENT_BURIED`. They measure the same heuristic three ways.

### 6.5 Sourcing/citations → suppress-children
`CITATIONS_MISSING_SUBSTANTIAL_CONTENT` is the parent when a page has no citations at all. It suppresses `EXTERNAL_CITATIONS_LOW`, `ORPHAN_CLAIM_TECHNICAL`, `QUOTATIONS_MISSING`, `LINK_PROFILE_PROMOTIONAL`, `CITATIONS_ORPHANED`, `CITATIONS_SOURCES_INACCESSIBLE`.

### 6.6 Chunk self-containment → merge
Merge `CHUNKS_NOT_SELF_CONTAINED`, `SECTION_CROSS_REFERENCES`, `SECTION_VAGUE_OPENER` into one code — proposed name `SECTIONS_NOT_SELF_CONTAINED`. Same theory, three phrase detectors.

### 6.7 Title/meta duplication → delete
Delete `TITLE_META_DUPLICATE_PAIR`. It fires exactly when both `TITLE_DUPLICATE` and `META_DESC_DUPLICATE` fire — pure triple-counting.

### 6.8 Heavy image → suppress-children
Promote `IMG_OVERSIZED` to parent. Suppresses `IMG_POOR_COMPRESSION`, `IMG_OVERSCALED`, `IMG_FORMAT_LEGACY`, `IMG_SLOW_LOAD`, `IMG_NO_SRCSET` when they co-fire on the same image URL.

### 6.9 Alt-text family → suppress-children
Promote `IMG_ALT_MISSING` to parent for images with no alt. For images with a defective alt, `IMG_ALT_GENERIC` is the parent, suppressing `IMG_ALT_TOO_SHORT`, `IMG_ALT_DUP_FILENAME`, `IMG_ALT_MISUSED`. `IMG_ALT_TOO_LONG` remains independent (opposite failure mode).

### 6.10 Social meta → merge
Merge `OG_TITLE_MISSING`, `OG_DESC_MISSING`, `OG_IMAGE_MISSING`, `TWITTER_CARD_MISSING` into one code — proposed name `SOCIAL_PREVIEW_METADATA_MISSING`. A single plugin setting drives all four.

### 6.11 Blanket robots disallow → suppress-children
`AI_BOT_BLANKET_DISALLOW` suppresses `AI_BOT_SEARCH_BLOCKED`, `AI_BOT_USER_FETCH_BLOCKED`, `ROBOTS_BLOCKED`, `AI_BOT_NO_AI_DIRECTIVES`.

### 6.12 Noindexed page → scope reduction
When `NOINDEX_META` or `NOINDEX_HEADER` fires on a page, suppress **all other page-level codes** except those in `security` and `redirect` categories. A page excluded from search cannot benefit from content, schema, or heading fixes.

### 6.13 Redirect chain → suppress-children
`REDIRECT_CHAIN` suppresses `REDIRECT_301` and `REDIRECT_302` for the same source URL. `INTERNAL_REDIRECT_301` remains independent (measures a distinct condition — the link source).

### 6.14 Poorly linked page → cap-only
`ORPHAN_PAGE`, `NOT_IN_SITEMAP`, `HIGH_CRAWL_DEPTH` legitimately partially overlap but measure distinct conditions. Rely on the `crawlability` category cap rather than explicit suppression.

### 6.15 Thin page → suppress-children
`CONTENT_THIN` (<100 words) is a strict subset of `THIN_CONTENT` (<300 words). When `CONTENT_THIN` fires, suppress `THIN_CONTENT`, `CONTENT_UNSTRUCTURED`, `STRUCTURED_ELEMENTS_LOW`, `SEMANTIC_DENSITY_LOW`.

---

## 7. Code registry summary — codes to delete or merge

| Action | Codes | Result |
|---|---|---|
| Delete | `SCHEMA_MISSING` | Duplicate of `JSON_LD_MISSING` |
| Delete | `TITLE_META_DUPLICATE_PAIR` | Triple-counts existing codes |
| Merge → `ANSWER_PLACEMENT_BURIED` | `CENTRAL_CLAIM_BURIED`, `FIRST_VIEWPORT_NO_ANSWER`, `GEO_SUMMARY_BURIED` | 3 → 1 |
| Merge → `SECTIONS_NOT_SELF_CONTAINED` | `CHUNKS_NOT_SELF_CONTAINED`, `SECTION_CROSS_REFERENCES`, `SECTION_VAGUE_OPENER` | 3 → 1 |
| Merge → `SOCIAL_PREVIEW_METADATA_MISSING` | `OG_TITLE_MISSING`, `OG_DESC_MISSING`, `OG_IMAGE_MISSING`, `TWITTER_CARD_MISSING` | 4 → 1 |

Net registry size: 151 → 143 codes (2 deletions, 8 codes collapsed into 3).

---

## 8. Data model / persistence changes

Anything storing historical scores needs a compatibility strategy.

1. **Code definitions:** schema change per section 1.2. Migration: derive new `confidence` and `effect_size` for every existing code from the R3 CSV; recompute impact and severity.
2. **Issue rows:** add `occurrences: int` (default 1) and `occurrence_urls: list[str]` (default empty) for the per-target family (section 2). Existing per-target rows must be collapsed on migration — one row per (page, code) pair, occurrences summed.
3. **Code definitions gain:** `fatal_override: bool`, `scope: enum(page|site)` (section 6.3), `suppresses: list[code]` (section 6). Optional `deprecated: bool` for codes being removed.
4. **Historical page/site scores:** these become non-comparable after adoption. Recommend storing a `scoring_model_version` field on every saved audit and displaying it in the UI. Do not migrate old scores in place.

---

## 9. Rollout order

Priority ordering for implementation. Steps 1–3 are the ones that most distort current scores; do them first even if the rest slips.

1. **Section 2** (per-target counting normalization) — largest single distortion in the current tool
2. **Section 1** (derivation matrix + reload all 151 codes from R3 CSV)
3. **Section 6.3** (TLS cluster → site-scope) — currently multiplies across every page
4. **Section 3** (per-category cap)
5. **Section 6** remaining suppression rules
6. **Section 7** code merges/deletions
7. **Section 4** priority formula + Quick Wins list
8. **Section 5** severity derivation cleanup

---

## 10. Test fixtures to build before merging

- **Matrix conformance:** for every code, assert `derived_impact` matches the R3 CSV.
- **Per-target multiplier:** synthetic page with 1, 2, 5, 20 broken 404s → deductions of impact × {1.0, 1.25, 2.0, 2.0}.
- **Category cap:** synthetic page with 10 issues of impact 5 in one category → deduction capped at 25, not 50.
- **Suppression:** for each cluster in section 6, a synthetic page tripping the parent + all children — assert children contribute 0.
- **Site-scope:** synthetic 50-page site with HTTP → exactly one deduction across the site total, not 50.
- **Severity derivation:** for each code, assert severity is the derived enum, not a stored field.
- **Noindex scope reduction:** noindexed page with 15 other content issues → only the noindex deduction counts.

---

## 11. Deliberately out of scope

- **Per-check threshold tuning** (150-word paragraph limit, 300-word thin-content limit, 40% main-content ratio, etc.). These are separately arguable and would need false-positive-rate data from your existing crawls to calibrate honestly. This spec does not change any of them.
- **Detector logic changes.** Suppression and merging happen after detection; the detectors themselves are unchanged except where two codes collapse into one (section 7).
- **A separate "intentional configuration" acknowledgement mechanism** for site owners to mark `LOGIN_REDIRECT`, `AI_BOT_SEARCH_BLOCKED`, noindex directives, etc. as deliberate. Recommended follow-up work but adds product complexity beyond scoring calibration.
- **Semi-annual recalibration process.** AI-bot behavior, llms.txt adoption, and schema's role in LLM grounding are fast-moving. A cadence for reviewing the CSV should exist, but is a process question, not a spec item.
