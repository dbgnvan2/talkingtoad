"""D4 — page blueprints: drafted title/description/H1/lead, with a review gate.

Purpose: give the operator a starting draft for the pages that matter, grounded
         in what the page actually says, and never let an unapproved draft reach
         a client.
Spec:    docs/pending/2026-08-29_D4-page-blueprints.md
Tests:   tests/test_blueprints.py

**The grounding check is the feature.** Without it this is a plausible-text
generator with a nonprofit's name on the output. The site this was built against
is a counselling charity: a draft that invents a service, implies a clinical
outcome, or softens crisis-resource language is a fabrication published under
their brand. Rule 1 — never invent content — is not advisory here.

**Two tiers, and the verbatim floor is never relaxed.**

    Verbatim floor   Proper nouns, numbers, dates, prices and named services in
                     the draft MUST appear in the source page. Anything that does
                     not is listed and the draft is marked `unverified`.
    Topical overlap  The lead is a paraphrase, so it is checked more loosely.

P19's corollary is explicit that relaxing the paraphrase tier while dropping the
verbatim floor lets a hallucination ride through on the loosened one. Both tiers
run; only the looser one is loose.

An `unverified` draft is **shown with its unsupported claims listed**, never
silently discarded — the operator needs to see what the model tried to assert.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from api.config import load_config

logger = logging.getLogger(__name__)

_CFG_KEYS = ("title_max", "description_min", "description_max", "lead_min_words",
             "lead_max_words", "stopwords", "generic_claim_markers")


def _cfg() -> dict:
    return load_config("blueprints", required_keys=_CFG_KEYS)


class BlueprintError(RuntimeError):
    """A typed failure. Never returned as draft text (P14)."""


@dataclass
class Grounding:
    status: str = "grounded"                       # "grounded" | "unverified"
    unsupported_claims: list[str] = field(default_factory=list)
    unsupported_assertions: list[str] = field(default_factory=list)

    @property
    def is_grounded(self) -> bool:
        return self.status == "grounded"


@dataclass
class Blueprint:
    url: str
    proposed_title: str = ""
    proposed_meta_description: str = ""
    proposed_h1: str = ""
    proposed_lead: str = ""
    rationale: str = ""
    source_findings: list[str] = field(default_factory=list)
    grounding: Grounding = field(default_factory=Grounding)
    status: str = "draft"                          # draft | approved | rejected
    approved_by: str | None = None
    approved_at: str | None = None
    model: str = ""

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’\-]+|\d[\d,.:%$£€/]*\d|\d")
# A capitalised run not at the start of a sentence, plus numbers, dates, money.
_PROPER_NOUN = re.compile(r"\b(?:[A-Z][a-z’'\-]+)(?:\s+(?:of|and|the|for|de|la))?"
                          r"(?:\s+[A-Z][a-z’'\-]+)*\b")
_NUMERIC = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b|\b(?:19|20)\d{2}\b|[$£€]\s?\d[\d,.]*")


def _words(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower().replace("’", "'")


_SENTENCE_START = re.compile(r"(?:^|[.!?|:;]\s*|\n\s*)$")


def verbatim_claims(draft_text: str) -> list[str]:
    """Specific, checkable assertions: proper nouns, numbers, dates, money.

    These are the claims a reader would take as fact about the organisation, and
    the ones a model most readily invents.

    Precision matters more than recall here. A check that flags "Explore Bowen
    family systems…" because "Explore" happens to start a sentence marks every
    draft unverified, which makes the approval gate meaningless — the operator
    learns to click through it. So a capitalised word in sentence-initial
    position is dropped from the front of a candidate: it is grammar, not a name.
    """
    text = draft_text or ""
    claims: list[str] = []
    seen: set[str] = set()
    for match in _PROPER_NOUN.finditer(text):
        token = match.group(0).strip()
        # Sentence-initial capitalisation is grammar. Drop the leading word and
        # judge what remains — "Toronto Counselling Centre" still loses only
        # "Toronto" and is caught by the rest.
        if _SENTENCE_START.search(text[: match.start()]):
            parts = token.split()
            token = " ".join(parts[1:]).strip()
        if not token or len(token.split()) == 1 and len(token) < 4:
            continue
        key = token.lower()
        if key not in seen:
            seen.add(key)
            claims.append(token)
    for match in _NUMERIC.findall(draft_text or ""):
        token = match.strip()
        key = token.lower()
        if key not in seen:
            seen.add(key)
            claims.append(token)
    return claims


def check_grounding(draft: Blueprint, source_text: str) -> Grounding:
    """Verify the draft against the page it was written from.

    Returns a `Grounding`. An unsupported claim never blocks generation — it
    blocks *approval*, and it is shown to the operator so they can judge it.
    """
    cfg = _cfg()
    haystack = _normalise(source_text)
    if not haystack:
        return Grounding(status="unverified",
                         unsupported_claims=["the source page had no readable text"])

    # ── Tier 1: the verbatim floor. Never relaxed. ──
    unsupported: list[str] = []
    for field_text in (draft.proposed_title, draft.proposed_meta_description,
                       draft.proposed_h1, draft.proposed_lead):
        for claim in verbatim_claims(field_text):
            if _normalise(claim) not in haystack:
                if claim not in unsupported:
                    unsupported.append(claim)

    # ── Tier 2: the paraphrased lead. Looser BY DESIGN, and only this tier. ──
    unsupported_assertions: list[str] = []
    stopwords = set(cfg["stopwords"])
    lead_words = [w for w in _words(draft.proposed_lead) if w not in stopwords]
    if lead_words:
        source_words = set(_words(source_text)) - stopwords
        overlap = sum(1 for w in lead_words if w in source_words) / len(lead_words)
        if overlap < 0.5:
            unsupported_assertions.append(
                f"the proposed lead shares only {overlap:.0%} of its meaningful "
                f"vocabulary with the page — it may be describing something the "
                f"page does not say"
            )

    # A fabricated stance or causal claim carries no proper noun and no number,
    # so the verbatim floor cannot see it. P20 is explicit that a gold set of
    # concrete-specific fabrications misses exactly this class.
    for marker in cfg["generic_claim_markers"]:
        if marker in _normalise(draft.proposed_lead) and marker not in haystack:
            unsupported_assertions.append(
                f'the draft asserts "{marker}", which does not appear on the page'
            )

    status = "grounded" if not unsupported and not unsupported_assertions else "unverified"
    return Grounding(status=status, unsupported_claims=unsupported,
                     unsupported_assertions=unsupported_assertions)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You draft SEO metadata for a nonprofit's existing web page.

You are given the page's actual text. Draft:
  1. an SEO title (max {title_max} characters)
  2. a meta description ({description_min}-{description_max} characters)
  3. one H1
  4. an answer-first opening paragraph ({lead_min}-{lead_max} words)

HARD RULES:
- Use ONLY information present in the page text you are given. Do not add
  services, credentials, locations, dates, prices or claims that are not there.
- Do not imply clinical, medical or therapeutic outcomes.
- Do not soften or reword any crisis, emergency or safeguarding language.
- If the page does not support a confident answer-first opening, say so in
  "rationale" and keep the lead close to what the page already says.

Return ONLY a JSON object with keys: title, meta_description, h1, lead, rationale.
"""


