"""
AI Analyzer service for TalkingToad (spec §4).

Detects semantic issues and provides remediation suggestions using LLMs.

v2.6 Cycle BB: migrated through :class:`api.services.ai_router.AIRouter`.
All LLM calls now go via the central router — cost tracking, sanitised
usage logging, and (future M2.3) per-customer credential fallback apply
uniformly. The previous direct-to-httpx call sites
(``_call_openai``, ``_call_gemini``, ``_call_openai_vision``,
``_call_gemini_vision``) and the ``_fetch_image_base64`` helper have
been removed — provider drivers under ``api/services/providers/``
handle HTTP, base64 encoding, response parsing, and token extraction.

Public API preserved exactly:
    - ``analyze_with_ai(prompt_key, context) -> str``
    - ``analyze_image_with_ai(image_url, current_alt) -> dict``
    - ``analyze_image_with_geo(image_url, page_h1, surrounding_text, geo_config) -> dict``

When AIRouter raises ``ProviderAuthError`` (no customer key + no env
key), each public function maps it back to its pre-Cycle-BB
"AI analysis skipped" shape so callers see identical behaviour.
"""

import json
import logging
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from api.crawler.fetcher import is_ssrf_safe
from api.services.ai_router import (
    ModelConfig,
    ProviderAuthError,
    SYSTEM_CONTEXT_ID,
    ai_router,
)

# Ensure environment is loaded for ai_router's credential resolution.
load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt library (unchanged from pre-Cycle-BB)
# ---------------------------------------------------------------------------

