"""
Advisor service (Tool A) — Content quality evaluation for AI retrieval.

Evaluates page across 6 properties with findings traceable to specific text.
No scoring. Optional: generates rewrite prompt or diagnosis.

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md

v2.6 Cycle CC: migrated through :class:`api.services.ai_router.AIRouter`.
The previous direct-to-httpx call sites (``_call_openai_critic``,
``_call_gemini_critic``) and module-level provider state (``_OPENAI_API_KEY``,
``_GEMINI_API_KEY``, ``_OPENAI_ENDPOINT``, ``_GEMINI_ENDPOINT``, ``_TIMEOUT``)
have been removed. AIRouter now handles credential resolution, provider
selection, cost tracking, and usage logging uniformly.

``_fetch_page`` continues to use ``httpx.Client`` — it fetches target page
HTML (SSRF-guarded), not LLM endpoints, so it's outside the migration
scope per the approved spec.

Per the user's approved JSON-mode decision (option A): the OpenAI
``response_format`` hint is removed. The prompt already mandates "Return
valid JSON only" and OpenAI / Gemini comply reliably on gpt-4o /
gemini-2.0-flash. Parse failures get graceful degradation rather than
propagating as 5xx — see ``_run_critic`` below.
"""

import json
import logging
from typing import Any

import httpx
from dotenv import load_dotenv

from api.crawler.fetcher import is_ssrf_safe
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
from api.services.ai_router import (
    ModelConfig,
    ProviderAuthError,
    SYSTEM_CONTEXT_ID,
    ai_router,
)

load_dotenv()
load_dotenv(".env-ttoad", override=True)

logger = logging.getLogger(__name__)


# ── Page-fetch timeout — local to _fetch_page only ──────────────────────
# The LLM-call timeout was 30s pre-migration; AIRouter's drivers manage
# their own (60s for text). The page-fetch timeout below applies to
# `_fetch_page` exclusively — it fetches arbitrary target page HTML, not
# provider APIs.
_PAGE_FETCH_TIMEOUT_SECONDS = 30.0


# ── Default models per provider (for AIRouter calls) ────────────────────
# Same model strings used by the pre-migration code. Both in PRICING.
_DEFAULT_CRITIC_MODEL_BY_PROVIDER = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
}


def _pick_critic_model() -> ModelConfig:
    """Pre-flight credential resolution so we pass the right model
    string to AIRouter. Same pattern as rewriter.py / ai_analyzer.py.
    Falls back to the OpenAI default if resolution fails — AIRouter
    will raise ProviderAuthError on the actual call and ``evaluate_page``
    converts that to the appropriate degraded response.
    """
    try:
        provider, _ = ai_router._resolve_credentials(SYSTEM_CONTEXT_ID)
    except ProviderAuthError:
        provider = "openai"
    model = _DEFAULT_CRITIC_MODEL_BY_PROVIDER.get(
        provider, _DEFAULT_CRITIC_MODEL_BY_PROVIDER["openai"]
    )
    # Critic responses are JSON, can be substantial — give them room.
    # Same temperature (0.2) as pre-migration for deterministic critic output.
    return ModelConfig(model=model, max_tokens=4000, temperature=0.2)


def _fetch_page(url: str) -> str:
    """Fetch page HTML from URL."""
    # v2.3 (M0.6.3) SSRF guard: refuse to fetch URLs that resolve to
    # private/internal addresses (localhost, 169.254.169.254 AWS metadata,
    # RFC1918 ranges, IPv6 loopback/link-local). Without this, the advisor
    # endpoint can be coerced into reaching internal services.
    if not is_ssrf_safe(url):
        logger.warning("advisor_ssrf_blocked", extra={"url": url})
        raise RuntimeError(
            f"SSRF_BLOCKED: URL resolves to a private/internal address: {url}"
        )
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
        with httpx.Client(timeout=_PAGE_FETCH_TIMEOUT_SECONDS, headers=headers) as client:
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


