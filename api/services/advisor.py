"""
Advisor service (Tool A) — Content quality evaluation for AI retrieval.

Evaluates page across 6 properties with findings traceable to specific text.
No scoring. Optional: generates rewrite prompt or diagnosis.

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md
"""

import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from api.models.advisor import (
    AdvisorReport,
    AdvisorRequest,
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

load_dotenv()
load_dotenv(".env-ttoad", override=True)

logger = logging.getLogger(__name__)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={key}"
_TIMEOUT = 30.0


def _get_model() -> tuple[str, str]:
    """Resolve LLM model (prefers OpenAI, falls back to Gemini)."""
    if _OPENAI_API_KEY:
        return "openai", "gpt-4o"
    if _GEMINI_API_KEY:
        return "gemini", "gemini-2.0-flash"
    raise RuntimeError("No OPENAI_API_KEY or GEMINI_API_KEY configured")


def _fetch_page(url: str) -> str:
    """Fetch page HTML from URL."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}")


def _html_to_markdown(html: str) -> str:
    """Basic HTML to markdown conversion. In production, use html2text or similar."""
    # For now, return as-is if already markdown, or perform basic conversion
    # This is a placeholder — in real use, call html2text or BeautifulSoup
    return html


def _call_openai_critic(content: str, original: str | None) -> dict:
    """Call OpenAI API with critic prompt."""
    comparison_note = ""
    if original:
        comparison_note = (
            "\n\nALSO provide a 'source_fidelity' assessment comparing the provided "
            "page to the original. Check for fabrications, losses, degradations, and preserved strengths."
        )

    system_prompt = """You are a content quality reviewer for Generative Engine Optimization (GEO).

Evaluate the provided page across 6 properties. For EACH finding, cite specific page text.
Flag findings as critical or informational based on severity.

DO NOT score, rank, or compute metrics. Findings are qualitative with evidence.

Return valid JSON only. No markdown wrapping."""

    user_prompt = f"""Content to evaluate:

{content}{comparison_note}

Return JSON with these keys:
- source_fidelity (object, only if comparing to original):
  - is_critical (boolean)
  - fabrications (list of strings)
  - losses (list of strings)
  - degradations (list of strings)
  - preserved_strengths (list of strings)
- factual_grounding (object):
  - is_critical (boolean)
  - specific_facts (list of objects with 'text' and 'is_specific' boolean)
  - generalities (list of objects with 'text' and 'issue')
  - verdict (string: "grounded" | "weak" | "minimal")
- self_containment (object):
  - sections (list of objects with 'heading', 'can_stand_alone' boolean, 'requires_context' list)
- structural_fitness (object):
  - mismatches (list of objects with 'pattern' and 'location')
  - unnecessary_structure (list of objects with 'element' and 'reason')
- authority_signals (object):
  - citations_present (list of objects with 'text' and optional 'source')
  - citations_missing (list of objects with 'claim' and 'why_needed')
  - placeholder_citations (list of objects with 'text' and 'issue')
- honest_placeholders (object, only if placeholders exist):
  - at_real_gaps (list of objects with 'text' and 'gap_type')
  - decorative (list of objects with 'text' and 'reason')
- strengths (list of strings, mandatory, at least 2)
- confidence_notes (list of objects with 'finding' and 'reason')"""

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                _OPENAI_ENDPOINT,
                headers={"Authorization": f"Bearer {_OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        logger.error(f"OpenAI critic call failed: {e}")
        raise


def _call_gemini_critic(content: str, original: str | None) -> dict:
    """Call Gemini API with critic prompt."""
    comparison_note = ""
    if original:
        comparison_note = (
            "\n\nALSO provide a 'source_fidelity' assessment comparing the provided "
            "page to the original. Check for fabrications, losses, degradations, and preserved strengths."
        )

    system_prompt = """You are a content quality reviewer for Generative Engine Optimization (GEO).

Evaluate the provided page across 6 properties. For EACH finding, cite specific page text.
Flag findings as critical or informational based on severity.

DO NOT score, rank, or compute metrics. Findings are qualitative with evidence.

Return valid JSON only."""

    user_prompt = f"""Content to evaluate:

{content}{comparison_note}

Return JSON with these keys (see OpenAI endpoint for schema).

Return JSON only."""

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                _GEMINI_ENDPOINT.format(model="gemini-2.0-flash", key=_GEMINI_API_KEY),
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "generationConfig": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)
    except Exception as e:
        logger.error(f"Gemini critic call failed: {e}")
        raise


def _parse_critic_response(data: dict, original: str | None) -> AdvisorReport:
    """Parse LLM response into AdvisorReport."""
    # Build source fidelity
    source_fidelity = None
    if original and "source_fidelity" in data:
        sf = data["source_fidelity"]
        source_fidelity = SourceFidelity(
            is_critical=sf.get("is_critical", False),
            fabrications=sf.get("fabrications", []),
            losses=sf.get("losses", []),
            degradations=sf.get("degradations", []),
            preserved_strengths=sf.get("preserved_strengths", []),
        )

    # Build factual grounding
    fg_data = data.get("factual_grounding", {})
    specific_facts = [
        Finding(text=f["text"] if isinstance(f, dict) else f, is_specific=f.get("is_specific", True) if isinstance(f, dict) else True)
        for f in fg_data.get("specific_facts", [])
        if f  # Skip empty entries
    ]
    generalities = [
        Finding(text=f["text"] if isinstance(f, dict) else f, issue=f.get("issue") if isinstance(f, dict) else None)
        for f in fg_data.get("generalities", [])
        if f  # Skip empty entries
    ]
    factual_grounding = FactualGrounding(
        is_critical=fg_data.get("is_critical", False),
        specific_facts=specific_facts,
        generalities=generalities,
        verdict=fg_data.get("verdict", "minimal"),
    )

    # Build self-containment
    sc_data = data.get("self_containment", {})
    sections = [
        Section(
            heading=s["heading"],
            can_stand_alone=s.get("can_stand_alone", False),
            requires_context=s.get("requires_context", []),
        )
        for s in sc_data.get("sections", [])
    ]
    self_containment = SelfContainment(sections=sections)

    # Build structural fitness
    sf_data = data.get("structural_fitness", {})
    mismatches = [
        StructuralMismatch(pattern=m["pattern"], location=m.get("location", ""))
        for m in sf_data.get("mismatches", [])
    ]
    unnecessary = [
        StructuralMismatch(pattern=u.get("element", ""), location=u.get("reason", ""))
        for u in sf_data.get("unnecessary_structure", [])
    ]
    structural_fitness = StructuralFitness(
        mismatches=mismatches, unnecessary_structure=unnecessary
    )

    # Build authority signals
    as_data = data.get("authority_signals", {})
    citations_present = [
        CitationFinding(text=c["text"], source=c.get("source"))
        for c in as_data.get("citations_present", [])
    ]
    citations_missing = as_data.get("citations_missing", [])
    placeholder_citations = [
        CitationFinding(text=c["text"], issue=c.get("issue"))
        for c in as_data.get("placeholder_citations", [])
    ]
    authority_signals = AuthoritySignals(
        citations_present=citations_present,
        citations_missing=citations_missing,
        placeholder_citations=placeholder_citations,
    )

    # Build honest placeholders
    honest_placeholders = None
    if "honest_placeholders" in data:
        hp_data = data["honest_placeholders"]
        at_real_gaps = [
            PlaceholderFinding(text=p["text"], gap_type=p.get("gap_type"))
            for p in hp_data.get("at_real_gaps", [])
        ]
        decorative = [
            PlaceholderFinding(text=p["text"], reason=p.get("reason"))
            for p in hp_data.get("decorative", [])
        ]
        honest_placeholders = HonestPlaceholders(
            at_real_gaps=at_real_gaps, decorative=decorative
        )

    strengths = data.get("strengths", [])
    confidence_notes = data.get("confidence_notes", [])

    # Determine critical issues
    critical_issues = []
    if source_fidelity and source_fidelity.is_critical:
        critical_issues.extend([f"Fabrication: {f}" for f in source_fidelity.fabrications])
        critical_issues.extend([f"Loss: {l}" for l in source_fidelity.losses])
    if factual_grounding.is_critical:
        critical_issues.extend([f.text for f in factual_grounding.generalities])

    # Determine if rewrite prompt should be generated
    should_generate = (
        factual_grounding.verdict != "minimal"
        and (len(critical_issues) > 0 or factual_grounding.verdict in ["weak", "minimal"])
    )

    return AdvisorReport(
        overall_assessment="[Assessment will be rendered in markdown]",
        source_fidelity=source_fidelity,
        factual_grounding=factual_grounding,
        self_containment=self_containment,
        structural_fitness=structural_fitness,
        authority_signals=authority_signals,
        honest_placeholders=honest_placeholders,
        strengths=strengths,
        confidence_notes=confidence_notes,
        critical_issues=critical_issues,
        should_generate_prompt=should_generate,
    )


def _render_report_to_markdown(report: AdvisorReport) -> str:
    """Render AdvisorReport to markdown."""
    lines = []

    lines.append("# Content Quality Review")
    lines.append("")

    # Overall Assessment
    lines.append("## Overall Assessment")
    if report.critical_issues:
        lines.append(
            f"This page has {len(report.critical_issues)} critical issue(s) that significantly impact quality. "
            "See Critical Issues section below."
        )
    elif report.factual_grounding.verdict == "minimal":
        lines.append(
            "This page's substance is thin at the source level. Rewriting alone won't add facts that aren't there."
        )
    elif report.factual_grounding.verdict == "weak":
        lines.append("This page has weak factual grounding. Substantial improvements are possible through rewriting.")
    else:
        lines.append(
            "This page is well-grounded with specific facts and clear structure. Minor refinements could improve clarity."
        )
    lines.append("")

    # Critical Issues
    lines.append("## Critical Issues")
    if report.critical_issues:
        for issue in report.critical_issues:
            lines.append(f"- {issue}")
    else:
        lines.append("No critical issues found.")
    lines.append("")

    # Source Fidelity (if comparison)
    if report.source_fidelity:
        lines.append("## Source Fidelity")
        if report.source_fidelity.fabrications:
            lines.append("**Fabrications (explicit falsehoods):**")
            for f in report.source_fidelity.fabrications:
                lines.append(f"- {f}")
        if report.source_fidelity.losses:
            lines.append("**Losses (important facts lost):**")
            for l in report.source_fidelity.losses:
                lines.append(f"- {l}")
        if report.source_fidelity.degradations:
            lines.append("**Degradations (facts weakened):**")
            for d in report.source_fidelity.degradations:
                lines.append(f"- {d}")
        if report.source_fidelity.preserved_strengths:
            lines.append("**Preserved Strengths:**")
            for s in report.source_fidelity.preserved_strengths:
                lines.append(f"- {s}")
        lines.append("")

    # Factual Grounding
    lines.append("## Factual Grounding")
    lines.append(f"**Verdict:** {report.factual_grounding.verdict}")
    lines.append("")
    if report.factual_grounding.specific_facts:
        lines.append("**Specific facts found:**")
        for fact in report.factual_grounding.specific_facts:
            lines.append(f"- {fact.text}")
    if report.factual_grounding.generalities:
        lines.append("**Generalities that should be grounded:**")
        for gen in report.factual_grounding.generalities:
            issue = gen.issue if gen.issue else "lacks specificity"
            lines.append(f"- {gen.text} ({issue})")
    lines.append("")

    # Self-Containment
    if report.self_containment.sections:
        lines.append("## Self-Containment")
        for section in report.self_containment.sections:
            status = "✓" if section.can_stand_alone else "✗"
            lines.append(f"{status} **{section.heading}**")
            if section.requires_context:
                lines.append(f"   Requires: {', '.join(section.requires_context)}")
        lines.append("")

    # Structural Fitness
    if report.structural_fitness.mismatches or report.structural_fitness.unnecessary_structure:
        lines.append("## Structural Fitness")
        if report.structural_fitness.mismatches:
            lines.append("**Pattern mismatches (prose not matching structure):**")
            for m in report.structural_fitness.mismatches:
                lines.append(f"- {m.pattern} (at: {m.location})")
        if report.structural_fitness.unnecessary_structure:
            lines.append("**Unnecessary structure:**")
            for u in report.structural_fitness.unnecessary_structure:
                lines.append(f"- {u.pattern}: {u.location}")
        lines.append("")

    # Authority Signals
    if (
        report.authority_signals.citations_present
        or report.authority_signals.citations_missing
        or report.authority_signals.placeholder_citations
    ):
        lines.append("## Authority Signals")
        if report.authority_signals.citations_present:
            lines.append("**Real citations:**")
            for c in report.authority_signals.citations_present:
                src = f" ({c.source})" if c.source else ""
                lines.append(f"- {c.text}{src}")
        if report.authority_signals.citations_missing:
            lines.append("**Missing citations (would strengthen claims):**")
            for m in report.authority_signals.citations_missing:
                lines.append(f"- {m.get('claim', '')}: {m.get('why_needed', '')}")
        if report.authority_signals.placeholder_citations:
            lines.append("**Placeholder or vague citations:**")
            for p in report.authority_signals.placeholder_citations:
                lines.append(f"- {p.text} ({p.issue})")
        lines.append("")

    # Honest Placeholders
    if report.honest_placeholders:
        lines.append("## Placeholder Honesty")
        if report.honest_placeholders.at_real_gaps:
            lines.append("**Placeholders at real gaps:**")
            for p in report.honest_placeholders.at_real_gaps:
                lines.append(f"- {p.text} ({p.gap_type})")
        if report.honest_placeholders.decorative:
            lines.append("**Decorative placeholders:**")
            for p in report.honest_placeholders.decorative:
                lines.append(f"- {p.text}: {p.reason}")
        lines.append("")

    # What Cannot Be Fixed by Rewriting
    if report.what_cannot_be_fixed:
        lines.append("## What Cannot Be Fixed by Rewriting")
        lines.append(report.what_cannot_be_fixed)
        lines.append("")

    # Strengths
    lines.append("## Strengths")
    for strength in report.strengths:
        lines.append(f"- {strength}")
    lines.append("")

    # Confidence Notes
    if report.confidence_notes:
        lines.append("## Confidence Notes")
        for note in report.confidence_notes:
            lines.append(f"- **{note.get('finding', '')}**: {note.get('reason', '')}")
        lines.append("")

    return "\n".join(lines)


async def evaluate_page(request: AdvisorRequest) -> tuple[str, bool]:
    """
    Evaluate a page and return (markdown_report, should_generate_prompt).

    Args:
        request: AdvisorRequest with url/content and optional original

    Returns:
        (markdown_report, should_generate_prompt)
    """
    # Fetch or use provided content
    content = request.content
    if request.url and not request.content:
        html = _fetch_page(request.url)
        content = _html_to_markdown(html)

    # Call critic
    provider, model = _get_model()
    if provider == "openai":
        response_data = _call_openai_critic(content, request.original_content)
    else:
        response_data = _call_gemini_critic(content, request.original_content)

    # Parse response
    report = _parse_critic_response(response_data, request.original_content)

    # Update assessment based on verdict
    if report.factual_grounding.verdict == "minimal":
        report.what_cannot_be_fixed = (
            "This page's substance is too thin at the source level. Rewriting won't add facts that aren't there. "
            "The author should expand the content with specific facts, citations, and examples."
        )

    # Render to markdown
    markdown = _render_report_to_markdown(report)

    return markdown, report.should_generate_prompt
