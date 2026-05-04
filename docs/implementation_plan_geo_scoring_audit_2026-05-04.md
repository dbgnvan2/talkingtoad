# GEO Scoring Audit — Remediation Plan

**Date:** 2026-05-04  
**Scope:** Text-transformation path alignment, check-scope corrections, denominator
hardening, and a comprehensive robustness test suite for all GEO scoring logic  
**Status:** Awaiting approval

---

## Context

A targeted code review — prompted by finding that `_content_score()` was crediting
placeholder text written in GEO NOTES rather than in the body — revealed a class of
bugs: **wrong-scope text processing**. Functions were operating on larger (or different)
text buffers than their spec required, producing plausible-looking but incorrect scores.

A systematic audit identified 10 additional instances of the same class of bug across
the GEO pipeline. This plan remediates all of them, then builds a test suite designed
to catch future regressions of the same kind.

---

## Audit Findings Summary

| ID | File | Description | Risk |
|----|------|-------------|------|
| F1 | parser.py | Field `first_150_words` extracts 200 words (naming deception) | HIGH |
| F2 | geo_analyzer.py | Extracts 150 words, excludes `<aside>` differently from parser.py | HIGH |
| F3 | issue_checker.py | `STATISTICS_COUNT_LOW` searches unbounded heading text + first 200 words | HIGH |
| F4 | issue_checker.py | `QUOTATIONS_MISSING` combines full-page blockquote count + first-200-words attribution | HIGH |
| F5 | geo_analyzer.py | `CHUNKS_NOT_SELF_CONTAINED` tests only first 8 sections silently | HIGH |
| F6 | geo_analyzer.py | `QUERY_MATCH_SCORE` denominator is LLM-generated count; no validation vs spec (7) | HIGH |
| F7 | geo_analyzer.py | `check_central_claim()` accepts `first_150_words` parameter but never uses it | MEDIUM |
| F8 | geo_rewrite_prompt.py | `_score_rewrite_query_match()` truncates to 3,000 chars — answers after char 3,000 are invisible | MEDIUM |
| F9 | geo_analyzer.py | Mix of character limits (800, 2,000, 3,000) vs word limits (150, 200) with no consistent unit | MEDIUM |
| F10 | geo_scoring_map.py | Unbounded Conventional findings list can dominate overall score without limit | MEDIUM |

---

## Acceptance Criteria

### Phase 1 — Text Extraction Alignment

**P1-1: Rename `first_150_words` to `first_200_words` throughout**

The `ParsedPage` field extracts 200 words. The name `first_150_words` is actively
misleading and caused an unreachable parameter bug in `check_central_claim()`.

- Implementation: rename field in `ParsedPage` dataclass; update all 20+ callers
- Callers include: `issue_checker.py` (8 references), `geo_analyzer.py` (4 references),
  `geo_rewrite_prompt.py` (indirect via synthetic page), `test_geo_static_checks.py`
- Test: `test_p1_1_field_name_matches_word_count` — parse a known 250-word HTML page;
  assert `len(page.first_200_words.split()) == 200`
- Test: `test_p1_1_no_first_150_words_references` — grep the repo for the literal string
  `first_150_words`; assert 0 matches

**P1-2: Align `<aside>` exclusion between parser.py and geo_analyzer.py**

parser.py Path A excludes `<aside>`; geo_analyzer.py Path B does not. This means LLM
checks operate on different text than static checks for pages with sidebar content.

Decision (to be confirmed before implementation): **exclude `<aside>` in geo_analyzer too**,
matching parser.py. Rationale: aside content is navigation/callouts, not primary text.

- Implementation: add `"aside"` to the tag list at `geo_analyzer.py:329`
- Test: `test_p1_2_aside_excluded_from_geo_analyzer_extraction` — build HTML with a
  `<p>` in an `<aside>` containing the word "ASIDE_SIGNAL". Extract via geo_analyzer
  path; assert "ASIDE_SIGNAL" is not in the extracted text
- Test: `test_p1_2_paths_agree_on_aside` — same HTML; compare parser.py path vs
  geo_analyzer.py path; assert both exclude aside content

**P1-3: Align word-count across extraction paths (Path A vs Path B vs Path C)**

| Path | File | Word count | `<aside>` excluded |
|------|------|-----------|-------------------|
| A | parser.py `_extract_first_n_words(soup, 200)` | 200 | Yes |
| B | geo_analyzer.py inline extraction | 150 | No (before P1-2 fix) |
| C | parser.py `_check_query_coverage_weak()` | 200 | Yes |