async def generate_blueprint(
    url: str,
    page_text: str,
    *,
    findings: list[str] | None = None,
    model: str | None = None,
) -> Blueprint:
    """Draft a blueprint for one page, then ground it.

    Every LLM call goes through AIRouter (Cycle Z) — no direct provider HTTP, so
    usage, cost and credentials stay centralised.
    """
    import json

    from api.services.ai_router import SYSTEM_CONTEXT_ID, ModelConfig, ai_router

    if not (page_text or "").strip():
        raise BlueprintError("the page has no readable text to draft from")

    cfg = _cfg()
    system = _SYSTEM_PROMPT.format(
        title_max=cfg["title_max"], description_min=cfg["description_min"],
        description_max=cfg["description_max"], lead_min=cfg["lead_min_words"],
        lead_max=cfg["lead_max_words"],
    )
    chosen = model or "gpt-4o"
    try:
        response = await ai_router.call_text(
            customer_id=SYSTEM_CONTEXT_ID,
            system_prompt=system,
            user_prompt=f"Page URL: {url}\n\nPage text:\n\n{page_text[:12000]}",
            model_config=ModelConfig(model=chosen, temperature=0.2, max_tokens=900),
        )
    except Exception as exc:  # noqa: BLE001
        # P14: a provider failure is an error, never draft text. Returning the
        # message as content would put "Error calling AI" into a client report.
        raise BlueprintError(f"the drafting model was unavailable: {exc}") from exc

    raw = (response.content or "").strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise BlueprintError("the model did not return a usable draft")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise BlueprintError(f"the model's draft could not be parsed: {exc}") from exc

    draft = Blueprint(
        url=url,
        proposed_title=str(data.get("title") or "").strip(),
        proposed_meta_description=str(data.get("meta_description") or "").strip(),
        proposed_h1=str(data.get("h1") or "").strip(),
        proposed_lead=str(data.get("lead") or "").strip(),
        rationale=str(data.get("rationale") or "").strip(),
        source_findings=list(findings or []),
        model=chosen,
    )
    draft.grounding = check_grounding(draft, page_text)
    return draft


def approve(draft: Blueprint, *, by: str) -> Blueprint:
    """Mark a draft approved. Only an approved draft may be exported (D4.4)."""
    draft.status = "approved"
    draft.approved_by = by
    draft.approved_at = datetime.now(timezone.utc).isoformat()
    return draft


def to_dict(draft: Blueprint) -> dict:
    return {
        "url": draft.url,
        "proposed_title": draft.proposed_title,
        "proposed_meta_description": draft.proposed_meta_description,
        "proposed_h1": draft.proposed_h1,
        "proposed_lead": draft.proposed_lead,
        "rationale": draft.rationale,
        "source_findings": draft.source_findings,
        "grounding": {
            "status": draft.grounding.status,
            "unsupported_claims": draft.grounding.unsupported_claims,
            "unsupported_assertions": draft.grounding.unsupported_assertions,
        },
        "status": draft.status,
        "approved_by": draft.approved_by,
        "approved_at": draft.approved_at,
        "model": draft.model,
    }


def approved_only(drafts: list[dict] | None) -> list[dict]:
    """The export filter. An unapproved draft must never reach a client (D4.4a)."""
    return [d for d in (drafts or []) if d.get("status") == "approved"]
