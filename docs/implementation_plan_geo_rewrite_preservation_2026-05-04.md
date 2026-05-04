# GEO Rewrite Preservation Floor — Implementation Plan

**Date:** 2026-05-04  
**Scope:** Fix the rewrite pipeline's content-stripping failure mode  
**Status:** Planning — awaiting user approval before any code changes

---

## Problem Statement

The current rewrite pipeline optimises for structural tidiness rather than extractable specificity.
It strips high-value elements (FAQ sections, named tool lists, comparison tables, code blocks,
outbound citations) because:

1. **§(j) QUERY DISTRIBUTION explicitly bans standalone FAQ sections.**
2. **§(i) limits bullet lists to 2 per 500 words** — causes list stripping on dense pages.
3. **`generate_rewrite_prompt` never receives the original content**, so it cannot tell the
   LLM which specific elements exist and must be preserved.
4. **The scorer has no regression detection** — a rewrite that removes an FAQ section and
   a comparison table can score higher than the original.
5. **The hallucination guard for numbers is absent** — the LLM can invent "45 minutes"
   or "73% of users" when no such figure appeared in the original.

---

## Root Cause: Architectural Gap

`generate_rewrite_prompt(report, page_type, url)` receives a GEO **report** (audit scores) but
not the original **content** (text of the page). Without the content it cannot:

- List the specific FAQ pairs that must be preserved
- Count the code blocks that must not be removed  
- Name the outbound links that must survive
- Set a floor on table count

The fix is twofold: (a) extract a "preservation floor" from the original content before
the prompt is built, and (b) inject page-specific preservation rules into the prompt.

---

## Acceptance Criteria

### RP1 — Preservation Floor Extractor

**RP1.1** `_extract_preservation_floor(text: str) -> dict` exists in
`api/services/geo_rewrite_prompt.py` and returns a dict with at least these keys:
`faq_pair_count`, `named_list_count`, `code_block_count`, `table_count`,
`outbound_link_count`, `original_number_set` (frozenset of specific numbers
found: integers ≥ 2, decimals, percentages, durations).

**RP1.2** FAQ detection: a pair is counted when a line ending in `?` is followed
within 3 lines by a non-empty answer line. Six Q&A blocks on a test page must
return `faq_pair_count == 6`. A prose-only page must return 0.

**RP1.3** Named list detection: a bullet list is "named" when ≥ 2 of its items
contain a proper noun (capitalised word not at sentence start) or a quoted string.
A page with 2 named bullet lists must return `named_list_count == 2`.

**RP1.4** Code block detection: counts fenced ` ```...``` ` blocks. A page with
3 code blocks must return `code_block_count == 3`.

**RP1.5** Table detection: counts distinct Markdown table blocks (minimum 2
separator rows). A page with 1 table returns `table_count == 1`.

**RP1.6** Outbound link detection: counts `[text](https://...)` links where the
domain is external (not relative `/path` and not the same origin when a `url`
hint is available). A page with 2 external links returns `outbound_link_count == 2`.

**RP1.7** Number extraction: `original_number_set` contains all integers ≥ 2,
decimal numbers, percentages (`45%`), and durations (e.g. `"45 minutes"`).
A fabricated number not in the original will not be in this set.

---

### RP2 — Preservation Floor Prompt Section

**RP2.1** `generate_rewrite_prompt` gains an `original_content: str | None = None`
parameter. When provided and non-empty, `_extract_preservation_floor` is called
and the results are injected as **§(k) PRESERVATION FLOOR** in the system prompt.

**RP2.2** When `faq_pair_count >= 2`, §(k) lists the detected FAQ pairs by their
question text and states: _"FAILURE CONDITION: The rewrite must contain at least
[N] Q&A pairs. Fewer is a failing rewrite."_

**RP2.3** When `code_block_count >= 1`, §(k) states: _"This page has [N] code
block(s). Preserve all of them. Do NOT remove code blocks."_

**RP2.4** When `table_count >= 1`, §(k) states: _"This page has [N] table(s).
Preserve or improve all of them. A comparison table that lists named alternatives
(competing products, platforms, tools) must survive unchanged."_

**RP2.5** When `outbound_link_count >= 1`, §(k) states: _"This page has [N]
outbound citation link(s). Every one must appear in the rewrite. If a real URL
cannot be included, replace it with `[SOURCE NEEDED: describe source type]`."_

**RP2.6** When `named_list_count >= 1`, §(k) states: _"This page contains [N]
named bullet list(s) with specific tool/product/platform names. The specific
names must be preserved — do not replace them with generic terms."_

**RP2.7** The §(k) section appears **after §(j)** so it overrides any conflicting
style guidance. It is the highest-priority section in the prompt.

---

### RP3 — Prompt Bug Fixes

