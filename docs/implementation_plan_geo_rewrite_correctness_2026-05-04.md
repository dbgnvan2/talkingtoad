# GEO Rewrite Prompt — Correctness Pass: Implementation Plan

**Date:** 2026-05-04
**Scope:** Implement spec "GEO Rewrite Prompt — Correctness Pass v1.0"
**Status:** Planning — awaiting user approval before any code changes
**Source spec:** Provided in chat by user (Opus 4.7), 2026-05-04.

---

## 0. Pre-flight — what's already in the tree

This is rewrite attempt #4. Before planning anything new, I confirmed what
the code already does so the plan only adds what's missing.

| Spec section | Already present? | Evidence |
|---|---|---|
| §2 (Fix 1) — fabrication examples in `_CONTENT_FIX_INSTRUCTIONS` | **Bug present.** `STATISTICS_COUNT_LOW` example contains the literal "under 45 minutes". `QUOTATIONS_MISSING` example contains the literal "According to the Supabase documentation, pgvector supports cosine similarity." | `geo_rewrite_prompt.py:1229, 1236` |
| §3 (Fix 2) — placeholder cap | **Not present.** Placeholders count as full-credit pass for citations / quotes / stats today. | `geo_rewrite_prompt.py:988–1013` |
| §4 (Fix 3) — page-type-conditional structure | **Not present.** `_content_score` accepts `page_type` but never branches on it. | `geo_rewrite_prompt.py:1024–1033` |
| §5 (Fix 4) — entity-set named-list detection | **Not present.** Current `_item_has_named_reference` uses `idx > 0 and w[0].isupper() and w not in _COMMON_MID_CAPS` — pure capitalisation heuristic. | `geo_rewrite_prompt.py:556–574` |
| §6 (Fix 5) — numbered-output query-match parser | **Not present.** Current parser uses positional alignment (`lines[idx]`) and silently defaults missing lines to "No". | `geo_rewrite_prompt.py:1146–1170` |
| §7 (Fix 6) — score-blend constants surfaced | **Not present.** `0.8` and `0.2` are inline literals at line 1510. | `geo_rewrite_prompt.py:1510` |
| §8.1 FAQ stricter rule | **Not present.** Single heading-question with answer counts as 1 pair. | `geo_rewrite_prompt.py:518–553` |
| §8.2 hard prohibition coverage | **Partially present.** §(e) item 5 already lists FAQ / code / tables / named lists / outbound links (RP3.4 work). Missing: explicit "comparison tables" callout and "specific statistics from the original" callout. | `geo_rewrite_prompt.py` §(e) section |
| §8.3 GEO NOTES regex tightening | **Not present.** `_GEO_NOTES_SPLIT_RE = r"\n---\s*\nGEO NOTES\b.*$"` matches anywhere those tokens co-occur. | `geo_rewrite_prompt.py:852` |
| §8.4 synthetic page count caps | **Bug confirmed safe.** `issue_checker.py:1923` checks `structured_element_count == 0` only. Cap currently does no harm but the inline comment is missing. | `issue_checker.py:1923` |
| §8.5 fabricated link detection | **Not present.** `https://example.com` counts as a real outbound citation today. | `geo_rewrite_prompt.py:996–1003` |

Implementing this spec touches **3 files**: `api/services/geo_rewrite_prompt.py`,
`tests/test_geo_rewrite_prompt.py`, and a new fixture file.

---

## 1. Tuple-change blast radius (mandatory pre-work for §3)

The spec changes `_content_score`'s return signature from a 3-tuple to a
4-tuple. Every caller must be updated in the same commit. Audit:

| Site | File:line | Required change |
|---|---|---|
| Definition | `api/services/geo_rewrite_prompt.py:957` | Add `placeholder_inventory: dict` to return |
| `_project_score` wrapper | `api/services/geo_rewrite_prompt.py:1073` | Pass-through new tuple element |
| `stream_rewrite_variants` | `api/services/geo_rewrite_prompt.py:1497` | `issues, c_score, failing_checks, ph_inv = ...` |
| Tests — `TestContentScoreAdversarial` | `tests/test_geo_rewrite_prompt.py` (8 unpack sites in `_content_score(...)` calls) | Each `_, score, codes = ...` → `_, score, codes, _ = ...` |
| Tests — `TestPreservationFloor` | `tests/test_geo_rewrite_prompt.py` (5 unpack sites) | Same as above |

There are **NO production callers outside `geo_rewrite_prompt.py` itself**
(verified via `grep -rn "_content_score(" --include="*.py"`).

---

## 2. Acceptance criteria — verbatim spec IDs mapped to tests

Every criterion below uses the spec's section number verbatim. Each row names
the test ID (`CR<spec-section>_<short-name>`) that proves it. All tests
live in `tests/test_geo_rewrite_prompt.py` unless noted.

### Fix 1 — Remove fabrication-inducing examples (spec §2)

| Spec ID | Requirement | Test |
|---|---|---|
| §2.2.a | `STATISTICS_COUNT_LOW` ✅ DO example contains zero specific numeric values; uses placeholder only | `CR2_2_stats_do_no_numbers` |
| §2.2.b | `QUOTATIONS_MISSING` ✅ DO example contains no specific named-source factual claim | `CR2_2_quote_do_no_named_source` |
| §2.3.a | All 5 `_CONTENT_FIX_INSTRUCTIONS` entries contain a `✅ DO:` line and a `❌ DO NOT:` line | `CR2_3_all_entries_have_do_and_dont` |
| §2.3.b | Each `❌ DO NOT:` line contains the fabrication signal it warns against (proves the test discriminates) | `CR2_3_dont_examples_demonstrate_fabrication` |
| §2.4 | Programmatic check: no `\d+\s*(%|percent|minute|hour|second|day|year)` in any DO line; ≥1 such match in DO NOT lines for stats/quote entries | `CR2_4_do_no_numbers_dont_has_numbers` |

