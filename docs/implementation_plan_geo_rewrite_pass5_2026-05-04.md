# GEO Rewrite Prompt — Pass 5 Revisions: Implementation Plan

**Date:** 2026-05-04
**Scope:** Implement spec "GEO Rewrite Prompt — Pass 5 Revisions v5.0"
**Status:** Planning — awaiting user approval before any code changes
**Source spec:** Provided in chat by user, 2026-05-04. Pass 5 is a calibration/correctness pass following Pass 4 implementation review.

---

## 0. Pre-flight audit

Verified each Pass 5 fix site exists in current code as the spec describes:

| Spec section | Site present as described? | Evidence |
|---|---|---|
| R1 outbound link threshold (>= 2) | **Yes — bug confirmed.** Both sites still use `>= 2`. | `geo_rewrite_prompt.py:1193, 1450` |
| R1 outbound regression instruction text | **Yes — needs updating.** Current text says "removed all external links." | `geo_rewrite_prompt.py:1784–1789` |
| R2 conditional placeholder credit | **Not present.** No `original_had_real_*` fields anywhere. | grep returns nothing |
| R3 qualitative quantifier | **Not present.** No `_QUALITATIVE_QUANTIFIER_RE`. | grep returns nothing |
| R4 entity extraction tightening | **Not present.** Strategy 3 still uses `count >= 2`; no `_DOMAIN_COMMON_NOUNS`. | `geo_rewrite_prompt.py:629–638` |
| R5 Hard Prohibition 9 inconsistency | **Yes — bug confirmed.** Line 329 uses `[STATISTIC NEEDED:` while line 298, 356 (and the fix instructions) use `[STATISTIC:`. | `geo_rewrite_prompt.py:329` |
| R6 deprecated-fallback docstring | **Not present.** Functions exist but have no deprecation note. | `_count_named_lists` line 760, `_item_has_named_reference` |
| R7 Strategy 3/4 deduplication | **Not present.** Strategy 3 doesn't skip allowlisted words. | `geo_rewrite_prompt.py:629–638` |
| §10.7 OpenBrain rewrite fixture | **Missing.** Only `openbrain_original.md` exists; `openbrain_rewrite.md` does not. | `tests/fixtures/` |

**Surface area:** all changes land in 1 file (`api/services/geo_rewrite_prompt.py`) plus tests (`tests/test_geo_rewrite_prompt.py`). The OpenBrain rewrite fixture for §10.7 is the only open question — see §4 below.

---

## 1. Acceptance criteria — verbatim spec IDs mapped to tests

Every Pass 5 spec section and acceptance test is mapped here. Test IDs use the
prefix `R<spec-section>_<short-name>`. All tests live in
`tests/test_geo_rewrite_prompt.py` unless noted.

### Fix R1 — Outbound link regression threshold (spec §3)

| Spec ID | Requirement | Test |
|---|---|---|
| §3.2 Change 1 | `_check_preservation_regression` line 1193 changes `>= 2` → `>= 1` | `R1_single_link_loss_triggers_regression` |
| §3.2 Change 2 | `_content_score` denominator counter line 1450 changes `>= 2` → `>= 1` | `R1_denominator_includes_one_link_case` (verifies the regression check actually fires AND a violation is counted) |
| §3.2 Change 3 | `_REGRESSION_FIX_INSTRUCTIONS["OUTBOUND_LINK_REMOVED"]` rewritten to handle single-link case (mentions "single outbound link" or equivalent, mentions `[SOURCE NEEDED:`) | `R1_instruction_handles_single_link` |
| §3.3 acceptance | Original=1, rewrite=0 → triggers `OUTBOUND_LINK_REMOVED` | `R1_single_link_loss_triggers_regression` |
| §10.1.b control | Original=1, rewrite preserves the link → no regression | `R1_link_preserved_no_regression` |
| §10.1.c control | Original=0 → never triggers regression | `R1_zero_original_links_no_regression` |

### Fix R2 — Conditional placeholder credit (spec §4)