PROMPT_LIBRARY = {
    "geo_image_analysis": (
        "Role: You are an AI Search Architect specializing in Generative Engine Optimization (GEO).\n\n"
        "You are analyzing an image for {{ORG_NAME}} located in {{PRIMARY_LOCATION}}. "
        "Service locations include: {{LOCATION_POOL}}. "
        "Topic entities: {{TOPIC_ENTITIES}}.\n\n"
        "Context from the page:\n"
        "H1: {{H1}}\n"
        "Text around image: {{SURROUNDING_TEXT}}\n\n"
        "Instructions:\n"
        "Phase 1: Semantic Analysis\n"
        "1. Identify the primary Subject in the image (e.g., 'Two people in a clinical setting').\n"
        "2. Extract the Contextual Theme from the surrounding text (e.g., 'Family Cutoff').\n"
        "3. Identify the Geographic Anchor to be used from the location pool "
        "(if H1 contains the primary location, use a secondary location; otherwise, rotate through the pool).\n\n"
        "Phase 2: Generate Alt Text (80-125 chars)\n"
        "1. Start with the Subject + Theme.\n"
        "2. Anchor it to the Geography.\n"
        "3. Format: '[Subject] [Action] regarding [Theme] at {{ORG_NAME}} in [Geography].'\n"
        "4. Constraint: No 'Photo of'. No generic adjectives. MUST be 80-125 characters.\n"
        "5. MUST include 1 location entity from the pool AND 1 topic entity.\n\n"
        "Phase 3: Generate Long Description (GEO-rich, 150-300 words)\n"
        "1. Describe the visual details (lighting, posture, setting) as they relate to {{TOPIC_ENTITIES}}.\n"
        "2. Explain the 'Purpose' of the image for a Generative Search Engine to use as a 'Knowledge Snippet.'\n"
        "3. Explicitly mention how this image represents the organization's work in the {{PRIMARY_LOCATION}} community.\n"
        "4. MUST be factual, entity-rich, and suitable for AI Overviews.\n"
        "5. MUST be 150-300 words.\n\n"
        "Final Goal: Every word must serve as a 'signal' that connects this image to a high-intent search "
        "for services in the service area.\n\n"
        "IMPORTANT: Respond with ONLY valid JSON, no markdown formatting, no code blocks.\n"
        "Format:\n"
        "{{\n"
        '  "subject": "primary subject identified",\n'
        '  "theme": "contextual theme from page",\n'
        '  "geographic_anchor": "location used",\n'
        '  "alt_text": "80-125 char alt text with entities",\n'
        '  "long_description": "150-300 word GEO-rich description",\n'
        '  "entities_used": ["location entity", "topic entity"],\n'
        '  "char_count": 95,\n'
        '  "word_count": 200\n'
        "}}"
    ),
    "title_meta_optimize": (
        "Rewrite this title tag and meta description to be more 'quotable' "
        "for an AI summary while staying under character limits (60 for title, 160 for meta).\n"
        "Title: {title}\n"
        "Meta: {meta_description}\n"
        "Content Summary: {content_summary}"
    ),
    "semantic_alignment": (
        "Compare this page's H1 with its body content. Are there conflicting "
        "semantic signals that would cause an LLM hallucination?\n"
        "H1: {h1}\n"
        "Body Text Snippet: {body_snippet}"
    ),
    "issue_advisor": (
        "You are an SEO and GEO (Generative Engine Optimization) consultant for nonprofit organizations.\n"
        "A specific issue has been found on a page. Your job is to write the ACTUAL replacement text the user can copy and paste.\n\n"
        "Issue type: {issue_code}\n"
        "Issue description: {issue_description}\n"
        "Page URL: {url}\n"
        "Current Title: {title}\n"
        "Current Meta Description: {meta_description}\n"
        "Current H1: {h1}\n"
        "Extra context: {extra_context}\n\n"
        "What to put in each JSON field:\n"
        "- suggested_text: The COPY-READY replacement text. Not a description. Not instructions. The actual words.\n"
        "  Examples by issue type:\n"
        "  TITLE_MISSING / TITLE_TOO_SHORT / TITLE_TOO_LONG / TITLE_DUPLICATE: Write the full title tag text (≤60 chars).\n"
        "  META_DESC_MISSING / META_DESC_TOO_SHORT / META_DESC_TOO_LONG / META_DESC_DUPLICATE: Write the full meta description (≤160 chars).\n"
        "  OG_TITLE_MISSING: Write the Open Graph title text.\n"
        "  OG_DESC_MISSING: Write the Open Graph description text.\n"
        "  H1_MISSING: Write the H1 heading text.\n"
        "  H1_MULTIPLE: Write which H1 to keep (copy the exact text) and what the others should be demoted to (e.g. 'Keep: [text]. Demote the others to H2.').\n"
        "  HEADING_EMPTY: Write the text to fill in the empty heading.\n"
        "  CONVERSATIONAL_H2_MISSING: Rewrite each existing H2 as a question. List them as: '1. How to...\\n2. What is...\\n3. Why does...'\n"
        "  QUERY_COVERAGE_WEAK: Write one improved intro sentence and one new H2 heading that naturally include the H1 topic terms.\n"
        "  IMG_ALT_MISSING / IMG_ALT_TOO_SHORT / IMG_ALT_TOO_LONG / IMG_ALT_GENERIC / IMG_ALT_DUP_FILENAME / IMG_ALT_MISUSED: Write the alt text string only (80-125 chars, entity-rich, no quotes).\n"
        "  LINK_EMPTY_ANCHOR: Write the descriptive anchor text to use for this link.\n"
        "  THIN_CONTENT: Write 3-5 bullet points of specific content topics/angles to add to this page.\n"
        "  SCHEMA_MISSING: Write a complete JSON-LD <script> block with the most appropriate Schema.org type.\n"
        "  SCHEMA_ORG_MISSING: Write a complete Organization JSON-LD <script> block.\n"
        "  TITLE_META_DUPLICATE_PAIR: Write both a new title (≤60 chars) and new meta description (≤160 chars), clearly labelled.\n"
        "- why: One sentence explaining why this change helps SEO or AI discoverability.\n"
        "- where_to_apply: One sentence saying exactly where in the CMS to paste this (e.g. 'Paste into Yoast SEO → SEO Title field on this page').\n\n"
        "Respond with ONLY valid JSON (no markdown, no code blocks, no extra keys):\n"
        "{{\n"
        "  \"suggested_text\": \"<the actual copy-ready text here>\",\n"
        "  \"why\": \"<one sentence>\",\n"
        "  \"where_to_apply\": \"<one sentence>\"\n"
        "}}"
    ),
    "page_advisor": (
        "You are an SEO consultant for nonprofit organizations. Analyze this page and provide specific, "
        "actionable recommendations with ACTUAL suggested content (not just 'improve this').\n\n"
        "Current Page Data:\n"
        "URL: {url}\n"
        "Title: {title}\n"
        "Meta Description: {meta_description}\n"
        "H1 Tags: {h1_tags}\n"
        "H2 Tags: {h2_tags}\n"
        "Issues Found: {issues}\n\n"
        "For each element that needs improvement, provide:\n"
        "1. Current Value\n"
        "2. Suggested Value (actual content)\n"
        "3. Why (brief explanation)\n\n"
        "Focus ONLY on: Title, Meta Description, H1, and H2 headings. "
        "Respond in JSON format with this structure:\n"
        "{{\n"
        "  \"title\": {{\"current\": \"...\", \"suggested\": \"...\", \"why\": \"...\"}},\n"
        "  \"meta_description\": {{\"current\": \"...\", \"suggested\": \"...\", \"why\": \"...\"}},\n"
        "  \"h1\": {{\"current\": \"...\", \"suggested\": \"...\", \"why\": \"...\"}},\n"
        "  \"h2\": {{\"current\": [...], \"suggested\": [...], \"why\": \"...\"}}\n"
        "}}"
    ),
    "executive_summary": (
        "You are a web consultant writing a 3-5 sentence executive summary of an SEO audit "
        "for a nonprofit executive director who does not know SEO terminology.\n\n"
        "Site Health Score: {health_score}/100\n"
        "Pages Crawled: {pages_crawled}\n"
        "Critical Issues: {critical}\n"
        "Warnings: {warnings}\n"
        "Top 3 Issue Types: {top_issues}\n\n"
        "Write in plain English. Be specific about what needs attention and why it matters "
        "for the organization's online presence. Do not use jargon like 'meta tags' or "
        "'canonical URLs'. Start with the health score interpretation."
    ),
    "site_advisor": (
        "You are an SEO consultant for nonprofit organizations. Analyze these site-wide patterns and provide "
        "high-level recommendations.\n\n"
        "Site Summary:\n"
        "Total Pages: {total_pages}\n"
        "Common Issues: {common_issues}\n"
        "Sample Pages: {sample_pages}\n\n"
        "Provide top 5 site-wide recommendations in JSON format:\n"
        "[\n"
        "  {{\"priority\": \"high|medium|low\", \"category\": \"...\", \"recommendation\": \"...\", \"impact\": \"...\"}}\n"
        "]"
    )
}


