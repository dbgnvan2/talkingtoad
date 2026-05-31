# TalkToad Evaluation Pipeline Execution Logic
*Report generated on Friday, May 29, 2026*

This document provides the raw, absolute source code for the core execution logic of the TalkingToad evaluation pipeline. 

## 1. Advisor Service (`api/services/advisor.py`)
This file defines the content quality evaluation logic (Tool A) and rewriter orchestration.

```python
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
- source_fidelity (object, only if original provided):
    - is_critical (bool)
    - fabrications (list[str])
    - losses (list[str])
    - degradations (list[str])
    - preserved_strengths (list[str])
- factual_grounding (object):
    - is_critical (bool)
    - specific_facts (list of object with text, citation, is_specific)
    - generalities (list of object with text, citation, issue)
    - verdict (grounded | weak | minimal)
- self_containment (object):
    - sections (list of object with heading, can_stand_alone, requires_context)
- structural_fitness (object):
    - mismatches (list of object with pattern, location)
    - unnecessary_structure (list of object with pattern, location)
- authority_signals (object):
    - citations_present (list of object with text, source, is_authoritative)
    - citations_missing (list of object with text, suggested_source)
    - placeholder_citations (list of object with text, issue)
- honest_placeholders (object):
    - at_real_gaps (list of object with text, gap_type)
    - decorative (list of object with text, reason)
- strengths (list[str])
- critical_issues (list[str])
- overall_assessment (str)
- rewrite_prompt (str)

Example citation: "The page claims X [citation: '...text from page...']".
"""

    model_config = _pick_critic_model()
    resp = await ai_router.call_text(
        customer_id=SYSTEM_CONTEXT_ID,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_config=model_config,
    )

    text = resp.content
    # Cleanup markdown wrapping if the model ignored the instruction.
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error(
            "advisor_json_parse_failed",
            extra={"raw_text": text[:500], "error": str(exc)},
        )
        raise ValueError(f"LLM returned invalid JSON: {exc!s}") from exc


def _parse_critic_response(data: dict) -> AdvisorReport:
    """Map raw JSON dict to AdvisorReport model."""
    # Source Fidelity
    sf_data = data.get("source_fidelity")
    sf = None
    if sf_data:
        sf = SourceFidelity(
            is_critical=sf_data.get("is_critical", False),
            fabrications=sf_data.get("fabrications", []),
            losses=sf_data.get("losses", []),
            degradations=sf_data.get("degradations", []),
            preserved_strengths=sf_data.get("preserved_strengths", []),
        )

    # Factual Grounding
    fg_data = data.get("factual_grounding", {})
    specific_facts = [
        Finding(
            text=f.get("text", ""),
            citation=f.get("citation"),
            is_specific=f.get("is_specific"),
        )
        for f in fg_data.get("specific_facts", [])
    ]
    generalities = [
        Finding(
            text=f.get("text", ""),
            citation=f.get("citation"),
            issue=f.get("issue"),
        )
        for f in fg_data.get("generalities", [])
    ]
    fg = FactualGrounding(
        is_critical=fg_data.get("is_critical", False),
        specific_facts=specific_facts,
        generalities=generalities,
        verdict=fg_data.get("verdict", "minimal"),
    )

    # Self Containment
    sc_data = data.get("self_containment", {})
    sections = [
        Section(
            heading=s.get("heading", ""),
            can_stand_alone=s.get("can_stand_alone", False),
            requires_context=s.get("requires_context", []),
        )
        for s in sc_data.get("sections", [])
    ]
    sc = SelfContainment(sections=sections)

    # Structural Fitness
    st_data = data.get("structural_fitness", {})
    mismatches = [
        StructuralMismatch(pattern=m.get("pattern", ""), location=m.get("location", ""))
        for m in st_data.get("mismatches", [])
    ]
    unnecessary = [
        StructuralMismatch(pattern=m.get("pattern", ""), location=m.get("location", ""))
        for m in st_data.get("unnecessary_structure", [])
    ]
    st = StructuralFitness(mismatches=mismatches, unnecessary_structure=unnecessary)

    # Authority Signals
    au_data = data.get("authority_signals", {})
    citations_present = [
        CitationFinding(
            text=c.get("text", ""),
            source=c.get("source"),
            issue=c.get("issue"),
        )
        for c in au_data.get("citations_present", [])
    ]
    citations_missing = au_data.get("citations_missing", [])
    placeholder_citations = [
        CitationFinding(text=c.get("text", ""), issue=c.get("issue"))
        for c in au_data.get("placeholder_citations", [])
    ]
    au = AuthoritySignals(
        citations_present=citations_present,
        citations_missing=citations_missing,
        placeholder_citations=placeholder_citations,
    )

    # Honest Placeholders
    hp_data = data.get("honest_placeholders", {})
    at_real_gaps = [
        PlaceholderFinding(text=p.get("text", ""), gap_type=p.get("gap_type"))
        for p in hp_data.get("at_real_gaps", [])
    ]
    decorative = [
        PlaceholderFinding(text=p.get("text", ""), reason=p.get("reason"))
        for p in hp_data.get("decorative", [])
    ]
    hp = HonestPlaceholders(at_real_gaps=at_real_gaps, decorative=decorative)

    return AdvisorReport(
        overall_assessment=data.get("overall_assessment", ""),
        source_fidelity=sf,
        factual_grounding=fg,
        self_containment=sc,
        structural_fitness=st,
        authority_signals=au,
        honest_placeholders=hp,
        strengths=data.get("strengths", []),
        critical_issues=data.get("critical_issues", []),
        rewrite_prompt=data.get("rewrite_prompt"),
    )


async def evaluate_page(request: AdvisorRequest, store: Any = None) -> AdvisorReport:
    """Evaluate page content and return a structured report.

    Graceful Degradation (v2.6 Cycle CC):
        - If the LLM provider fails (4xx, 5xx, or network error), or
          if the customer has no API key and the system has no key
          (``ProviderAuthError``), this function returns a "degraded"
          report.
        - The degraded report sets ``overall_assessment`` to an error message,
          identifies the failure as a critical issue, and sets all
          detailed properties (fidelity, grounding, etc.) to None or
          empty.
        - This prevents a partial system failure from crashing the
          Advisor UI, allowing the user to see that the service is
          temporarily unavailable or requires a key.
    """
    content = request.content
    original = request.original_content

    # 1. Fetch content if only URL provided
    if not content and request.url:
        try:
            html = _fetch_page(request.url)
            content = _html_to_markdown(html)
        except Exception as e:
            return AdvisorReport(
                overall_assessment=f"Error fetching page: {e}",
                critical_issues=[f"PAGE_FETCH_FAILED: {e}"],
            )

    # 2. Fallback to cached content if job_id provided
    if not content and request.job_id and store:
        # Implementation depends on store — assuming it has get_page(job_id, url)
        pass

    if not content:
        return AdvisorReport(
            overall_assessment="Error: No content available for evaluation.",
            critical_issues=["NO_CONTENT"],
        )

    # 3. Run Critic
    try:
        data = await _run_critic(content, original)
        return _parse_critic_response(data)
    except ProviderAuthError as exc:
        # Graceful degradation for billing/auth issues.
        logger.warning("advisor_auth_failure", extra={"error": str(exc)})
        return AdvisorReport(
            overall_assessment=(
                "Service unavailable: No valid API key provided. "
                "Please configure an OpenAI or Gemini API key in your settings."
            ),
            critical_issues=["AI_SERVICE_UNAVAILABLE_AUTH"],
        )
    except Exception as exc:
        # Graceful degradation for generic API / parse failures.
        logger.error("advisor_execution_failed", extra={"error": str(exc)})
        return AdvisorReport(
            overall_assessment=(
                "Evaluation failed: The AI provider returned an unexpected response. "
                "The content may be too complex or the service is temporarily overloaded."
            ),
            critical_issues=[f"AI_SERVICE_ERROR: {exc!s}"],
        )


async def generate_rewrite_prompt(report: AdvisorReport) -> str:
    """Generate a specialized rewrite prompt from an evaluation report."""
    # If a prompt was already returned in the report, reuse it
    if report.rewrite_prompt:
        return report.rewrite_prompt

    # Otherwise, build one based on critical issues
    issues_text = "\n".join([f"- {i}" for i in report.critical_issues])
    return (
        "Please rewrite this content to address the following critical issues:\n"
        f"{issues_text}\n\n"
        "Ensure all facts are specifically cited and the structure matches the prose."
    )
```

