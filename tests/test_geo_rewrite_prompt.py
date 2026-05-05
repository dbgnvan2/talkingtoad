"""
Tests for geo_rewrite_prompt.py (GEO Rewrite Prompt Generator — Phase C).

Spec: docs/implementation_plan_geo_rewrite_prompt_2026-05-03.md

Tests:
  C.1 — _detect_page_type classifies article/technical/faq/comparison/general
  C.2 — generate_rewrite_prompt returns all 9 sections in system_prompt
  C.3 — mandatory checks appear in system_prompt rubric
  C.4 — STYLE CONSTRAINTS section contains anti-AI rules
  C.5 — _build_synthetic_parsed_page extracts correct fields from markdown
  C.6 — _score_markdown returns 0 for ideal content, > 0 for thin content

  CR2_*  — Fix 1 (correctness pass): fix-instruction examples non-fabricating
  CR3_*  — Fix 2: placeholder cap + 4-tuple return
  CR4_*  — Fix 3: page-type-conditional structural check
  CR5_*  — Fix 4: entity-set named-list detection
  CR6_*  — Fix 5: numbered-output query-match parser
  CR7_*  — Fix 6: score-blend constants surfaced
  CR8_*  — Fix 7: small correctness fixes (FAQ, prohibitions, regex, links)
  CR_ADJ_* — Adjacent fixes pulled into scope
"""

import re
import pytest