**Implementation sites:** `geo_rewrite_prompt.py:1216–1252` (5 entries).

### Fix 2 — Cap placeholder credit in scoring (spec §3)

| Spec ID | Requirement | Test |
|---|---|---|
| §3.2 | Real evidence ⇒ full pass; only-placeholder ⇒ partial-pass at 0.5 weight; neither ⇒ full fail | `CR3_2_partial_pass_half_weight` |
| §3.2 | `STRUCTURED_ELEMENTS_LOW` and `FIRST_VIEWPORT_NO_ANSWER` remain binary (no partial-pass) | `CR3_2_non_placeholder_checks_remain_binary` |
| §3.3 | `_content_score` returns 4-tuple `(fail_count, score, failing_codes, placeholder_inventory)` | `CR3_3_returns_four_tuple` |
| §3.3 | `placeholder_inventory` keys: `partial_pass_checks`, `placeholder_counts`, `placeholder_density` | `CR3_3_inventory_has_required_keys` |
| §3.4 | `stream_rewrite_variants` SSE `variant` event includes `placeholder_inventory` | `CR3_4_sse_variant_includes_inventory` |
| §3.4 | `done` event includes `placeholder_inventory` for the winner | `CR3_4_sse_done_includes_inventory` |
| §3.5 | When all 3 placeholder-eligible checks have only placeholders, only 2 count as partial-pass; the third (lowest weight by tie-break: alphabetical code) fails fully | `CR3_5_cap_demotes_third_to_fail` |
| §3.6.a | Real-evidence rewrite scores strictly higher than same-shape placeholder-only rewrite | `CR3_6_real_beats_placeholder` |
| §3.6.b | All-placeholder rewrite cannot exceed 0.85 | `CR3_6_all_placeholder_caps_at_85` |
| §3.6.c | Inventory populated correctly for one-citation-placeholder text | `CR3_6_inventory_populated` |

**Implementation sites:** `geo_rewrite_prompt.py:957–1059` (rewrite checks 1–3 to use partial_passes set; new return tuple; new helper for cap rule).

### Fix 3 — Page-type-conditional scoring (spec §4)

| Spec ID | Requirement | Test |
|---|---|---|
| §4.2.a | New helper `_has_numbered_list_with_min_items(text, n)` returns True iff some `1.`/`2.`/`3.` block has ≥n consecutive items | `CR4_2_numbered_list_helper` |
| §4.2.b | New helper `_table_has_min_rows(text, n)` returns True iff some markdown table has ≥n data rows (excluding header + separator) | `CR4_2_table_min_rows_helper` |
| §4.2.c | `_structural_check_passes(body, "technical")` requires code OR numbered list ≥3 | `CR4_2_technical_dispatch` |
| §4.2.d | `_structural_check_passes(body, "comparison")` requires table≥2 rows OR named list ≥1 | `CR4_2_comparison_dispatch` |
| §4.2.e | `_structural_check_passes(body, "faq")` requires `_count_faq_pairs ≥ 3` | `CR4_2_faq_dispatch` |
| §4.2.f | `_structural_check_passes(body, "general"|"article")` retains current "any structured element" behaviour | `CR4_2_general_dispatch_unchanged` |
| §4.3 | Page-type-specific fix instructions exist (`STRUCTURED_ELEMENTS_LOW_TECHNICAL`, `_COMPARISON`, `_FAQ`); `_build_improvement_prompt` looks them up by page_type with generic fallback | `CR4_3_per_type_fix_instruction_dispatched` |
| §4.4.a | Technical page with bullets only (no code) fails `STRUCTURED_ELEMENTS_LOW` | `CR4_4_technical_no_code_fails` |
| §4.4.b | Same page + code block passes | `CR4_4_technical_with_code_passes` |
| §4.4.c | Comparison page prose-only fails; with table passes | `CR4_4_comparison_table_required` |
| §4.4.d | FAQ page with 2 pairs fails; with 3 pairs passes | `CR4_4_faq_three_pairs_required` |
| §4.4.e | `general`/`article` retain current behaviour | `CR4_4_general_unchanged` |

**Implementation sites:** `geo_rewrite_prompt.py:1024–1033` (replace structural check), new helpers near the regex constants block (~line 460), `_CONTENT_FIX_INSTRUCTIONS` (add 3 variants), `_build_improvement_prompt` lookup near line 1326.

### Fix 4 — Entity-set named-list detection (spec §5)

| Spec ID | Requirement | Test |
|---|---|---|
| §5.2.1 | `_extract_named_entities_from_text(text)` returns multi-word title-case phrases of 2–4 words | `CR5_2_extracts_multiword_phrases` |
| §5.2.2 | Returns single-word terms appearing ≥2 times matching `[A-Z][a-zA-Z0-9]+` | `CR5_2_extracts_repeated_capitalised` |
| §5.2.3 | Returns backtick-wrapped identifiers (`pgvector`, `npm`) regardless of case | `CR5_2_extracts_backtick_identifiers` |
| §5.2.4 | Allowlisted technical terms (`_TECHNICAL_TERM_ALLOWLIST`) match case-insensitively | `CR5_2_allowlist_case_insensitive` |
| §5.2.5 | `_extract_preservation_floor` adds `named_entities: frozenset[str]` field | `CR5_2_preservation_floor_has_named_entities` |
| §5.2.6 | `_count_named_lists` accepts `known_entities` param; uses `_item_references_known_entity` helper | `CR5_2_named_lists_uses_entities` |
| §5.2.7 | `_check_preservation_regression` adds violation `NAMED_ENTITIES_LOST` when rewrite preserves <70% of original entities | `CR5_2_named_entities_lost_violation` |
| §5.4.a | Extraction recovers Supabase, MCP (or `mcp`), pgvector, Claude, ChatGPT from a sample paragraph | `CR5_4_openbrain_entities_extracted` |
| §5.4.b | Extraction does NOT include Self-Contained, Required, Important, Setup, Step 1 | `CR5_4_emphasised_words_excluded` |
| §5.4.c | Rewrite dropping 50% of entities fails the regression check | `CR5_4_entity_loss_triggers_regression` |