**RP3.1** §(j) QUERY DISTRIBUTION no longer contains the text _"Do NOT write a
standalone FAQ section"_. The replacement reads: _"If the original page has a FAQ
section, **preserve it and expand it if needed**. Do not fold FAQ content into
prose sections — the Q&A format is the strongest AI-retrievable structure."_

**RP3.2** §(i) STYLE CONSTRAINTS no longer contains the rule _"No more than 2
bullet lists per 500 words"_. Lists are a positive GEO signal, not a noise signal.
The replacement reads: _"Do not pad content with meaningless bullet lists. Every
list item must state a specific fact, name, or step."_

**RP3.3** A hallucination guard is added to §(e) HARD PROHIBITIONS as item 9:
_"Do NOT introduce specific numbers (durations such as '45 minutes', percentages,
survey results, user counts) that did not appear in the original text. Use
`[STATISTIC NEEDED: describe figure type]` as a placeholder."_

**RP3.4** §(e) item 5 is strengthened from _"do not remove substantive information"_
to: _"Do not remove any of the following from the original: FAQ Q&A pairs, code
blocks, tables, named example lists (lists containing specific tool or product
names), or outbound citation links."_ This makes the prohibition concrete rather
than abstract.

---

### RP4 — Regression Detection in Scorer

**RP4.1** `_check_preservation_regression(original_features: dict, rewrite_text: str)
-> list[str]` exists in `geo_rewrite_prompt.py`. It returns one violation string
per failing check. Empty list means no regression.

**RP4.2** Violations detected by RP4.1:
- `"FAQ_REMOVED"` — `original_features["faq_pair_count"] >= 2` but rewrite has
  fewer than `floor(original * 0.7)` FAQ pairs (tolerates minor structural reshaping).
- `"CODE_BLOCK_REMOVED"` — original had ≥1 code block, rewrite has 0.
- `"TABLE_REMOVED"` — original had ≥1 table, rewrite has 0.
- `"OUTBOUND_LINK_REMOVED"` — original had ≥2 outbound links, rewrite has 0.
- `"NAMED_LIST_GENERICISED"` — original had ≥1 named list, rewrite has 0
  (all lists are now generic without proper nouns).

**RP4.3** `_content_score(url, content, page_type, original_features=None)` gains
an `original_features` keyword argument. When provided and non-None,
`_check_preservation_regression` is called. Each violation adds 1 to the
fail count and appends the violation code to the `fails` set.
The denominator grows by 1 for each violation checked.
This keeps monotonicity: more violations → strictly lower score.

**RP4.4** `stream_rewrite_variants` computes `original_features` once before the
loop (by calling `_extract_preservation_floor(page_content)`) and passes it to
every `_content_score` call inside the loop.

**RP4.5** When a variant's `per_query_results` or content score reveals
preservation regressions, the `_build_improvement_prompt` for the **next** try
includes a `[REGRESSIONS TO FIX]` section listing each violation with explicit
instructions (e.g. "Try #2 removed the FAQ section. Restore all Q&A pairs.").

**RP4.6** The SSE `variant` event includes a `regressions` field (list of
violation codes). The SSE `done` event includes `regressions` on each variant
summary so the UI can show which variants regressed.

---

### RP5 — Caller API Updates

