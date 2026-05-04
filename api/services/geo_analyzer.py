"""
GEO Analyzer LLM service.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md#GEO.10

Runs LLM-based GEO checks (GEO.2.4, GEO.3.1, GEO.3.2, GEO.4.4, GEO.7.1)
and returns a structured GEOReport. Also integrates JS rendering results.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env-ttoad", override=True)

logger = logging.getLogger(__name__)

_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "{model}:generateContent?key={key}"
)
_OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GEOFinding:
    code: str
    label: str
    evidence_tier: str        # Empirical | Mechanistic | Conventional
    pass_fail: str            # pass | fail | info
    score: float              # 0.0 – 1.0
    findings: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class GEOReport:
    url: str
    model_used: str
    overall_score: float = 0.0
    aggarwal_score: float = 0.0
    findings: list[GEOFinding] = field(default_factory=list)
    js_rendering: dict = field(default_factory=dict)
    query_match_table: list[dict] = field(default_factory=list)
    chunk_containedness: list[dict] = field(default_factory=list)
    playwright_available: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "model_used": self.model_used,
            "overall_score": self.overall_score,
            "aggarwal_score": self.aggarwal_score,
            "findings": [
                {
                    "code": f.code,
                    "label": f.label,
                    "evidence_tier": f.evidence_tier,
                    "pass_fail": f.pass_fail,
                    "score": f.score,
                    "findings": f.findings,
                    "details": f.details,
                }
                for f in self.findings
            ],
            "js_rendering": self.js_rendering,
            "query_match_table": self.query_match_table,
            "chunk_containedness": self.chunk_containedness,
            "playwright_available": self.playwright_available,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# AI call helpers
# ---------------------------------------------------------------------------

def _resolve_model(preferred: str | None) -> tuple[str, str]:
    """Return (model_id, provider). Raises if no keys configured."""
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if preferred and preferred.startswith("gpt") and openai_key:
        return preferred, "openai"
    if preferred and preferred.startswith("gemini") and gemini_key:
        return preferred, "gemini"

    # Fall back to whatever key is available
    if openai_key:
        return "gpt-4o", "openai"
    if gemini_key:
        return "gemini-1.5-flash", "gemini"
    raise RuntimeError("No AI API key configured (OPENAI_API_KEY or GEMINI_API_KEY).")


async def _call_ai(prompt: str, model: str, provider: str) -> str:
    if provider == "openai":
        return await _call_openai(prompt, model, os.getenv("OPENAI_API_KEY", ""))
    return await _call_gemini(prompt, model, os.getenv("GEMINI_API_KEY", ""))


async def _call_openai(prompt: str, model: str, api_key: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _OPENAI_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def _call_gemini(prompt: str, model: str, api_key: str) -> str:
    url = _GEMINI_ENDPOINT.format(model=model, key=api_key)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.2}},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _safe_json(text: str) -> Any:
    """Extract JSON from an LLM response that may have markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GEO.7.1 — Query-match test
# ---------------------------------------------------------------------------

_QUERY_MATCH_PROMPT = """\
You are a GEO (Generative Engine Optimization) analyst. Your task is to test how well a web page answers user queries.

Page content (first 3000 characters):
---
{content}
---

Step 1: Generate 7 realistic search queries that a user would ask to find this page.
Step 2: For each query, find the most relevant 1-3 sentences from the page that answer it.
Step 3: Score each: Yes (self-contained answer), Partial (incomplete), or No (not answered).

Return ONLY a JSON array, no other text:
[
  {{"query": "...", "best_chunk": "...", "answered": "Yes|Partial|No", "reason": "..."}}
]
"""