# ---------------------------------------------------------------------------
# Default models per provider (for AIRouter calls)
# ---------------------------------------------------------------------------

# Mirrors the existing pre-Cycle-BB behaviour. The text path used
# "gpt-4o" (OpenAI) or "gemini-1.5-flash" (Gemini); vision paths used the
# same models. All four model strings are in api/services/ai_pricing.py
# PRICING, so AIRouter post-processing finds prices cleanly.
_DEFAULT_TEXT_MODEL_BY_PROVIDER = {
    "openai": "gpt-4o",
    "gemini": "gemini-1.5-flash",
}
_DEFAULT_VISION_MODEL_BY_PROVIDER = {
    "openai": "gpt-4o",
    "gemini": "gemini-1.5-flash",
}


def _pick_model(model_table: dict[str, str]) -> tuple[str, ModelConfig]:
    """Pre-flight credential resolution so we know which model string to
    pass. AIRouter picks the provider based on key availability; we pick
    the right model for that provider.

    Falls back to the OpenAI default if resolution fails — AIRouter will
    raise ProviderAuthError on the actual call and the public-API
    wrappers below convert that to the appropriate "skipped" shape.
    """
    try:
        provider, _ = ai_router._resolve_credentials(SYSTEM_CONTEXT_ID)
    except ProviderAuthError:
        provider = "openai"
    model = model_table.get(provider, model_table["openai"])
    return provider, ModelConfig(model=model, max_tokens=500)


