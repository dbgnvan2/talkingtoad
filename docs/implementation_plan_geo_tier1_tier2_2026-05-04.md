# GEO Tier 1 + Tier 2 Implementation Plan

**Date:** 2026-05-04  
**Spec:** AI GEO Optimization Spec (Refactored) — Two-Tier System  
**Status:** Approved, ready for implementation

---

## Context

The refactored spec introduces a two-tier architecture:
- **Tier 1:** Lightweight heuristic checks run at crawl time on all pages (no LLM calls)
- **Tier 2:** Deeper rewrite + validation using LLM, applied selectively

Several Tier 1 checks already exist as LLM-based (expensive) Tier 2 checks. This plan adds
lightweight heuristic equivalents and wires them into the rewrite scoring.

---

## Acceptance Criteria

### Phase 1 — Tier 1 New Issue Codes

**T1-AC1 (spec 4.2):** `FIRST_VIEWPORT_NO_ANSWER` detection window extended from 150 to 200 words.
- Evidence: `parser.py` calls `_extract_first_n_words(soup, 200)`; `_CATALOGUE` description updated
- Test: `test_geo_static_checks.py::test_geo_first_viewport_short_page` still passes; new boundary test at 200 words

**T1-AC2 (spec 4.3):** New issue code `QUERY_COVERAGE_WEAK` fires when H1 significant tokens
(stop-words stripped, len ≥ 3) are represented in fewer than 50% of the first 200 words OR
absent from all H2/H3 headings. Does not fire if H1 has fewer than 2 significant tokens or
page is under 200 words.
- Evidence: `"QUERY_COVERAGE_WEAK"` in `_ISSUE_SCORING`, `_CATALOGUE`, detection in `_check_ai_readiness()`
- Test: `test_geo_static_checks.py::test_t1ac2_query_coverage_weak_fires` and `::test_t1ac2_query_coverage_weak_passes`

**T1-AC3 (spec 4.4):** New issue code `SECTION_VAGUE_OPENER` fires when ≥1 H2/H3 section's
first paragraph opens with a vague demonstrative reference pattern:
"This method/approach/system/technique/process/solution/tool/strategy/concept/model/option…"
or a bare pronoun opener "It …" / "These …" / "Those …" as a sentence start.
- Evidence: `vague_opener_count` field on `ParsedPage`; detection in parser; issue fired in `_check_ai_readiness()`
- Test: `test_geo_static_checks.py::test_t1ac3_vague_opener_fires` and `::test_t1ac3_vague_opener_passes`

**T1-AC4 (spec 4.5):** New issue code `SECTION_CROSS_REFERENCES` fires when body text contains
≥1 backward-reference phrase: "as mentioned above", "as discussed earlier", "as noted above",
"as described above", "as stated above", "the above", "as shown above", "as covered above",
"see above", "refer to the previous".
- Evidence: `cross_reference_count` field on `ParsedPage`; detection in parser; issue fired in `_check_ai_readiness()`
- Test: `test_geo_static_checks.py::test_t1ac4_cross_references_fires` and `::test_t1ac4_cross_references_passes`

**T1-AC5 (spec 4.6):** New issue code `PARA_TOO_LONG` fires when ≥1 `<p>` tag contains more
than 150 words. Stored as `long_paragraph_count` on `ParsedPage`. Severity: info. Category:
crawlability (general content quality; appears in main audit AND GEO report).
- Evidence: `long_paragraph_count` field on `ParsedPage`; detection in parser; issue in `_check_crawlability()`
- Test: `test_geo_static_checks.py::test_t1ac5_para_too_long_fires` and `::test_t1ac5_para_too_long_passes`

**T1-AC6:** All 4 new issue codes present in `issueHelp.js` (architecture parity test passes).
- Evidence: `tests/test_architecture_constraints.py` passes without changes
- Test: `test_architecture_constraints.py::test_issue_help_parity`

---

### Phase 2 — Tier 1 Scores in GEO Report

**T2-AC1 (spec 4.7):** `compute_tier1_scores(page_issues)` function added to `geo_analyzer.py`
returning `{"intro": 0–100, "query_coverage": 0–100, "section_clarity": 0–100, "independence": 0–100}`.
Scores derived from presence/count of T1 issue codes (no extra API calls).
- Evidence: function exists in `geo_analyzer.py`; scores present in `GET /api/ai/geo-report` response JSON
- Test: `test_geo_analyzer.py::test_t2ac1_tier1_scores_in_report`