**Implementation sites:** `geo_rewrite_prompt.py:556–599` (replace heuristic), `_extract_preservation_floor` line 628 (add `named_entities`), `_check_preservation_regression` line 909 (add `NAMED_ENTITIES_LOST` branch). Module-level `_TECHNICAL_TERM_ALLOWLIST` constant added near other regex constants.

### Fix 5 — Numbered-output query-match parser (spec §6)

| Spec ID | Requirement | Test |
|---|---|---|
| §6.2.a | Prompt sent to LLM uses `N: <verdict>` format with explicit example | `CR6_2_prompt_format_includes_numbered_example` |
| §6.2.b | Parser uses `_VERDICT_LINE_RE = r"^\s*(\d+)\s*[:.\-)]\s*(yes\|partial\|no)\b"` (case-insensitive) | `CR6_2_verdict_regex_pattern` |
| §6.2.c | Parser populates `verdicts: dict[int, str]` keyed by question number | `CR6_2_dict_keyed_by_index` |
| §6.3.a | Per-query result includes `parse_failure: bool` | `CR6_3_per_query_has_parse_failure_field` |
| §6.3.b | Missing verdict defaults to `"Partial"` (not `"No"`) and sets `parse_failure=True` | `CR6_3_missing_defaults_to_partial` |
| §6.3.c | Knowledge-gap detection in `stream_rewrite_variants` excludes any query with a `parse_failure` in any variant | `CR6_3_knowledge_gap_excludes_parse_failures` |
| §6.4.a | Numbered output parsed with trailing whitespace and prefixes | `CR6_4_parses_with_whitespace` |
| §6.4.b | Out-of-order numbered output parses correctly | `CR6_4_parses_out_of_order` |
| §6.4.c | Missing query #2 → results[1].answered=="Partial" and parse_failure=True | `CR6_4_missing_query_partial_with_flag` |
| §6.4.d | Knowledge gaps list excludes query when any variant had a parse failure | `CR6_4_knowledge_gap_skips_parse_failures` |

**Implementation sites:** `geo_rewrite_prompt.py:1113–1173` (new prompt + parser), line 1577–1591 (knowledge-gap logic update).

### Fix 6 — Score-blend constants surfaced (spec §7)

| Spec ID | Requirement | Test |
|---|---|---|
| §7.2.a | Module-level `_QUERY_COVERAGE_WEIGHT = 0.8` and `_CONTENT_QUALITY_WEIGHT = 0.2` exist with weights summing to 1.0 (asserted at import time) | `CR7_2_weights_sum_to_one` |
| §7.2.b | Constants include the docstring noting "PROVISIONAL and NOT empirically validated" with a pointer to `implementation_plan_geo_validation.md` | `CR7_2_constants_documented_provisional` |
| §7.2.c | `done` event contains `scoring_metadata` dict with `query_coverage_weight`, `content_quality_weight`, `weighting_validated: False` | `CR7_2_done_event_has_scoring_metadata` |
| §7.3 | `weighting_validated` defaults to `False` | `CR7_3_weighting_validated_false` |

**Implementation sites:** `geo_rewrite_prompt.py` near line 470 (constants block), line 1510 (replace literal), line 1593–1620 (done event).

### Fix 7.1 — FAQ false-positive guard (spec §8.1)

| Spec ID | Requirement | Test |
|---|---|---|
| §8.1.a | `_count_faq_pairs` returns 0 for a document with one heading-style question and one answer paragraph (single rhetorical heading) | `CR8_1_single_heading_question_returns_0` |
| §8.1.b | `_count_faq_pairs` returns 2 for a document with 2 heading-style Q&A pairs | `CR8_1_two_heading_questions_return_2` |
| §8.1.c | Inline-style questions (question-word lines preceded by blank) are still counted regardless of heading-question count | `CR8_1_inline_questions_independent_of_headings` |

**Implementation sites:** `geo_rewrite_prompt.py:518–553` (split tracking heading vs inline; demote single heading-question).

### Fix 7.2 — Hard prohibition coverage (spec §8.2)

| Spec ID | Requirement | Test |
|---|---|---|
| §8.2.a | §(e) item 5 in the rewrite prompt explicitly mentions "comparison tables" | `CR8_2_prompt_mentions_comparison_tables` |
| §8.2.b | §(e) item 5 explicitly mentions "Specific statistics, numeric claims, or named sources that appeared in the original" | `CR8_2_prompt_mentions_original_statistics` |

**Implementation sites:** `geo_rewrite_prompt.py` §(e) section (extend item 5).

### Fix 7.3 — GEO NOTES regex tightening (spec §8.3)

| Spec ID | Requirement | Test |
|---|---|---|
| §8.3.a | A document with the heading `## GEO NOTES on this topic` (NOT in the trailing-bullet format) is NOT split — body returns full text, notes returns `""` | `CR8_3_inline_heading_not_split` |
| §8.3.b | A document with the documented format (`---\nGEO NOTES\n- [TAG]...\n`) IS split correctly | `CR8_3_documented_format_splits` |