| Spec ID | Requirement | Test |
|---|---|---|
| §4.2 Change 1.a | `_extract_preservation_floor` returns new key `original_had_real_stat: bool` | `R2_floor_has_original_had_real_stat` |
| §4.2 Change 1.b | New key `original_had_real_citation: bool` | `R2_floor_has_original_had_real_citation` |
| §4.2 Change 1.c | New key `original_had_real_quote: bool` | `R2_floor_has_original_had_real_quote` |
| §4.2 Change 1.d | All three new fields are computed from text-with-code-stripped (per spec) | `R2_floor_fields_strip_code_blocks` |
| §4.2 Change 2.stat | Stats Check: placeholder + `original_had_real_stat=False` → full pass (NOT partial) | `R2_placeholder_full_credit_when_original_lacked_evidence` |
| §4.2 Change 2.cite | Citations Check: placeholder + `original_had_real_citation=False` → full pass | `R2_citation_full_credit_when_original_lacked` |
| §4.2 Change 2.quote | Quotes Check: placeholder + `original_had_real_quote=False` → full pass | `R2_quote_full_credit_when_original_lacked` |
| §4.2 Change 2 partial | Placeholder + `original_had_real_*=True` → partial pass (existing behaviour) | `R2_placeholder_partial_credit_when_original_had_evidence` |
| §4.2 Change 2 default | When `original_features=None`, all three default to True (conservative) | `R2_default_when_original_features_missing` |
| §4.2 Change 3 cap | Cap rule still applies to surviving partial-passes | `R2_cap_still_applies_after_filter` |
| §4.2 Change 4 docstring | `_content_score` docstring documents the new rule | `R2_docstring_mentions_original_had_logic` |
| §4.4 acceptance | Pre-existing tests that don't pass `original_features` still pass | covered by full `pytest tests/test_geo_rewrite_prompt.py` run |

### Fix R3 — Qualitative quantifier detection (spec §5)

| Spec ID | Requirement | Test |
|---|---|---|
| §5.2 Change 1 | `_QUALITATIVE_QUANTIFIER_RE` constant exists at module level with the patterns from spec | `R3_qualitative_regex_exists_and_matches_spec_phrases` |
| §5.2 Change 2 | Stats Check: qualitative quantifier alone → partial pass (regardless of `original_had_real_stat`) | `R3_under_an_hour_passes_at_half_credit` |
| §5.2 Change 2 control | Real number alone → full pass (unchanged) | `R3_real_number_passes_at_full_credit` |
| §5.2 Change 2 control | Plain prose with no quantifier → still fails | `R3_no_quantifier_fails` |
| §5.2 no double count | Both qualitative AND placeholder → only one partial-pass entry | `R3_qualitative_does_not_double_count_with_placeholder` |
| §5.3 acceptance | "most users find this approach effective" → partial pass | `R3_majority_users_qualifier_works` |
| §5.2 scope-discipline | Citations and Quotations checks NOT modified to add qualitative variants | `R3_qualitative_not_extended_to_citations_or_quotes` |

### Fix R4 — Tighten Strategy 3 entity extraction (spec §6)

| Spec ID | Requirement | Test |
|---|---|---|
| §6.2 Change 1 | `_DOMAIN_COMMON_NOUNS` constant exists with at least the spec's listed words (Memory, Database, System, Platform, etc.) | `R4_domain_common_nouns_constant_present` |
| §6.2 Change 2 | Strategy 3 filters against both `_EMPHASIS_STOP_WORDS` AND `_DOMAIN_COMMON_NOUNS` | `R4_recurring_common_nouns_not_extracted` |
| §6.2 Change 3 | Strategy 3 threshold raised from 2 to 3 | `R4_proper_noun_threshold_3` |
| §6.2 Change 4 | Docstring of `_extract_named_entities_from_text` mentions threshold = 3 and the new stoplist | `R4_docstring_documents_threshold_change` |
| §6.3 acceptance | "Memory" recurring 5x not extracted | `R4_recurring_common_nouns_not_extracted` |
| §6.3 acceptance | "Acme" 2x not extracted; "Acme" 4x IS extracted | `R4_proper_noun_threshold_3` |
| §6.3 acceptance | Allowlisted "Supabase" still captured (Strategy 4) | `R4_allowlisted_term_still_captured_via_strategy_4` |

### Fix R5 — Hard Prohibition 9 placeholder name consistency (spec §7)

| Spec ID | Requirement | Test |
|---|---|---|
| §7.2 | Line 329 changes `[STATISTIC NEEDED: describe figure type]` → `[STATISTIC: describe figure type]` | `R5_prompt_uses_consistent_statistic_placeholder` |
| §7.3 | `[STATISTIC NEEDED` does not appear anywhere in the generated prompt | covered by same test (assertion 1) |

### Fix R6 — Document legacy named-list heuristic as deprecated (spec §8)

| Spec ID | Requirement | Test |
|---|---|---|
| §8.2 Change 1 | `_item_has_named_reference` docstring contains `[DEPRECATED — Pass 5 R6]` | `R6_item_has_named_reference_marked_deprecated` |
| §8.2 Change 2 | `_count_named_lists` docstring mentions Pass 5 R6 deprecation note | `R6_count_named_lists_mentions_deprecation` |
| §8.2 Change 3 | No code removed (purely documentation) | implicit — full test suite still passes |

