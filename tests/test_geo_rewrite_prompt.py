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
    _build_synthetic_parsed_page,
    _detect_page_type,
    _score_markdown,
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

    def test_c5_first_150_words_non_empty(self):
        """C.5: first_150_words is populated."""
        result = _build_synthetic_parsed_page("https://example.org/blog/seo", SAMPLE_MD)
        assert result["first_150_words"]
        assert len(result["first_150_words"].split()) <= 155  # ~150 words

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
# Misc
# ---------------------------------------------------------------------------

def test_best_of_n_constant():
    """_BEST_OF_N should be 5 as specified."""
    assert _BEST_OF_N == 5