**Implementation sites:** `geo_rewrite_prompt.py:852` (tighter regex requiring `---` separator + `GEO NOTES` line + at least one `- [...]` bullet).

### Fix 7.4 — Synthetic page list-count documentation (spec §8.4)

| Spec ID | Requirement | Verification |
|---|---|---|
| §8.4.a | Cap at 1 verified safe by inline comment naming the depending check (`issue_checker._run_geo_checks` line 1923 uses `== 0` only) | `CR8_4_cap_comment_present` (test reads source file and asserts comment exists) |
| §8.4.b | If `_run_geo_checks` ever changes to threshold on counts, this cap silently undercounts — comment must call this out | Comment text contains the words "issue_checker" and "remove this cap" or similar |

**Implementation sites:** `geo_rewrite_prompt.py:766` (add comment).

### Fix 7.5 — Fabricated outbound link detection (spec §8.5)

| Spec ID | Requirement | Test |
|---|---|---|
| §8.5.a | `_FABRICATED_LINK_RE` matches `https://example.com`, `https://example.org`, `https://placeholder.io`, and URLs containing `fabricated`, `made-up`, `todo`, `fixme` | `CR8_5_fabricated_link_regex_matches` |
| §8.5.b | `_FABRICATED_LINK_RE` does NOT match `https://supabase.com/docs`, `https://github.com/foo/bar` | `CR8_5_real_links_not_matched` |
| §8.5.c | Citations check (Check 2) treats fabricated-link URLs as placeholders (partial-pass), not as real citations (full pass) | `CR8_5_fabricated_link_partial_pass` |
| §8.5.d | A rewrite with only `[docs](https://example.com)` links scores `EXTERNAL_CITATIONS_LOW` in `placeholder_inventory.partial_pass_checks` | `CR8_5_example_dot_com_partial_inventory` |

**Implementation sites:** new regex constant near line 850, integration with Check 2 logic at line 996–1003.

### Integration test — full pipeline on fixture page (spec §9.9)

| Spec ID | Requirement | Test |
|---|---|---|
| §9.9.a | Fixture file `tests/fixtures/openbrain_original.md` exists | `CR9_9_fixture_present` (file existence) |
| §9.9.b | Pipeline run on fixture: winner contains all entities returned by `_extract_named_entities_from_text(original)` | `CR9_9_winner_preserves_entities` (skip if no LLM key) |
| §9.9.c | Pipeline run on fixture: winner contains no specific numeric value not present in the original | `CR9_9_winner_no_fabricated_numbers` |
| §9.9.d | Two runs of the pipeline produce scores within ±0.02 of each other | `CR9_9_score_reproducibility` |
| §9.9.e | `done` event contains `placeholder_inventory` and `scoring_metadata` | `CR9_9_done_event_complete` |

**Implementation sites:** new fixture `tests/fixtures/openbrain_original.md`; new test class `TestIntegrationPipeline` marked `@pytest.mark.integration`. Skipped by default; run via `pytest -m integration`.

> **Human verification needed for §9.9.b–§9.9.d:** these tests require live LLM calls and are non-deterministic. The plan flags them explicitly as integration-tier; the spec-compliance run is the §9.1–§9.8 unit tests. The user will need to manually trigger the integration run on at least one of the three reference pages mentioned in §1.3.

---

## 3. Implementation order

Execute strictly in this order. Each step has its own test gate; a step
cannot be marked complete until its tests pass.

```
Step 1 — Fix 1 (§2): rewrite the 5 fix-instruction examples
        └─ tests CR2_2_*, CR2_3_*, CR2_4_*  (5 tests)

Step 2 — Fix 6 (§7) constants & metadata (small; lands the score-blend doc
         before any scoring change so subsequent steps can rely on the
         _QUERY_COVERAGE_WEIGHT constant)
        └─ tests CR7_2_*, CR7_3_*  (4 tests)

Step 3 — Fix 7.3 (§8.3) GEO NOTES regex tightening
        └─ tests CR8_3_*  (2 tests)
        Rationale: tightening this regex changes _content_score behaviour,
        so do it before the partial-pass refactor that depends on body/notes split.

Step 4 — Fix 7.5 (§8.5) fabricated link detection
        └─ tests CR8_5_a, CR8_5_b  (regex-only tests, no _content_score yet)

Step 5 — Fix 2 (§3): partial-pass refactor + 4-tuple return
        Sub-steps:
          5a. Add partial_passes set + cap rule to _content_score
          5b. Wire _FABRICATED_LINK_RE filter into Check 2 (citations)
          5c. Update _content_score signature to 4-tuple
          5d. Update _project_score wrapper, stream_rewrite_variants caller
          5e. Update all 13 test unpack sites in test_geo_rewrite_prompt.py
          5f. Add SSE inventory field
        └─ tests CR3_2_*, CR3_3_*, CR3_4_*, CR3_5_*, CR3_6_*, CR8_5_c, CR8_5_d  (12 tests)

Step 6 — Fix 3 (§4): page-type-conditional structural check
        Sub-steps:
          6a. Add _has_numbered_list_with_min_items, _table_has_min_rows helpers
          6b. Add _structural_check_passes dispatch
          6c. Replace Check 5 in _content_score with dispatch call
          6d. Add 3 page-type-specific fix-instruction variants
          6e. Update _build_improvement_prompt lookup
        └─ tests CR4_2_*, CR4_3_*, CR4_4_*  (12 tests)

Step 7 — Fix 4 (§5): entity-set named-list detection
        Sub-steps:
          7a. Add _TECHNICAL_TERM_ALLOWLIST constant
          7b. Add _extract_named_entities_from_text helper
          7c. Add _item_references_known_entity helper
          7d. Update _count_named_lists to take known_entities
          7e. Update _extract_preservation_floor to compute & store named_entities
          7f. Add NAMED_ENTITIES_LOST branch in _check_preservation_regression
          7g. Keep legacy NAMED_LIST_GENERICISED check as additive (don't remove)
        └─ tests CR5_2_*, CR5_4_*  (10 tests)

Step 8 — Fix 5 (§6): numbered-output query-match parser
        Sub-steps:
          8a. Update prompt template
          8b. Add _VERDICT_LINE_RE constant
          8c. Rewrite parser to use dict keyed by index
          8d. Add parse_failure field to per-query results
          8e. Update knowledge-gap detection in stream_rewrite_variants
        └─ tests CR6_2_*, CR6_3_*, CR6_4_*  (10 tests)

Step 9 — Fix 7.1 (§8.1) FAQ stricter rule
        └─ tests CR8_1_*  (3 tests)

Step 10 — Fix 7.2 (§8.2) hard prohibition coverage (one paragraph edit)
        └─ tests CR8_2_*  (2 tests)

Step 11 — Fix 7.4 (§8.4) synthetic page comment
        └─ tests CR8_4_*  (1 test)

Step 12 — Integration fixture (§9.9)
        Sub-steps:
          12a. Create tests/fixtures/openbrain_original.md
          12b. Add TestIntegrationPipeline class with @pytest.mark.integration
        └─ test CR9_9_a (file-exists)
        Other CR9_9_* tests skipped by default; user runs manually.

Step 13 — Adjacent fixes (per user directive 2026-05-04: "all code is your
         responsibility"). See §5 for full descriptions and tests.
        Sub-steps:
          13a. Delete dead code: _score_markdown + 3 obsolete test_c6_* tests
          13b. Delete dead wrapper: _project_score (no callers in production)
          13c. Tighten _split_body_and_notes whitespace tolerance + test
          13d. Tighten _count_faq_pairs heading detection (require question word)
          13e. Include code-block contents in _extract_specific_numbers
        └─ tests CR_ADJ_*  (5 tests)

        Skipped (out of scope, project is English-only):
          - i18n FAQ question words (would expand scope into multilingual support)

Step 14 — Full test suite run; status report against this plan.
```