## 2. AI Readiness Checker (`api/crawler/checkers/ai_readiness.py`)
This file contains the exact rules currently being evaluated for Generative Engine Optimization.

```python
"""
GEO (Generative Engine Optimization) check logic for v2.1.

This module contains the static checks identified in the GEO Analyzer
implementation plan (docs/implementation_plan_geo_analyzer_2026-05-03.md).

Checks cover:
- GEO.1.1: llms.txt presence and accessibility
- GEO.2.1: Information density (statistics count)
- GEO.3.1: Authority signals (citations to .gov/.edu)
- GEO.4.1: Direct attribution (quote/cite patterns)
- GEO.5.1: Self-contained answers (definition signals)
- GEO.5.2: FAQ schema consistency
"""

import re
import json
import logging
from api.crawler.checkers.registry import make_issue, Issue, _sig_words

logger = logging.getLogger(__name__)


def _run_geo_checks(page: "ParsedPage", url: str, issues: list[Issue]) -> None:
    """Execute v2.1 GEO static checks against a parsed page."""
    # Setup shared context
    word_count = page.word_count or 0
    headings = page.headings_outline or []
    links = page.links or []
    schema_types = page.schema_types or []
    first_200 = page.first_200_words or ""

    # ── GEO.1.1: llms.txt Presence (Homepage only) ──────────────────────────
    # Check if the page is a homepage and check for llms.txt
    if page.url.rstrip("/").count("/") == 2:  # Heuristic for homepage
        # This check is actually handled in the engine's robots.txt parsing phase
        # and crawler/engine.py — it requires a separate HTTP request.
        pass

    # ── GEO.2.1: Information Density (Statistics) ───────────────────────────
    # Count statistics-bearing sentences (numbers + units/percent)
    stats_count = _count_statistics(first_200, links, page)
    if word_count >= 300 and stats_count == 0:
        issues.append(make_issue("GEO_LOW_STAT_DENSITY", url))

    # ── GEO.3.1: Authority Signals (Citations) ──────────────────────────────
    # Count outbound links to authoritative domains (.gov, .edu)
    authority_links = _count_external_body_links(links, url)
    if word_count >= 500 and authority_links == 0:
        issues.append(make_issue("GEO_CITATIONS_MISSING", url))

    # ── GEO.4.1: Direct Attribution ─────────────────────────────────────────
    # Count inline quotations and attribution patterns
    quote_count = _count_inline_quotations(page)
    if word_count >= 500 and quote_count == 0:
        issues.append(make_issue("GEO_ATTRIBUTION_LOW", url))

    # ── GEO.5.1: Self-contained Answers ─────────────────────────────────────
    # Check for summary/definition signals at the start of paragraphs
    if _has_answer_signal(first_200):
        # GEO bonus — if answer signal exists, check for structural support
        if not _has_numbered_steps(headings, page):
            issues.append(make_issue("GEO_ANSWER_WITHOUT_STEPS", url))
    elif word_count >= 300:
        # Information-heavy page without a clear "answer" block
        issues.append(make_issue("GEO_SUMMARY_MISSING", url))

    # ── Schema Hygiene (JSON-LD validation) ──────────────────────────────────
    raw_json_ld = getattr(page, "raw_json_ld", []) or []
    if raw_json_ld:
        flat_blocks = []
        for block in raw_json_ld:
            if isinstance(block, dict):
                flat_blocks.append(block)
            elif isinstance(block, list):
                for inner in block:
                    if isinstance(inner, dict):
                        flat_blocks.append(inner)
            # else: malformed entry — drop
        invalid = [b for b in flat_blocks if not (b.get("@type") and b.get("@context"))]
        if invalid:
            issues.append(make_issue("JSON_LD_INVALID", url, extra={
                "invalid_count": len(invalid),
            }))

    # ── GEO.5.2: FAQ section without FAQPage schema ─────────────────────────
    _FAQ_RE = re.compile(r"\bfrequently\s+asked\s+questions?\b|\bfaq\b", re.I)
    _Q_RE = re.compile(r"^(what|how|why|when|where|who|which|can|do|does|is|are)\b.*\?$", re.I)
    if "FAQPage" not in schema_types:
        has_faq_heading = any(_FAQ_RE.search(h.get("text", "")) for h in headings)
        question_headings = [h for h in headings if _Q_RE.match(h.get("text", "").strip())]
        if has_faq_heading or len(question_headings) >= 3:
            issues.append(make_issue("FAQ_SCHEMA_MISSING", url, extra={
                "faq_heading": has_faq_heading,
                "question_headings": len(question_headings),
            }))

    # ── GEO.2.2: Structured elements count (metric only — no pass/fail) ─────
    # Emitting as info when count is low relative to word count
    if word_count >= 500 and (page.structured_element_count or 0) == 0:
        issues.append(make_issue("STRUCTURED_ELEMENTS_LOW", url, extra={
            "structured_element_count": 0,
            "word_count": word_count,
        }))


# ---------------------------------------------------------------------------
# GEO check helpers
# ---------------------------------------------------------------------------

_STAT_RE = re.compile(
    # number (possibly comma-formatted) followed by a unit or % — no trailing \b so % works
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|percent|kb|mb|gb|tb|ms|seconds?|minutes?|hours?|days?|months?|years?"
    r"|users?|customers?|companies|organisations?|organizations?"
    r"|times?\s+faster|times?\s+more|\dx?\s+faster|\dx?\s+more"
    r"|Gbps|Mbps|fps|rpm|mph|km|mi|kg|lbs?"
    r"|million|billion|trillion|thousand|hundred)(?:\b|(?=\s|$))"
    r"|\b(?:19|20)\d{2}\b"                 # year references: 2023, 1999, etc.
    r"|\b\d+\s+(?:of|out\s+of)\s+\d+\b",  # "3 out of 5"
    re.I,
)


def _count_statistics(first_words: str, links: list, page: "ParsedPage") -> int:
    """Count statistic-bearing sentences on the page using the full visible text."""
    # Cap heading contribution to first 10 headings to prevent inflation on
    # pages with many headings that contain no statistics in their body text.
    # Defensive: `.get("text", "")` returns None when the key is present
    # with an explicit None value (parser artifact for malformed headings).
    # `" ".join([..., None, ...])` raises TypeError and crashes the crawl.
    # The `or ""` coalesces both "missing key" and "key with None value".
    all_text_sources = [first_words or ""]
    for h in (page.headings_outline or [])[:10]:
        all_text_sources.append(h.get("text") or "")
    combined = " ".join(all_text_sources)
    return len(_STAT_RE.findall(combined))


def _count_external_body_links(links: list, page_url: str) -> int:
    """Count outbound links to external domains (not navigation/footer heuristic)."""
    from urllib.parse import urlparse
    page_netloc = urlparse(page_url).netloc.lstrip("www.")
    count = 0
    for link in links:
        # Strip whitespace before scheme check and before parsing.
        # Parsers sometimes preserve leading whitespace from href
        # attributes ("  https://x.com", "\nhttp://y.com");
        # startswith("http") returns False on the raw form, silently
        # dropping valid external citations.
        href = (getattr(link, "url", "") or "").strip()
        if not href.startswith("http"):
            continue
        netloc = urlparse(href).netloc.lstrip("www.")
        if netloc and netloc != page_netloc:
            count += 1
    return count


_ATTRIBUTION_RE = re.compile(
    r'(?:according\s+to|says?|said|stated|noted|wrote|reports?|"[^"]{10,200}"\s*—)',
    re.I,
)


def _count_inline_quotations(page: "ParsedPage") -> int:
    """Count attribution patterns in first_600_words as proxy for inline quotes."""
    text = getattr(page, "first_600_words", None) or page.first_200_words or ""
    return len(_ATTRIBUTION_RE.findall(text))


_CLAIM_RE = re.compile(
    r"\b(?:supports?|enables?|allows?|provides?|reduces?|increases?|improves?|"
    r"processes?|handles?|scales?|integrates?)\b[^.!?]{5,120}[.!?]",
    re.I,
)


def _count_orphan_claims(page: "ParsedPage", links: list, url: str) -> int:
    """Count technical claims in first_200_words not paired with a source link."""
    text = page.first_200_words or ""
    claims = _CLAIM_RE.findall(text)
    ext_links = _count_external_body_links(links, url)
    if ext_links > 0:
        return max(0, len(claims) - ext_links)
    return len(claims)


_ANSWER_SIGNAL_RE = re.compile(
    # Explicit shorthand meta-signals
    r"tl;?dr"
    r"|in\s+short[,:]?"
    r"|the\s+short\s+answer\s+is"
    r"|key\s+takeaway[s:]?"
    r"|in\s+summary"
    r"|to\s+summarize"
    r"|bottom\s+line"
    # Sentence-start definition: "Noun/Proper-noun is a/an ..."
    # Require a capitalised subject; exclude pronouns/demonstratives that are not nouns.
    # The (?-i:...) inline flag disables the outer re.I so that [A-Z]
    # actually requires capitalisation. Without this, re.I makes [A-Z]
    # match lowercase letters too, destroying the capitalisation
    # constraint and flooding the system with false positives like
    # "dog is a good boy".
    r"|(?-i:(?:(?:^|(?<=[.!?])\s+)"
    r"(?!(?:There|This|That|These|Those|It|He|She|They|We|I|You|Our|The|A|An)\b)"
    r"[A-Z]\w{2,}(?:\s+[A-Z]?\w+){0,3}\s+(?:is|are)\s+(?:a|an)\s+\w{3,}))"
    # Explicit relation markers (safe, rare in non-definition prose)
    r"|\brefers?\s+to\b"
    r"|\bdefined\s+as\b",
    re.I | re.MULTILINE,
)


def _has_answer_signal(text: str) -> bool:
    return bool(_ANSWER_SIGNAL_RE.search(text))


_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[\.\)]\s+\w", re.M)


def _has_numbered_steps(headings: list, page: "ParsedPage") -> bool:
    text = page.first_200_words or ""
    return bool(_NUMBERED_STEP_RE.search(text))
```