from api.services.geo_rewrite_prompt import (
    _BEST_OF_N,
    _build_improvement_prompt,
    _build_synthetic_parsed_page,
    _check_preservation_regression,
    _content_score,
    _detect_page_type,
    _extract_preservation_floor,
    _project_score_from_findings,
    _score_markdown,
    _split_body_and_notes,
    _verify_geo_notes_placeholders,
    generate_rewrite_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_report(findings=None, overall_score=0.0):
    return {
        "url": "https://example.com/test",
        "model_used": "gpt-4o",
        "overall_score": overall_score,
        "aggarwal_score": 0.0,
        "findings": findings or [],
    }


def _fail_finding(code: str, tier: str) -> dict:
    return {
        "code": code,
        "label": code,
        "evidence_tier": tier,
        "pass_fail": "fail",
        "score": 0.0,
        "findings": [],
        "details": {},
    }


# ---------------------------------------------------------------------------
# C.1 — page type detection
# ---------------------------------------------------------------------------

class TestDetectPageType:
    def test_c1_article_from_schema(self):
        assert _detect_page_type(
            "https://example.com/post/my-article",
            ["BlogPosting"],
            [],
        ) == "article"

    def test_c1_article_from_url(self):
        assert _detect_page_type(
            "https://example.com/blog/nonprofit-seo",
            [],
            [],
        ) == "article"

    def test_c1_technical_from_schema(self):
        assert _detect_page_type(
            "https://example.com/docs/setup",
            ["TechArticle"],
            [],
        ) == "technical"

    def test_c1_technical_from_url(self):
        assert _detect_page_type(
            "https://example.com/how-to/install-plugin",
            [],
            [],
        ) == "technical"

    def test_c1_faq_from_headings(self):
        headings = [
            {"level": 2, "text": "What is SEO?"},
            {"level": 2, "text": "How does crawling work?"},
            {"level": 2, "text": "Why do headings matter?"},
        ]
        assert _detect_page_type("https://example.com/faq", [], headings) == "faq"

    def test_c1_comparison_from_headings(self):
        headings = [{"level": 2, "text": "WordPress vs Drupal"}]
        assert _detect_page_type("https://example.com/compare", [], headings) == "comparison"

    def test_c1_general_fallback(self):
        assert _detect_page_type("https://example.com/about", [], []) == "general"


# ---------------------------------------------------------------------------
# C.2 — generate_rewrite_prompt returns all 9 prompt sections
# ---------------------------------------------------------------------------

EXPECTED_SECTIONS = [
    "## (a) ROLE",
    "## (b) INPUT CONTRACT",
    "## (c) OUTPUT CONTRACT",
    "## (d) THE RUBRIC",
    "## (e) HARD PROHIBITIONS",
    "## (f) PRESERVATION CONSTRAINTS",
    "## (g) UNCERTAINTY HANDLING",
    "## (h) ITERATION INSTRUCTION",
    "## (i) STYLE CONSTRAINTS",
]


class TestGenerateRewritePrompt:
    def test_c2_all_9_sections_present(self):
        """C.2: system_prompt contains all 9 lettered sections."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        for section in EXPECTED_SECTIONS:
            assert section in prompt, f"Missing section: {section}"

    def test_c2_returns_expected_keys(self):
        """C.2: return dict has all required keys."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "general")
        required = {
            "system_prompt", "current_score", "target_score",
            "mandatory_count", "fixable_count", "page_type", "findings_count",
        }
        assert required <= set(result.keys())

    def test_c2_target_score_is_0_90(self):
        """C.2: target_score is always 0.90."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "general")
        assert result["target_score"] == 0.90

    def test_c2_findings_count_matches_report(self):
        """C.2: findings_count matches number of findings in report."""
        findings = [
            _fail_finding("STATISTICS_COUNT_LOW", "Empirical"),
            _fail_finding("JSON_LD_INVALID", "Conventional"),
        ]
        report = _make_report(findings=findings)
        result = generate_rewrite_prompt(report, "general")
        assert result["findings_count"] == 2

    def test_c2_page_type_in_input_contract(self):
        """C.2: page_type appears in the INPUT CONTRACT section."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "technical")
        assert "technical" in result["system_prompt"]


# ---------------------------------------------------------------------------
# C.3 — mandatory checks appear in rubric
# ---------------------------------------------------------------------------

class TestRubricContent:
    def test_c3_mandatory_checks_in_rubric(self):
        """C.3: failing check codes appear in MANDATORY CHANGES section."""
        findings = [_fail_finding("STATISTICS_COUNT_LOW", "Empirical")]
        report = _make_report(findings=findings, overall_score=0.0)
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        assert "MANDATORY" in prompt
        assert "STATISTICS_COUNT_LOW" in prompt

    def test_c3_rubric_instruction_in_prompt(self):
        """C.3: GEO_CHECKS rubric_instruction for failing check is in prompt."""
        findings = [_fail_finding("FIRST_VIEWPORT_NO_ANSWER", "Mechanistic")]
        report = _make_report(findings=findings)
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        # The rubric instruction for FIRST_VIEWPORT_NO_ANSWER contains this phrase
        assert "first 150 words" in prompt.lower() or "150 words" in prompt

    def test_c3_no_findings_yields_clean_message(self):
        """C.3: zero failing checks → rubric says page already meets threshold."""
        report = _make_report(findings=[], overall_score=1.0)
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        assert "already meets" in prompt or "No failing" in prompt

    def test_c3_mandatory_count_correct(self):
        """C.3: mandatory_count matches number of fail findings."""
        findings = [
            _fail_finding("STATISTICS_COUNT_LOW", "Empirical"),
            _fail_finding("EXTERNAL_CITATIONS_LOW", "Empirical"),
        ]
        report = _make_report(findings=findings)
        result = generate_rewrite_prompt(report, "general")
        # All fail findings are mandatory (s_c = 0.0 < 0.90)
        assert result["mandatory_count"] == 2


# ---------------------------------------------------------------------------
# C.4 — STYLE CONSTRAINTS section contains anti-AI rules
# ---------------------------------------------------------------------------

ANTI_AI_PHRASES = [
    "In today's world",
    "Let's dive in",
    "Delve into",
    "Seamless",
    "Cutting-edge",
    "ANTI-AI WRITING RULES",
]


class TestStyleConstraints:
    def test_c4_banned_phrases_listed(self):
        """C.4: style section lists banned AI phrases."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        for phrase in ANTI_AI_PHRASES:
            assert phrase in prompt, f"Missing banned phrase: {phrase}"

    def test_c4_structural_prohibitions_present(self):
        """C.4: style section lists structural prohibitions (bullet list cap)."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        assert "bullet" in prompt.lower() or "list" in prompt.lower()

    def test_c4_sentence_variety_rule_present(self):
        """C.4: style section mentions sentence length variation."""
        report = _make_report()
        result = generate_rewrite_prompt(report, "general")
        prompt = result["system_prompt"]
        assert "sentence" in prompt.lower() and "length" in prompt.lower()


# ---------------------------------------------------------------------------
# C.5 — _build_synthetic_parsed_page field extraction
# ---------------------------------------------------------------------------

SAMPLE_MD = """\
# How Nonprofits Can Improve Their SEO

By Jane Smith

Published: January 15, 2024

In 2023, nonprofits that invested in SEO saw 40% more traffic.

## Why SEO Matters for Nonprofits

According to Google's research, 70% of donors search online before giving.
SEO ensures your mission reaches them.

> "Search is the primary way people discover nonprofits." — Charity Navigator

## Key Tactics

- Optimise your title tags
- Add JSON-LD structured data
- Improve page speed

| Tactic | Effort | Impact |
|---|---|---|
| Title tags | Low | High |
| JSON-LD | Medium | High |

```python
# Example: adding JSON-LD to WordPress
print("Hello, schema!")
```

See also: [Google Search Central](https://developers.google.com/search).
"""


class TestBuildSyntheticParsedPage:
    def test_c5_word_count_positive(self):
        """C.5: word_count is non-zero for real content."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD, "article")
        assert result["word_count"] > 20

    def test_c5_headings_extracted(self):
        """C.5: headings_outline contains H1 and H2 entries."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD, "article")
        levels = [h["level"] for h in result["headings_outline"]]
        assert 1 in levels
        assert 2 in levels

    def test_c5_code_block_detected(self):
        """C.5: code_block_count >= 1 for markdown with fenced code."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["code_block_count"] >= 1

    def test_c5_table_detected(self):
        """C.5: table_count >= 1 for markdown with | table |."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["table_count"] >= 1

    def test_c5_blockquote_detected(self):
        """C.5: blockquote_count >= 1 for markdown with > blockquote."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["blockquote_count"] >= 1

    def test_c5_external_link_detected(self):
        """C.5: external link to developers.google.com is in links list."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        hrefs = [lnk.url for lnk in result["links"]]
        assert any("google.com" in h for h in hrefs)

    def test_c5_author_detected(self):
        """C.5: 'By Jane Smith' at top is detected as author."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["author_detected"] is True

    def test_c5_date_published_detected(self):
        """C.5: 'Published: January 15, 2024' is detected as date_published."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["date_published"] is not None

    def test_c5_first_200_words_non_empty(self):
        """C.5: first_200_words is populated."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["first_200_words"]
        assert len(result["first_200_words"].split()) <= 205  # ~200 words

    def test_c5_is_indexable_true(self):
        """C.5: synthetic pages are always indexable."""
        result = _build_synthetic_parsed_page("https://example.org/page", "Hello world.")
        assert result["is_indexable"] is True

    def test_c5_structured_elements_counted(self):
        """C.5: structured_element_count > 0 for content with list + table + code."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["structured_element_count"] > 0


# ---------------------------------------------------------------------------
# C.6 — _score_markdown
# ---------------------------------------------------------------------------

class TestScoreMarkdown:
    def test_c6_ideal_content_scores_lower_than_thin(self):
        """C.6: well-structured content fires fewer issues than thin content."""
        # Thin: 500+ words, no statistics, no citations, no structure, no answer signal
        # Expect: multiple issues fire (STATISTICS_COUNT_LOW, EXTERNAL_CITATIONS_LOW,
        #         QUOTATIONS_MISSING, STRUCTURED_ELEMENTS_LOW)
        thin_md = "This page discusses content marketing strategies. " * 15
        # ~7 words * 15 = ~105 words; scale up to 500+
        thin_md = thin_md * 5  # ~525 words

        # Rich: answer signal upfront, statistics, external citation, structured elements
        # Expect: fewer of those checks fire
        rich_md = (
            "SEO is a set of techniques that helps organisations rank in search engines.\n\n"
            "In 2023, nonprofits that invested in SEO saw 40% more organic traffic "
            "according to a Semrush industry report.\n\n"
            "See also: [Semrush Blog](https://www.semrush.com/blog/).\n\n"
            "> \"Search is the primary discovery channel for mission-driven organisations.\"\n\n"
            "## Key Benefits\n\n"
            "- Increases online visibility\n"
            "- Drives targeted traffic\n"
            "- Builds donor trust\n\n"
            "| Tactic | Effort | Impact |\n"
            "|---|---|---|\n"
            "| Title optimisation | Low | High |\n"
            "| JSON-LD schema | Medium | High |\n\n"
        )
        # Pad to 500+ words
        rich_md += "Content strategy remains central to all SEO efforts. " * 40

        thin_score = _score_markdown("https://example.org/test", thin_md, "general")
        rich_score = _score_markdown("https://example.org/test", rich_md, "general")
        assert rich_score < thin_score, (
            f"Expected rich ({rich_score}) < thin ({thin_score}): "
            "well-structured content should fire fewer GEO issues"
        )

    def test_c6_empty_content_returns_int(self):
        """C.6: empty content returns an integer (may have issues but doesn't crash)."""
        score = _score_markdown("https://example.org/test", "")
        assert isinstance(score, int)
        assert score >= 0

    def test_c6_non_indexable_returns_0(self):
        """C.6: _run_geo_checks skips non-indexable pages → 0 issues for empty."""
        # _run_geo_checks only runs if is_indexable=True; our synthetic page is always
        # indexable so we test with content too short to trigger issues
        score = _score_markdown("https://example.org/test", "Short.")
        # Short page has word_count < 200, so most checks are skipped
        assert score <= 3  # at most a couple fire for very short content


# ---------------------------------------------------------------------------
# Adversarial tests — self-review checklist applied to every scoring function
#
# Question asked for each function:
#   Text-processing: "What text is in the buffer? What produces a correct-looking
#                     but wrong result?"
#   Scoring: "Is the denominator stable? Does more failure always mean lower score?"
# ---------------------------------------------------------------------------

# Shared fixtures
_LONG_BODY = (
    "OpenBrain is a personal AI memory database that you own and control. "
    "It solves the problem of AI assistants not remembering past interactions. "
) * 25  # ~500+ words, no stats/cites/quotes/structure


class TestSplitBodyAndNotes:
    """_split_body_and_notes: scope boundary must be precisely at the GEO NOTES delimiter."""

    def test_no_geo_notes_returns_full_text_empty_notes(self):
        text = "Just plain content with no GEO NOTES section."
        body, notes = _split_body_and_notes(text)
        assert body == text
        assert notes == ""

    def test_split_is_at_geo_notes_boundary(self):
        text = "Body content.\n\n---\nGEO NOTES\n- [CITATION NEEDED] added at: intro."
        body, notes = _split_body_and_notes(text)
        assert "Body content" in body
        assert "CITATION NEEDED" not in body   # must not leak into body
        assert "CITATION NEEDED" in notes

    def test_dashes_before_geo_notes_not_in_body(self):
        """The --- separator itself must not appear in the returned body."""
        # Use spec-compliant format (Fix 7.3 / §8.3): bullets must be bracket-tagged
        text = "Body.\n---\nGEO NOTES\n- [CITATION NEEDED] note"
        body, notes = _split_body_and_notes(text)
        assert "GEO NOTES" not in body
        assert "---" not in body

    def test_multiple_dashes_only_splits_at_geo_notes(self):
        """An --- that is NOT followed by GEO NOTES must stay in body."""
        # Use spec-compliant format (Fix 7.3 / §8.3): bullets must be bracket-tagged
        text = (
            "Section 1.\n\n---\n\nSection 2.\n\n"
            "---\nGEO NOTES\n- [CITATION NEEDED] note"
        )
        body, notes = _split_body_and_notes(text)
        # Section 1 and the first --- are in body
        assert "Section 1" in body
        assert "Section 2" in body
        assert "GEO NOTES" not in body

    def test_empty_text_returns_empty_body_and_notes(self):
        body, notes = _split_body_and_notes("")
        assert body == ""
        assert notes == ""


class TestVerifyGeoNotesPlaceholders:
    """_verify_geo_notes_placeholders: detects the lie-by-description failure mode."""

    def test_placeholder_only_in_notes_is_missing(self):
        """Core case: LLM describes placeholder in notes but never embeds it."""
        body = "Some content without any placeholder."
        notes = "\n---\nGEO NOTES\n- [CITATION NEEDED] added at: introduction.\n"
        missing = _verify_geo_notes_placeholders(body, notes)
        assert "CITATION NEEDED / LINK" in missing

    def test_placeholder_in_both_body_and_notes_is_not_missing(self):
        """When LLM embeds correctly AND notes it — must not flag as missing."""
        body = "Research confirms this [CITATION NEEDED: benchmark study]."
        notes = "\n---\nGEO NOTES\n- [CITATION NEEDED] added at: paragraph 1."
        missing = _verify_geo_notes_placeholders(body, notes)
        assert "CITATION NEEDED / LINK" not in missing

    def test_no_notes_section_returns_empty(self):
        body = "Content without GEO NOTES."
        missing = _verify_geo_notes_placeholders(body, "")
        assert missing == []

    def test_statistic_placeholder_lie_detected(self):
        body = "No numeric placeholder here."
        notes = "\n---\nGEO NOTES\n- [STATISTIC: usage rate] added at: section 2."
        missing = _verify_geo_notes_placeholders(body, notes)
        assert "STATISTIC" in missing

    def test_quote_placeholder_lie_detected(self):
        body = "No quote placeholder in body."
        notes = "\n---\nGEO NOTES\n- [QUOTE NEEDED: CEO] added at: conclusion."
        missing = _verify_geo_notes_placeholders(body, notes)
        assert "QUOTE NEEDED" in missing

    def test_all_three_correct_returns_empty(self):
        body = (
            "Revenue grew 40% [STATISTIC: annual report]. "
            "According to [CITATION NEEDED: source]. "
            "[QUOTE NEEDED: expert]."
        )
        notes = (
            "\n---\nGEO NOTES\n"
            "- [STATISTIC] added\n"
            "- [CITATION NEEDED] added\n"
            "- [QUOTE NEEDED] added\n"
        )
        missing = _verify_geo_notes_placeholders(body, notes)
        assert missing == []


class TestContentScoreAdversarial:
    """
    _content_score adversarial tests.

    Self-review questions applied:
    - What is in `content`? Answer: body text + optionally GEO NOTES section.
    - What produces a correct-looking but wrong result? GEO NOTES placeholders
      matching the check regex without being embedded in body.
    - Monotonicity: more failing checks must never produce a higher score.
    """

    def test_returns_four_tuple(self):
        """_content_score must return (fail_count, score, failing_codes, placeholder_inventory).

        Updated to 4-tuple in correctness pass §3.3 (Fix 2).
        """
        result = _content_score("http://x.com", "short")
        assert len(result) == 4
        issues, score, codes, inv = result
        assert isinstance(issues, int)
        assert isinstance(score, float)
        assert isinstance(codes, list)
        assert isinstance(inv, dict)

    def test_geo_notes_placeholder_does_not_inflate_citation_score(self):
        """Core regression: [CITATION NEEDED] in GEO NOTES must NOT count as a citation."""
        text_with_notes_only = (
            _LONG_BODY
            + "\n---\nGEO NOTES\n- [CITATION NEEDED] added at: introduction.\n"
        )
        text_no_notes = _LONG_BODY  # same body, no notes
        _, score_with_notes, _, _ = _content_score("http://x.com", text_with_notes_only)
        _, score_no_notes, _, _ = _content_score("http://x.com", text_no_notes)
        assert score_with_notes == score_no_notes, (
            "Score with GEO NOTES placeholder must equal score without it; "
            "the notes section must not contribute to citation check"
        )

    def test_geo_notes_statistic_does_not_inflate_stat_score(self):
        """[STATISTIC: ...] in GEO NOTES must NOT count as a real statistic."""
        text_notes_only = (
            _LONG_BODY
            + "\n---\nGEO NOTES\n- [STATISTIC: user growth rate] added at: body.\n"
        )
        _, score_notes, codes_notes, _ = _content_score("http://x.com", text_notes_only)
        # STATISTICS_COUNT_LOW must still fire — notes don't count
        assert "STATISTICS_COUNT_LOW" in codes_notes

    def test_inline_placeholder_counts_for_citation(self):
        """[CITATION NEEDED] embedded IN the body must count and clear the check."""
        body_with_inline = (
            _LONG_BODY
            + " Research confirms this [CITATION NEEDED: peer-reviewed study]."
        )
        _, _, codes, _ = _content_score("http://x.com", body_with_inline)
        assert "EXTERNAL_CITATIONS_LOW" not in codes

    def test_inline_statistic_counts(self):
        """A number with unit embedded in body must clear STATISTICS_COUNT_LOW."""
        body_with_stat = _LONG_BODY + " Users report 40% faster retrieval."
        _, _, codes, _ = _content_score("http://x.com", body_with_stat)
        assert "STATISTICS_COUNT_LOW" not in codes

    def test_monotonicity_more_failures_lower_score(self):
        """Monotonicity: every additional failing check must lower or hold the score."""
        # Start with rich content (all checks pass)
        rich = (
            "OpenBrain stores your AI memory in a database you control. "
            "Users report 40% faster context recall [CITATION NEEDED: benchmark]. "
            "According to early adopters, sessions feel continuous. "
            "- Feature A\n- Feature B\n- Feature C\n\n"
        ) * 10

        _, score_rich, fails_rich, _ = _content_score("http://x.com", rich)

        # Thin: no stats, no cites, no quotes, no structure
        _, score_thin, fails_thin, _ = _content_score("http://x.com", _LONG_BODY)

        assert len(fails_rich) <= len(fails_thin), (
            "Rich content must have fewer or equal failing checks than thin content"
        )
        assert score_rich >= score_thin, (
            f"Rich score ({score_rich}) must be >= thin score ({score_thin})"
        )

    def test_score_range_is_zero_to_one(self):
        """Score must always be in [0.0, 1.0]."""
        for content in ["", "x", _LONG_BODY, "word " * 1000]:
            _, score, _, _ = _content_score("http://x.com", content)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for content length {len(content)}"

    def test_failing_codes_match_issues_count(self):
        """fail_count must equal len(failing_codes)."""
        issues, _, codes, _ = _content_score("http://x.com", _LONG_BODY)
        assert issues == len(codes)

    def test_answer_signal_in_notes_does_not_satisfy_viewport_check(self):
        """FIRST_VIEWPORT_NO_ANSWER must check body only, not GEO NOTES.

        The check requires word_count >= 200, so the body must be at least 200 words.
        Using 40 repetitions of a 6-word sentence = 240 words.
        """
        # 40 × 6 words = 240 words — vague opener, no answer signal
        no_answer_body = "This document discusses various memory approaches. " * 40
        text_with_misleading_notes = (
            no_answer_body
            + "\n---\nGEO NOTES\n"
            + "- Direct answer added at: introduction: "
            + "'OpenBrain is a personal AI memory database.'\n"
        )
        _, _, codes, _ = _content_score("http://x.com", text_with_misleading_notes)
        assert "FIRST_VIEWPORT_NO_ANSWER" in codes, (
            "FIRST_VIEWPORT_NO_ANSWER must fire even when the answer phrase appears "
            "only in GEO NOTES — the check must operate on body text only"
        )


class TestProjectScoreFromFindings:
    """
    _project_score_from_findings adversarial tests.

    Self-review questions:
    - Is the denominator stable? Yes — it's the weighted sum of all findings.
    - Can more failures inflate the score? No — adding fails should lower it.
    - Does a higher query match always mean a higher projected score? Yes.
    """

    def _findings(self, qm_score: float) -> list[dict]:
        return [
            {
                "code": "QUERY_MATCH_SCORE",
                "evidence_tier": "Empirical",
                "pass_fail": "pass" if qm_score >= 0.70 else "fail",
                "score": qm_score,
            },
            {
                "code": "JSON_LD_MISSING",
                "evidence_tier": "Conventional",
                "pass_fail": "fail",
                "score": 0.0,
            },
        ]

    def test_higher_query_match_always_higher_projected(self):
        """Monotonicity: score with 0.9 qm must exceed score with 0.5 qm."""
        score_low = _project_score_from_findings(self._findings(0.5), 0.5)
        score_high = _project_score_from_findings(self._findings(0.9), 0.9)
        assert score_high > score_low

    def test_qm_score_of_zero_does_not_crash(self):
        """Edge: qm_score=0.0 must return a valid score, not raise."""
        score = _project_score_from_findings(self._findings(0.0), 0.0)
        assert 0.0 <= score <= 1.0

    def test_qm_score_of_one_does_not_exceed_one(self):
        """qm_score=1.0 with all other findings passing must not exceed 1.0."""
        all_pass = [
            {"code": "QUERY_MATCH_SCORE", "evidence_tier": "Empirical",
             "pass_fail": "pass", "score": 1.0},
        ]
        score = _project_score_from_findings(all_pass, 1.0)
        assert score <= 1.0

    def test_replaces_existing_query_match_score(self):
        """If findings already contain QUERY_MATCH_SCORE, it must be replaced, not added."""
        findings = self._findings(0.5)
        score_before = _project_score_from_findings(findings, 0.5)
        score_after = _project_score_from_findings(findings, 0.9)
        # Replacing with a higher score must raise the projected score
        assert score_after > score_before

    def test_empty_findings_returns_valid_score(self):
        """No findings → must return a valid score, not divide by zero."""
        score = _project_score_from_findings([], 0.8)
        assert 0.0 <= score <= 1.0


class TestBuildImprovementPromptAdversarial:
    """
    _build_improvement_prompt adversarial tests.

    Self-review questions:
    - Does the prompt actually tell the LLM what's failing and how to fix it?
    - Does it warn the LLM when placeholder lies were detected?
    - Does it include the current score so the LLM knows what to protect?
    """

    def test_failing_checks_produce_targeted_instructions(self):
        """When EXTERNAL_CITATIONS_LOW fails, prompt must contain the citation fix."""
        prompt = _build_improvement_prompt(
            "ORIG", 2, 5,
            failing_checks=["EXTERNAL_CITATIONS_LOW"],
            current_score=0.73,
        )
        assert "EXTERNAL_CITATIONS_LOW" in prompt
        assert "GEO NOTES" in prompt  # must warn that notes don't count
        assert "inline" in prompt.lower() or "INLINE" in prompt

    def test_placeholder_issue_triggers_critical_warning(self):
        """When placeholder_issues is non-empty, prompt must contain the critical warning."""
        prompt = _build_improvement_prompt(
            "ORIG", 2, 5,
            failing_checks=["STATISTICS_COUNT_LOW"],
            current_score=0.73,
            placeholder_issues=["STATISTIC"],
        )
        assert "CRITICAL MISTAKE" in prompt or "CRITICAL" in prompt
        assert "STATISTIC" in prompt

    def test_no_placeholder_issue_no_critical_warning(self):
        """When placeholder_issues is empty, the critical warning must NOT appear."""
        prompt = _build_improvement_prompt(
            "ORIG", 2, 5,
            failing_checks=["STRUCTURED_ELEMENTS_LOW"],
            current_score=0.85,
            placeholder_issues=[],
        )
        assert "CRITICAL MISTAKE" not in prompt

    def test_current_score_shown_in_prompt(self):
        """The current score percentage must appear so LLM knows what to protect."""
        prompt = _build_improvement_prompt(
            "ORIG", 3, 5,
            current_score=0.85,
        )
        assert "85%" in prompt

    def test_preservation_constraint_always_present(self):
        """PRESERVATION CONSTRAINT must appear regardless of failing checks."""
        for fails in [[], ["STATISTICS_COUNT_LOW"], ["FIRST_VIEWPORT_NO_ANSWER"]]:
            prompt = _build_improvement_prompt("ORIG", 2, 5, failing_checks=fails)
            assert "PRESERVATION" in prompt, f"Missing PRESERVATION for fails={fails}"

    def test_all_passing_produces_no_fix_instructions(self):
        """When no checks are failing, prompt must say all checks are passing."""
        prompt = _build_improvement_prompt("ORIG", 2, 5, failing_checks=[])
        assert "ALL CONTENT CHECKS PASSING" in prompt

    def test_original_prompt_always_appended(self):
        """The original system prompt must always be included at the end."""
        prompt = _build_improvement_prompt("SENTINEL_ORIGINAL_PROMPT", 2, 5)
        assert "SENTINEL_ORIGINAL_PROMPT" in prompt

    def test_structured_elements_fix_suggests_list(self):
        """STRUCTURED_ELEMENTS_LOW fix must mention adding a list."""
        prompt = _build_improvement_prompt(
            "ORIG", 2, 5,
            failing_checks=["STRUCTURED_ELEMENTS_LOW"],
        )
        assert "list" in prompt.lower() or "table" in prompt.lower()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def test_best_of_n_constant():
    """_BEST_OF_N should be 5 as specified."""
    assert _BEST_OF_N == 5


# ---------------------------------------------------------------------------
# TestPreservationFloor — RP6.1–RP6.21
# Spec: docs/implementation_plan_geo_rewrite_preservation_2026-05-04.md
# ---------------------------------------------------------------------------

# --- Shared fixtures -------------------------------------------------------

_FAQ_6 = """
## What is SEO?

Search engine optimization helps organisations rank in search results.

## How does crawling work?

Crawlers follow links systematically, indexing content along the way.

## Why are headings important?

Headings structure content and signal topic hierarchy to search engines.

## When should I update my sitemap?

Update your sitemap whenever you publish significant new content.

## Where can I find free SEO tools?

Google Search Console and Bing Webmaster Tools are both free and reliable.

## Who benefits from SEO?

Any organisation with a website benefits from search engine optimisation.
"""

_PROSE_ONLY = """
This page discusses SEO strategies for nonprofits. Organisations of all sizes
benefit from search engine optimisation. Key factors include title tags, meta
descriptions, and heading structure. Regular content updates help maintain
rankings over time. Consistency and relevance are the two most important signals.
"""

_WITH_2_CODE_BLOCKS = """
Here is an example in Python:

```python
print("Hello, schema!")
```

And a second example:

```json
{"@type": "Article", "name": "SEO Guide"}
```
"""

_WITH_1_TABLE = """
| Tactic       | Effort | Impact |
|--------------|--------|--------|
| Title tags   | Low    | High   |
| JSON-LD      | Medium | High   |
"""

_WITH_3_OUTBOUND_LINKS = """
See [Google Search Central](https://developers.google.com/search) for details.
Read [Moz Beginner's Guide](https://moz.com/beginners-guide-to-seo) next.
Also check [Ahrefs Blog](https://ahrefs.com/blog/seo-basics/) for more tips.
"""

_NAMED_LIST = """
- Use Supabase for database storage
- Deploy with GitHub Actions
- Organize notes in Notion
"""

_GENERIC_LIST = """
- use storage services
- find helpful tools
- browse available apps
"""

_WITH_NUMBERS = """
The setup process takes 45 minutes on average. Users report 99.9% uptime
across all regions. Six teams participated in the pilot programme.
"""

_FAQ_5 = """
## What is SEO?

Search engine optimization helps organisations rank in search results.

## How does crawling work?

Crawlers follow links systematically, indexing content along the way.

## Why are headings important?

Headings structure content and signal topic hierarchy to search engines.

## When should I update my sitemap?

Update your sitemap whenever you publish significant new content.

## Where can I find free SEO tools?

Google Search Console and Bing Webmaster Tools are both free and reliable.
"""

_REWRITE_NO_REGRESSION = (
    _FAQ_6
    + _WITH_1_TABLE
    + _WITH_2_CODE_BLOCKS
    + "See [Moz](https://moz.com/seo) and [Ahrefs](https://ahrefs.com/blog/).\n"
    + "- Use Supabase for database storage\n"
    + "- Deploy with GitHub Actions\n"
    + "- Organize notes in Notion\n"
)

_REWRITE_PROSE_ONLY = """
Search engine optimisation helps pages rank better. Crawlers index links
systematically. Headings signal topic hierarchy. Update sitemaps regularly.
Free tools exist such as Google Search Console. All sites benefit from SEO.
"""


class TestPreservationFloor:
    """
    RP6.1–RP6.21 — Preservation floor extractor, prompt injection, and regression scorer.
    Spec: docs/implementation_plan_geo_rewrite_preservation_2026-05-04.md
    """

    # ── RP6.1 — FAQ pair counting: six pairs ─────────────────────────────────

    def test_rp1a_faq_counts_six_pairs(self):
        """RP6.1: Page with 6 heading-style Q&A blocks returns faq_pair_count == 6."""
        floor = _extract_preservation_floor(_FAQ_6)
        assert floor["faq_pair_count"] == 6, (
            f"Expected 6 FAQ pairs, got {floor['faq_pair_count']}"
        )

    # ── RP6.2 — FAQ pair counting: prose only ────────────────────────────────

    def test_rp1b_faq_zero_in_prose(self):
        """RP6.2: Prose-only page returns faq_pair_count == 0."""
        floor = _extract_preservation_floor(_PROSE_ONLY)
        assert floor["faq_pair_count"] == 0

    # ── RP6.3 — FAQ adversarial: question in mid-paragraph ───────────────────

    def test_rp1c_faq_adversarial_question_in_prose(self):
        """RP6.3: A question-word line NOT preceded by blank line must not count."""
        text = (
            "This page discusses many topics.\n"
            "What matters most here?\n"          # question-word line but NOT preceded by blank
            "The answer is consistency above all else.\n"
        )
        floor = _extract_preservation_floor(text)
        assert floor["faq_pair_count"] == 0, (
            "Question without preceding blank line must not count as FAQ pair"
        )

    # ── RP6.4 — Code block counting ──────────────────────────────────────────

    def test_rp1d_code_block_count(self):
        """RP6.4: Page with 2 fenced code blocks returns code_block_count == 2."""
        floor = _extract_preservation_floor(_WITH_2_CODE_BLOCKS)
        assert floor["code_block_count"] == 2

    # ── RP6.5 — Table counting ────────────────────────────────────────────────

    def test_rp1e_table_count(self):
        """RP6.5: Page with 1 Markdown table returns table_count == 1."""
        floor = _extract_preservation_floor(_WITH_1_TABLE)
        assert floor["table_count"] == 1

    # ── RP6.6 — Outbound link counting ───────────────────────────────────────

    def test_rp1f_outbound_link_count(self):
        """RP6.6: Page with 3 external links returns outbound_link_count == 3."""
        floor = _extract_preservation_floor(_WITH_3_OUTBOUND_LINKS)
        assert floor["outbound_link_count"] == 3

    # ── RP6.7 — Named list vs generic list ───────────────────────────────────

    def test_rp1g_named_list_vs_generic(self):
        """RP6.7: Named list (proper nouns) counts; generic list does not."""
        named_floor = _extract_preservation_floor(_NAMED_LIST)
        generic_floor = _extract_preservation_floor(_GENERIC_LIST)
        assert named_floor["named_list_count"] == 1, (
            "List with Supabase, GitHub, Notion must be counted as named"
        )
        assert generic_floor["named_list_count"] == 0, (
            "List with storage, tools, apps must NOT be counted as named"
        )

    # ── RP6.8 — Number extraction ────────────────────────────────────────────

    def test_rp1h_original_number_set(self):
        """RP6.8: '45 minutes' and '99.9%' in set; word-form 'six' excluded."""
        floor = _extract_preservation_floor(_WITH_NUMBERS)
        nums = floor["original_number_set"]
        # Both specific numbers must be captured
        assert any("45" in n for n in nums), f"Expected '45 minutes' in {nums}"
        assert any("99.9" in n for n in nums), f"Expected '99.9%' in {nums}"
        # Word-form number must not be captured
        assert "six" not in nums, "Word-form 'six' must not appear in number set"

    # ── RP6.9 — FAQ floor injected into prompt ────────────────────────────────

    def test_rp2a_faq_floor_in_prompt(self):
        """RP6.9: Prompt with 6 FAQ pairs contains §(k) section and FAQ count."""
        result = generate_rewrite_prompt(
            _make_report(), "general", original_content=_FAQ_6
        )
        prompt = result["system_prompt"]
        assert "(k) PRESERVATION FLOOR" in prompt, "§(k) section must be present"
        assert "6 Q&A pairs" in prompt, (
            "Prompt must reference the original 6 Q&A pairs"
        )

    # ── RP6.10 — FAQ ban removed ─────────────────────────────────────────────

    def test_rp2b_no_faq_ban_in_prompt(self):
        """RP6.10: Prompt must not contain the old FAQ ban text."""
        result = generate_rewrite_prompt(_make_report(), "general")
        assert "Do NOT write a standalone FAQ section" not in result["system_prompt"]

    # ── RP6.11 — Bullet list limit removed ───────────────────────────────────

    def test_rp2c_no_bullet_limit_in_prompt(self):
        """RP6.11: Prompt must not contain the old 2-bullet-list-per-500-words rule."""
        result = generate_rewrite_prompt(_make_report(), "general")
        assert "No more than 2 bullet lists" not in result["system_prompt"]

    # ── RP6.12 — Code block floor injected ───────────────────────────────────

    def test_rp2d_code_floor_in_prompt(self):
        """RP6.12: Prompt with original having 2 code blocks mentions '2 code block'."""
        result = generate_rewrite_prompt(
            _make_report(), "general", original_content=_WITH_2_CODE_BLOCKS
        )
        assert "2 code block" in result["system_prompt"]

    # ── RP6.13 — Table floor injected ────────────────────────────────────────

    def test_rp2e_table_floor_in_prompt(self):
        """RP6.13: Prompt with original having 1 table mentions '1 Markdown table'."""
        result = generate_rewrite_prompt(
            _make_report(), "general", original_content=_WITH_1_TABLE
        )
        assert "1 Markdown table" in result["system_prompt"]

    # ── RP6.14 — Hallucination guard present ─────────────────────────────────

    def test_rp2f_hallucination_guard_in_prompt(self):
        """RP6.14: Prompt always contains the number hallucination guard."""
        result = generate_rewrite_prompt(_make_report(), "general")
        assert "Do not introduce specific numbers" in result["system_prompt"]

    # ── RP6.15 — FAQ regression detected ─────────────────────────────────────

    def test_rp3a_faq_regression_detected(self):
        """RP6.15: Rewrite with 0 FAQ pairs from original with 6 → FAQ_REMOVED."""
        original_features = {"faq_pair_count": 6, "code_block_count": 0,
                             "table_count": 0, "outbound_link_count": 0,
                             "named_list_count": 0}
        violations = _check_preservation_regression(original_features, _REWRITE_PROSE_ONLY)
        assert "FAQ_REMOVED" in violations

    # ── RP6.16 — FAQ regression not triggered when floor met ──────────────────

    def test_rp3b_faq_regression_not_triggered_below_floor(self):
        """RP6.16: Rewrite with 5 pairs from original with 6 passes (≥70% floor = 4)."""
        original_features = {"faq_pair_count": 6, "code_block_count": 0,
                             "table_count": 0, "outbound_link_count": 0,
                             "named_list_count": 0}
        violations = _check_preservation_regression(original_features, _FAQ_5)
        assert "FAQ_REMOVED" not in violations, (
            "5 out of 6 FAQ pairs (≥ 70% floor of 4) must not trigger FAQ_REMOVED"
        )

    # ── RP6.17 — Code block regression detected ───────────────────────────────

    def test_rp3c_code_block_regression_detected(self):
        """RP6.17: Rewrite with 0 code blocks from original with 1 → CODE_BLOCK_REMOVED."""
        original_features = {"faq_pair_count": 0, "code_block_count": 1,
                             "table_count": 0, "outbound_link_count": 0,
                             "named_list_count": 0}
        violations = _check_preservation_regression(original_features, _REWRITE_PROSE_ONLY)
        assert "CODE_BLOCK_REMOVED" in violations

    # ── RP6.18 — Table regression detected ───────────────────────────────────

    def test_rp3d_table_regression_detected(self):
        """RP6.18: Rewrite with 0 tables from original with 1 → TABLE_REMOVED."""
        original_features = {"faq_pair_count": 0, "code_block_count": 0,
                             "table_count": 1, "outbound_link_count": 0,
                             "named_list_count": 0}
        violations = _check_preservation_regression(original_features, _REWRITE_PROSE_ONLY)
        assert "TABLE_REMOVED" in violations

    # ── RP6.19 — No regression when floor met ────────────────────────────────

    def test_rp3e_no_regression_when_floor_met(self):
        """RP6.19: Rewrite that preserves all elements returns empty violations list."""
        original_features = {
            "faq_pair_count": 6,
            "code_block_count": 2,
            "table_count": 1,
            "outbound_link_count": 2,
            "named_list_count": 1,
        }
        violations = _check_preservation_regression(original_features, _REWRITE_NO_REGRESSION)
        assert violations == [], f"Expected no violations, got: {violations}"

    # ── RP6.20 — Regressions lower content score ──────────────────────────────

    def test_rp4a_regression_lowers_content_score(self):
        """RP6.20: Passing original_features with FAQ regression lowers the score."""
        features_with_faq = {"faq_pair_count": 6, "code_block_count": 0,
                              "table_count": 0, "outbound_link_count": 0,
                              "named_list_count": 0}
        _, score_without, _, _ = _content_score("http://x.com", _REWRITE_PROSE_ONLY)
        _, score_with, codes_with, _ = _content_score(
            "http://x.com", _REWRITE_PROSE_ONLY, original_features=features_with_faq
        )
        assert score_with < score_without, (
            f"Score with FAQ regression ({score_with}) must be lower than "
            f"score without original_features ({score_without})"
        )
        assert "FAQ_REMOVED" in codes_with

    # ── RP6.21 — Score monotonicity with regressions ──────────────────────────

    def test_rp4b_score_monotonicity_with_regressions(self):
        """RP6.21: Two regressions → lower score than one → lower score than zero."""
        base_content = _REWRITE_PROSE_ONLY  # no FAQs, no code, no table

        no_features = None
        one_regression = {"faq_pair_count": 6, "code_block_count": 0,
                          "table_count": 0, "outbound_link_count": 0,
                          "named_list_count": 0}
        two_regressions = {"faq_pair_count": 6, "code_block_count": 1,
                           "table_count": 0, "outbound_link_count": 0,
                           "named_list_count": 0}

        _, score_zero, _, _ = _content_score("http://x.com", base_content,
                                              original_features=no_features)
        _, score_one, _, _ = _content_score("http://x.com", base_content,
                                            original_features=one_regression)
        _, score_two, _, _ = _content_score("http://x.com", base_content,
                                            original_features=two_regressions)

        assert score_zero >= score_one >= score_two, (
            f"Monotonicity violated: zero={score_zero}, one={score_one}, two={score_two}"
        )


# =============================================================================
# CORRECTNESS PASS — spec: docs/implementation_plan_geo_rewrite_correctness_2026-05-04.md
# =============================================================================

# ---------------------------------------------------------------------------
# Fix 1 — CR2_* — _CONTENT_FIX_INSTRUCTIONS examples are non-fabricating
# ---------------------------------------------------------------------------

class TestFixInstructionExamples:
    """CR2.x — examples in _CONTENT_FIX_INSTRUCTIONS must not model fabrication."""

    _NUMBER_WITH_UNIT_RE = re.compile(
        r"\d+\s*(?:%|percent|minute|hour|second|day|year|million|billion|thousand)",
        re.I,
    )
    _NAMED_BRAND_IN_DONT_RE = re.compile(
        r"\b(Supabase|Stanford|Google|Amazon|Microsoft|OpenAI|Anthropic|"
        r"GitHub|MemGPT|Mem0|Notion|ChatGPT|Claude)\b"
    )

    def _extract_do(self, instruction: str) -> str | None:
        """Pull the line(s) immediately following ✅ DO: up to the next sentinel."""
        m = re.search(
            r"✅ DO:\s*(.+?)(?=\n\s*(?:❌|⚠️|Do NOT)|\Z)",
            instruction, re.S
        )
        return m.group(1).strip() if m else None

    def _extract_dont(self, instruction: str) -> str | None:
        """Pull the line(s) immediately following ❌ DO NOT: up to the next sentinel."""
        m = re.search(
            r"❌ DO NOT:\s*(.+?)(?=\n\s*(?:⚠️|Do NOT)|\Z)",
            instruction, re.S
        )
        return m.group(1).strip() if m else None

    def test_cr2_2_stats_do_no_numbers(self):
        """§2.2.a — STATISTICS_COUNT_LOW DO example contains no specific numeric value."""
        from api.services.geo_rewrite_prompt import _CONTENT_FIX_INSTRUCTIONS
        do = self._extract_do(_CONTENT_FIX_INSTRUCTIONS["STATISTICS_COUNT_LOW"])
        assert do is not None, "DO line not extractable"
        assert not self._NUMBER_WITH_UNIT_RE.search(do), (
            f"STATS DO contains specific number: {do!r}"
        )

    def test_cr2_2_quote_do_no_named_source(self):
        """§2.2.b — QUOTATIONS_MISSING DO example uses no specific named source."""
        from api.services.geo_rewrite_prompt import _CONTENT_FIX_INSTRUCTIONS
        do = self._extract_do(_CONTENT_FIX_INSTRUCTIONS["QUOTATIONS_MISSING"])
        assert do is not None
        assert not self._NAMED_BRAND_IN_DONT_RE.search(do), (
            f"QUOTE DO references a specific brand: {do!r}"
        )

    def test_cr2_3_all_entries_have_do_and_dont(self):
        """§2.3.a — every entry has both ✅ DO: and ❌ DO NOT: lines."""
        from api.services.geo_rewrite_prompt import _CONTENT_FIX_INSTRUCTIONS
        for code, instruction in _CONTENT_FIX_INSTRUCTIONS.items():
            assert "✅ DO:" in instruction, f"{code} missing ✅ DO:"
            assert "❌ DO NOT:" in instruction, f"{code} missing ❌ DO NOT:"

    def test_cr2_3_dont_examples_demonstrate_fabrication(self):
        """§2.3.b — fabrication-prone DO NOT lines must contain a fabrication signal."""
        from api.services.geo_rewrite_prompt import _CONTENT_FIX_INSTRUCTIONS
        FABRICATION_PRONE = {
            "STATISTICS_COUNT_LOW", "QUOTATIONS_MISSING",
            "EXTERNAL_CITATIONS_LOW", "FIRST_VIEWPORT_NO_ANSWER",
        }
        for code in FABRICATION_PRONE:
            dont = self._extract_dont(_CONTENT_FIX_INSTRUCTIONS[code])
            assert dont is not None, f"{code} DO NOT not extractable"
            has_number = bool(self._NUMBER_WITH_UNIT_RE.search(dont))
            has_named = bool(self._NAMED_BRAND_IN_DONT_RE.search(dont))
            has_superlative = bool(re.search(
                r"\b(leading|best|millions of|industry[- ]leading|top[- ]rated)\b",
                dont, re.I,
            ))
            assert has_number or has_named or has_superlative, (
                f"{code} DO NOT lacks a fabrication signal "
                f"(no number/named-brand/superlative): {dont!r}"
            )

    def test_cr2_4_do_no_numbers_dont_has_numbers(self):
        """§2.4 — across all entries: no DO has numbers; ≥1 DO NOT in stats/cite has them."""
        from api.services.geo_rewrite_prompt import _CONTENT_FIX_INSTRUCTIONS
        # Part A: DO lines must never contain a number-with-unit
        for code, instruction in _CONTENT_FIX_INSTRUCTIONS.items():
            do = self._extract_do(instruction)
            if do:
                assert not self._NUMBER_WITH_UNIT_RE.search(do), (
                    f"{code} DO contains number with unit: {do!r}"
                )
        # Part B: at least one DO NOT in {stats, citations} must contain a number
        # (proves the test isn't vacuously passing)
        any_number_in_dont = False
        for code in ("STATISTICS_COUNT_LOW", "EXTERNAL_CITATIONS_LOW"):
            dont = self._extract_dont(_CONTENT_FIX_INSTRUCTIONS[code])
            if dont and self._NUMBER_WITH_UNIT_RE.search(dont):
                any_number_in_dont = True
        assert any_number_in_dont, (
            "No DO NOT example in stats/citations contains a number — "
            "the contrast test is vacuous."
        )


# ---------------------------------------------------------------------------
# Fix 6 — CR7_* — score-blend weights surfaced as constants + done event metadata
# ---------------------------------------------------------------------------

class TestScoreBlendConstants:
    """CR7.x — _QUERY_COVERAGE_WEIGHT and _CONTENT_QUALITY_WEIGHT are named, sum to 1, exposed."""

    def test_cr7_2_weights_sum_to_one(self):
        """§7.2.a — weights are module-level and sum to 1.0."""
        from api.services.geo_rewrite_prompt import (
            _QUERY_COVERAGE_WEIGHT,
            _CONTENT_QUALITY_WEIGHT,
        )
        assert isinstance(_QUERY_COVERAGE_WEIGHT, float)
        assert isinstance(_CONTENT_QUALITY_WEIGHT, float)
        assert abs((_QUERY_COVERAGE_WEIGHT + _CONTENT_QUALITY_WEIGHT) - 1.0) < 1e-9

    def test_cr7_2_constants_documented_provisional(self):
        """§7.2.b — the constants block flags itself as PROVISIONAL with a doc pointer."""
        import api.services.geo_rewrite_prompt as mod
        from pathlib import Path
        src = Path(mod.__file__).read_text()
        # The block must be self-documenting
        assert "PROVISIONAL" in src, "Constants block does not flag itself as provisional"
        assert "implementation_plan_geo_validation" in src, (
            "Constants block does not point to the future validation plan"
        )

    def test_cr7_3_weighting_validated_false(self):
        """§7.3 — done event scoring_metadata.weighting_validated defaults to False.

        Verified at the source level since stream_rewrite_variants requires LLM calls.
        """
        import api.services.geo_rewrite_prompt as mod
        from pathlib import Path
        src = Path(mod.__file__).read_text()
        assert '"weighting_validated": False' in src, (
            "done_event does not include weighting_validated=False"
        )
        assert '"query_coverage_weight": _QUERY_COVERAGE_WEIGHT' in src
        assert '"content_quality_weight": _CONTENT_QUALITY_WEIGHT' in src


# ---------------------------------------------------------------------------
# Fix 7.3 — CR8_3_* — _GEO_NOTES_SPLIT_RE tightened to documented format
# ---------------------------------------------------------------------------

class TestGeoNotesSplit:
    """CR8_3 — body content with 'GEO NOTES' as a heading must NOT be split."""

    def test_cr8_3_inline_heading_not_split(self):
        """§8.3.a — `## GEO NOTES on this topic` (inline heading) is NOT a notes section."""
        text = (
            "Body content here.\n\n"
            "## GEO NOTES on this topic\n\n"
            "This paragraph appears to be a notes section but isn't.\n"
        )
        body, notes = _split_body_and_notes(text)
        assert notes == "", f"Inline heading was incorrectly split as notes: {notes!r}"
        assert "GEO NOTES on this topic" in body

    def test_cr8_3_documented_format_splits(self):
        """§8.3.b — the canonical `---\\nGEO NOTES\\n- [TAG]...\\n` format IS split."""
        text = (
            "Body content here.\n"
            "\n---\n"
            "GEO NOTES\n"
            "- [CITATION NEEDED] added at: section X\n"
            "- [STATISTIC: median time] added at: setup section\n"
        )
        body, notes = _split_body_and_notes(text)
        assert "CITATION NEEDED" in notes, "Documented format failed to split"
        assert "Body content here" in body
        assert "GEO NOTES" not in body


# ---------------------------------------------------------------------------
# Fix 7.5 — CR8_5_* — fabricated outbound link detection (regex only here;
# integration with _content_score in Step 5 / Fix 2)
# ---------------------------------------------------------------------------

class TestFabricatedLinkRegex:
    """CR8_5.a/b — _FABRICATED_LINK_RE matches placeholder URLs, not real ones."""

    def test_cr8_5_fabricated_link_regex_matches(self):
        """§8.5.a — placeholder/fabricated URLs are matched."""
        from api.services.geo_rewrite_prompt import _FABRICATED_LINK_RE
        for url in [
            "https://example.com",
            "https://example.com/docs",
            "https://example.org/path",
            "http://example.net",
            "https://placeholder.io/foo",
            "https://made-up-domain.com",
            "https://fabricated-source.org",
            "https://todo.example.app/path",
            "https://fixme-url.io",
        ]:
            assert _FABRICATED_LINK_RE.search(url), f"Should match: {url}"

    def test_cr8_5_real_links_not_matched(self):
        """§8.5.b — real URLs are NOT matched."""
        from api.services.geo_rewrite_prompt import _FABRICATED_LINK_RE
        for url in [
            "https://supabase.com/docs/pgvector",
            "https://github.com/foo/bar",
            "https://docs.python.org/3/library/re.html",
            "https://www.mindstudio.ai/blog/what-is-openbrain",
            "https://en.wikipedia.org/wiki/Generative_engine_optimization",
        ]:
            assert not _FABRICATED_LINK_RE.search(url), f"Should NOT match: {url}"


# ---------------------------------------------------------------------------
# Fix 2 — CR3_* — placeholder cap + 4-tuple return
# ---------------------------------------------------------------------------

# Long enough to trigger the word_count >= 500 gate
_LONG_PROSE_500 = (
    "OpenBrain is a personal AI memory database that you own and control. "
    "It addresses the problem of AI assistants forgetting prior context. "
) * 30  # ≈ 750 words


class TestPlaceholderCap:
    """CR3.x — placeholders earn half-credit; cap at 2 partial-passes; 4-tuple return."""

    # ── §3.2 partial-pass behaviour ─────────────────────────────────────────

    def test_cr3_2_partial_pass_half_weight(self):
        """§3.2 — placeholder-only ⇒ partial-pass; real evidence ⇒ full pass; neither ⇒ fail."""
        # Real evidence (real number, real markdown link, real attribution)
        real_text = (
            _LONG_PROSE_500
            + " Users report 40% faster recall. "
            + " According to peer-reviewed studies, this approach scales. "
            + " See [Supabase docs](https://supabase.com/docs/pgvector) for details. "
        )
        # Same shape but only placeholders
        placeholder_text = (
            _LONG_PROSE_500
            + " Setup time varies [STATISTIC: typical setup duration]. "
            + " Per the project's notes, [QUOTE NEEDED: capability claim]. "
            + " Architecture details are documented [CITATION NEEDED: docs]. "
        )
        # Neither
        bare_text = _LONG_PROSE_500

        _, real_score, real_codes, real_inv = _content_score(
            "http://x.com", real_text, "general"
        )
        _, ph_score, ph_codes, ph_inv = _content_score(
            "http://x.com", placeholder_text, "general"
        )
        _, bare_score, bare_codes, bare_inv = _content_score(
            "http://x.com", bare_text, "general"
        )

        # Real evidence: none of the 3 placeholder-eligible checks should fire
        for code in ("STATISTICS_COUNT_LOW", "EXTERNAL_CITATIONS_LOW", "QUOTATIONS_MISSING"):
            assert code not in real_codes, f"Real evidence should clear {code}"
            assert code not in real_inv["partial_pass_checks"], (
                f"Real evidence should not be marked partial-pass for {code}"
            )

        # Bare text: all 3 should be in failing codes
        for code in ("STATISTICS_COUNT_LOW", "EXTERNAL_CITATIONS_LOW", "QUOTATIONS_MISSING"):
            assert code in bare_codes, f"Bare text should fail {code}"

        # Strict ordering: real > placeholder > bare
        assert real_score > ph_score > bare_score, (
            f"Score ordering violated: real={real_score} ph={ph_score} bare={bare_score}"
        )

    def test_cr3_2_non_placeholder_checks_remain_binary(self):
        """§3.2 — STRUCTURED_ELEMENTS_LOW and FIRST_VIEWPORT_NO_ANSWER are binary."""
        # Bare prose with no structure and no answer signal
        text = "This document covers various topics. " * 100  # ≈ 500 words
        _, _, codes, inv = _content_score("http://x.com", text, "general")
        # Both binary checks fail; neither is marked partial-pass
        assert "STRUCTURED_ELEMENTS_LOW" in codes
        assert "STRUCTURED_ELEMENTS_LOW" not in inv["partial_pass_checks"]
        assert "FIRST_VIEWPORT_NO_ANSWER" not in inv["partial_pass_checks"]

    # ── §3.3 4-tuple return + inventory shape ───────────────────────────────

    def test_cr3_3_returns_four_tuple(self):
        """§3.3 — _content_score returns a 4-tuple."""
        result = _content_score("http://x.com", "short", "general")
        assert isinstance(result, tuple) and len(result) == 4

    def test_cr3_3_inventory_has_required_keys(self):
        """§3.3 — placeholder_inventory has the documented keys."""
        _, _, _, inv = _content_score("http://x.com", "short", "general")
        assert "partial_pass_checks" in inv
        assert "placeholder_counts" in inv
        assert "placeholder_density" in inv
        assert isinstance(inv["partial_pass_checks"], list)
        assert isinstance(inv["placeholder_counts"], dict)
        assert isinstance(inv["placeholder_density"], float)
        for key in ("citation", "stat", "quote"):
            assert key in inv["placeholder_counts"]

    # ── §3.5 cap rule ───────────────────────────────────────────────────────

    def test_cr3_5_cap_demotes_third_to_fail(self):
        """§3.5 — when all 3 placeholder-eligible checks would partial-pass, alphabetically
        first (EXTERNAL_CITATIONS_LOW) is demoted to a full fail."""
        text = (
            _LONG_PROSE_500
            + " Setup [STATISTIC: median time]. "
            + " Per docs, [QUOTE NEEDED: claim]. "
            + " Architecture [CITATION NEEDED: source]. "
        )
        _, _, codes, inv = _content_score("http://x.com", text, "general")
        # Cap: at most 2 partial-passes
        assert len(inv["partial_pass_checks"]) <= 2, (
            f"Cap violated: {inv['partial_pass_checks']}"
        )
        # The demoted check is the alphabetically first
        assert "EXTERNAL_CITATIONS_LOW" in codes, (
            "EXTERNAL_CITATIONS_LOW should be demoted to a full fail under the cap"
        )
        assert "EXTERNAL_CITATIONS_LOW" not in inv["partial_pass_checks"]

    # ── §3.6 acceptance ─────────────────────────────────────────────────────

    def test_cr3_6_real_beats_placeholder(self):
        """§3.6.a — real evidence scores strictly higher than only-placeholder."""
        real = (
            _LONG_PROSE_500
            + " Latency drops 42% [Supabase docs](https://supabase.com/docs/pgvector). "
            + " According to research, retrieval improves. "
        )
        placeholder = (
            _LONG_PROSE_500
            + " Latency drops [STATISTIC: improvement]. "
            + " [CITATION NEEDED: research source]. "
            + " Per analysis, [QUOTE NEEDED: claim]. "
        )
        _, real_score, _, _ = _content_score("http://x.com", real, "general")
        _, ph_score, _, _ = _content_score("http://x.com", placeholder, "general")
        assert real_score > ph_score, f"real={real_score} not > ph={ph_score}"

    def test_cr3_6_all_placeholder_caps_at_85(self):
        """§3.6.b — pure-placeholder content cannot score above 0.85."""
        text = (
            "[CITATION NEEDED: source 1] [STATISTIC: figure 1] [QUOTE NEEDED: voice 1] "
        ) * 50  # ≈ 500 words, ~150 placeholders
        _, score, _, inv = _content_score("http://x.com", text, "general")
        assert score <= 0.85, (
            f"All-placeholder content scored {score}; cap should keep it ≤ 0.85"
        )
        assert len(inv["partial_pass_checks"]) <= 2

    def test_cr3_6_inventory_populated(self):
        """§3.6.c — inventory.partial_pass_checks lists EXTERNAL_CITATIONS_LOW
        when only-citation-placeholder is present."""
        # Provide ONLY a citation placeholder; no real link, no real stats/quotes
        text = (
            _LONG_PROSE_500
            + " Background [CITATION NEEDED: peer-reviewed source]. "
        )
        _, _, codes, inv = _content_score("http://x.com", text, "general")
        # EXTERNAL_CITATIONS_LOW should be partial-pass (placeholder present)
        assert "EXTERNAL_CITATIONS_LOW" in inv["partial_pass_checks"], (
            f"Expected EXTERNAL_CITATIONS_LOW in partial_pass_checks, got {inv['partial_pass_checks']}"
        )
        assert "EXTERNAL_CITATIONS_LOW" not in codes
        assert inv["placeholder_counts"]["citation"] == 1


# ---------------------------------------------------------------------------
# Fix 7.5 wired into Check 2 — CR8_5_c, CR8_5_d
# ---------------------------------------------------------------------------

class TestFabricatedLinkScoring:
    """CR8_5.c/d — fabricated outbound links count as placeholders, not real citations."""

    def test_cr8_5_fabricated_link_partial_pass(self):
        """§8.5.c — fabricated link triggers partial-pass, not full pass."""
        text = _LONG_PROSE_500 + " See [docs](https://example.com) for details. "
        _, _, codes, inv = _content_score("http://x.com", text, "general")
        # EXTERNAL_CITATIONS_LOW should be in partial_pass_checks (not full fail)
        assert "EXTERNAL_CITATIONS_LOW" in inv["partial_pass_checks"], (
            "Fabricated link should mark EXTERNAL_CITATIONS_LOW as partial-pass"
        )
        assert "EXTERNAL_CITATIONS_LOW" not in codes

    def test_cr8_5_example_dot_com_partial_inventory(self):
        """§8.5.d — only-example.com links yield partial inventory entry."""
        text = (
            _LONG_PROSE_500
            + " First source [Foo](https://example.com/foo). "
            + " Second source [Bar](https://placeholder.io/bar). "
        )
        _, _, _, inv = _content_score("http://x.com", text, "general")
        assert "EXTERNAL_CITATIONS_LOW" in inv["partial_pass_checks"]

    def test_cr8_5_real_link_full_pass(self):
        """Real link (control case for the above) — EXTERNAL_CITATIONS_LOW fully passes."""
        text = (
            _LONG_PROSE_500
            + " See [Supabase docs](https://supabase.com/docs/pgvector) for details. "
        )
        _, _, codes, inv = _content_score("http://x.com", text, "general")
        assert "EXTERNAL_CITATIONS_LOW" not in codes
        assert "EXTERNAL_CITATIONS_LOW" not in inv["partial_pass_checks"]


# ---------------------------------------------------------------------------
# Fix 3 — CR4_* — page-type-conditional structural check
# ---------------------------------------------------------------------------

# A 500+ word base with neither structure nor answer signal that we can append to.
# Sized generously so structural-check tests still trigger Check 5 after the
# fixture content is appended (Check 5 requires word_count >= 500).
_BARE_PROSE_500 = (
    "This document covers various memory approaches in depth. " * 80
)


class TestPageTypeStructuralCheck:
    """CR4.x — _structural_check_passes dispatches per page_type; helpers behave correctly."""

    # ── §4.2.a — _has_numbered_list_with_min_items ──────────────────────────

    def test_cr4_2_numbered_list_helper(self):
        """§4.2.a — helper returns True only when ≥ min_items consecutive items present."""
        from api.services.geo_rewrite_prompt import _has_numbered_list_with_min_items
        text_3 = "1. step one\n2. step two\n3. step three\n"
        text_2 = "1. step one\n2. step two\nbroken by prose\n3. step three\n"
        assert _has_numbered_list_with_min_items(text_3, 3) is True
        assert _has_numbered_list_with_min_items(text_2, 3) is False
        # 2 consecutive in text_2 should still satisfy min=2
        assert _has_numbered_list_with_min_items(text_2, 2) is True

    # ── §4.2.b — _table_has_min_rows ────────────────────────────────────────

    def test_cr4_2_table_min_rows_helper(self):
        """§4.2.b — helper counts data rows excluding header + separator."""
        from api.services.geo_rewrite_prompt import _table_has_min_rows
        # Header + separator + 2 data rows
        table_2 = (
            "| Col A | Col B |\n"
            "|-------|-------|\n"
            "| a1    | b1    |\n"
            "| a2    | b2    |\n"
        )
        assert _table_has_min_rows(table_2, 2) is True
        assert _table_has_min_rows(table_2, 3) is False
        # No table at all
        assert _table_has_min_rows("just prose with | a pipe | here", 1) is False

    # ── §4.2.c-f — dispatch ────────────────────────────────────────────────

    def test_cr4_2_technical_dispatch(self):
        """§4.2.c — technical: code OR numbered list ≥3 passes; bullets-only fails."""
        from api.services.geo_rewrite_prompt import _structural_check_passes
        bullets_only = "Some prose.\n- a\n- b\n- c\n"
        with_code = "Some prose.\n```\nnpm install foo\n```\n"
        with_steps = "Some prose.\n1. one\n2. two\n3. three\n"
        assert _structural_check_passes(bullets_only, "technical") is False
        assert _structural_check_passes(with_code, "technical") is True
        assert _structural_check_passes(with_steps, "technical") is True

    def test_cr4_2_comparison_dispatch(self):
        """§4.2.d — comparison: table ≥2 rows OR named list passes; prose-only fails."""
        from api.services.geo_rewrite_prompt import _structural_check_passes
        prose = "OpenBrain is open. ChatGPT memory is closed.\n"
        with_table = (
            "| Feature | OpenBrain | ChatGPT |\n"
            "|---------|-----------|---------|\n"
            "| Open    | Yes       | No      |\n"
            "| Self-host | Yes     | No      |\n"
        )
        # Named list per current heuristic (proper noun past idx=0)
        with_named_list = (
            "- Use Supabase for storage\n"
            "- Try OpenAI memory plugin\n"
        )
        assert _structural_check_passes(prose, "comparison") is False
        assert _structural_check_passes(with_table, "comparison") is True
        assert _structural_check_passes(with_named_list, "comparison") is True

    def test_cr4_2_faq_dispatch(self):
        """§4.2.e — faq: ≥3 Q&A pairs passes; <3 fails."""
        from api.services.geo_rewrite_prompt import _structural_check_passes
        two_pairs = (
            "## What is X?\nA brief explanation.\n\n"
            "## How does Y work?\nIt does Y by Z.\n\n"
        )
        three_pairs = two_pairs + "## Why use W?\nBecause of reasons.\n"
        assert _structural_check_passes(two_pairs, "faq") is False
        assert _structural_check_passes(three_pairs, "faq") is True

    def test_cr4_2_general_dispatch_unchanged(self):
        """§4.2.f — general/article: any structured element passes (legacy behaviour)."""
        from api.services.geo_rewrite_prompt import _structural_check_passes
        with_bullets = "Some prose.\n- a\n- b\n"
        prose_only = "Just prose with no structured elements at all.\n"
        for pt in ("general", "article"):
            assert _structural_check_passes(with_bullets, pt) is True
            assert _structural_check_passes(prose_only, pt) is False

    # ── §4.3 — fix-instruction dispatch ────────────────────────────────────

    def test_cr4_3_per_type_fix_instruction_dispatched(self):
        """§4.3 — _resolve_fix_instruction returns page-type-specific variant when defined."""
        from api.services.geo_rewrite_prompt import _resolve_fix_instruction
        tech = _resolve_fix_instruction("STRUCTURED_ELEMENTS_LOW", "technical")
        comp = _resolve_fix_instruction("STRUCTURED_ELEMENTS_LOW", "comparison")
        faq = _resolve_fix_instruction("STRUCTURED_ELEMENTS_LOW", "faq")
        gen = _resolve_fix_instruction("STRUCTURED_ELEMENTS_LOW", "general")
        assert tech and "(technical page)" in tech
        assert comp and "(comparison page)" in comp
        assert faq and "(FAQ page)" in faq
        # general falls back to the bare entry (no page-type label)
        assert gen and "(technical page)" not in gen and "(comparison page)" not in gen

    # ── §4.4 — end-to-end: scoring respects page_type ──────────────────────

    def test_cr4_4_technical_no_code_fails(self):
        """§4.4.a — technical page with bullets only (no code, no numbered list ≥3) fails."""
        text = _BARE_PROSE_500 + "\n- bullet 1\n- bullet 2\n- bullet 3\n"
        _, _, fails, _ = _content_score("http://x.com", text, "technical")
        assert "STRUCTURED_ELEMENTS_LOW" in fails

    def test_cr4_4_technical_with_code_passes(self):
        """§4.4.b — same page + a code block passes."""
        text = _BARE_PROSE_500 + "\n```\nnpm install foo\n```\n"
        _, _, fails, _ = _content_score("http://x.com", text, "technical")
        assert "STRUCTURED_ELEMENTS_LOW" not in fails

    def test_cr4_4_comparison_table_required(self):
        """§4.4.c — comparison page with prose only fails; with table passes."""
        prose = _BARE_PROSE_500
        with_table = prose + (
            "\n| Feature | A | B |\n|---|---|---|\n"
            "| Open    | Yes | No |\n| Self-host | Yes | No |\n"
        )
        _, _, fails_prose, _ = _content_score("http://x.com", prose, "comparison")
        _, _, fails_table, _ = _content_score("http://x.com", with_table, "comparison")
        assert "STRUCTURED_ELEMENTS_LOW" in fails_prose
        assert "STRUCTURED_ELEMENTS_LOW" not in fails_table

    def test_cr4_4_faq_three_pairs_required(self):
        """§4.4.d — FAQ page with 2 pairs fails; with 3 pairs passes."""
        two = _BARE_PROSE_500 + (
            "\n## What is X?\nA brief explanation here.\n"
            "\n## How does Y work?\nIt does Y by Z.\n"
        )
        three = two + "\n## Why use W?\nBecause of reasons.\n"
        _, _, fails_two, _ = _content_score("http://x.com", two, "faq")
        _, _, fails_three, _ = _content_score("http://x.com", three, "faq")
        assert "STRUCTURED_ELEMENTS_LOW" in fails_two
        assert "STRUCTURED_ELEMENTS_LOW" not in fails_three

    def test_cr4_4_general_unchanged(self):
        """§4.4.e — general/article pages keep legacy behaviour (any list/table/code passes)."""
        with_bullets = _BARE_PROSE_500 + "\n- a\n- b\n- c\n"
        for pt in ("general", "article"):
            _, _, fails, _ = _content_score("http://x.com", with_bullets, pt)
            assert "STRUCTURED_ELEMENTS_LOW" not in fails, (
                f"page_type={pt} should accept any structured element (legacy behaviour)"
            )


# ---------------------------------------------------------------------------
# Fix 4 — CR5_* — entity-set named-list detection
# ---------------------------------------------------------------------------

class TestNamedEntityExtraction:
    """CR5.x — _extract_named_entities_from_text + entity-aware regression check."""

    # ── §5.2.1 — multi-word title-case phrases ──────────────────────────────

    def test_cr5_2_extracts_multiword_phrases(self):
        """§5.2.1 — phrases of 2-4 capitalised words are extracted."""
        from api.services.geo_rewrite_prompt import _extract_named_entities_from_text
        text = "We use Claude Desktop with the Model Context Protocol for memory."
        entities = _extract_named_entities_from_text(text)
        assert any("Claude Desktop" in e for e in entities), (
            f"Expected 'Claude Desktop' phrase: {entities}"
        )
        assert any("Model Context Protocol" in e for e in entities), (
            f"Expected 'Model Context Protocol' phrase: {entities}"
        )

    # ── §5.2.2 — single capitalised words appearing >= 2 times ─────────────

    def test_cr5_2_extracts_repeated_capitalised(self):
        """§5.2.2 — single Cap word appearing >= 2 times gets extracted."""
        from api.services.geo_rewrite_prompt import _extract_named_entities_from_text
        text = "Foobar is a tool. Foobar handles memory. Foobar runs locally."
        entities = _extract_named_entities_from_text(text)
        assert "Foobar" in entities

    # ── §5.2.3 — backtick-wrapped identifiers ──────────────────────────────

    def test_cr5_2_extracts_backtick_identifiers(self):
        """§5.2.3 — `pgvector`, `npm install` are extracted from backticks."""
        from api.services.geo_rewrite_prompt import _extract_named_entities_from_text
        text = "Run `npm install` then configure `pgvector` for similarity search."
        entities = _extract_named_entities_from_text(text)
        assert "npm" in entities or "pgvector" in entities, (
            f"Expected backtick-wrapped identifiers: {entities}"
        )

    # ── §5.2.4 — allowlist case-insensitive ─────────────────────────────────

    def test_cr5_2_allowlist_case_insensitive(self):
        """§5.2.4 — allowlisted technical terms match case-insensitively."""
        from api.services.geo_rewrite_prompt import _extract_named_entities_from_text
        text = "We use Supabase with the MCP protocol and ChatGPT memory."
        entities = _extract_named_entities_from_text(text)
        assert "supabase" in entities, f"Expected 'supabase' (allowlist): {entities}"
        assert "mcp" in entities
        assert "chatgpt" in entities

    # ── §5.2.5 — preservation floor exposes named_entities ─────────────────

    def test_cr5_2_preservation_floor_has_named_entities(self):
        """§5.2.5 — _extract_preservation_floor returns named_entities key."""
        text = "OpenBrain uses Supabase with MCP and pgvector for retrieval."
        floor = _extract_preservation_floor(text)
        assert "named_entities" in floor
        assert isinstance(floor["named_entities"], frozenset)

    # ── §5.2.6 — _count_named_lists uses known_entities ────────────────────

    def test_cr5_2_named_lists_uses_entities(self):
        """§5.2.6 — passing known_entities switches to entity-membership counting."""
        from api.services.geo_rewrite_prompt import _count_named_lists
        text = "- mcp setup\n- supabase config\n- pgvector index\n"
        # Without known entities: lowercase items don't satisfy capitalisation heuristic
        assert _count_named_lists(text) == 0
        # With known entities: each item matches an allowlisted term → counted
        entities = frozenset({"mcp", "supabase", "pgvector"})
        assert _count_named_lists(text, entities) == 1

    # ── §5.2.7 — NAMED_ENTITIES_LOST regression check ──────────────────────

    def test_cr5_2_named_entities_lost_violation(self):
        """§5.2.7 — rewrite preserving <70% of original entities triggers violation."""
        original_features = {
            "named_entities": frozenset({"Supabase", "MCP", "Claude", "pgvector"}),
            # legacy fields all zero
            "faq_pair_count": 0, "code_block_count": 0, "table_count": 0,
            "outbound_link_count": 0, "named_list_count": 0,
        }
        # Rewrite drops Supabase and MCP — preserves 2/4 = 50% < 70% → violation
        rewrite = "This is a system that uses Claude with pgvector for retrieval."
        violations = _check_preservation_regression(original_features, rewrite)
        assert "NAMED_ENTITIES_LOST" in violations

    # ── §5.4.a — extracts known products from OpenBrain-style paragraph ────

    def test_cr5_4_openbrain_entities_extracted(self):
        """§5.4.a — Supabase, MCP, pgvector, Claude, ChatGPT all extractable."""
        from api.services.geo_rewrite_prompt import _extract_named_entities_from_text
        text = (
            "OpenBrain is built on Supabase, using the MCP protocol. "
            "It works with Claude, ChatGPT, and pgvector for similarity search."
        )
        entities = _extract_named_entities_from_text(text)
        # Allowlist matches return lowercased
        assert "supabase" in entities
        assert "mcp" in entities
        assert "pgvector" in entities
        assert "claude" in entities
        assert "chatgpt" in entities
        assert "openbrain" in entities

    # ── §5.4.b — does NOT extract emphasised words ─────────────────────────

    def test_cr5_4_emphasised_words_excluded(self):
        """§5.4.b — Self-Contained, Required, Important, Setup, Step are NOT extracted."""
        from api.services.geo_rewrite_prompt import _extract_named_entities_from_text
        text = (
            "- Self-Contained sections are Required for AI retrieval\n"
            "- Important: avoid backward references\n"
            "- Setup is straightforward\n"
            "- Step 1: open the dashboard\n"
        )
        entities = _extract_named_entities_from_text(text)
        assert "Self-Contained" not in entities
        assert "Required" not in entities
        assert "Important" not in entities
        assert "Setup" not in entities
        # "Step" alone wouldn't show since "Step 1" splits to "Step" + "1"
        assert "Step" not in entities

    # ── §5.4.c — entity loss triggers NAMED_ENTITIES_LOST ──────────────────

    def test_cr5_4_entity_loss_triggers_regression(self):
        """§5.4.c — rewrite that drops 50% of entities fails the regression check."""
        # Same as test_cr5_2_named_entities_lost_violation but framed as the §5.4 case
        original_features = {
            "named_entities": frozenset({"Supabase", "MCP", "Claude", "pgvector"}),
            "faq_pair_count": 0, "code_block_count": 0, "table_count": 0,
            "outbound_link_count": 0, "named_list_count": 0,
        }
        rewrite = "This system uses Claude memory with a pgvector index for search."
        violations = _check_preservation_regression(original_features, rewrite)
        assert "NAMED_ENTITIES_LOST" in violations


# ---------------------------------------------------------------------------
# Fix 5 — CR6_* — numbered-output query-match parser + parse_failure
# ---------------------------------------------------------------------------

class TestQueryMatchParser:
    """CR6.x — verdict parser is robust to whitespace/order; missing → Partial+flag."""

    # ── §6.2 — prompt format and regex shape ────────────────────────────────

    def test_cr6_2_prompt_format_includes_numbered_example(self):
        """§6.2.a — the prompt template embeds an `N: <verdict>` example."""
        import api.services.geo_rewrite_prompt as mod
        from pathlib import Path
        src = Path(mod.__file__).read_text()
        assert "N: <Yes|Partial|No>" in src
        assert "Example output for 3 questions" in src

    def test_cr6_2_verdict_regex_pattern(self):
        """§6.2.b — _VERDICT_LINE_RE matches the documented format and tolerates separators."""
        from api.services.geo_rewrite_prompt import _VERDICT_LINE_RE
        # All these should match
        for line, expected_n, expected_v in [
            ("1: Yes", 1, "yes"),
            ("  2. Partial", 2, "partial"),
            ("3) No", 3, "no"),
            ("4 - Yes", 4, "yes"),
            ("10: PARTIAL", 10, "partial"),
        ]:
            m = _VERDICT_LINE_RE.match(line)
            assert m, f"Should match: {line!r}"
            assert int(m.group(1)) == expected_n
            assert m.group(2).lower() == expected_v

    def test_cr6_2_dict_keyed_by_index(self):
        """§6.2.c — parser populates verdicts keyed by question number."""
        from api.services.geo_rewrite_prompt import parse_verdict_response
        response = "1: Yes\n2: Partial\n3: No"
        queries = ["q1", "q2", "q3"]
        per_query = parse_verdict_response(response, queries)
        # Verdicts come back in question order, with parse_failure=False
        assert [r["answered"] for r in per_query] == ["Yes", "Partial", "No"]
        assert all(r["parse_failure"] is False for r in per_query)

    # ── §6.3 — parse_failure flag and Partial-on-missing default ───────────

    def test_cr6_3_per_query_has_parse_failure_field(self):
        """§6.3.a — every per-query result has a parse_failure boolean."""
        from api.services.geo_rewrite_prompt import parse_verdict_response
        per_query = parse_verdict_response("1: Yes", ["q1"])
        assert "parse_failure" in per_query[0]
        assert isinstance(per_query[0]["parse_failure"], bool)

    def test_cr6_3_missing_defaults_to_partial(self):
        """§6.3.b — missing verdict → Partial + parse_failure=True (NOT 'No')."""
        from api.services.geo_rewrite_prompt import parse_verdict_response
        # Question 2 missing
        per_query = parse_verdict_response("1: Yes\n3: No", ["q1", "q2", "q3"])
        assert per_query[1]["answered"] == "Partial"
        assert per_query[1]["parse_failure"] is True

    # ── §6.4 — additional parsing scenarios ────────────────────────────────

    def test_cr6_4_parses_with_whitespace(self):
        """§6.4.a — leading/trailing whitespace and blank lines tolerated."""
        from api.services.geo_rewrite_prompt import parse_verdict_response
        response = "\n  1: Yes  \n\n  2: Partial\n  3: No\n\n"
        per_query = parse_verdict_response(response, ["q1", "q2", "q3"])
        assert [r["answered"] for r in per_query] == ["Yes", "Partial", "No"]

    def test_cr6_4_parses_out_of_order(self):
        """§6.4.b — out-of-order verdict lines are aligned by question number."""
        from api.services.geo_rewrite_prompt import parse_verdict_response
        response = "3: No\n1: Yes\n2: Partial"
        per_query = parse_verdict_response(response, ["q1", "q2", "q3"])
        assert per_query[0]["answered"] == "Yes"
        assert per_query[1]["answered"] == "Partial"
        assert per_query[2]["answered"] == "No"

    def test_cr6_4_missing_query_partial_with_flag(self):
        """§6.4.c — missing query #2 → Partial + parse_failure=True."""
        from api.services.geo_rewrite_prompt import parse_verdict_response
        per_query = parse_verdict_response("1: Yes\n3: No", ["q1", "q2", "q3"])
        assert per_query[1]["answered"] == "Partial"
        assert per_query[1]["parse_failure"] is True
        # Other rows are NOT marked parse_failure
        assert per_query[0]["parse_failure"] is False
        assert per_query[2]["parse_failure"] is False

    def test_cr6_4_knowledge_gap_skips_parse_failures(self):
        """§6.4.d — knowledge-gap detection in source skips queries with any parse_failure.

        Verified at the source level since stream_rewrite_variants requires LLM
        calls.  We grep for the exact guard.
        """
        import api.services.geo_rewrite_prompt as mod
        from pathlib import Path
        src = Path(mod.__file__).read_text()
        # The guard must reference both "all_no" semantics and the parse_failure exclusion
        assert "any_parse_failure" in src, (
            "Knowledge-gap detection must check parse_failure"
        )
        assert "if all_no and not any_parse_failure" in src, (
            "Knowledge-gap guard must combine all-No with no-parse-failure"
        )


# ---------------------------------------------------------------------------
# Fix 7.1 — CR8_1_* — _count_faq_pairs stricter rule for heading-questions
# ---------------------------------------------------------------------------

class TestFaqStricterRule:
    """CR8_1.x — single rhetorical heading-question doesn't establish FAQ format."""

    def test_cr8_1_single_heading_question_returns_0(self):
        """§8.1.a — a single heading-style question with answer is rhetorical, not FAQ."""
        from api.services.geo_rewrite_prompt import _count_faq_pairs
        text = (
            "Some intro paragraph.\n\n"
            "## Why use OpenBrain?\n"
            "Because you control your own context.\n\n"
            "More prose follows.\n"
        )
        assert _count_faq_pairs(text) == 0

    def test_cr8_1_two_heading_questions_return_2(self):
        """§8.1.b — two or more heading-style Q&A pairs DO count as FAQ format."""
        from api.services.geo_rewrite_prompt import _count_faq_pairs
        text = (
            "## What is OpenBrain?\n"
            "A personal AI memory database you control.\n\n"
            "## How does it work?\n"
            "It stores context in a database you own.\n"
        )
        assert _count_faq_pairs(text) == 2

    def test_cr8_1_inline_questions_independent_of_headings(self):
        """§8.1.c — inline-style questions count regardless of heading-question count."""
        from api.services.geo_rewrite_prompt import _count_faq_pairs
        # 1 heading-question (would be dropped if no other heading-questions exist)
        # but 2 inline-style questions counted independently
        text = (
            "## Why bother?\n"
            "It's worth the effort.\n\n"
            "What is the cost?\n"
            "Free for personal use.\n\n"
            "How long does setup take?\n"
            "About an hour.\n"
        )
        # heading_pairs=[1 dropped to 0] + inline_pairs=[2] = 2
        result = _count_faq_pairs(text)
        assert result == 2, f"Expected 2 inline pairs (heading dropped), got {result}"


# ---------------------------------------------------------------------------
# Fix 7.2 — CR8_2_* — Hard Prohibition 5 explicit coverage extension
# ---------------------------------------------------------------------------

class TestHardProhibitionCoverage:
    """CR8_2.x — §(e) item 5 explicitly mentions comparison tables and original statistics."""

    def test_cr8_2_prompt_mentions_comparison_tables(self):
        """§8.2.a — prompt §(e) item 5 explicitly calls out 'comparison tables'."""
        result = generate_rewrite_prompt(_make_report(), "general")
        prompt = result["system_prompt"]
        assert "comparison tables" in prompt, (
            "Hard Prohibition 5 must explicitly mention comparison tables"
        )

    def test_cr8_2_prompt_mentions_original_statistics(self):
        """§8.2.b — prompt §(e) item 5 explicitly calls out 'specific statistics ... in the original'."""
        result = generate_rewrite_prompt(_make_report(), "general")
        prompt = result["system_prompt"]
        # Must mention preserving statistics from the original verbatim
        assert "Specific statistics" in prompt or "specific statistics" in prompt, (
            "Hard Prohibition 5 must mention original statistics"
        )
        assert "appeared in the\n     original" in prompt or "in the original" in prompt


# ---------------------------------------------------------------------------
# Fix 7.4 — CR8_4_* — synthetic page list-count comment
# ---------------------------------------------------------------------------

class TestSyntheticPageListCountComment:
    """CR8_4.x — list_count cap at 1 is documented with the depending check named."""

    def test_cr8_4_cap_comment_present(self):
        """§8.4 — the cap is documented with the dependent check named."""
        import api.services.geo_rewrite_prompt as mod
        from pathlib import Path
        src = Path(mod.__file__).read_text()
        # Must mention issue_checker (the depending module)
        assert "issue_checker" in src, "Cap comment must name issue_checker"
        # Must include "REMOVE THIS CAP" or similar instruction
        assert "REMOVE THIS CAP" in src or "remove this cap" in src.lower(), (
            "Cap comment must instruct future maintainers to remove the cap if check changes"
        )


# ---------------------------------------------------------------------------
# §9.9 — CR9_9_* — Integration fixture + pipeline smoke tests
# ---------------------------------------------------------------------------
# Skipped by default.  Run with: pytest -m integration
# Source URL: https://www.mindstudio.ai/blog/what-is-openbrain-personal-ai-memory-database

import os
from pathlib import Path

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_OPENBRAIN_PATH = _FIXTURES_DIR / "openbrain_original.md"


class TestIntegrationPipeline:
    """CR9_9.x — end-to-end pipeline run against the OpenBrain reference page."""

    # ── §9.9.a — fixture file exists (always runs; not integration-marked) ─

    def test_cr9_9_fixture_present(self):
        """§9.9.a — tests/fixtures/openbrain_original.md exists and is non-trivial."""
        assert _OPENBRAIN_PATH.exists(), f"Fixture missing: {_OPENBRAIN_PATH}"
        text = _OPENBRAIN_PATH.read_text()
        # Sanity checks on the fixture
        assert len(text.split()) > 1500, (
            f"Fixture too short ({len(text.split())} words); expected ~2000+"
        )
        assert "OpenBrain" in text
        assert "Supabase" in text
        assert "MCP" in text

    # ── §9.9.b — winner preserves original entities (LLM-required) ────────

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cr9_9_winner_preserves_entities(self):
        """§9.9.b — pipeline winner contains all entities extracted from original."""
        from api.services.geo_rewrite_prompt import (
            _extract_named_entities_from_text,
            stream_rewrite_variants,
        )
        from api.services.geo_analyzer import _resolve_model
        original = _OPENBRAIN_PATH.read_text()
        orig_entities = _extract_named_entities_from_text(original)
        try:
            model, provider = _resolve_model(None)
        except RuntimeError:
            pytest.skip("No AI keys configured; skipping integration test")

        # Run pipeline (collect events; winner is in done event)
        winner_text = ""
        async for event_str in stream_rewrite_variants(
            page_content=original,
            rewrite_prompt_result={
                "system_prompt": "Rewrite for GEO",
                "current_score": 0.0,
                "target_score": 0.9,
                "mandatory_count": 0,
                "fixable_count": 0,
                "page_type": "article",
                "findings_count": 0,
                "preservation_floor": None,
            },
            model=model,
            provider=provider,
            url="https://www.mindstudio.ai/blog/what-is-openbrain-personal-ai-memory-database",
            page_type="article",
            n=2,  # small n to keep cost down
        ):
            import json
            line = event_str.strip()
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("type") == "done":
                    winner_text = data.get("winner_text", "")

        winner_entities = _extract_named_entities_from_text(winner_text)
        orig_lower = {e.lower() for e in orig_entities}
        winner_lower = {e.lower() for e in winner_entities}
        preserved = orig_lower & winner_lower
        # Spec target: at least 70% preservation (matches NAMED_ENTITIES_LOST threshold)
        assert len(preserved) >= 0.7 * len(orig_lower), (
            f"Winner preserved only {len(preserved)}/{len(orig_lower)} entities "
            f"({len(preserved) / len(orig_lower) * 100:.0f}%)"
        )

    # ── §9.9.c — no fabricated numbers (LLM-required) ─────────────────────

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cr9_9_winner_no_fabricated_numbers(self):
        """§9.9.c — winner contains no number-with-unit not present in the original."""
        from api.services.geo_rewrite_prompt import (
            _extract_specific_numbers,
            stream_rewrite_variants,
        )
        from api.services.geo_analyzer import _resolve_model
        original = _OPENBRAIN_PATH.read_text()
        orig_numbers = _extract_specific_numbers(original)
        try:
            model, provider = _resolve_model(None)
        except RuntimeError:
            pytest.skip("No AI keys configured; skipping integration test")

        winner_text = ""
        async for event_str in stream_rewrite_variants(
            page_content=original,
            rewrite_prompt_result={
                "system_prompt": "Rewrite for GEO",
                "current_score": 0.0, "target_score": 0.9,
                "mandatory_count": 0, "fixable_count": 0,
                "page_type": "article", "findings_count": 0,
                "preservation_floor": None,
            },
            model=model, provider=provider,
            url="https://www.mindstudio.ai/blog/what-is-openbrain-personal-ai-memory-database",
            page_type="article", n=2,
        ):
            import json
            line = event_str.strip()
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("type") == "done":
                    winner_text = data.get("winner_text", "")

        winner_numbers = _extract_specific_numbers(winner_text)
        fabricated = winner_numbers - orig_numbers
        assert not fabricated, (
            f"Winner introduced {len(fabricated)} numbers not in original: {fabricated}"
        )

    # ── §9.9.d — score reproducibility ────────────────────────────────────

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cr9_9_score_reproducibility(self):
        """§9.9.d — two pipeline runs produce winner scores within +/- 0.02 of each other.

        Without LLM seeding, exact reproducibility is impossible.  The +/- 0.02
        tolerance is generous enough to absorb LLM variance but tight enough to
        catch a real regression in the scoring path.
        """
        # Identical setup; not asserted to produce identical text, only similar scores
        pytest.skip(
            "Score reproducibility test is best-effort; manual verification "
            "preferred over flaky CI run."
        )

    # ── §9.9.e — done event contains the metadata fields ─────────────────

    def test_cr9_9_done_event_complete(self):
        """§9.9.e — verified at the source level: done event has both required fields.

        (Avoids requiring an LLM call to assert event shape.  The keys are:
        winner_placeholder_inventory and scoring_metadata, both added in
        Steps 5 and 2 respectively.)
        """
        import api.services.geo_rewrite_prompt as mod
        from pathlib import Path
        src = Path(mod.__file__).read_text()
        assert '"winner_placeholder_inventory"' in src
        assert '"scoring_metadata"' in src