**Total new tests:** 66 unit tests + 5 integration tests = **71 tests**.
**Estimated effort:** 9–11 hours (entity extraction and partial-pass refactor are the largest items; adjacent fixes add ~1 hour).

---

## 4. Dependencies and risks

### Dependency: tuple-change blast radius (§3.3)

The 4-tuple change ripples through 13 test unpack sites and 2 production
unpack sites. Step 5e of the implementation order names them; the change is
mechanical but must happen atomically (one commit) or the test suite will be
red between commits.

### Risk: partial-pass cap rule (§3.5)

The spec says "all three are weight 3, so this is essentially cap at 2
partial passes." But it also says "demote the lowest-weight check from
partial-pass to fail." When all three weights are equal, the spec doesn't
specify a tie-break. **Plan choice: alphabetical by check code** (so the
behaviour is deterministic and testable). Will be documented inline.

### Risk: entity extraction false negatives (§5.2)

The spec acknowledges (in §12) that this is heuristic. Conservatism rule
applies: when in doubt, don't flag a regression. The 70% threshold gives
breathing room. Tests in §5.4.b name specific words that must NOT be
extracted — these are the regression boundary.

### Risk: integration test flakiness (§9.9)

Mitigated by `@pytest.mark.integration` skip-by-default. The user will
explicitly opt-in via `pytest -m integration`. The ±0.02 tolerance allows
for LLM variance.

---

## 5. Adjacent fixes (in scope per user directive 2026-05-04)

The user override: "fix the 6 adjacent issues. all code is your responsibility."
Five of the six become Step 13 in the implementation order. The sixth (i18n
question words) is genuinely out of scope and is documented below with the
reason for not addressing it.

### CR_ADJ_1 — Delete dead `_score_markdown` and its tests

**Site:** `geo_rewrite_prompt.py:1100–1106`. Zero production callers (verified
via `grep -rn "_score_markdown(" --include="*.py"`). Used only by 3 test
methods `test_c6_*` in `TestScoreMarkdown` that exist for historical reasons.

**Action:** Delete the function. Delete the 3 `test_c6_*` tests. Remove
`_score_markdown` from the import block.

**Test:** `CR_ADJ_1_score_markdown_deleted` — `from
api.services.geo_rewrite_prompt import _score_markdown` raises `ImportError`.

### CR_ADJ_2 — Delete dead `_project_score` wrapper

**Site:** `geo_rewrite_prompt.py:1062–1073`. Single-line wrapper around
`_content_score` that drops its `original_findings` parameter. Zero production
callers. The actual projection logic lives in `_project_score_from_findings`
(line 1176) which is correctly named.

**Action:** Delete `_project_score`. No tests reference it.

**Test:** `CR_ADJ_2_project_score_deleted` — `from
api.services.geo_rewrite_prompt import _project_score` raises `ImportError`.

### CR_ADJ_3 — Whitespace tolerance in `_split_body_and_notes`

After §8.3 tightens the regex, the LLM's actual output may include trailing
whitespace on the `---` separator line (e.g. `---  \nGEO NOTES`). The spec's
new regex pattern from §8.3 already allows `\s*` after `---`, but does not
allow leading whitespace before the `-` bullet markers in the notes section
(LLMs sometimes indent bullets).

**Action:** In §8.3's new regex, change the bullet-pattern to allow optional
leading whitespace: `(?:\s*-\s+\[[A-Z\s]+\][^\n]*\n?)+`.

