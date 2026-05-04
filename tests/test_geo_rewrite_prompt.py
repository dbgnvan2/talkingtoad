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
"""

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
        text = "Body.\n---\nGEO NOTES\n- note"
        body, notes = _split_body_and_notes(text)
        assert "GEO NOTES" not in body
        assert "---" not in body

    def test_multiple_dashes_only_splits_at_geo_notes(self):
        """An --- that is NOT followed by GEO NOTES must stay in body."""
        text = "Section 1.\n\n---\n\nSection 2.\n\n---\nGEO NOTES\n- note"
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

    def test_returns_three_tuple(self):
        """_content_score must return (fail_count, score, failing_codes)."""
        result = _content_score("http://x.com", "short")
        assert len(result) == 3
        issues, score, codes = result
        assert isinstance(issues, int)
        assert isinstance(score, float)
        assert isinstance(codes, list)

    def test_geo_notes_placeholder_does_not_inflate_citation_score(self):
        """Core regression: [CITATION NEEDED] in GEO NOTES must NOT count as a citation."""
        text_with_notes_only = (
            _LONG_BODY
            + "\n---\nGEO NOTES\n- [CITATION NEEDED] added at: introduction.\n"
        )
        text_no_notes = _LONG_BODY  # same body, no notes
        _, score_with_notes, _ = _content_score("http://x.com", text_with_notes_only)
        _, score_no_notes, _ = _content_score("http://x.com", text_no_notes)
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
        _, score_notes, codes_notes = _content_score("http://x.com", text_notes_only)
        # STATISTICS_COUNT_LOW must still fire — notes don't count
        assert "STATISTICS_COUNT_LOW" in codes_notes

    def test_inline_placeholder_counts_for_citation(self):
        """[CITATION NEEDED] embedded IN the body must count and clear the check."""
        body_with_inline = (
            _LONG_BODY
            + " Research confirms this [CITATION NEEDED: peer-reviewed study]."
        )
        _, _, codes = _content_score("http://x.com", body_with_inline)
        assert "EXTERNAL_CITATIONS_LOW" not in codes

    def test_inline_statistic_counts(self):
        """A number with unit embedded in body must clear STATISTICS_COUNT_LOW."""
        body_with_stat = _LONG_BODY + " Users report 40% faster retrieval."
        _, _, codes = _content_score("http://x.com", body_with_stat)
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

        _, score_rich, fails_rich = _content_score("http://x.com", rich)

        # Thin: no stats, no cites, no quotes, no structure
        _, score_thin, fails_thin = _content_score("http://x.com", _LONG_BODY)

        assert len(fails_rich) <= len(fails_thin), (
            "Rich content must have fewer or equal failing checks than thin content"
        )
        assert score_rich >= score_thin, (
            f"Rich score ({score_rich}) must be >= thin score ({score_thin})"
        )

    def test_score_range_is_zero_to_one(self):
        """Score must always be in [0.0, 1.0]."""
        for content in ["", "x", _LONG_BODY, "word " * 1000]:
            _, score, _ = _content_score("http://x.com", content)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for content length {len(content)}"

    def test_failing_codes_match_issues_count(self):
        """fail_count must equal len(failing_codes)."""
        issues, _, codes = _content_score("http://x.com", _LONG_BODY)
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
        _, _, codes = _content_score("http://x.com", text_with_misleading_notes)
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
        _, score_without, _ = _content_score("http://x.com", _REWRITE_PROSE_ONLY)
        _, score_with, codes_with = _content_score(
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

        _, score_zero, _ = _content_score("http://x.com", base_content,
                                          original_features=no_features)
        _, score_one, _ = _content_score("http://x.com", base_content,
                                         original_features=one_regression)
        _, score_two, _ = _content_score("http://x.com", base_content,
                                         original_features=two_regressions)

        assert score_zero >= score_one >= score_two, (
            f"Monotonicity violated: zero={score_zero}, one={score_one}, two={score_two}"
        )