async def run_query_match_test(content: str, model: str, provider: str) -> list[dict]:
    prompt = _QUERY_MATCH_PROMPT.format(content=content[:3000])
    try:
        raw = await _call_ai(prompt, model, provider)
        parsed = _safe_json(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        logger.warning("query_match_test_failed", extra={"error": str(e)})
    return []


# ---------------------------------------------------------------------------
# GEO.2.4 — Chunk self-containedness
# ---------------------------------------------------------------------------

_CHUNK_PROMPT = """\
Read this section of a web article IN ISOLATION (pretend you haven't read anything else):

---
{chunk}
---

Can a reader understand the main claim of this section WITHOUT reading the rest of the article?
Answer with ONLY: Yes or No, then a one-sentence reason.
Format: {{"self_contained": true/false, "reason": "..."}}
"""

async def run_chunk_containedness(
    headings_and_text: list[dict],
    model: str,
    provider: str,
) -> list[dict]:
    """Check each H2/H3 section for self-containedness."""
    results = []
    for section in headings_and_text[:8]:  # cap at 8 sections to limit API calls
        heading = section.get("heading", "")
        text = section.get("text", "")
        if not text or len(text) < 50:
            continue
        prompt = _CHUNK_PROMPT.format(chunk=f"## {heading}\n\n{text[:800]}")
        try:
            raw = await _call_ai(prompt, model, provider)
            parsed = _safe_json(raw)
            if isinstance(parsed, dict):
                results.append({
                    "heading": heading,
                    "self_contained": parsed.get("self_contained", True),
                    "reason": parsed.get("reason", ""),
                })
        except Exception as e:
            logger.warning("chunk_check_failed", extra={"heading": heading, "error": str(e)})
    return results


# ---------------------------------------------------------------------------
# GEO.3.1 — Central claim buried check
# ---------------------------------------------------------------------------

_CENTRAL_CLAIM_PROMPT = """\
Read this web page content. In one sentence, what is the page's central claim or main answer?

Content:
---
{content}
---

Return ONLY JSON: {{"central_claim": "...", "appears_in_first_150_words": true/false}}
"""

async def check_central_claim(
    content: str,
    first_150_words: str,
    model: str,
    provider: str,
) -> dict:
    prompt = _CENTRAL_CLAIM_PROMPT.format(content=content[:2000])
    try:
        raw = await _call_ai(prompt, model, provider)
        parsed = _safe_json(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception as e:
        logger.warning("central_claim_check_failed", extra={"error": str(e)})
    return {}


# ---------------------------------------------------------------------------
# GEO.4.4 — Promotional content detection
# ---------------------------------------------------------------------------

_PROMO_PROMPT = """\
Read each section of this article and classify it as "main_content" or "promotional".
Promotional means: selling a product/service, CTA buttons, discount offers, sign-up prompts.

Sections:
---
{sections}
---

Return ONLY JSON array:
[{{"heading": "...", "type": "main_content|promotional"}}]
"""

async def check_promotional_content(
    sections: list[dict],
    model: str,
    provider: str,
) -> list[dict]:
    section_text = "\n\n".join(
        f"## {s['heading']}\n{s['text'][:300]}"
        for s in sections[:10]
    )
    prompt = _PROMO_PROMPT.format(sections=section_text)
    try:
        raw = await _call_ai(prompt, model, provider)
        parsed = _safe_json(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        logger.warning("promo_check_failed", extra={"error": str(e)})
    return []


# ---------------------------------------------------------------------------
# Main report orchestrator
# ---------------------------------------------------------------------------

async def generate_geo_report(
    url: str,
    raw_html: str,
    *,
    preferred_model: str | None = None,
    page_data: dict | None = None,
) -> GEOReport:
    """
    Run all LLM-based GEO checks and return a GEOReport.

    Args:
        url: The page URL.
        raw_html: Raw HTML of the page (used for content extraction).
        preferred_model: Optional model ID override.
        page_data: Optional dict with parsed page fields (first_150_words, headings_outline, etc.)
    """
    try:
        model, provider = _resolve_model(preferred_model)
    except RuntimeError as e:
        return GEOReport(url=url, model_used="none", error=str(e))

    report = GEOReport(url=url, model_used=model)

    # Extract content from HTML
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "lxml")
    for noise in soup.find_all(["script", "style", "nav", "header", "footer"]):
        noise.decompose()
    full_text = soup.get_text(separator=" ", strip=True)
    first_150_words = " ".join(full_text.split()[:150])

    # Build sections from headings
    headings_outline = (page_data or {}).get("headings_outline", [])
    sections = _extract_sections(soup, headings_outline)

    # ── JS rendering (GEO.1.3b/c/d) ─────────────────────────────────────
    from api.services.js_renderer import run_js_render_checks, HAS_PLAYWRIGHT
    report.playwright_available = HAS_PLAYWRIGHT
    if HAS_PLAYWRIGHT:
        js_result = await run_js_render_checks(url)
        report.js_rendering = {
            "js_rendered_content_differs": js_result.js_rendered_content_differs,
            "content_cloaking_detected": js_result.content_cloaking_detected,
            "ua_content_differs": js_result.ua_content_differs,
            "rendered_token_count": js_result.rendered_token_count,
            "raw_token_count": js_result.raw_token_count,
            "added_token_ratio": js_result.added_token_ratio,
            "topic_jaccard": js_result.topic_jaccard,
            "gptbot_token_count": js_result.gptbot_token_count,
            "claudebot_token_count": js_result.claudebot_token_count,
            "error": js_result.error,
        }

        if js_result.js_rendered_content_differs:
            report.findings.append(GEOFinding(
                code="JS_RENDERED_CONTENT_DIFFERS",
                label="JS-Gated Content",
                evidence_tier="Mechanistic",
                pass_fail="fail",
                score=0.0,
                findings=[
                    f"Rendered page has {js_result.added_token_ratio:.0%} more tokens than raw HTML",
                    f"Raw: {js_result.raw_token_count} tokens, Rendered: {js_result.rendered_token_count} tokens",
                ],
            ))
        if js_result.content_cloaking_detected:
            report.findings.append(GEOFinding(
                code="CONTENT_CLOAKING_DETECTED",
                label="Possible Content Cloaking",
                evidence_tier="Mechanistic",
                pass_fail="fail",
                score=0.0,
                findings=[
                    f"Topic keyword Jaccard similarity: {js_result.topic_jaccard:.2f} (< 0.30 = topic shift)",
                    "Raw HTML and rendered page appear to cover different topics",
                ],
            ))
        if js_result.ua_content_differs:
            report.findings.append(GEOFinding(
                code="UA_CONTENT_DIFFERS",
                label="AI Bot Content Stripping",
                evidence_tier="Mechanistic",
                pass_fail="fail",
                score=0.0,
                findings=[
                    f"GPTBot received {js_result.gptbot_token_count} tokens vs {js_result.rendered_token_count} rendered",
                    f"ClaudeBot received {js_result.claudebot_token_count} tokens vs {js_result.rendered_token_count} rendered",
                ],
            ))

    # ── GEO.7.1 — Query-match test ────────────────────────────────────────
    query_table = await run_query_match_test(full_text, model, provider)
    report.query_match_table = query_table

    if query_table:
        answered = sum(1 for q in query_table if q.get("answered") == "Yes")
        partial = sum(1 for q in query_table if q.get("answered") == "Partial")
        total = len(query_table)
        score = (answered + 0.5 * partial) / total if total else 0
        report.findings.append(GEOFinding(
            code="QUERY_MATCH_SCORE",
            label="Query-Match Test",
            evidence_tier="Empirical",
            pass_fail="pass" if score >= 0.7 else "fail",
            score=round(score, 2),
            findings=[
                f"{answered}/{total} queries fully answered",
                f"{partial}/{total} queries partially answered",
            ],
            details={"answered": answered, "partial": partial, "total": total},
        ))

    # ── GEO.2.4 — Chunk self-containedness ───────────────────────────────
    if sections:
        chunk_results = await run_chunk_containedness(sections, model, provider)
        report.chunk_containedness = chunk_results
        if chunk_results:
            self_contained = sum(1 for c in chunk_results if c.get("self_contained"))
            total_chunks = len(chunk_results)
            ratio = self_contained / total_chunks if total_chunks else 1
            if ratio < 0.5:
                report.findings.append(GEOFinding(
                    code="CHUNKS_NOT_SELF_CONTAINED",
                    label="Sections Lack Context",
                    evidence_tier="Mechanistic",
                    pass_fail="fail",
                    score=round(ratio, 2),
                    findings=[
                        f"{self_contained}/{total_chunks} sections are self-contained",
                        "More than half of sections require prior context to understand",
                    ],
                ))

    # ── GEO.3.1 — Central claim check ────────────────────────────────────
    claim_result = await check_central_claim(full_text, first_150_words, model, provider)
    if claim_result and not claim_result.get("appears_in_first_150_words", True):
        report.findings.append(GEOFinding(
            code="CENTRAL_CLAIM_BURIED",
            label="Main Point Buried",
            evidence_tier="Mechanistic",
            pass_fail="fail",
            score=0.5,
            findings=[
                f"Central claim: \"{claim_result.get('central_claim', 'unknown')}\"",
                "This claim does not appear in the first 150 words",
            ],
        ))

    # ── GEO.4.4 — Promotional content ────────────────────────────────────
    if sections:
        promo_results = await check_promotional_content(sections, model, provider)
        mid_promo = [r for r in promo_results
                     if r.get("type") == "promotional"
                     and promo_results.index(r) not in (0, len(promo_results) - 1)]
        if len(mid_promo) > 1:
            report.findings.append(GEOFinding(
                code="PROMOTIONAL_CONTENT_INTERRUPTS",
                label="Promotional Content in Article",
                evidence_tier="Conventional",
                pass_fail="fail",
                score=0.5,
                findings=[
                    f"{len(mid_promo)} mid-article sections classified as promotional",
                ],
            ))

    # ── Compute scores ────────────────────────────────────────────────────
    _compute_scores(report)

    return report


def _extract_sections(soup: Any, headings_outline: list) -> list[dict]:
    """Split page content into sections by H2/H3 headings."""
    sections = []
    h_tags = soup.find_all(["h2", "h3"])
    for h in h_tags:
        heading_text = h.get_text(strip=True)
        texts = []
        for sib in h.next_siblings:
            if hasattr(sib, "name") and sib.name in ("h2", "h3"):
                break
            if hasattr(sib, "get_text"):
                t = sib.get_text(separator=" ", strip=True)
                if t:
                    texts.append(t)
        sections.append({"heading": heading_text, "text": " ".join(texts)})
    return sections


def _compute_scores(report: GEOReport) -> None:
    """Compute overall_score and aggarwal_score from findings."""
    tier_weights = {"Empirical": 3, "Mechanistic": 2, "Conventional": 1}
    total_weight = 0.0
    weighted_score = 0.0
    aggarwal_weight = 0.0
    aggarwal_score = 0.0

    # Base score from findings
    for f in report.findings:
        w = tier_weights.get(f.evidence_tier, 1)
        total_weight += w
        # pass = 1.0, fail = 0.0, info = 0.75
        s = f.score if f.pass_fail == "pass" else (0.75 if f.pass_fail == "info" else 0.0)
        weighted_score += w * s
        if f.evidence_tier == "Empirical":
            aggarwal_weight += w
            aggarwal_score += w * s

    if total_weight > 0:
        report.overall_score = round(weighted_score / total_weight, 2)
    else:
        report.overall_score = 1.0  # no findings = clean

    if aggarwal_weight > 0:
        report.aggarwal_score = round(aggarwal_score / aggarwal_weight, 2)
    else:
        report.aggarwal_score = 1.0
