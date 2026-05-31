"""GA4 — Authoritative Entity Schema Factory.

Generates a nested Schema.org JSON-LD block:
  Organization (name, sameAs?) -> hasOfferCatalog -> Service[] -> FAQPage

Deterministic — no LLM, no network calls, no SSRF surface.
Pure construction from GeoConfig.

Spec: docs/pending/2026-05-31_ga4_entity_schema_factory.md
"""

from __future__ import annotations

from api.models.geo_config import GeoConfig
from api.services.geo_faq import _build_faq_block, _build_template_questions


def build_entity_schema(geo_config: GeoConfig) -> dict:
    """Return a nested Organization JSON-LD dict.

    Structure:
        Organization (name, sameAs?) -> hasOfferCatalog -> Service[]
        (from topic_entities, areaServed = primary_location) -> FAQPage (subjectOf).

    Deterministic; no I/O. `sameAs` is included only when
    entity_wikipedia_url is non-blank.
    """
    organization: dict = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": geo_config.org_name or "",
    }

    # sameAs: ONLY when entity_wikipedia_url is non-blank
    if geo_config.entity_wikipedia_url and geo_config.entity_wikipedia_url.strip():
        organization["sameAs"] = [geo_config.entity_wikipedia_url.strip()]

    # Services from topic_entities
    services = []
    for topic in (geo_config.topic_entities or []):
        services.append({
            "@type": "Service",
            "name": topic,
            "areaServed": geo_config.primary_location or "",
        })

    organization["hasOfferCatalog"] = {
        "@type": "OfferCatalog",
        "name": "Services",
        "itemListElement": services,
    }

    # FAQPage — reuse GA3's template builder
    questions = _build_template_questions(geo_config, limit=8)
    faq_block = _build_faq_block(questions)
    # Remove @context from nested FAQ (it's on the top-level Organization)
    faq_nested = {k: v for k, v in faq_block.items() if k != "@context"}

    organization["subjectOf"] = faq_nested

    return organization