# ---------------------------------------------------------------------------
# Image fetching (kept local to ai_analyzer)
# ---------------------------------------------------------------------------
#
# AIRouter.call_vision takes raw bytes + mime type. We fetch once at the
# caller layer (here) and pass bytes to AIRouter. Provider drivers
# under api/services/providers/ handle base64 encoding internally.
#
# This replaces the previous _fetch_image_base64 — same SSRF-safe path,
# returns bytes instead of base64 string.

_IMAGE_FETCH_TIMEOUT_SECONDS = 10.0


async def _fetch_image_bytes(image_url: str) -> tuple[bytes, str]:
    """Fetch an image as raw bytes + mime type, with SSRF protection.

    Returns:
        (bytes, mime_type) — mime defaults to "image/jpeg" if the server
        omits Content-Type (common for old CDNs).

    Raises:
        ValueError: if SSRF guard blocks the URL, or if the fetch fails.
    """
    if not is_ssrf_safe(image_url):
        logger.warning("image_fetch_ssrf_blocked", extra={"image_url": image_url})
        raise ValueError(
            "SSRF_BLOCKED: image URL resolves to a private/internal address"
        )

    try:
        async with httpx.AsyncClient(timeout=_IMAGE_FETCH_TIMEOUT_SECONDS) as client:
            res = await client.get(image_url)
            if res.status_code != 200:
                raise ValueError(f"Failed to fetch image: HTTP {res.status_code}")
            mime = res.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                # Some servers return wrong content-type; default and log.
                logger.debug(
                    "image_fetch_unexpected_mime",
                    extra={"image_url": image_url, "mime": mime},
                )
                mime = "image/jpeg"
            return res.content, mime
    except httpx.HTTPError as exc:
        logger.error(
            "image_fetch_failed",
            extra={"error": str(exc), "url": image_url},
        )
        raise ValueError(f"Image fetch error: {exc!s}") from exc


# ---------------------------------------------------------------------------
# Public API — text analysis
# ---------------------------------------------------------------------------

async def analyze_with_ai(prompt_key: str, context: dict[str, Any]) -> str:
    """Send a request to the configured LLM using a prompt from the library.

    Returns the LLM's response text. When no AI provider is configured,
    returns a "skipped" string (preserves pre-Cycle-BB behaviour so that
    callers expecting a string never see an exception).
    """
    if prompt_key not in PROMPT_LIBRARY:
        raise ValueError(f"Unknown prompt key: {prompt_key}")

    prompt_template = PROMPT_LIBRARY[prompt_key]
    prompt = prompt_template.format(**context)

    _provider, cfg = _pick_model(_DEFAULT_TEXT_MODEL_BY_PROVIDER)

    try:
        # The ai_analyzer prompts are designed as full user instructions
        # — they include their own role definition and output format
        # rules. Pass them as the user_prompt; leave system_prompt
        # empty so the provider doesn't get confused by a second
        # instruction layer.
        response = await ai_router.call_text(
            customer_id=SYSTEM_CONTEXT_ID,
            system_prompt="",
            user_prompt=prompt,
            model_config=cfg,
        )
        return response.content
    except ProviderAuthError:
        logger.warning("ai_analysis_skipped_no_key")
        return (
            "AI analysis skipped: No API key configured "
            "(GEMINI_API_KEY or OPENAI_API_KEY)."
        )
    except Exception as exc:
        logger.error("ai_analysis_failed", extra={"error": str(exc)})
        return f"Error calling AI: {str(exc)}"


# ---------------------------------------------------------------------------
# Public API — image analysis (general)
# ---------------------------------------------------------------------------