async def _run_critic(content: str, original: str | None) -> dict:
    """Send the critic prompt through AIRouter and return parsed JSON.

    Single entry point replacing the pre-Cycle-CC pair of
    ``_call_openai_critic`` / ``_call_gemini_critic``. AIRouter selects
    the provider via credential resolution; this function only builds
    the prompts, dispatches, and parses.

    Behaviour preserved:
        - Same system + user prompts as the OpenAI critic
          (the Gemini critic had a slimmer user prompt; we unify on the
          richer OpenAI prompt since Gemini handles the longer instruction
          fine and the explicit schema reduces parse failures).
        - Same temperature (0.2) and JSON-only output rule.
        - Same response-shape contract (parsed dict matching
          ``_parse_critic_response``'s expectations).

    Behaviour changed (intentional per the approved spec):
        - No more ``response_format`` hint (OpenAI-specific —
          ModelConfig is provider-neutral per Cycle Z). Prompt + parse
          handle JSON discipline.
        - Async — pre-migration ``httpx.Client`` was sync inside an async
          ``evaluate_page``, blocking the event loop. AIRouter is async,
          so this call no longer blocks.
        - Errors raise ``api.services.ai_router.AIRouterError`` subclasses
          rather than the old generic ``Exception``. ``evaluate_page``
          catches both classes — ``ProviderAuthError`` for "no key" and
          generic Exception for parse / API failures — and degrades
          gracefully (see ``evaluate_page`` docstring).

    Raises:
        ProviderAuthError: no customer key and no system env key.
        ProviderAPIError: provider HTTP failure (5xx, network, etc.).
        ValueError: the LLM returned content that didn't parse as JSON
            after the standard cleanup. Distinct from the AIRouter
            exceptions so the caller's graceful-degrade path can
            distinguish billing-relevant from parse-failure scenarios.
    """
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