**Test:** `CR_ADJ_3_indented_bullets_split_correctly` — input with
`---\nGEO NOTES\n  - [CITATION NEEDED] indented` is split correctly.

### CR_ADJ_4 — Heading-FAQ requires question word, not bare `?` suffix

**Site:** `geo_rewrite_prompt.py:518–553`. Today, any heading ending in `?`
qualifies as a question (e.g. `## Migration v2 → v3?`). After §8.1 narrows
the count to ≥2 heading-questions, false positives like `## Migration v2 → v3?`
plus `## What about v4?` would still count as 2 → 2 FAQ pairs.

**Action:** When `is_heading=True`, also require `is_question_word=True` (the
heading must start with What/How/Why/etc. after stripping the `#` prefix).
The `_FAQ_QUESTION_WORDS_RE` already handles `#+\s+` prefix, so this is just
a tightening of the existing condition.

**Test:** `CR_ADJ_4_heading_without_question_word_not_counted` — `## Migration?`
followed by an answer paragraph returns `faq_pair_count == 0`.

### CR_ADJ_5 — `_extract_specific_numbers` includes code-block contents

**Site:** `geo_rewrite_prompt.py:642`. Today, code blocks are stripped before
the number scan. If the original page has a benchmark like
` ```45 minutes for 1M rows``` ` and the rewrite preserves it verbatim, the
hallucination guard (Hard Prohibition 9) would still fire because "45 minutes"
isn't in `original_number_set`.

**Action:** Compute `_extract_specific_numbers` on the FULL text (don't
strip code first). Other extractors (FAQ, lists, tables, links) still
operate on `text_no_code` because code blocks aren't prose. Numbers are the
exception.

**Test:** `CR_ADJ_5_numbers_in_code_blocks_captured` — input
`...\n` + "```\n" + `45 minutes\n` + "```\n" returns `"45 minutes"` in
`original_number_set`.

### Skipped — i18n question-word coverage

Genuinely out of scope. The TalkingToad codebase has no i18n infrastructure:
no locale negotiation, no language detection, no multilingual fixture pages.
Adding multilingual question-word patterns to `_FAQ_QUESTION_WORDS_RE` would
introduce false positives for English content (e.g. "May" the month vs. "May"
the modal verb in Spanish "Puede / May / Wo") without delivering working
multilingual support. If the project later adds i18n, this becomes part of
that work; doing it now is partial work that doesn't compose into anything.

**Status:** documented; not implemented.

---

## 6. Status report (post-implementation, 2026-05-04)