After P1-2, Path B will still extract 150 words. Update to 200 to match Paths A and C.

- Implementation: change `[:150]` to `[:200]` at `geo_analyzer.py:332`
- Test: `test_p1_3_extraction_paths_agree` — take one real HTML fixture; run all three
  paths; assert word counts agree (all 200) and content matches when `<aside>` handling
  is aligned
- Adjacent finding: the `first_150_words` local variable in geo_analyzer should also be
  renamed to `first_200_words` as part of this change

---

### Phase 2 — Check Scope Corrections

**P2-1: Cap `STATISTICS_COUNT_LOW` to body text, not unbounded heading text**

`_count_statistics()` searches `first_200_words + all heading text`. Heading text is
unbounded — a page with 20 H2 headings each containing a number would never fire this
check. Spec (`geo_scoring_map.py:48`) says "headings + first_150_words", so headings
are in-scope, but the combined buffer has no size cap.

Two options:
- **(Chosen)** Cap the combined statistics search to a total of 400 words (200 intro
  words + up to 200 words of heading text). This prevents heading inflation while
  still allowing headings to contribute statistics.
- Alternative: remove headings from scope, search first 200 words only.

- Implementation: `issue_checker.py:1948–1956` — build heading text from
  `" ".join(...)[:400_chars]` or limit to first 10 headings
- Test: `test_p2_1_stat_count_not_inflated_by_headings` — build a page with 0
  statistics in first 200 words but 5 numbers in H2/H3 tags; assert
  `STATISTICS_COUNT_LOW` still fires (stat count should not pass purely on heading data)
- Test: `test_p2_1_stat_in_intro_passes` — build a page with one statistic in the
  first 200 words; assert `STATISTICS_COUNT_LOW` does NOT fire

**P2-2: Align scope for `QUOTATIONS_MISSING`**

Current: `blockquote_count` scans full page; `_count_inline_quotations()` scans only
first 200 words. A page with an attributed quote only after word 200 never passes.

Decision: expand `_count_inline_quotations()` to scan full body text. Rationale:
attribution phrases ("according to", "said") can legitimately appear anywhere; there
is no GEO benefit to restricting them to the first 200 words.

- Implementation: `issue_checker.py:1980–1983` — pass full body text to
  `_count_inline_quotations()` instead of `page.first_200_words`. The `page` object
  has no full-body text field; pass `page.body_text` (new field) or accept the
  fact that attribution after first 200 words is missed and document this. For now,
  expand to search the first 600 words (3× intro) as a pragmatic compromise.
- Test: `test_p2_2_attribution_after_intro_detected` — build a page where "according
  to" appears at word 300; assert `QUOTATIONS_MISSING` does NOT fire
- Test: `test_p2_2_blockquote_at_page_end_detected` — build a page where a `<blockquote>`
  appears only in the last paragraph; assert `QUOTATIONS_MISSING` does NOT fire

**P2-3: Surface the 8-section cap in `CHUNKS_NOT_SELF_CONTAINED`**

`run_chunk_containedness()` silently tests only the first 8 of N sections, but the
spec says ">= 50% of H2/H3 sections". For a 20-section page, 8 of 20 tested is not
representative.

Two options:
- **(Chosen)** Add the tested count and total count to the finding's `extra` field so
  the UI can show "7 of 15 sections tested"; also warn in logs when `total > 8`
- Alternative: test all sections (increases API calls and latency)

- Implementation: `geo_analyzer.py:416–434` — after computing `chunk_results`, attach
  `{"sections_tested": len(chunk_results), "sections_total": total_sections}` to the
  finding's extra dict; add a `logger.warning` when `total_sections > 8`
- Test: `test_p2_3_section_cap_surfaced_in_extra` — mock `run_chunk_containedness` to
  return 8 results for a 15-section page; assert finding extra contains
  `sections_tested=8, sections_total=15`
- Test: `test_p2_3_no_finding_when_all_8_pass` — all 8 results self_contained=True;
  assert no CHUNKS_NOT_SELF_CONTAINED finding

**P2-4: Validate `QUERY_MATCH_SCORE` denominator**

`_call_ai()` returns however many queries the LLM generates. If it returns 4 instead
of 7, the score is inflated. No validation exists.