async def analyze_image_with_ai(
    image_url: str, current_alt: str = ""
) -> dict[str, Any]:
    """
    Analyze an image using AI vision models.

    Returns:
        {
            "description": "AI-generated description of the image",
            "suggested_alt": "Suggested alt text",
            "accuracy_score": 0-100,
            "quality_score": 0-100,
            "issues": ["list of issues found"],
            "semantic_score": 0-100
        }
    """
    # v2.3 (M0.6.6) SSRF guard at entry. Both the GEO and the general
    # paths fetch image_url locally via _fetch_image_bytes, but checking
    # here gives the user a clear error before any work happens.
    if not is_ssrf_safe(image_url):
        logger.warning("image_ai_analyze_ssrf_blocked", extra={"image_url": image_url})
        return {
            "description": "Image URL rejected: resolves to a private/internal address",
            "suggested_alt": current_alt,
            "accuracy_score": 0,
            "quality_score": 0,
            "issues": ["SSRF_BLOCKED"],
            "semantic_score": 0,
        }

    prompt = (
        f"Analyze this image for SEO and accessibility.\n\n"
        f"Current alt text: '{current_alt or '(none)'}'\n\n"
        f"Provide:\n"
        f"1. A detailed description of what you see\n"
        f"2. Whether the current alt text accurately describes the image (score 0-100)\n"
        f"3. The quality of the current alt text for SEO (score 0-100)\n"
        f"4. A suggested improved alt text (max 125 characters)\n"
        f"5. Any issues found (e.g., 'alt text too generic', 'alt text missing key details', 'decorative image has alt text')\n\n"
        f"IMPORTANT: Respond with ONLY valid JSON, no markdown formatting, no code blocks.\n"
        f"Format:\n"
        f"{{\n"
        f'  "description": "detailed description",\n'
        f'  "accuracy_score": 0-100,\n'
        f'  "quality_score": 0-100,\n'
        f'  "suggested_alt": "improved alt text",\n'
        f'  "issues": ["issue1", "issue2"]\n'
        f"}}"
    )

    _provider, cfg = _pick_model(_DEFAULT_VISION_MODEL_BY_PROVIDER)

    try:
        image_bytes, image_mime = await _fetch_image_bytes(image_url)
    except ValueError as exc:
        # SSRF or fetch failure — already logged inside _fetch_image_bytes.
        return {
            "description": f"Error: {str(exc)}",
            "suggested_alt": current_alt,
            "accuracy_score": 0,
            "quality_score": 0,
            "issues": ["IMAGE_FETCH_FAILED"],
            "semantic_score": 0,
        }

    try:
        response = await ai_router.call_vision(
            customer_id=SYSTEM_CONTEXT_ID,
            system_prompt="",
            image_bytes=image_bytes,
            image_mime=image_mime,
            model_config=cfg,
        )
        result_text = response.content
    except ProviderAuthError:
        logger.warning("image_ai_analysis_skipped_no_key")
        return {
            "description": "AI analysis unavailable: No API key configured",
            "suggested_alt": current_alt,
            "accuracy_score": 0,
            "quality_score": 0,
            "issues": ["NO_API_KEY"],
            "semantic_score": 0,
        }
    except Exception as exc:
        logger.error("image_ai_analysis_failed", extra={"error": str(exc)})
        return {
            "description": f"Error: {str(exc)}",
            "suggested_alt": current_alt,
            "accuracy_score": 0,
            "quality_score": 0,
            "issues": ["AI_ANALYSIS_ERROR"],
            "semantic_score": 0,
        }

    # Parse JSON response — strip markdown code blocks if present.
    cleaned_result = re.sub(
        r'```(?:json)?\s*\n?(.*?)\n?```', r'\1', result_text, flags=re.DOTALL
    )
    cleaned_result = cleaned_result.strip()

    try:
        data = json.loads(cleaned_result)
        # Calculate semantic score (average of accuracy and quality).
        semantic_score = (
            data.get("accuracy_score", 0) + data.get("quality_score", 0)
        ) // 2
        data["semantic_score"] = semantic_score
        return data
    except json.JSONDecodeError as exc:
        logger.error(
            "json_parse_error",
            extra={"error": str(exc), "result": result_text},
        )
        # Fallback if AI doesn't return valid JSON.
        return {
            "description": result_text,
            "suggested_alt": current_alt,
            "accuracy_score": 50,
            "quality_score": 50,
            "issues": ["AI_RESPONSE_PARSE_ERROR"],
            "semantic_score": 50,
        }


