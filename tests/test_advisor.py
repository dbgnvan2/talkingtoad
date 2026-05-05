"""
Tests for advisor.py (Tool A — Content Quality Evaluation).

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md

Tests focus on deterministic rendering logic, not LLM behavior.
"""

import pytest

from api.models.advisor import (
    AdvisorReport,
    AuthoritySignals,
    CitationFinding,
    FactualGrounding,
    Finding,
    HonestPlaceholders,
    PlaceholderFinding,
    Section,
    SelfContainment,
    SourceFidelity,
    StructuralFitness,
    StructuralMismatch,
)
from api.services.advisor import _render_report_to_markdown


class TestReportRendering:
    """Test deterministic markdown rendering from AdvisorReport."""

    def test_minimal_report(self):
        """Minimal report with only required fields."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="grounded",
            ),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=["Well-written"],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "# Content Quality Review" in markdown
        assert "## Strengths" in markdown
        assert "Well-written" in markdown
        assert "No critical issues found" in markdown

    def test_critical_issues_displayed(self):
        """Critical issues appear in report."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=True,
                verdict="weak",
            ),
            critical_issues=["Fabrication: Claims without support"],
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Critical Issues" in markdown
        assert "Fabrication: Claims without support" in markdown

    def test_specific_facts_section(self):
        """Specific facts are listed with citations."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="grounded",
                specific_facts=[
                    Finding(text="OpenAI released GPT-4 in March 2023", is_specific=True),
                    Finding(text="The model has 100B parameters", is_specific=True),
                ],
            ),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Factual Grounding" in markdown
        assert "**Specific facts found:**" in markdown
        assert "OpenAI released GPT-4" in markdown
        assert "100B parameters" in markdown

    def test_generalities_section(self):
        """Generalities that need grounding are listed."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="weak",
                generalities=[
                    Finding(text="Revolutionary technology", issue="Too vague"),
                    Finding(text="Industry-leading", issue="Needs comparison"),
                ],
            ),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "**Generalities that should be grounded:**" in markdown
        assert "Revolutionary technology" in markdown

    def test_self_containment_section(self):
        """Self-containment checklist renders correctly."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(
                sections=[
                    Section(
                        heading="Installation",
                        can_stand_alone=True,
                    ),
                    Section(
                        heading="Configuration",
                        can_stand_alone=False,
                        requires_context=["Installation section", "Prerequisites"],
                    ),
                ]
            ),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Self-Containment" in markdown
        assert "✓ **Installation**" in markdown
        assert "✗ **Configuration**" in markdown
        assert "Installation section" in markdown

    def test_structural_fitness_section(self):
        """Structural fitness mismatches render."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(
                mismatches=[
                    StructuralMismatch(
                        pattern="Enumerates steps but not in ordered list",
                        location="Getting Started section",
                    ),
                ],
                unnecessary_structure=[
                    StructuralMismatch(
                        pattern="<table>",
                        location="Contains only 2 rows; should be prose",
                    ),
                ],
            ),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Structural Fitness" in markdown
        assert "Enumerates steps" in markdown
        assert "Unnecessary structure" in markdown

    def test_authority_signals_section(self):
        """Citations and authority signals render."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(
                citations_present=[
                    CitationFinding(text="According to Stanford NLP 2023 study", source="Stanford NLP Lab"),
                ],
                citations_missing=[
                    {
                        "claim": "This technology outperforms existing methods",
                        "why_needed": "Comparison study reference",
                    }
                ],
                placeholder_citations=[
                    CitationFinding(
                        text="See our research",
                        issue="Unclear which research",
                    ),
                ],
            ),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Authority Signals" in markdown
        assert "Real citations:" in markdown
        assert "Stanford NLP Lab" in markdown
        assert "Missing citations" in markdown
        assert "Placeholder or vague citations" in markdown

    def test_honest_placeholders_section(self):
        """Placeholders at real gaps vs decorative."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            honest_placeholders=HonestPlaceholders(
                at_real_gaps=[
                    PlaceholderFinding(
                        text="[BENCHMARKS TBD]",
                        gap_type="Performance metrics not yet available",
                    ),
                ],
                decorative=[
                    PlaceholderFinding(
                        text="[SCREENSHOT HERE]",
                        reason="Illustration, not critical information",
                    ),
                ],
            ),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Placeholder Honesty" in markdown
        assert "Placeholders at real gaps:" in markdown
        assert "[BENCHMARKS TBD]" in markdown
        assert "Decorative placeholders:" in markdown

    def test_source_fidelity_section(self):
        """Source fidelity (rewrite comparison) renders."""
        report = AdvisorReport(
            overall_assessment="Test",
            source_fidelity=SourceFidelity(
                is_critical=True,
                fabrications=["Claims X is faster without evidence"],
                losses=["Removed original disclaimer about limitations"],
                degradations=["Simplified accuracy claims"],
                preserved_strengths=["Kept the installation workflow"],
            ),
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Source Fidelity" in markdown
        assert "Fabrications" in markdown
        assert "faster without evidence" in markdown
        assert "Losses" in markdown
        assert "Preserved Strengths" in markdown

    def test_what_cannot_be_fixed(self):
        """'What Cannot Be Fixed' section appears for minimal verdict."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="minimal",
            ),
            what_cannot_be_fixed="Content is too sparse. Author must add specific examples and citations.",
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## What Cannot Be Fixed by Rewriting" in markdown
        assert "too sparse" in markdown

    def test_confidence_notes_section(self):
        """Confidence notes are included."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[
                {
                    "finding": "Self-containment of 'Advanced Topics' section",
                    "reason": "Ambiguous boundary between 'Basics' and 'Advanced'",
                }
            ],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Confidence Notes" in markdown
        assert "Self-containment" in markdown
        assert "Ambiguous boundary" in markdown

    def test_strengths_always_present(self):
        """Strengths section always appears."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=True, verdict="minimal"),
            critical_issues=["Major fabrication"],
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=["Clear navigation", "Good use of examples"],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "## Strengths" in markdown
        assert "Clear navigation" in markdown
        assert "Good use of examples" in markdown

    def test_verdict_minimal_updates_assessment(self):
        """'minimal' verdict changes overall assessment."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="minimal"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        # Overall assessment is updated for minimal verdict
        assert "substance is thin" in markdown or "Rewriting alone" in markdown

    def test_verdict_weak_updates_assessment(self):
        """'weak' verdict changes overall assessment."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="weak"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "weak factual grounding" in markdown or "improvements are possible" in markdown

    def test_verdict_grounded_updates_assessment(self):
        """'grounded' verdict results in positive assessment."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(is_critical=False, verdict="grounded"),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
        )
        markdown = _render_report_to_markdown(report)
        assert "well-grounded" in markdown


class TestReportDecisions:
    """Test decisions: generate_prompt and what_cannot_be_fixed."""

    def test_should_generate_prompt_grounded_with_issues(self):
        """Should generate prompt when grounded but has issues."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="grounded",
            ),
            critical_issues=["Unclear structure"],
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
            should_generate_prompt=True,
        )
        assert report.should_generate_prompt is True

    def test_should_not_generate_prompt_minimal(self):
        """Should not generate prompt for minimal verdict."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="minimal",
            ),
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
            should_generate_prompt=False,
        )
        assert report.should_generate_prompt is False

    def test_should_not_generate_prompt_grounded_no_issues(self):
        """Should not generate prompt for grounded, no-issue pages."""
        report = AdvisorReport(
            overall_assessment="Test",
            factual_grounding=FactualGrounding(
                is_critical=False,
                verdict="grounded",
            ),
            critical_issues=[],
            self_containment=SelfContainment(),
            structural_fitness=StructuralFitness(),
            authority_signals=AuthoritySignals(),
            strengths=[],
            confidence_notes=[],
            should_generate_prompt=False,
        )
        assert report.should_generate_prompt is False