- Implementation: `geo_analyzer.py:393–413` — after building `query_table`, if
  `len(query_table) < 5`, log a warning and record `{"query_count": len(query_table)}`
  in the finding's extra dict. If `len(query_table) == 0`, set score to 0.0 explicitly.
  Do not fabricate missing queries — report what the LLM provided.
- Test: `test_p2_4_short_query_table_logged` — mock LLM to return 3 queries; assert
  warning is logged and `finding.extra["query_count"] == 3`
- Test: `test_p2_4_empty_query_table_scores_zero` — mock LLM to return []; assert
  QUERY_MATCH_SCORE finding has score 0.0

**P2-5: Expand query re-match truncation for long pages**

`_score_rewrite_query_match()` truncates to 3,000 characters. A well-structured 1,500-
word article is ~9,000 characters. The last 6,000 chars are invisible to the scorer —
if the best query answers are in section 4 of 6, they go unscored.

- Implementation: `geo_rewrite_prompt.py:665` — increase truncation to 6,000 chars.
  Additionally, if the text is > 6,000 chars, take chars 0–4,000 (intro + first sections)
  plus chars `[-2,000:]` (final sections). This captures both beginning and end without
  sending the full text.
- Test: `test_p2_5_answers_after_3000_chars_scored` — build a rewrite where the best
  query answer appears at char 3,500; assert query re-match score is non-zero
- Test: `test_p2_5_long_page_uses_head_and_tail` — rewrite text of 10,000 chars; assert
  the text passed to LLM contains content from both the first 4,000 and last 2,000 chars

---

### Phase 3 — Dead Code and Consistency

**P3-1: Remove or use the dead `first_150_words` parameter in `check_central_claim()`**

`check_central_claim(full_text, first_150_words, model, provider)` at
`geo_analyzer.py:247` accepts `first_150_words` but never uses it — the LLM prompt
only receives `content[:2000]`. After P1-1's rename, this will be `first_200_words`.

Decision: use the parameter. The central claim check should prioritise the intro; send
`first_200_words` as the primary text and `full_text[:2000]` as supporting context.
Update the LLM prompt to reflect this.

- Implementation: `geo_analyzer.py:247–265` — revise prompt to use `first_200_words`
  as primary, with optional full-text context appended
- Test: `test_p3_1_central_claim_uses_intro` — build a page where the central claim
  is only in the first 200 words; mock LLM to verify the intro text appears in the
  prompt; assert finding fires correctly

**P3-2: Document word vs. character limits with a constants file**

The mix of `[:800]`, `[:2000]`, `[:3000]` char limits and `[:150]`, `[:200]` word
limits across `geo_analyzer.py` is undocumented. Future contributors will introduce
new inconsistencies.

- Implementation: add a `_GEO_ANALYSIS_LIMITS` dict at the top of `geo_analyzer.py`:
  ```python
  _GEO_ANALYSIS_LIMITS = {
      "first_words": 200,          # words — intro extraction
      "query_match_chars": 6000,   # chars — after P2-5 fix
      "chunk_section_chars": 800,  # chars — per H2 section
      "central_claim_chars": 2000, # chars — supporting context
  }
  ```
  Replace all hardcoded limits with references to this dict.
- Test: `test_p3_2_limits_dict_used` — grep for hardcoded `[:800]`, `[:2000]`,
  `[:3000]`, `[:3500]` in geo_analyzer.py; assert 0 matches (all replaced by dict refs)

---

### Phase 4 — Robustness Test Suite

This phase builds the tests that would have caught all findings above before they shipped.
It goes beyond testing individual fixes — it establishes invariants that hold for any future
change to GEO scoring.

**P4-1: Path agreement tests — every extraction path must produce the same text**

For a shared HTML fixture, all three extraction paths must agree on:
- Word count (200)
- `<aside>` content excluded
- `<nav>`, `<header>`, `<footer>` content excluded

```python
HTML_FIXTURE = """<html><body>
<nav>NAV_SIGNAL</nav>
<aside>ASIDE_SIGNAL</aside>
<header>HEADER_SIGNAL</header>
<p>Word1 Word2 ... Word200</p>
<footer>FOOTER_SIGNAL</footer>
</body></html>"""
```

- `test_p4_1_parser_path_a_extraction` — Path A (parser.py `_extract_first_n_words`)
  excludes NAV_SIGNAL, ASIDE_SIGNAL, HEADER_SIGNAL, FOOTER_SIGNAL; returns 200 words