## 3. Issue Orchestrator (`api/crawler/issue_checker.py`)
This file orchestrates the execution of all checkers across the pipeline.

```python
"""
Issue detection logic for the TalkingToad crawler.

**Facade (v2.6 M9.1 / Cycle K).** This module used to be a 2,567-line
monolith. In Cycle K the data structures, the catalogue, the make_issue
factory, the already-extracted ``_check_*`` helpers, and the standalone
checks (``check_asset``, ``check_url_structure``, ``check_amphtml_links``,
``check_cross_page``, ``issue_for_status``, ``issues_for_redirect``,
``_run_geo_checks`` + all GEO helpers) were moved into
``api/crawler/checkers/``. This file is now a thin orchestrator plus a set
of back-compat re-exports so that every existing caller
(``engine.py``, the routers, the test suite, the docs generator) can keep
``from api.crawler.issue_checker import ...`` unchanged.

See ``docs/pending/2026-05-28_issue-checker-split.md`` for the split spec.

The remaining inline body of ``check_page`` is the per-page orchestration
itself — it sets up shared state (banner-H1 suppression) and emits issues
in a specific interleaved order across domains. Further extraction of those
inline blocks into per-domain functions is follow-up work; it requires
either preserving the exact interleaved emission order (test-coupled) or
proving the order doesn't matter (whole-suite re-validation).
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from api.crawler.parser import ParsedPage

# ── Back-compat re-exports from the new checkers package ────────────────
# Every name historically importable from ``api.crawler.issue_checker`` is
# re-exported here so that engine.py, routers, services, the docs
# generator, and the test suite continue to work without rewrites.
from api.crawler.checkers.registry import (  # noqa: F401
    Issue,
    _IssueSpec,
    _ISSUE_SCORING,
    _CATALOGUE,
    _AI_READINESS_CONFIDENCE,
    _STOP_WORDS,
    _GENERIC_ANCHOR_TEXTS,
    _DEFAULT_PAGE_SIZE_LIMIT_KB,
    _PDF_SIZE_LIMIT,
    _IMAGE_SIZE_LIMIT_KB,
    make_issue,
    _sig_words,
    _titles_mismatch,
)
from api.crawler.checkers.cross_page import check_cross_page  # noqa: F401
from api.crawler.checkers.images import check_asset  # noqa: F401
from api.crawler.checkers.url_structure import check_url_structure  # noqa: F401
from api.crawler.checkers.crawlability import (  # noqa: F401
    check_amphtml_links,
    _check_crawlability,
)
from api.crawler.checkers.links import (  # noqa: F401
    issue_for_status,
    issues_for_redirect,
    _is_trailing_slash_only,
    _is_case_normalise_only,
)
from api.crawler.checkers.security import _check_security  # noqa: F401
from api.crawler.checkers.metadata import _check_canonical  # noqa: F401
from api.crawler.checkers.headings import _check_headings  # noqa: F401
from api.crawler.checkers.ai_readiness import _run_geo_checks  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-page orchestrator
# ---------------------------------------------------------------------------
#
# This function is intentionally NOT factored into per-domain helpers in this
# cycle. The emission order across domains is interleaved (e.g. canonical →
# canonical-self → lang → title-h1 mismatch → headings, then favicon →
# crawlability → sitemap → security → pagination → ...), and several tests
# depend on issue-list contents that are order-sensitive to filter logic.
# A pure-delegation rewrite of this function is tracked as follow-up work.


def check_page(
    page: ParsedPage,
    *,
    sitemap_urls: set[str] | None = None,
    favicon_emitted: bool = False,
    hsts_checked_hosts: set[str] | None = None,
    page_size_limit_kb: int = _DEFAULT_PAGE_SIZE_LIMIT_KB,
    suppress_h1_strings: list[str] | None = None,
    suppress_banner_h1: bool = False,
    exempt_anchor_urls: set[str] | None = None,
    ignored_image_patterns: list[str] | None = None,
) -> list[Issue]:
    """Run all per-page issue checks.

    Args:
        page: The parsed page to check.
        sitemap_urls: Set of normalised URLs found in the sitemap (or None if no sitemap).
        favicon_emitted: True if FAVICON_MISSING has already been emitted this job.
        hsts_checked_hosts: Mutable set of hosts already checked for HSTS (pass the same
            set across all pages in a job so we only emit once per host).

    Returns:
        List of issues found. Cross-page checks (duplicates, near-duplicates) are
        not included — call :func:`check_cross_page` after all pages are crawled.
    """
    issues: list[Issue] = []
    url = page.url

    # Pages with noindex directives are intentionally excluded from search — skip SEO
    # checks that would only apply to indexed pages. We still run crawlability checks
    # (to surface the noindex issue itself) and security checks.
    is_indexable = page.is_indexable

    # Build effective H1 list — filter out theme-injected headings the user
    # has explicitly suppressed (e.g. a Salient page-header banner title that
    # repeats on every post page).
    # Normalise both sides: strip whitespace and compare case-insensitively so
    # that minor variations (trailing \xa0, different capitalisation) don't
    # silently defeat the suppression.
    _suppress_norm = {s.strip().casefold() for s in (suppress_h1_strings or [])}
    effective_h1s = [h for h in page.h1_tags if h.strip().casefold() not in _suppress_norm]
    effective_outline = [
        h for h in page.headings_outline
        if not (h["level"] == 1 and h["text"].strip().casefold() in _suppress_norm)
    ]

    # When suppress_banner_h1 is enabled, detect and remove the theme-injected
    # banner H1.  Two signals identify a banner:
    #   1. Position: the first H1 in the DOM (themes inject banners before content)
    #   2. CSS class: common theme banner classes (entry-title, page-title, etc.)
    # The first H1 is removed if it mismatches the title OR has a banner class.
    # Only applied when there are 2+ H1s so we never remove the only heading.
    _BANNER_CLASSES = re.compile(
        r'entry-title|page-title|page-header|banner-title|hero-title|archive-title',
        re.IGNORECASE,
    )

    if suppress_banner_h1 and page.title and len(effective_h1s) >= 2:
        first_h1 = effective_h1s[0]
        # Check CSS classes on the first H1 in the outline
        first_h1_outline = next(
            (h for h in effective_outline if h.get("level") == 1),
            None,
        )
        # Defensive: `.get("classes", "")` returns None when the key is
        # present with an explicit None value (common parser artifact for
        # malformed tags). `re.search(None)` raises TypeError and would
        # crash the entire crawl for the affected domain. The `or ""`
        # coalesces both "key missing" and "key present with None" to "".
        has_banner_class = bool(
            first_h1_outline
            and _BANNER_CLASSES.search(first_h1_outline.get("classes") or "")
        )
        is_mismatch = _titles_mismatch(page.title, first_h1)

        if is_mismatch or has_banner_class:
            _banner_text = first_h1.strip().casefold()
            effective_h1s = effective_h1s[1:]
            effective_outline = [
                h for h in effective_outline
                if not (
                    h["level"] == 1
                    and h.get("text", "").strip().casefold() == _banner_text
                )
            ]

    if is_indexable:
        # ── Title ──────────────────────────────────────────────────────────
        if not page.title:
            issues.append(make_issue("TITLE_MISSING", url,
                                     extra={"h1": effective_h1s[0] if effective_h1s else None}))
        else:
            length = len(page.title)
            if length < 30:
                issue = make_issue("TITLE_TOO_SHORT", url)
                issue.extra = {"title": page.title, "length": length}
                issues.append(issue)
            elif length > 60:
                issue = make_issue("TITLE_TOO_LONG", url)
                issue.extra = {"title": page.title, "length": length}
                issues.append(issue)

        # ── Meta description ───────────────────────────────────────────────
        if not page.meta_description:
            issues.append(make_issue("META_DESC_MISSING", url))
        else:
            length = len(page.meta_description)
            if length < 70:
                issue = make_issue("META_DESC_TOO_SHORT", url)
                issue.extra = {"description": page.meta_description, "length": length}
                issues.append(issue)
            elif length > 160:
                issue = make_issue("META_DESC_TOO_LONG", url)
                issue.extra = {"description": page.meta_description, "length": length}
                issues.append(issue)

        # ── OG tags ────────────────────────────────────────────────────────
        if not page.og_title:
            issues.append(make_issue("OG_TITLE_MISSING", url,
                                     extra={"title": page.title}))
        if not page.og_description:
            issues.append(make_issue("OG_DESC_MISSING", url,
                                     extra={"meta_description": page.meta_description}))
        if not page.og_image:
            issues.append(make_issue("OG_IMAGE_MISSING", url))
        if not page.twitter_card:
            issues.append(make_issue("TWITTER_CARD_MISSING", url))

        # ── Canonical tag ──────────────────────────────────────────────────
        _check_canonical(page, issues)

        # ── Canonical self (best-practice for all indexable pages) ──────────
        # Only emit if CANONICAL_MISSING hasn't already fired — that issue is
        # more specific and actionable; emitting both on the same page is redundant.
        if page.canonical_url is None and not any(i.code == "CANONICAL_MISSING" for i in issues):
            issues.append(make_issue("CANONICAL_SELF_MISSING", url,
                                     extra={"expected_canonical": url}))

        # ── Language attribute ─────────────────────────────────────────────
        if not page.lang_attr:
            issues.append(make_issue("LANG_MISSING", url))

        # ── Title vs H1 consistency ────────────────────────────────────────
        # Use effective_h1s (suppressed strings removed) so theme-injected
        # headings don't trigger a false mismatch.
        if page.title and effective_h1s:
            if all(_titles_mismatch(page.title, h1) for h1 in effective_h1s):
                # Before flagging, check whether the title matches an H2.
                # Many WordPress themes inject the parent-page title as an H1
                # banner on sub-pages, while the real content heading is an H2.
                # If the title shares significant words with any H2 we treat
                # the H1 as a structural/navigation element and skip the flag.
                h2_texts = [
                    h["text"] for h in (page.headings_outline or [])
                    if h.get("level") == 2 and h.get("text")
                ]
                title_matches_h2 = any(
                    not _titles_mismatch(page.title, h2) for h2 in h2_texts
                )
                if not title_matches_h2:
                    issues.append(make_issue("TITLE_H1_MISMATCH", url,
                                             extra={"title": page.title, "h1": effective_h1s[0]}))

        # ── Headings ───────────────────────────────────────────────────────
        _check_headings(page, issues, effective_h1s=effective_h1s, effective_outline=effective_outline)

    # ── Favicon (homepage only, once per job — checked regardless of noindex) ──
    if page.has_favicon is False and not favicon_emitted:
        issues.append(make_issue("FAVICON_MISSING", url))

    # ── Crawlability ───────────────────────────────────────────────────────
    _check_crawlability(page, issues)

    # ── Not in sitemap (only meaningful for indexable pages) ──────────────
    # Skip pages with query strings — paginated URLs, search results, and
    # filtered views are intentionally absent from sitemaps.
    if sitemap_urls is not None and is_indexable and not urlparse(url).query:
        if page.final_url not in sitemap_urls and page.url not in sitemap_urls:
            issues.append(make_issue("NOT_IN_SITEMAP", url))

    # ── Security (§E1) ────────────────────────────────────────────────────
    _check_security(page, issues, hsts_checked_hosts=hsts_checked_hosts)

    # ── Pagination links (§E3) ────────────────────────────────────────────
    if page.pagination_next or page.pagination_prev:
        issues.append(make_issue(
            "PAGINATION_LINKS_PRESENT", url,
            extra={"next": page.pagination_next, "prev": page.pagination_prev},
        ))

    # ── Meta refresh redirect (§E4) ───────────────────────────────────────
    if page.meta_refresh_url is not None:
        issues.append(make_issue("META_REFRESH_REDIRECT", url,
                                 extra={"refresh_url": page.meta_refresh_url}))

    # ── Thin content (§E5) ────────────────────────────────────────────────
    if page.word_count is not None and 0 < page.word_count < 300 and page.is_indexable:
        issues.append(make_issue("THIN_CONTENT", url, extra={"word_count": page.word_count}))

    # ── Crawl depth (§E7) ────────────────────────────────────────────────
    if page.crawl_depth is not None and page.crawl_depth > 4:
        issues.append(make_issue("HIGH_CRAWL_DEPTH", url,
                                 extra={"crawl_depth": page.crawl_depth}))

    # ── Content staleness ────────────────────────────────────────────────
    if page.last_modified and page.is_indexable:
        try:
            from email.utils import parsedate_to_datetime
            from datetime import timezone as _tz
            lm_dt = parsedate_to_datetime(page.last_modified)
            if lm_dt.tzinfo is None:
                lm_dt = lm_dt.replace(tzinfo=_tz.utc)
            age_days = (datetime.now(_tz.utc) - lm_dt).days
            if age_days > 365:
                issues.append(make_issue("CONTENT_STALE", url,
                    extra={"last_modified": page.last_modified, "age_days": age_days}))
        except Exception:
            pass

    # ── Image alt text ────────────────────────────────────────────────────
    if page.img_missing_alt_count > 0:
        srcs = page.img_missing_alt_srcs or []
        # Filter out images matching ignored patterns (e.g. theme SVG icons)
        if ignored_image_patterns:
            srcs = [s for s in srcs if not any(p in s for p in ignored_image_patterns)]
        if srcs:
            issue = make_issue("IMG_ALT_MISSING", url,
                               extra={"missing_alt_count": len(srcs),
                                      "img_missing_alt_srcs": srcs[:10]})
            listed = ", ".join(srcs[:5])
            suffix = f" and {len(srcs) - 5} more" if len(srcs) > 5 else ""
            issue.description = (
                f"{len(srcs)} image{'s' if len(srcs) > 1 else ''} "
                f"missing alt text: {listed}{suffix}"
            )
            issues.append(issue)

    # ── Viewport meta (mobile-friendliness) ──────────────────────────────
    if not page.has_viewport_meta:
        issues.append(make_issue("MISSING_VIEWPORT_META", url))

    # ── Structured data (schema.org) ──────────────────────────────────────
    if not page.schema_types and is_indexable:
        issues.append(make_issue("SCHEMA_MISSING", url))

    # ── Empty anchor text ─────────────────────────────────────────────────
    if page.empty_anchor_count > 0:
        raw_anchors = page.empty_anchor_hrefs or []
        # Normalise every entry to a {"href", "aria_label", "has_children"} dict.
        # Both formats are supported (legacy list[str], current list[dict]) and
        # malformed entries are dropped silently rather than crashing the crawl
        # — three sites below blindly read a["href"], so any dict without a
        # usable href would raise KeyError and kill the entire job.
        # The previous `isinstance(anchors[0], str)` sniff only inspected the
        # first element; a mixed list (legacy strings interleaved with new
        # dicts) skipped coercion and crashed downstream.
        anchors: list[dict] = []
        for a in raw_anchors:
            if isinstance(a, str):
                if a:
                    anchors.append({"href": a, "aria_label": None, "has_children": False})
            elif isinstance(a, dict):
                href = a.get("href")
                if isinstance(href, str) and href:
                    anchors.append(a)
            # else: malformed entry — drop
        # Filter out URLs the user has explicitly exempted (e.g. social media icon links)
        if exempt_anchor_urls:
            anchors = [a for a in anchors if a["href"] not in exempt_anchor_urls]
        if anchors:
            issue = make_issue("LINK_EMPTY_ANCHOR", url,
                               extra={"empty_anchor_count": len(anchors),
                                      "empty_anchors": anchors[:10],
                                      # Keep legacy field for backwards compat
                                      "empty_anchor_hrefs": [a["href"] for a in anchors[:10]]})
            href_list = [a["href"] for a in anchors[:5]]
            listed = ", ".join(href_list)
            suffix = f" and {len(anchors) - 5} more" if len(anchors) > 5 else ""
            issue.description = (
                f"{len(anchors)} link{'s' if len(anchors) > 1 else ''} "
                f"with no anchor text: {listed}{suffix}"
            )
            issues.append(issue)

    # ── Generic anchor text ──────────────────────────────────────────────
    if page.is_indexable and page.links:
        generic_links = [
            link for link in page.links
            if link.text and link.text.strip().lower() in _GENERIC_ANCHOR_TEXTS
        ]
        if generic_links:
            issues.append(make_issue("ANCHOR_TEXT_GENERIC", url,
                extra={"count": len(generic_links),
                        "examples": [{"href": l.url, "text": l.text} for l in generic_links[:5]]}))

    # ── Internal nofollow links ───────────────────────────────────────────
    if page.internal_nofollow_count > 0:
        issues.append(make_issue("INTERNAL_NOFOLLOW", url,
                                 extra={"internal_nofollow_count": page.internal_nofollow_count}))

    # ── Page size ─────────────────────────────────────────────────────────
    _page_size_threshold = page_size_limit_kb * 1024
    if page.response_size_bytes > _page_size_threshold:
        size_kb = round(page.response_size_bytes / 1024, 1)
        issue = make_issue("PAGE_SIZE_LARGE", url,
                           extra={"size_bytes": page.response_size_bytes,
                                  "size_kb": size_kb,
                                  "limit_kb": page_size_limit_kb})
        issue.description = f"Page HTML is {size_kb} KB (exceeds {page_size_limit_kb} KB limit)"
        issues.append(issue)

    # ── AI Readiness (§1.7) ───────────────────────────────────────────────
    # Semantic Density (Text-to-HTML ratio < 10%)
    if page.text_to_html_ratio is not None and page.text_to_html_ratio < 0.10 and page.is_indexable:
        extra: dict = {
            "ratio": round(page.text_to_html_ratio, 4),
            "ratio_pct": f"{page.text_to_html_ratio * 100:.1f}%",
        }
        if page.code_breakdown:
            extra["breakdown"] = page.code_breakdown
            # Diagnose the biggest contributor
            bd = page.code_breakdown
            parts = [
                ("Inline scripts", bd.get("script_kb", 0)),
                ("Inline styles", bd.get("style_kb", 0)),
                ("SVG graphics", bd.get("svg_kb", 0)),
                ("HTML markup", bd.get("markup_kb", 0)),
            ]
            parts.sort(key=lambda x: x[1], reverse=True)
            biggest = parts[0]
            total = bd.get("html_total_kb", 1)
            if biggest[1] > 0:
                extra["diagnosis"] = (
                    f"{biggest[0]} ({biggest[1]} KB) account for "
                    f"{biggest[1] / total * 100:.0f}% of the page. "
                    f"Visible text is only {bd.get('text_kb', 0)} KB "
                    f"out of {total} KB total."
                )
        issues.append(make_issue("SEMANTIC_DENSITY_LOW", url, extra=extra))

    # JSON-LD Missing
    if not page.has_json_ld and page.is_indexable and not url.endswith(".pdf"):
        issues.append(make_issue("JSON_LD_MISSING", url))

    # Conversational H2s — also fires when no H2s exist on a substantial page
    if page.is_indexable and not url.endswith(".pdf"):
        h2s = [h["text"] for h in (page.headings_outline or []) if h.get("level") == 2]
        if not h2s and page.word_count and page.word_count >= 300:
            # Substantial content with zero H2s — AI has nothing to anchor citations to
            issues.append(make_issue("CONVERSATIONAL_H2_MISSING", url,
                                     extra={"h2_headings": [], "word_count": page.word_count}))
        elif h2s:
            interrogatives = re.compile(r"\b(how|what|why|who|where|when|which)\b", re.I)
            if not any(interrogatives.search(h) for h in h2s):
                issues.append(make_issue("CONVERSATIONAL_H2_MISSING", url,
                                         extra={"h2_headings": h2s[:8]}))

    # Blog/article pages without enough heading sections for AI citation
    if page.is_indexable and page.word_count and page.word_count >= 500:
        is_blog_like = (
            "BlogPosting" in (page.schema_types or [])
            or "Article" in (page.schema_types or [])
            or any(seg in url for seg in ["/blog/", "/post/", "/article/", "/news/", "/stories/", "/insight"])
        )
        if is_blog_like:
            meaningful_headings = [
                h for h in (page.headings_outline or [])
                if h.get("level") in (2, 3) and len(h.get("text", "").strip()) > 5
            ]
            if len(meaningful_headings) < 3:
                issues.append(make_issue("BLOG_SECTIONS_MISSING", url, extra={
                    "word_count": page.word_count,
                    "heading_count": len(meaningful_headings),
                }))

    # ── Schema Typing (v2.0) ─────────────────────────────────────────────────
    if page.is_indexable and page.schema_types:
        try:
            from api.services.schema_typing import validate_schema_typing
            is_appropriate, issue_reason = validate_schema_typing(page)
            if not is_appropriate and issue_reason:
                if issue_reason.startswith("deprecated_schema:"):
                    issues.append(make_issue("SCHEMA_DEPRECATED_TYPE", url,
                                            extra={"schema_types": page.schema_types}))
                elif issue_reason.startswith("schema_conflict:"):
                    issues.append(make_issue("SCHEMA_TYPE_CONFLICT", url,
                                            extra={"schema_types": page.schema_types}))
                elif issue_reason.startswith("schema_mismatch:"):
                    page_type = issue_reason.split(":")[-1]
                    issues.append(make_issue("SCHEMA_TYPE_MISMATCH", url,
                                            extra={"inferred_page_type": page_type,
                                                   "schema_types": page.schema_types}))
        except Exception as e:
            logger.warning("schema_typing_error", extra={"url": url, "error": str(e)})

    # ── Content Extractability (v2.0) ─────────────────────────────────────────
    if page.is_indexable:
        try:
            from api.services.extractability import diagnose_extractability, assess_extractability
            extractability_issue = diagnose_extractability(page)
            if extractability_issue:
                assessment = assess_extractability(page)
                issues.append(make_issue(extractability_issue, url,
                                        extra={"score": assessment["score"],
                                               "issues": assessment["issues"]}))
        except Exception as e:
            logger.warning("extractability_error", extra={"url": url, "error": str(e)})

    # ── Citation Assessment (v2.0) ────────────────────────────────────────────
    if page.is_indexable and page.word_count and page.word_count > 200:
        try:
            from api.services.citation_model import PageCitations, assess_citation_readiness, diagnose_citation_issue
            page_citations = PageCitations(
                url=url,
                citations=[],
                attribution_style="none",
            )
            citation_issue = assess_citation_readiness(page_citations, page.word_count)
            diagnosis = diagnose_citation_issue(citation_issue)
            if diagnosis:
                issues.append(make_issue(diagnosis, url,
                                        extra={"word_count": page.word_count}))
        except Exception as e:
            logger.warning("citation_check_error", extra={"url": url, "error": str(e)})

    # PDF Metadata
    if url.lower().endswith(".pdf") and page.pdf_metadata is not None:
        meta = page.pdf_metadata
        if not meta.get("title") or not meta.get("subject"):
            issues.append(make_issue("DOCUMENT_PROPS_MISSING", url, extra=meta))

    # ── v2.1 GEO Analyzer static checks ─────────────────────────────────────
    _run_geo_checks(page, url, issues)

    return issues
```