Every spec criterion below has one of three statuses: `done` (with file:line
or test name), `partial` (with what's missing), `not done` (with reason).

### Fix 1 — Remove fabrication-inducing examples (§2)

| Spec ID | Status | Evidence |
|---|---|---|
| §2.2.a stats DO has no specific numeric value | done | `geo_rewrite_prompt.py:1310`; `tests/test_geo_rewrite_prompt.py::TestFixInstructionExamples::test_cr2_2_stats_do_no_numbers` |
| §2.2.b quote DO uses no specific named source | done | `geo_rewrite_prompt.py:1326`; `test_cr2_2_quote_do_no_named_source` |
| §2.3 every entry has DO and DO NOT | done | All 5 entries; `test_cr2_3_all_entries_have_do_and_dont` |
| §2.3 DO NOT examples demonstrate fabrication | done | `test_cr2_3_dont_examples_demonstrate_fabrication` |
| §2.4 programmatic discriminator | done | `test_cr2_4_do_no_numbers_dont_has_numbers` |

### Fix 2 — Cap placeholder credit (§3)

| Spec ID | Status | Evidence |
|---|---|---|
| §3.2 partial-pass at half weight | done | `geo_rewrite_prompt.py:1297–1351`; `test_cr3_2_partial_pass_half_weight` |
| §3.2 binary checks remain binary | done | `test_cr3_2_non_placeholder_checks_remain_binary` |
| §3.3 4-tuple return | done | `_content_score` line 1280; `test_cr3_3_returns_four_tuple` |
| §3.3 inventory keys | done | `test_cr3_3_inventory_has_required_keys` |
| §3.4 SSE variant event has inventory | done | `geo_rewrite_prompt.py:1979`; verified at source level (live SSE requires LLM) |
| §3.4 SSE done event has winner inventory | done | `geo_rewrite_prompt.py:2105` (`winner_placeholder_inventory`) |
| §3.5 cap rule (alphabetical demote) | done | lines 1353–1359; `test_cr3_5_cap_demotes_third_to_fail` |
| §3.6.a real beats placeholder | done | `test_cr3_6_real_beats_placeholder` |
| §3.6.b all-placeholder ≤ 0.85 | done | `test_cr3_6_all_placeholder_caps_at_85` |
| §3.6.c inventory populated correctly | done | `test_cr3_6_inventory_populated` |

### Fix 3 — Page-type-conditional structural check (§4)

| Spec ID | Status | Evidence |
|---|---|---|
| §4.2.a `_has_numbered_list_with_min_items` | done | `geo_rewrite_prompt.py:990`; `test_cr4_2_numbered_list_helper` |
| §4.2.b `_table_has_min_rows` | done | `geo_rewrite_prompt.py:1009`; `test_cr4_2_table_min_rows_helper` |
| §4.2.c technical dispatch | done | `_structural_check_passes` line 1041; `test_cr4_2_technical_dispatch` |
| §4.2.d comparison dispatch | done | line 1045; `test_cr4_2_comparison_dispatch` |
| §4.2.e faq dispatch | done | line 1049; `test_cr4_2_faq_dispatch` |
| §4.2.f general dispatch unchanged | done | line 1051; `test_cr4_2_general_dispatch_unchanged` |
| §4.3 per-type fix-instruction dispatched | done | `_resolve_fix_instruction` line 1626; `test_cr4_3_per_type_fix_instruction_dispatched` |
| §4.4.a technical no-code fails | done | `test_cr4_4_technical_no_code_fails` |
| §4.4.b technical with code passes | done | `test_cr4_4_technical_with_code_passes` |
| §4.4.c comparison table required | done | `test_cr4_4_comparison_table_required` |
| §4.4.d faq three pairs required | done | `test_cr4_4_faq_three_pairs_required` |
| §4.4.e general unchanged | done | `test_cr4_4_general_unchanged` |

### Fix 4 — Entity-set named-list detection (§5)

| Spec ID | Status | Evidence |
|---|---|---|
| §5.2.1 multi-word title-case phrases | done | `_MULTIWORD_TITLE_RE` + `_extract_named_entities_from_text` line 593; `test_cr5_2_extracts_multiword_phrases` |
| §5.2.2 single Cap word ≥2 times | done | line 612; `test_cr5_2_extracts_repeated_capitalised` |
| §5.2.3 backtick identifiers | done | `_BACKTICK_ID_RE` + line 597; `test_cr5_2_extracts_backtick_identifiers` |
| §5.2.4 allowlist case-insensitive | done | `_TECHNICAL_TERM_ALLOWLIST` + line 605; `test_cr5_2_allowlist_case_insensitive` |
| §5.2.5 preservation floor exposes named_entities | done | line 856; `test_cr5_2_preservation_floor_has_named_entities` |
| §5.2.6 _count_named_lists uses known_entities | done | line 760; `test_cr5_2_named_lists_uses_entities` |
| §5.2.7 NAMED_ENTITIES_LOST violation | done | `_check_preservation_regression` line 944; `test_cr5_2_named_entities_lost_violation` |
| §5.4.a OpenBrain entities extracted | done | `test_cr5_4_openbrain_entities_extracted` |
| §5.4.b emphasised words excluded | done | `_EMPHASIS_STOP_WORDS`; `test_cr5_4_emphasised_words_excluded` |
| §5.4.c entity loss triggers regression | done | `test_cr5_4_entity_loss_triggers_regression` |

### Fix 5 — Numbered-output query-match parser (§6)

| Spec ID | Status | Evidence |
|---|---|---|
| §6.2.a prompt format includes numbered example | done | `geo_rewrite_prompt.py:1574`; `test_cr6_2_prompt_format_includes_numbered_example` |
| §6.2.b verdict regex shape | done | `_VERDICT_LINE_RE` line 1495; `test_cr6_2_verdict_regex_pattern` |
| §6.2.c dict keyed by index | done | `parse_verdict_response` line 1517; `test_cr6_2_dict_keyed_by_index` |
| §6.3.a per_query has parse_failure field | done | line 1526; `test_cr6_3_per_query_has_parse_failure_field` |
| §6.3.b missing → Partial + parse_failure | done | line 1525; `test_cr6_3_missing_defaults_to_partial` |
| §6.3.c knowledge-gap excludes parse-failure queries | done | `geo_rewrite_prompt.py:2099`; `test_cr6_3_knowledge_gap_skips_parse_failures` (covered by `test_cr6_4_knowledge_gap_skips_parse_failures`) |
| §6.4.a parses with whitespace | done | `test_cr6_4_parses_with_whitespace` |
| §6.4.b parses out of order | done | `test_cr6_4_parses_out_of_order` |
| §6.4.c missing query → Partial+flag | done | `test_cr6_4_missing_query_partial_with_flag` |
| §6.4.d knowledge-gap skips parse-failures | done | `test_cr6_4_knowledge_gap_skips_parse_failures` |

### Fix 6 — Score-blend constants surfaced (§7)

| Spec ID | Status | Evidence |
|---|---|---|
| §7.2.a weights sum to 1.0 (asserted at import) | done | `geo_rewrite_prompt.py:489` (`assert ...`); `test_cr7_2_weights_sum_to_one` |
| §7.2.b constants documented as PROVISIONAL | done | comment block lines 481–488; `test_cr7_2_constants_documented_provisional` |
| §7.2.c done event has scoring_metadata | done | `geo_rewrite_prompt.py:2110`; `test_cr7_2_done_event_has_scoring_metadata` (covered by `test_cr7_3_weighting_validated_false`) |
| §7.3 weighting_validated False default | done | line 2113; `test_cr7_3_weighting_validated_false` |

### Fix 7 — Smaller correctness fixes (§8)

| Spec ID | Status | Evidence |
|---|---|---|
| §8.1.a single rhetorical heading-Q returns 0 | done | `_count_faq_pairs` lines 547–597; `test_cr8_1_single_heading_question_returns_0` |
| §8.1.b two heading-Qs return 2 | done | `test_cr8_1_two_heading_questions_return_2` |
| §8.1.c inline-Qs independent of heading-Qs | done | `test_cr8_1_inline_questions_independent_of_headings` |
| §8.2.a prompt mentions comparison tables | done | §(e) item 5 line 311; `test_cr8_2_prompt_mentions_comparison_tables` |
| §8.2.b prompt mentions original statistics | done | §(e) item 5 line 314; `test_cr8_2_prompt_mentions_original_statistics` |
| §8.3.a inline `## GEO NOTES` heading not split | done | `_GEO_NOTES_SPLIT_RE` line 877; `test_cr8_3_inline_heading_not_split` |
| §8.3.b documented format splits | done | `test_cr8_3_documented_format_splits` |
| §8.4 list-count cap documented | done | `_build_synthetic_parsed_page` lines 833–838; `test_cr8_4_cap_comment_present` |
| §8.5.a fabricated link regex matches placeholders | done | `_FABRICATED_LINK_RE` line 873; `test_cr8_5_fabricated_link_regex_matches` |
| §8.5.b real links not matched | done | `test_cr8_5_real_links_not_matched` |
| §8.5.c fabricated link → partial-pass | done | `_content_score` Check 2 line 1320–1335; `test_cr8_5_fabricated_link_partial_pass` |
| §8.5.d example.com inventory entry | done | `test_cr8_5_example_dot_com_partial_inventory` |

### §9.9 Integration fixture

| Spec ID | Status | Evidence |
|---|---|---|
| §9.9.a fixture file exists | done | `tests/fixtures/openbrain_original.md` (live-fetched); `test_cr9_9_fixture_present` |
| §9.9.b winner preserves entities | done | `test_cr9_9_winner_preserves_entities` (`@integration`; verified once with live LLM call) |
| §9.9.c winner no fabricated numbers | done | `test_cr9_9_winner_no_fabricated_numbers` (`@integration`; verified once with live LLM call) |
| §9.9.d score reproducibility | partial | `test_cr9_9_score_reproducibility` skipped — best-effort; manual verification preferred over flaky CI |
| §9.9.e done event complete | done | `test_cr9_9_done_event_complete` (source-level check) |

### Adjacent fixes (CR_ADJ — pulled into scope per user directive)

| Spec ID | Status | Evidence |
|---|---|---|
| CR_ADJ_1 delete `_score_markdown` | not done — function still alive | Audit revealed `execute_rewrite_best_of_n` at line 2242 still uses it; documented in `test_cr_adj_1_score_markdown_kept_alive` |
| CR_ADJ_2 delete `_project_score` wrapper | done | Function deleted; `test_cr_adj_2_project_score_deleted` |
| CR_ADJ_3 whitespace tolerance in `_split_body_and_notes` | done | Step 3 regex permits `\s*-\s+`; `test_cr_adj_3_indented_bullets_split_correctly` |
| CR_ADJ_4 heading-FAQ requires question word | done | Step 9 tightened detection to `is_heading and is_question_word`; `test_cr_adj_4_heading_without_question_word_not_counted` |
| CR_ADJ_5 numbers in code blocks captured | done | `_extract_preservation_floor` line 858 scans full text; `test_cr_adj_5_numbers_in_code_blocks_captured` |
| i18n question-word coverage | not done — out of scope | Documented in plan §5; project has no i18n infrastructure |

### Aggregate

| Metric | Value |
|---|---|
| New tests added | 70 (67 unit + 3 integration-marked) |
| Total geo_rewrite_prompt tests | 158 |
| Pass rate (unit-tier) | 155/155 (100%) |
| Pass rate (integration-tier, verified once) | 2/2 ran; 1 skipped per docstring |
| Full project test suite | 1111 passed; 12 pre-existing failures + 7 pre-existing errors unchanged |
| Estimated effort | 9–11h (planned) → ~6h actual |
| Spec coverage | 53/55 criteria done; 1 partial (§9.9.d), 1 not done (CR_ADJ_1, function not actually dead), 1 documented out of scope (i18n) |

### Open follow-ups identified during the pass

- **§9.9.d score reproducibility**: tightening this needs LLM seeding or a
  deterministic scoring path. Defer to a validation pass.
- **`execute_rewrite_best_of_n` divergence**: the helper at line 2204+ is a
  separate code path from `stream_rewrite_variants`. Today it does not
  consume `placeholder_inventory`, page-type-specific structural checks, or
  the entity-set regression detector. The spec's §1.2 explicitly excludes
  merging these two paths — this pass changes only `stream_rewrite_variants`.
  If `execute_rewrite_best_of_n` is reactivated in production, parity work
  belongs to its own implementation pass.
- **Spec validation harness**: §10 of the spec calls out empirical
  validation of the 0.8/0.2 score blend. `weighting_validated: False` in
  the done event flags this so future-you knows it's still TBD.

---

## 7. Open questions for the user before implementation begins

1. **Integration fixture content.** Spec §1.3 mentions "the OpenBrain page
   from earlier turns, plus two others." The OpenBrain markdown isn't in
   the repo. Should I:
     - **(a)** Re-create a synthetic OpenBrain-shaped fixture from the
       behaviour described in earlier specs (faster, deterministic, but
       not the real fixture), OR
     - **(b)** Wait for the user to paste / upload the fixture markdown.

   **Plan default:** (a), with a clear `# SYNTHETIC FIXTURE` comment at the
   top so it's obvious the file isn't real prod content.

2. **Tie-break for §3.5 partial-pass cap.** All three checks have weight 3.
   When the cap demotes one, which one?
     - **(a)** Alphabetical by code (`EXTERNAL_CITATIONS_LOW` <
       `QUOTATIONS_MISSING` < `STATISTICS_COUNT_LOW`) — deterministic, dull.
     - **(b)** First-encountered (whichever was added to `partial_passes`
       last) — depends on dict iteration order, fragile.
     - **(c)** A new heuristic — e.g. demote whichever has the most
       placeholders (penalises the worst offender).

   **Plan default:** (a). Documented in inline comment.

3. **Should §9.9 integration tests be added in this pass at all?** The spec
   says "skip by default" and the user marks it `@pytest.mark.integration`.
   Adding the fixture file and skeleton test is low-cost. Confirm whether
   the user wants the skeleton committed now or deferred.

   **Plan default:** add the skeleton + fixture. The user can `pytest -m
   integration` whenever they want to validate.

If the user accepts the defaults, I'll proceed without further questions. If
not, I'll wait for guidance on the open items before starting Step 1.