- `test_p4_1_geo_analyzer_path_b_extraction` — Path B (geo_analyzer inline) after P1-2
  and P1-3 fixes: same exclusions, same 200 words
- `test_p4_1_query_coverage_path_c_extraction` — Path C (`_check_query_coverage_weak`)
  agrees with A and B

**P4-2: Score monotonicity tests**

These are invariants. Any future change that breaks a monotonicity test has introduced
a new wrong-scope bug.

```python
# M1: Adding a placeholder to the body must not decrease content score
def test_m1_body_placeholder_never_decreases_score():
    base = "content " * 200  # 200-word content with no placeholders
    with_placeholder = base + " [CITATION NEEDED: source] "
    _, score_base = _content_score("http://x.com", base)
    _, score_with = _content_score("http://x.com", with_placeholder)
    assert score_with >= score_base

# M2: Adding a placeholder only to GEO NOTES must have zero effect
def test_m2_notes_placeholder_has_no_score_effect():
    base = "content " * 200
    with_notes = base + "\n---\nGEO NOTES\n- [CITATION NEEDED] added at: intro."
    _, score_base = _content_score("http://x.com", base)
    _, score_with_notes = _content_score("http://x.com", with_notes)
    assert score_base == score_with_notes

# M3: A page with 2 failing checks must score lower than the same page with 1
def test_m3_more_failures_means_lower_score():
    one_fail = "content " * 600  # long enough to trigger all checks; has stats but no structure
    two_fail = one_fail  # same content, modify so stats check also fails
    _, score_one = _content_score("http://x.com", one_fail)
    _, score_two = _content_score("http://x.com", two_fail)
    # This test requires constructing controlled inputs; use parametrize

# M4: Projected score with a higher query-match must always be >= projected score with lower
def test_m4_higher_query_match_means_higher_projected():
    findings = [{"code": "QUERY_MATCH_SCORE", "evidence_tier": "Empirical", ...}]
    score_low = _project_score_from_findings(findings, 0.5)
    score_high = _project_score_from_findings(findings, 0.8)
    assert score_high > score_low

# M5: Overall GEO score with more failing findings must be <= score with fewer
def test_m5_more_geo_findings_lower_overall():
    base_findings = [{"code": "JSON_LD_MISSING", "pass_fail": "fail", "evidence_tier": "Conventional"}]
    extra_findings = base_findings + [{"code": "FAQ_SCHEMA_MISSING", "pass_fail": "fail", "evidence_tier": "Conventional"}]
    score_base = compute_score_from_findings(base_findings)
    score_extra = compute_score_from_findings(extra_findings)
    assert score_extra <= score_base
```

**P4-3: Golden dataset — OpenBrain regression fixture**

The OpenBrain rewrite (from the live run that revealed the placeholder bug) becomes a
permanent regression fixture. Any code change that produces a different score for this
input must be explained and intentional.

```python
OPENBRAIN_REWRITE = """# What Is OpenBrain? ...
[full text]
---
GEO NOTES
- [CITATION NEEDED] added at: Introduction...
- [STATISTIC: type of data needed] added at: Description...
"""

def test_openbrain_placeholders_not_in_body():
    """Placeholder inflation bug must not recur."""
    body, notes = _split_body_and_notes(OPENBRAIN_REWRITE)
    missing = _verify_geo_notes_placeholders(body, notes)
    assert "CITATION NEEDED / LINK" in missing
    assert "STATISTIC" in missing

def test_openbrain_content_score_reflects_reality():
    """Score must reflect that body has no placeholders, no links, no structure."""
    _, score = _content_score("https://example.com", OPENBRAIN_REWRITE)
    # EXTERNAL_CITATIONS_LOW (w=3) and STATISTICS_COUNT_LOW (w=3) both fire
    # score = 1 - 6/13 ≈ 0.538
    assert score < 0.7, f"Score too high ({score}); placeholder inflation may have recurred"

def test_openbrain_answer_signal_detected():
    """First sentence is a direct answer — must not fire FIRST_VIEWPORT_NO_ANSWER."""
    body, _ = _split_body_and_notes(OPENBRAIN_REWRITE)
    tokens = body.split()
    first_200 = " ".join(tokens[:200])
    from api.crawler.issue_checker import _has_answer_signal
    assert _has_answer_signal(first_200)
```

**P4-4: Denominator guard tests**