# ---------------------------------------------------------------------------
# Public API — GEO-optimized image analysis
# ---------------------------------------------------------------------------

async def analyze_image_with_geo(
    image_url: str,
    page_h1: str,
    surrounding_text: str,
    geo_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Analyze an image using GEO-optimized prompting with triple-context packet.

    Triple-Context Packet:
    1. Image bytes (high-resolution)
    2. Page context (H1 + surrounding text)
    3. Global settings (org identity + geo matrix)

    Returns:
        {
            "alt_text": "GEO-optimized alt text (80-125 chars with entities)",
            "long_description": "GEO-rich description (150-300 words)",
            "entities_used": ["location", "topic"],
            "geographic_anchor": "Vancouver",
            "subject": "identified subject",
            "theme": "contextual theme",
            "char_count": 95,
            "word_count": 200,
            "success": True
        }
    """
    # v2.3 (M0.6.6) SSRF guard at entry — see analyze_image_with_ai for rationale.
    if not is_ssrf_safe(image_url):
        logger.warning("geo_image_analyze_ssrf_blocked", extra={"image_url": image_url})
        return {
            "alt_text": "",
            "long_description": "",
            "success": False,
            "error": "Image URL rejected: resolves to a private/internal address",
        }

    # Build context for prompt.
    context = {
        "ORG_NAME": geo_config.get("org_name", ""),
        "PRIMARY_LOCATION": geo_config.get("primary_location", ""),
        "LOCATION_POOL": ", ".join(geo_config.get("location_pool", [])),
        "TOPIC_ENTITIES": ", ".join(geo_config.get("topic_entities", [])),
        "H1": page_h1 or "(none)",
        "SURROUNDING_TEXT": surrounding_text or "(none)",
    }

    prompt = PROMPT_LIBRARY["geo_image_analysis"]
    for key, value in context.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))

    _provider, cfg = _pick_model(_DEFAULT_VISION_MODEL_BY_PROVIDER)

    try:
        image_bytes, image_mime = await _fetch_image_bytes(image_url)
    except ValueError as exc:
        return {
            "alt_text": "",
            "long_description": "",
            "success": False,
            "error": str(exc),
        }

    try:
        response = await ai_router.call_vision(
            customer_id=SYSTEM_CONTEXT_ID,
            system_prompt="",
            image_bytes=image_bytes,
            image_mime=image_mime,
            model_config=cfg,
        )
        result_text = response.content
    except ProviderAuthError:
        logger.warning("geo_image_analysis_skipped_no_key")
        return {
            "alt_text": "",
            "long_description": "",
            "success": False,
            "error": "No API key configured",
        }
    except Exception as exc:
        logger.error("geo_image_analysis_failed", extra={"error": str(exc)})
        return {
            "alt_text": "",
            "long_description": "",
            "success": False,
            "error": str(exc),
        }

    # Parse JSON response — strip markdown code blocks if present.
    cleaned_result = re.sub(
        r'```(?:json)?\s*\n?(.*?)\n?```', r'\1', result_text, flags=re.DOTALL
    )
    cleaned_result = cleaned_result.strip()

    # Try to find JSON object in the response.
    json_match = re.search(
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_result, flags=re.DOTALL
    )
    if json_match:
        cleaned_result = json_match.group(0)

    try:
        data = json.loads(cleaned_result)
        data["success"] = True
        return data
    except json.JSONDecodeError as exc:
        logger.error(
            "geo_json_parse_error",
            extra={"error": str(exc), "result": result_text[:500]},
        )
        # Try to extract alt_text from raw response as fallback.
        alt_match = re.search(r'"alt_text"\s*:\s*"([^"]+)"', result_text)
        desc_match = re.search(r'"long_description"\s*:\s*"([^"]+)"', result_text)
        return {
            "alt_text": alt_match.group(1) if alt_match else "",
            "long_description": (
                desc_match.group(1) if desc_match else result_text[:300]
            ),
            "success": False,
            "error": "Failed to parse AI response",
        }
