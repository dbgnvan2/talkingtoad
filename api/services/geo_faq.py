"""GA3 — GEO FAQ Schema Generator.

Generates Schema.org FAQPage JSON-LD from a domain's GeoConfig
(topic_entities × locations). Hybrid engine: deterministic templates
by default, optional AI enrichment via AIRouter.

Spec: docs/pending/2026-05-31_ga3_faq_generator.md

Hard constraints:
- Generate-and-suggest ONLY. No WordPress write.
- Every generated question MUST be >= 6 words (enforced by _passes_longtail).
- AI is additive: on no key / provider error / sub-6-word output, fall back
  to template mode.
"""

from __future__ import annotations

import json
import logging
from itertools import cycle
from typing import Literal

from api.models.geo_config import GeoConfig
from api.services.ai_router import (
    AIResponse,
    ModelConfig,
    SYSTEM_CONTEXT_ID,
    ai_router,
)

logger = logging.getLogger(__name__)


# ── Templates (each guaranteed >= 6 words once interpolated) ──────────────

_TEMPLATES = [
    "What is {entity} and how does it help people in {location}?",
    "How does {entity} support mental health care in {location}?",
    "What should I expect from {entity} counselling in {location}?",
    "Where can families access {entity} services near {location}?",
]


# ── AI model defaults (same pattern as advisor._DEFAULT_CRITIC_MODEL_BY_PROVIDER)

_DEFAULT_FAQ_MODEL_BY_PROVIDER = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}


_FAQ_SYSTEM_PROMPT = """\
You are an FAQ generator for nonprofit organisations. Given a list of topic \
entities and geographic locations, generate high-intent, long-tail FAQ \
questions that a person searching for these services would ask.

Rules:
- Every question MUST be at least 6 words long.
- Return ONLY a JSON array of question strings. No other text.
- Questions should be specific to the entities and locations provided.
- Frame questions from the searcher's perspective (what, how, where, why).

Example output: ["What is grief counselling and how does it help families in Vancouver?", ...]
"""


# ── Shared validator (the ONE rule, applied in BOTH modes) ────────────────


def _passes_longtail(query: str) -> bool:
    """Return True iff the query has >= 6 words."""
    return len(query.split()) >= 6


# ── Template engine ───────────────────────────────────────────────────────


def _build_template_questions(geo_config: GeoConfig, limit: int) -> list[str]:
    """Generate FAQ questions via deterministic templates.

    Round-robins across entities so coverage is even up to `limit`.
    """
    if not geo_config.topic_entities:
        return []

    # Build all locations (primary + pool)
    locations = []
    if geo_config.primary_location:
        locations.append(geo_config.primary_location)
    locations.extend(geo_config.location_pool or [])
    if not locations:
        return []

    # Round-robin: cycle through entities, then templates, then locations
    questions: list[str] = []
    entity_cycle = cycle(geo_config.topic_entities)
    template_cycle = cycle(_TEMPLATES)
    location_cycle = cycle(locations)

    # Generate enough candidates — entities × templates × locations
    max_candidates = len(geo_config.topic_entities) * len(_TEMPLATES) * len(locations)
    attempts = 0

    while len(questions) < limit and attempts < max_candidates:
        entity = next(entity_cycle)
        template = next(template_cycle)
        location = next(location_cycle)

        question = template.format(entity=entity, location=location)

        if _passes_longtail(question) and question not in questions:
            questions.append(question)

        attempts += 1

    return questions[:limit]


def _build_faq_block(questions: list[str]) -> dict:
    """Wrap questions into a Schema.org FAQPage dict.

    The accepted answer is a clearly-marked draft placeholder — GA3
    generates question *anchors*; the user writes the real answers.
    """
    main_entity = []
    for q in questions:
        main_entity.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "[Draft: write a concise 1-2 sentence answer about this topic for your organisation.]",
            },
        })

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity,
    }


# ── AI engine ───��─────────────────────────────────────────────────────────


def _render_entities(geo_config: GeoConfig) -> str:
    """Build user prompt for the AI from GeoConfig."""
    locations = [geo_config.primary_location] + (geo_config.location_pool or [])
    return (
        f"Organisation: {geo_config.org_name}\n"
        f"Topic entities: {', '.join(geo_config.topic_entities)}\n"
        f"Locations: {', '.join(locations)}\n"
        f"Generate FAQ questions covering these entities and locations."
    )


# ── Main entry point ──────────────────────────────────────────────────────


async def generate_faq_block(
    geo_config: GeoConfig,
    mode: Literal["template", "ai"] = "template",
    *,
    limit: int = 8,
) -> dict:
    """Return a Schema.org FAQPage dict with metadata.

    Returns:
        {
            "faq_block": {"@context": ..., "@type": "FAQPage", "mainEntity": [...]},
            "questions": ["<q1>", ...],
            "mode_used": "template" | "ai",
            "token_usage": {"input": N, "output": N, "cost_usd": F} | None
        }

    Async because mode="ai" awaits AIRouter; template mode does no I/O.
    """
    token_usage = None

    if mode == "ai":
        # Try AI path; fall back to template on any failure
        try:
            questions, token_usage = await _ai_generate(geo_config, limit)
            if questions:
                faq_block = _build_faq_block(questions)
                return {
                    "faq_block": faq_block,
                    "questions": questions,
                    "mode_used": "ai",
                    "token_usage": token_usage,
                }
            # Zero valid questions survived filter — fall back
            logger.warning("AI returned no valid >=6-word questions; falling back to template")
        except Exception as exc:
            logger.warning("AI FAQ generation failed (%s); falling back to template", exc)

    # Template mode (default or fallback)
    questions = _build_template_questions(geo_config, limit)
    faq_block = _build_faq_block(questions)
    return {
        "faq_block": faq_block,
        "questions": questions,
        "mode_used": "template",
        "token_usage": None,
    }


async def _ai_generate(geo_config: GeoConfig, limit: int) -> tuple[list[str], dict | None]:
    """Call AIRouter to generate FAQ questions. Returns (questions, token_usage)."""
    # Resolve provider and pick model (advisor pattern)
    provider, _ = ai_router._resolve_credentials(SYSTEM_CONTEXT_ID)
    model = _DEFAULT_FAQ_MODEL_BY_PROVIDER.get(
        provider, _DEFAULT_FAQ_MODEL_BY_PROVIDER["openai"]
    )
    cfg = ModelConfig(model=model, max_tokens=1500, temperature=0.4)

    resp: AIResponse = await ai_router.call_text(
        customer_id=SYSTEM_CONTEXT_ID,
        system_prompt=_FAQ_SYSTEM_PROMPT,
        user_prompt=_render_entities(geo_config),
        model_config=cfg,
    )

    # Parse response — expect a JSON array of strings
    questions = _parse_ai_questions(resp.content, limit)

    token_usage = {
        "input": resp.input_token_count,
        "output": resp.output_token_count,
        "cost_usd": resp.cost_estimate_usd,
    }

    return questions, token_usage


def _parse_ai_questions(content: str, limit: int) -> list[str]:
    """Parse AI response content into a list of validated questions."""
    # Strip markdown code fences if present
    cleaned = content.strip()
    if cleaned.startswith("```"):
        import re
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    try:
        raw = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("AI FAQ response is not valid JSON")
        return []

    if not isinstance(raw, list):
        logger.warning("AI FAQ response is not a JSON array")
        return []

    # Filter: must be string, >= 6 words
    questions = []
    for item in raw:
        if isinstance(item, str) and _passes_longtail(item):
            questions.append(item)
        if len(questions) >= limit:
            break

    return questions