Return valid JSON only. No markdown wrapping. Do not include explanatory text before or after the JSON object."""

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

    cfg = _pick_critic_model()
    response = await ai_router.call_text(
        customer_id=SYSTEM_CONTEXT_ID,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_config=cfg,
    )

    # AIRouter has already logged usage with success=True (per its
    # _call() success-path). The actual response text now needs to parse
    # as JSON. Per the approved spec (option A), there's no provider-
    # level JSON-mode hint — we rely on the prompt above + the parse
    # block below. If parsing fails we raise ValueError so the caller
    # can produce a graceful-degrade markdown report rather than 500.
    raw = response.content.strip()
    # Strip markdown code-block fences if the model added them despite
    # the instruction. Mirrors the same cleanup ai_analyzer.py uses.
    if raw.startswith("```"):
        # Drop the first line (opening fence + optional lang) and any
        # closing fence at end.
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        # TODO(M2.5): once the ai_usage table exists, record this as
        # success=False with a "parse_failure" category. Today we
        # surface it via the standard logger only — the AIRouter usage
        # log already has success=True for this call because the HTTP
        # exchange itself succeeded; parse failure is a downstream
        # application-layer concern, not a billing event.
        logger.warning(
            "advisor_critic_json_parse_failed",
            extra={
                "provider": response.provider_id,
                "model": response.model,
                "input_tokens": response.input_token_count,
                "output_tokens": response.output_token_count,
                "raw_excerpt": raw[:200],
                "error": str(exc),
            },
        )
        raise ValueError(
            f"Critic response did not parse as JSON: {exc!s}"
        ) from exc

    if not isinstance(parsed, dict):
        # Some models return JSON arrays / nulls under stress. The
        # downstream parser expects a dict; surface this as the same
        # kind of failure as a JSONDecodeError.
        logger.warning(
            "advisor_critic_json_wrong_type",
            extra={
                "provider": response.provider_id,
                "model": response.model,
                "got_type": type(parsed).__name__,
            },
        )
        raise ValueError(
            f"Critic response parsed but not as a JSON object "
            f"(got {type(parsed).__name__})"
        )

    logger.info(f"Critic response keys: {list(parsed.keys())}")
    logger.info(
        f"Factual grounding: "
        f"{parsed.get('factual_grounding', {}).get('verdict', 'N/A')}"
    )
    return parsed


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

    Graceful-degrade contract (Cycle CC):
        - Page fetch failure → returns a "Page could not be analyzed"
          markdown stub with should_generate_prompt=False. Same as
          pre-migration.
        - ``ProviderAuthError`` from AIRouter (no customer key + no env
          key) → returns "AI advisor unavailable: no API key configured"
          markdown stub, should_generate_prompt=False. Replaces the
          pre-migration RuntimeError-bubble-to-5xx behaviour.
        - ``ValueError`` from ``_run_critic`` (LLM returned non-JSON) →
          returns a "Critic response could not be parsed" markdown
          stub. AIRouter has already logged the underlying HTTP call as
          success=True; the application-level parse failure is logged
          via the standard logger inside ``_run_critic``.
          (TODO(M2.5): once ai_usage table exists, escalate parse
          failures to a success=False billing event.)
        - Any other AIRouter exception (``ProviderAPIError``, etc.) →
          re-raised. The advisor router maps these to 5xx with an
          error envelope — AIRouter's _log_usage success=False entry
          already captured the failure for observability.
    """
    logger.info(f"evaluate_page START: url={request.url}, has_content={bool(request.content)}")

    # Fetch or use provided content
    content = request.content
    if request.url and not request.content:
        logger.info(f"Fetching page from {request.url}")
        try:
            html = _fetch_page(request.url)
            content = _html_to_markdown(html)
            logger.info(f"Fetched content length: {len(content)} chars")
        except Exception as fetch_error:
            logger.info(f"Skipping advisor analysis — page could not be fetched: {fetch_error}")
            skip_markdown = (
                f"# Page could not be analyzed\n\n"
                f"The advisor was unable to fetch this page (`{request.url}`):\n\n"
                f"> {fetch_error}\n\n"
                f"Refer to the Broken Links / Crawlability sections of your SEO report "
                f"for diagnosis of this page."
            )
            return skip_markdown, False

    # Call critic via AIRouter.
    logger.info("Calling critic via AIRouter...")
    try:
        response_data = await _run_critic(content, request.original_content)
    except ProviderAuthError:
        logger.warning("advisor_skipped_no_key")
        skip_markdown = (
            "# AI advisor unavailable\n\n"
            "The Content Advisor needs an AI provider key to evaluate this page. "
            "Configure `OPENAI_API_KEY` or `GEMINI_API_KEY` in your environment, "
            "or set a per-customer key in Settings (when available)."
        )
        return skip_markdown, False
    except ValueError as parse_error:
        # JSON parse failure inside _run_critic. Already logged with
        # full context there; here we produce the user-facing graceful
        # degradation. Per Cycle CC strategic advisory: do not let the
        # raw error bubble to the client.
        logger.info(f"Advisor parse failure → graceful degrade: {parse_error}")
        skip_markdown = (
            "# Critic response could not be parsed\n\n"
            "The AI critic returned a response that did not parse as expected. "
            "This typically resolves on retry — please run the analysis again.\n\n"
            "If the issue persists, the source content may be unusual enough "
            "(very long, heavily encoded, etc.) that the critic model is "
            "struggling to produce structured output."
        )
        return skip_markdown, False

    logger.info(f"Critic response received, keys: {list(response_data.keys())}")

    # Parse response
    logger.info("Parsing critic response...")
    report = _parse_critic_response(response_data, request.original_content)
    logger.info(f"Report parsed: verdict={report.factual_grounding.verdict}")

    # Update assessment based on verdict
    if report.factual_grounding.verdict == "minimal":
        report.what_cannot_be_fixed = (
            "This page's substance is too thin at the source level. Rewriting won't add facts that aren't there. "
            "The author should expand the content with specific facts, citations, and examples."
        )

    # Render to markdown
    logger.info("Rendering report to markdown...")
    markdown = _render_report_to_markdown(report)
    logger.info(f"Markdown rendered: {len(markdown)} chars")

    return markdown, report.should_generate_prompt