**RP5.1** The `/api/ai/geo-rewrite-prompt` endpoint passes `page_content` (already
available via the job's crawl data) as `original_content` to `generate_rewrite_prompt`.

**RP5.2** The `/api/ai/geo-rewrite` endpoint does the same (it already has
`page_content`; it must pass it to `generate_rewrite_prompt`).

**RP5.3** The `/api/ai/geo-rewrite-stream` endpoint does the same.

---

### RP6 — Tests

All tests live in `tests/test_geo_rewrite_prompt.py`, class `TestPreservationFloor`.

| Test ID | Description | Pass condition |
|---------|-------------|----------------|
| RP6.1 | `test_rp1a_faq_counts_six_pairs` | `_extract_preservation_floor(text_with_6_faqs)["faq_pair_count"] == 6` |
| RP6.2 | `test_rp1b_faq_zero_in_prose` | Prose page returns `faq_pair_count == 0` |
| RP6.3 | `test_rp1c_faq_adversarial_question_in_prose` | Paragraph ending in `?` without following answer line does not count |
| RP6.4 | `test_rp1d_code_block_count` | Page with 2 fenced code blocks returns `code_block_count == 2` |
| RP6.5 | `test_rp1e_table_count` | Page with 1 table returns `table_count == 1` |
| RP6.6 | `test_rp1f_outbound_link_count` | Page with 3 `[text](https://...)` links returns `outbound_link_count == 3` |
| RP6.7 | `test_rp1g_named_list_vs_generic` | List with "Supabase, GitHub, Notion" = named; list with "storage, tools, apps" = not named |
| RP6.8 | `test_rp1h_original_number_set` | "45 minutes" and "99.9%" appear in set; "six" (word-form) does not |
| RP6.9 | `test_rp2a_faq_floor_in_prompt` | When original has 6 FAQ pairs, prompt contains "at least 6 Q&A pairs" |
| RP6.10 | `test_rp2b_no_faq_ban_in_prompt` | Prompt does not contain "Do NOT write a standalone FAQ section" |
| RP6.11 | `test_rp2c_no_bullet_limit_in_prompt` | Prompt does not contain "No more than 2 bullet lists" |
| RP6.12 | `test_rp2d_code_floor_in_prompt` | When original has 2 code blocks, prompt contains "2 code block" |
| RP6.13 | `test_rp2e_table_floor_in_prompt` | When original has 1 table, prompt contains "1 table" |
| RP6.14 | `test_rp2f_hallucination_guard_in_prompt` | Prompt contains "Do NOT introduce specific numbers" |
| RP6.15 | `test_rp3a_faq_regression_detected` | Rewrite with 0 FAQ pairs from original with 6 → `["FAQ_REMOVED"]` |
| RP6.16 | `test_rp3b_faq_regression_not_triggered_below_floor` | Rewrite with 5 pairs from original with 6 passes (≥70% floor) |
| RP6.17 | `test_rp3c_code_block_regression_detected` | Rewrite with 0 code blocks from original with 1 → `["CODE_BLOCK_REMOVED"]` |
| RP6.18 | `test_rp3d_table_regression_detected` | Rewrite with 0 tables from original with 1 → `["TABLE_REMOVED"]` |
| RP6.19 | `test_rp3e_no_regression_when_floor_met` | Rewrite meeting all floors → empty list |
| RP6.20 | `test_rp4a_regression_lowers_content_score` | `_content_score(..., original_features=features_with_faq)` on stripped rewrite < same without `original_features` |
| RP6.21 | `test_rp4b_score_monotonicity_with_regressions` | Two regressions → lower score than one regression → lower score than zero |

---

## Adjacent Issues Found — Not Fixed in This Change

1. **`_BEST_OF_N = 5` is a module-level constant** — it should be in a config dict alongside
   other tuneable parameters (like `_GEO_ANALYSIS_LIMITS`). Flag: `geo_rewrite_prompt.py:457`.

2. **`execute_rewrite_best_of_n` is a separate code path** from `stream_rewrite_variants` and
   doesn't share the evolutionary loop or preservation checks. Any fix to `stream_rewrite_variants`
   must be mirrored in `execute_rewrite_best_of_n` or the two should be merged.
   File: `geo_rewrite_prompt.py:1218+`.

3. **The `_detect_page_type` function** classifies "faq" pages but the FAQ-section detection
   in RP1.2 is separate. If the original page is classified as `page_type=faq`, the prompt
   should treat FAQ preservation as mandatory regardless of the floor count. This is not
   explicitly wired today.

---

## Implementation Order

Dependencies are shown as arrows. Steps with no arrow may proceed in parallel.

```
RP1 (_extract_preservation_floor)
  ↓
RP6.1–RP6.8 (tests for the extractor)
  ↓
RP3 (fix §(j) FAQ ban + §(i) bullet limit + §(e) hardened + hallucination guard)
  ↓
RP2 (§(k) PRESERVATION FLOOR in prompt, uses RP1 extractor)
  ↓
RP6.9–RP6.14 (tests for prompt content)
  ↓
RP4 (_check_preservation_regression + _content_score update + stream loop update)
  ↓
RP6.15–RP6.21 (tests for regression scorer)
  ↓
RP5 (caller API updates — pass original_content through)
```

Total estimated effort: **6–8 hours**.

---

## Status After Implementation

Use this checklist to verify completion:

- [ ] `_extract_preservation_floor` exists and passes RP6.1–RP6.8
- [ ] Prompt contains §(k) when original_content provided — RP6.9–RP6.14
- [ ] Prompt does NOT contain the FAQ ban or the 2-list-per-500-words rule — RP6.10–RP6.11
- [ ] Prompt contains hallucination guard — RP6.14
- [ ] `_check_preservation_regression` exists and passes RP6.15–RP6.19
- [ ] `_content_score` passes `original_features` through, with monotonicity — RP6.20–RP6.21
- [ ] `stream_rewrite_variants` passes `original_features` to every `_content_score` call
- [ ] `_build_improvement_prompt` lists regressions from prior try
- [ ] All three `generate_rewrite_prompt` call sites pass `original_content`
- [ ] 21 new tests in `TestPreservationFloor` all pass
- [ ] Zero pre-existing tests broken