### Fix R7 — Strategy 3/4 deduplication (spec §9)

| Spec ID | Requirement | Test |
|---|---|---|
| §9.2 Change 1 | Strategy 3 skips words whose lowercase form is in `_TECHNICAL_TERM_ALLOWLIST` | `R7_api_appears_only_once_in_entity_set` |
| §9.3 acceptance | Acronym in allowlist (e.g. "API" 4x) → only the lowercase form in entity set | `R7_api_appears_only_once_in_entity_set` |
| §9.3 acceptance | Acronym NOT in allowlist (e.g. "RACI" 4x) → still captured by Strategy 3 | `R7_uppercase_acronym_not_in_allowlist_still_captured` |

### §10.7 OpenBrain integration test

See §4 (open question). If the rewrite fixture is committed, the integration
test goes in `TestOpenBrainFixtureRescore` marked `@pytest.mark.integration`
and asserts the calibration changes (qualitative quantifier credit on stats,
single outbound link regression, no `Memory`/`Database`/`Platform` in
entities). If not committed, the test is added but skipped with
`@pytest.mark.skip(reason="...")` so the file ships but the user can
un-skip later.

---

## 2. Implementation order

Mirrors the spec's §11 order. Each step is testable independently.

```
Step 1 — R1 (§3): outbound link threshold + instruction text
        └─ tests R1_*  (3 tests)

Step 2 — R5 (§7): Hard Prohibition 9 [STATISTIC: ...] format
        └─ test R5_prompt_uses_consistent_statistic_placeholder  (1 test)

Step 3 — R2 (§4): conditional placeholder credit
        Sub-steps:
          3a. Extend _extract_preservation_floor with original_had_real_* fields
          3b. Modify Stats / Citations / Quotes checks in _content_score
          3c. Update _content_score docstring
        └─ tests R2_*  (10 tests)

Step 4 — R3 (§5): qualitative quantifier
        Sub-steps:
          4a. Add _QUALITATIVE_QUANTIFIER_RE constant
          4b. Wire into Stats check as half-credit (BEFORE the placeholder check)
        └─ tests R3_*  (6 tests)

Step 5 — R4 (§6): tightened entity extraction
        Sub-steps:
          5a. Add _DOMAIN_COMMON_NOUNS constant
          5b. Strategy 3: filter both stoplists, raise threshold to 3
          5c. Update docstring
        └─ tests R4_*  (4 tests)

Step 6 — R7 (§9): Strategy 3/4 deduplication
        └─ tests R7_*  (2 tests)

Step 7 — R6 (§8): documentation-only deprecation comments
        └─ tests R6_*  (2 tests)

Step 8 — §10.7 integration test
        └─ test TestOpenBrainFixtureRescore (committed; skip-status depends on §4)

Step 9 — Full test suite + status report
```

**Total new tests:** 30 unit + 1 integration-marked = **31 tests**.
**Estimated effort:** 2–3 hours (the changes are small and well-specified).

---

## 3. Dependency notes and risks

### Dependency: R3 qualitative-quantifier ordering

Spec §5.2 places the qualitative-quantifier check BETWEEN the "real stat"
check and the "placeholder + original_had" check. If implemented in the
wrong order, behavior diverges:

- Wrong order (placeholder before qualitative): a rewrite with both `[STATISTIC: x]` and "under an hour" would get partial-pass via the placeholder branch, never seeing the qualitative branch. Acceptable for §10.3.4 (no double-count test) but loses the "qualitative is half-credit regardless of original" intent for the case where `original_had_real_stat=False` AND only a qualitative quantifier is present.
- Correct order (per spec): qualitative is checked first as half-credit; only if no real stat AND no qualitative do we fall through to placeholder. This matches the spec snippet at §5.2.

The plan implements the spec's exact order.

### Risk: R2 default behaviour

The spec mandates a conservative default: when `original_features` is
`None`, treat all three categories as having existed. This preserves Pass 4
test behavior. Verified: `test_cr3_2_partial_pass_half_weight` and
similar Pass 4 tests don't pass `original_features`, so they should still
behave the same. I will run the existing `TestPlaceholderCap` and
`TestFabricatedLinkScoring` classes after the change to confirm.

### Risk: R4 threshold change recall loss

Spec §12 acknowledges this is intentional. Pass 4 tests don't seem to
depend on Strategy 3's `>= 2` threshold (they use the allowlist). I'll
verify by re-running `TestNamedEntityExtraction` after the change.

The one test that might be sensitive is
`test_cr5_2_extracts_repeated_capitalised`:
```python
text = "Foobar is a tool. Foobar handles memory. Foobar runs locally."
```
"Foobar" appears 3 times → still passes with the new `>= 3` threshold.
Confirmed: this test won't regress.