```python
def test_query_count_below_threshold_logged(caplog):
    """QUERY_MATCH_SCORE with < 5 queries must log a warning."""
    # Mock geo_analyzer to return 3 queries; assert warning in log

def test_query_count_zero_scores_zero():
    """Empty query table must produce score 0.0, not division-by-zero."""

def test_chunks_tested_count_in_finding_extra():
    """CHUNKS finding must expose sections_tested and sections_total in extra."""
    # Build a 12-section page; assert finding.extra["sections_tested"] == 8
    # assert finding.extra["sections_total"] == 12

def test_conventional_finding_flood_capped():
    """100 Conventional findings should not drag score below a floor that Empirical
    tier findings would not produce."""
    # Verify compute_score_from_findings with 100 Conventional fails vs. 3 Empirical fails
```

**P4-5: Integration smoke test — end-to-end score pipeline**

A single test that runs the full GEO scoring pipeline on a known HTML page and asserts:
- The score is in the expected range
- The number of findings matches expectations
- No extraction path crashes or returns empty

```python
def test_geo_pipeline_end_to_end_known_page():
    """Full pipeline smoke test with a controlled HTML input."""
    html = build_known_geo_test_page()  # helper: page with 1 statistic, 1 citation, answer in intro
    # Run compute_tier1_scores_from_html
    # Run _content_score on extracted markdown
    # Assert: intro score == 100, citation check passes, stat check passes
```

---

## Implementation Order

| Phase | Criteria | Effort | Why this order |
|-------|----------|--------|----------------|
| 1a | P1-1 (rename field) | 2h | Unblocks all other Phase 1 fixes; touches 20+ files |
| 1b | P1-2 + P1-3 (align aside + wordcount) | 1h | Small targeted fix once rename is done |
| 2a | P2-1 (stat scope cap) | 1h | Prevents false passes; high-risk finding |
| 2b | P2-2 (quotations scope) | 1h | Prevents false positives near-consistently |
| 2c | P2-3 (chunk cap surfacing) | 1h | No score change; adds transparency |
| 2d | P2-4 (query denominator) | 1h | Prevents inflated scores on LLM failure |
| 2e | P2-5 (extend rewrite truncation) | 1h | Affects rewrite scoring quality |
| 3 | P3-1 + P3-2 (dead param + constants) | 2h | Prevents future contributors repeating mistakes |
| 4 | P4-1 through P4-5 (test suite) | 6–8h | Must be written concurrently with phase 1–3 fixes; each fix needs its test |

**Total estimated effort:** 16–18 hours

---

## What This Does Not Change

- **GEO check thresholds** — the pass/fail criteria in `geo_scoring_map.py` are unchanged
- **Scoring weights** — tier weights (Empirical ×3, Mechanistic ×2, Conventional ×1) unchanged
- **Frontend** — no UI changes required (except P2-3 surfaces extra data already shown)
- **API contracts** — no response shape changes; extra fields are additive

---

## Verification Checklist

After implementation:

- [ ] `grep -r "first_150_words" api/ tests/ frontend/` returns 0 matches
- [ ] `grep -rn '"\bside\b"' api/services/geo_analyzer.py` shows `aside` in the tag list at line ~329
- [ ] `geo_analyzer.py:332` shows `[:200]` not `[:150]`
- [ ] `test_geo_rewrite_scoring.py::test_openbrain_content_score_reflects_reality` passes with score < 0.7
- [ ] All 5 monotonicity tests pass
- [ ] All 3 path-agreement tests pass (P4-1)
- [ ] `pytest tests/ -q` shows no regressions against existing 59 GEO tests

---

## Adjacent Issues Found, Not Fixed

These were observed during the audit but are out of scope for this plan:

1. **`geo_scoring_map.py:504–520`** — `compute_score_from_findings()` has no cap on Conventional-tier
   finding accumulation. 50+ Conventional failures could dominate an otherwise high-Empirical page.
   Architectural decision needed: cap per tier, or add a floor for empirical passes.

2. **`issue_checker.py:1948–1956`** — `_count_statistics()` includes heading text, but
   `_count_cross_references()` (parser.py) searches full body. The two most related checks use
   completely different scopes with no documented rationale.

3. **`geo_analyzer.py:215`** — 8-section cap on chunk testing is not configurable. Sites with
   20+ sections get incomplete analysis; no config option exists to raise the limit at the cost
   of more API calls.