**T2-AC2:** Four scores displayed as score cards in `GEOReportPanel.jsx` when a GEO report is loaded.
- Evidence: Visual test via browser; score cards visible above query match table
- Test: Human reviewer verifies (cannot be automated without e2e framework)

---

### Phase 3 — Rewrite Prompt Restructuring

**T3-AC1 (spec 5.1–5.7):** System prompt in `geo_rewrite_prompt.py` restructured to enforce:
1. Priority order: query alignment → intro answer → section independence → chunk optimization
2. Intro rules: answer in first 100–200 words, no narrative before the answer
3. Prohibited phrases in sections: "this approach", "as mentioned earlier", "the above method",
   "this method", "as discussed above" — must be replaced with explicit nouns
4. Controlled redundancy: repeat key entities across sections; no pronoun-only references
5. Query distribution: primary query language in intro + ≥1 section
6. Final structure template: H1 → direct-answer intro → H2 sections → supporting detail
- Evidence: system prompt text contains each rule explicitly
- Test: `test_geo_rewrite_prompt.py::test_t3ac1_prompt_contains_priority_order` and `::test_t3ac1_prompt_contains_prohibited_phrases`

---

### Phase 4 — Evolutionary Rewrite

**T4-AC1 (spec section 6 + Q6 decision):** `stream_rewrite_variants` uses the current best
result as the base for each subsequent try (not the original page content). Try 1 always starts
from the original. Try N (N > 1) starts from the highest-scoring variant seen so far.
System prompt for tries 2+ says "improve this existing draft" not "rewrite this page".
- Evidence: `stream_rewrite_variants` passes best text as `page_content` for subsequent calls
- Test: `test_geo_rewrite_prompt.py::test_t4ac1_iterative_uses_best_as_base`

---

### Phase 5 — Validation Scoring Replacement

**T5-AC1 (spec section 6):** Per-variant projected score formula changed to:
`70% × LLM query re-match + 30% × Tier 1 composite`
where Tier 1 composite = weighted average of intro (35%), query coverage (30%),
section independence (25%), structural clarity (10%) scores on rewrite markdown text.
Retires `_content_score` (5-check ad-hoc function).
- Evidence: `_project_score_from_findings` updated; `_content_score` function removed
- Test: `test_geo_rewrite_prompt.py::test_t5ac1_validation_scoring_formula`

---

## Implementation Order

```
Phase 1 (parser + issue codes)
  └─ Phase 2 (scores derived from codes)
       └─ Phase 5 (validation uses same heuristics on rewrite text)
Phase 3 (rewrite prompt — independent)
Phase 4 (evolutionary rewrite — independent)
```

Phases 3 and 4 can be done in parallel with Phases 1–2. Phase 5 depends on Phase 1 (reuses same detection logic on markdown output).

---

## Key Design Decisions

**`first_150_words` field:** Will be extended to 200 words in-place (parser call changed to
`_extract_first_n_words(soup, 200)`). Field name kept as `first_150_words` to avoid a
large rename cascade across 20+ call sites. Internal doc comment updated.

**Pre-compute in parser, not issue_checker:** `vague_opener_count`, `cross_reference_count`,
`long_paragraph_count` are computed during HTML parsing and stored as int fields on `ParsedPage`.
This keeps `issue_checker.py` as a consumer of pre-computed signals, consistent with existing
pattern (`mixed_content_count`, `table_count`, `structured_element_count`).

**Tier 1 scores computed on-the-fly:** No schema changes needed. Scores derived from issue
presence/count after page analysis. `compute_tier1_scores(page_issues)` takes the issue list
and returns scores.

**Evolutionary rewrite:** Single-file change to `stream_rewrite_variants`. Carry `best_text`
across iterations. Pass as content for tries 2+.

---

## Adjacent Issues (not fixed in this change)

- `CHUNKS_NOT_SELF_CONTAINED` (LLM-based) overlaps with new `SECTION_CROSS_REFERENCES` /
  `SECTION_VAGUE_OPENER` (heuristic). Both coexist by design (Tier 1 = fast/all pages, Tier 2 = deep/selected). No deduplication needed.
- `geo_scoring_map.py` string references to `first_150_words` (5 locations) are comment strings
  in a scoring metadata dictionary — leave as-is (cosmetic, not functional).