### Risk: R7 deduplication interaction with R4

R7 adds an `if w.lower() in _TECHNICAL_TERM_ALLOWLIST: continue` to
Strategy 3. R4 raises the threshold to 3 in the same loop. The combined
effect: Strategy 3 only captures non-allowlisted, non-stop-word capitalised
words appearing ≥3 times. Tests verify both behaviors independently
(R4_proper_noun_threshold_3 + R7_api_appears_only_once_in_entity_set).

---

## 4. Open question for the user

### Q1 — OpenBrain rewrite fixture for §10.7

The spec's §10.7 integration test expects two fixtures:
`tests/fixtures/openbrain_original.md` (committed in Pass 4) and
`tests/fixtures/openbrain_rewrite.md` (does NOT exist).

Three options:

- **(a)** You paste the OpenBrain rewrite text from "the prior message" in
  the Pass 5 spec. I save it as the fixture. The integration test runs
  cleanly under `pytest -m integration`.
- **(b)** I generate a rewrite by running the actual pipeline against the
  OpenBrain original fixture once (live LLM call, ~90s, ~$cost), save the
  output as `openbrain_rewrite.md`, and commit it. The test then verifies
  Pass 5 calibration on a real rewrite.
- **(c)** I commit the test skeleton with `@pytest.mark.skip(reason="awaiting
  openbrain_rewrite.md fixture")` and the user can un-skip later by
  providing the file. Other Pass 5 changes are validated by the
  unit-tier tests in §10.1–§10.6.

**My default if you say nothing: (c).** Reason: §10.7 is a single test that
checks a specific page; the unit-tier tests in §10.1–§10.6 are sufficient
to verify the Pass 5 changes are correct. Spending another ~$cost of LLM
to generate a fixture for one assertion isn't justified — and the user
already has the rewrite text from a prior conversation.

---

## 5. Adjacent issues found, not fixed

Spec §12 explicitly says to log adjacent issues as Pass 6 candidates rather
than fixing them here. Found during the audit:

1. **`_extract_preservation_floor` recomputes `_extract_named_entities_from_text`
   when called repeatedly on the same text.** No memoization. Cheap on small
   pages, potentially expensive on large ones. Pass 6 candidate if profiling
   ever shows it.

2. **`_content_score` uses the `body` (post-`_split_body_and_notes`) for
   structural checks, but `_extract_preservation_floor` uses `text_no_code`
   for the same checks.** Different normalisations could in theory produce
   different counts. In practice the GEO NOTES section never contains
   structured elements, so this is benign — but if a rewrite ever puts a
   bullet list in GEO NOTES, the two functions would disagree. Pass 6
   candidate.

3. **`_QUALITATIVE_QUANTIFIER_RE` (Pass 5 R3) overlaps with `_STAT_RE_FULL`
   for cases like "under 5 minutes" — `_STAT_RE_FULL` matches "5 minutes"
   while `_QUALITATIVE_QUANTIFIER_RE` would NOT match (its pattern
   requires `under\s+(?:an?\s+)?(?:second|minute...)` — no digits after
   "under"). So no overlap in practice. Documenting for future maintainers.

4. **`_DOMAIN_COMMON_NOUNS` includes "Information" twice** in the spec (line
   visible in the spec's Change 1 snippet — once in the technical group,
   once in the English group). I'll deduplicate when building the
   `frozenset` (Python frozenset semantics handle this automatically), but
   noting it for the user — could affect the test for stoplist completeness.

5. **`_count_named_lists` legacy fallback (R6) is documented as deprecated
   but not removed.** Per spec §8.2.3, "no code removal in this pass."
   Removal is itself a Pass 6 candidate after the deprecation has shipped.

---

## 6. Status report template — to be filled after implementation

This section will be replaced by a per-criterion status report listing each
Pass 5 spec ID with one of: `done` (with file:line + test), `partial` (with
what's missing), `not done` (with reason). Per CLAUDE.md, "implementation
complete" without this report is not sufficient.

---

## 7. Recommendation

Pass 5 is small (~30 tests, 1 file, ~2–3h actual). All seven fixes are
well-specified with explicit code snippets. The only judgement call is
Q1 above (the OpenBrain rewrite fixture).

**Awaiting:**
- Approval to proceed (just say "go" or "approved")
- Answer to Q1 (or confirm default = (c))

Once approved, I'll work through Steps 1–9 in order, committing after
each significant step (Steps 1–3 small enough to land together; Step 3 is
the largest; Steps 5–9 small enough to land together). After each commit
I'll run `pytest tests/test_geo_rewrite_prompt.py` to catch regressions
immediately.
