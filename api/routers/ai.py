"""
Router for AI-assisted analysis and remediation (spec §4).
"""

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.routers.crawl import get_store
from api.services.ai_analyzer import analyze_with_ai, analyze_image_with_geo
from api.services.auth import require_auth
from api.services.rate_limiter import AI_ANALYSIS_LIMIT, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", dependencies=[Depends(require_auth)])


class AIAnalysisRequest(BaseModel):
    job_id: str
    page_url: str
    analysis_type: str  # e.g. "title_meta_optimize", "semantic_alignment", "issue_advisor"
    issue_code: str | None = None
    issue_description: str | None = None
    extra_context: str | None = None


# Issue codes where AI can actually write better text (SEO/GEO rewriting only)
_AI_TEXT_SUGGESTION_CODES = {
    # Title / meta
    "TITLE_MISSING", "TITLE_TOO_SHORT", "TITLE_TOO_LONG", "TITLE_DUPLICATE",
    "TITLE_META_DUPLICATE_PAIR",
    "META_DESC_MISSING", "META_DESC_TOO_SHORT", "META_DESC_TOO_LONG", "META_DESC_DUPLICATE",
    # Social / OG
    "OG_TITLE_MISSING", "OG_DESC_MISSING",
    # Headings
    "H1_MISSING", "H1_MULTIPLE", "HEADING_EMPTY",
    # Images
    "IMG_ALT_MISSING", "IMG_ALT_TOO_SHORT", "IMG_ALT_TOO_LONG",
    "IMG_ALT_GENERIC", "IMG_ALT_DUP_FILENAME", "IMG_ALT_MISUSED",
    # Links
    "LINK_EMPTY_ANCHOR",
    # Content
    "THIN_CONTENT",
    # Schema
    "SCHEMA_MISSING", "SCHEMA_ORG_MISSING",
    # AI readiness — text AI can rewrite
    "CONVERSATIONAL_H2_MISSING", "QUERY_COVERAGE_WEAK",
}


@router.post("/analyze")
@limiter.limit(AI_ANALYSIS_LIMIT)
async def analyze_page(request: Request, body: AIAnalysisRequest, store=Depends(get_store)):
    """Analyze a page using AI and provide fix suggestions."""
    # Load page data
    page_data, _ = await store.get_page_issues_by_url(body.job_id, body.page_url)
    if not page_data:
        return {"error": f"Page not found: {body.page_url}"}

    context = {}
    if body.analysis_type == "title_meta_optimize":
        context = {
            "title": page_data.title or "",
            "meta_description": page_data.meta_description or "",
            "content_summary": (page_data.h1_tags[0] if page_data.h1_tags else "") + " " + (page_data.og_description or "")
        }
    elif body.analysis_type == "semantic_alignment":
        context = {
            "h1": page_data.h1_tags[0] if page_data.h1_tags else "None",
            "body_snippet": page_data.meta_description or "None"
        }
    elif body.analysis_type == "issue_advisor":
        if not body.issue_code:
            return {"error": "issue_code is required for issue_advisor analysis"}
        if body.issue_code not in _AI_TEXT_SUGGESTION_CODES:
            return {"error": f"Issue code '{body.issue_code}' does not support AI text suggestions"}
        context = {
            "issue_code": body.issue_code,
            "issue_description": body.issue_description or "",
            "url": body.page_url,
            "title": page_data.title or "(none)",
            "meta_description": page_data.meta_description or "(none)",
            "h1": page_data.h1_tags[0] if page_data.h1_tags else "(none)",
            "extra_context": body.extra_context or "none",
        }
    else:
        return {"error": f"Invalid analysis type: {body.analysis_type}"}

    import json, re as _re
    raw = await analyze_with_ai(body.analysis_type, context)

    if body.analysis_type == "issue_advisor":
        # C1: Detect error strings from analyze_with_ai (no key, timeout, etc.)
        # and route them as error responses rather than presenting them as suggestions.
        if raw.startswith("AI analysis skipped") or raw.startswith("Error calling AI"):
            return {"error": raw}

        # Strip markdown fences the model sometimes wraps around JSON
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = _re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            cleaned = _re.sub(r'\n?```\s*$', '', cleaned)
        try:
            parsed = json.loads(cleaned)
            # Preserve why / where_to_apply whatever shape the model returned
            why = parsed.get("why", "") if isinstance(parsed.get("why"), str) else ""
            where = parsed.get("where_to_apply", "") if isinstance(parsed.get("where_to_apply"), str) else ""
            suggested = parsed.get("suggested_text")
            if not isinstance(suggested, str) or not suggested.strip():
                # Model omitted suggested_text or returned wrong keys (e.g. h2_1, h2_2).
                # Collect values from keys that look like content — named with known prefixes
                # or long enough to be a real suggestion (>20 chars), and are not why/where.
                _META_KEYS = {"suggested_text", "why", "where_to_apply", "note", "source",
                              "confidence", "explanation", "instructions"}
                extra_vals = [
                    v for k, v in parsed.items()
                    if isinstance(v, str)
                    and k not in _META_KEYS
                    and len(v.strip()) > 20
                ]
                suggested = "\n".join(extra_vals) if extra_vals else ""
            parsed = {
                "suggested_text": suggested,
                "why": why,
                "where_to_apply": where,
            }
            raw = json.dumps(parsed)
        except (json.JSONDecodeError, AttributeError):
            # W3: Model returned prose rather than JSON. Best-effort: return as suggested_text
            # so why/where are empty but the user still gets content. Log for monitoring.
            logger.warning("issue_advisor_non_json_response", extra={
                "issue_code": body.issue_code, "length": len(raw)
            })
            raw = json.dumps({"suggested_text": raw, "why": "", "where_to_apply": ""})

    return {
        "page_url": body.page_url,
        "analysis_type": body.analysis_type,
        "suggestion": raw,
    }


@router.get("/test")
async def test_ai_connection():
    """Verify that the configured AI provider is reachable and responsive."""
    import os
    api_key_read = os.getenv("API_KEY_READ", "Not found")

    context = {
        "title": "Test Title",
        "meta_description": "Test Description",
        "content_summary": "This is a test of the AI connection."
    }
    try:
        suggestion = await analyze_with_ai("title_meta_optimize", context)
        # Check if the result is an error message from the service
        if suggestion.startswith("AI analysis skipped") or suggestion.startswith("Error calling"):
            return {
                "success": False,
                "message": suggestion,
                "api_key_read": api_key_read
            }

        return {
            "success": True,
            "message": "AI connection successful!",
            "sample": suggestion,
            "api_key_read": api_key_read
        }
    except Exception as exc:
        return {"success": False, "message": str(exc), "api_key_read": api_key_read}


class PageAdvisorRequest(BaseModel):
    job_id: str
    page_url: str


class SiteAdvisorRequest(BaseModel):
    job_id: str


@router.post("/page-advisor")
@limiter.limit(AI_ANALYSIS_LIMIT)
async def get_page_advisor(request: Request, body: PageAdvisorRequest, store=Depends(get_store)):
    """
    Get AI-generated SEO recommendations for a specific page.

    Returns specific content suggestions for title, meta description, headings, and alt text.
    """
    # Load page data
    page_data, issues_by_category = await store.get_page_issues_by_url(body.job_id, body.page_url)
    if not page_data:
        return {"error": f"Page not found: {body.page_url}"}

    # Format issues for AI context - issues_by_category is a dict[str, list[Issue]]
    issue_summary = []
    for category in ["metadata", "heading", "image"]:
        if category in issues_by_category:
            for issue in issues_by_category[category]:
                issue_summary.append(f"{issue.issue_code}: {issue.description}")

    # Extract H2 tags from headings_outline
    h2_tags = [h["text"] for h in (page_data.headings_outline or []) if h.get("level") == 2]

    context = {
        "url": body.page_url,
        "title": page_data.title or "(none)",
        "meta_description": page_data.meta_description or "(none)",
        "h1_tags": ", ".join(page_data.h1_tags) if page_data.h1_tags else "(none)",
        "h2_tags": ", ".join(h2_tags[:5]) if h2_tags else "(none)",  # First 5 H2s
        "issues": "; ".join(issue_summary[:10]) if issue_summary else "No major issues"
    }

    # Get AI recommendations
    import json
    import re
    suggestion = await analyze_with_ai("page_advisor", context)

    # Strip markdown code blocks if present (```json ... ``` or ``` ... ```)
    cleaned = suggestion.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language identifier)
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        # Remove closing fence
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    # Try to parse JSON response
    try:
        recommendations = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback if AI doesn't return valid JSON
        recommendations = {"raw_response": suggestion}

    return {
        "page_url": body.page_url,
        "recommendations": recommendations
    }


@router.post("/site-advisor")
@limiter.limit(AI_ANALYSIS_LIMIT)
async def get_site_advisor(request: Request, body: SiteAdvisorRequest, store=Depends(get_store)):
    """
    Get AI-generated site-wide SEO recommendations.

    Analyzes patterns across the entire site and provides high-level strategic advice.
    """
    # Get job summary
    summary = await store.get_summary(body.job_id)
    if not summary:
        return {"error": f"Job not found: {body.job_id}"}

    # Get all issues to find common patterns
    all_issues = await store.get_all_issues(body.job_id)

    # Count issue types
    from collections import Counter
    issue_counts = Counter([issue.issue_code for issue in all_issues])
    common_issues = [f"{code} ({count} occurrences)" for code, count in issue_counts.most_common(10)]

    # Get sample pages
    pages = await store.get_pages(body.job_id)
    sample_pages = [
        f"{page.url} (Title: {page.title or 'none'}, Issues: {len([i for i in all_issues if i.page_url == page.url])})"
        for page in pages[:5]
    ]

    context = {
        "total_pages": summary.get("total_pages", 0),
        "common_issues": ", ".join(common_issues),
        "sample_pages": "; ".join(sample_pages)
    }

    # Get AI recommendations
    import json
    import re
    suggestion = await analyze_with_ai("site_advisor", context)

    # Strip markdown code blocks if present (```json ... ``` or ``` ... ```)
    cleaned = suggestion.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    # Try to parse JSON response
    try:
        recommendations = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback if AI doesn't return valid JSON
        recommendations = [{"recommendation": suggestion, "priority": "high", "category": "general", "impact": "Unknown"}]

    return {
        "job_id": body.job_id,
        "total_pages": summary.get("total_pages", 0),
        "total_issues": len(all_issues),
        "recommendations": recommendations
    }


class GeoImageAnalysisRequest(BaseModel):
    job_id: str
    image_url: str


@router.post("/image/analyze-geo")
@limiter.limit(AI_ANALYSIS_LIMIT)
async def analyze_image_geo(request: Request, body: GeoImageAnalysisRequest, store=Depends(get_store)):
    """
    Analyze an image using GEO-optimized prompting.

    Requires GEO configuration to be set up for the domain.
    Uses triple-context packet: image + page context + GEO settings.

    Returns:
        {
            "success": bool,
            "alt_text": str (80-125 chars with entities),
            "long_description": str (150-300 words),
            "entities_used": list,
            "geographic_anchor": str,
            ...
        }
    """
    # Get job to extract domain
    job = await store.get_job(body.job_id)
    if not job:
        return {"error": "Job not found", "success": False}

    # Extract domain from target URL
    from urllib.parse import urlparse
    domain = urlparse(job.target_url).netloc.replace('www.', '')

    # Load GEO config for the domain
    geo_config = await store.get_geo_config(domain)
    if not geo_config:
        return {
            "error": f"No GEO configuration found for domain: {domain}. Please configure GEO settings first.",
            "success": False
        }

    if not geo_config.is_configured():
        errors = geo_config.validate()
        return {
            "error": "GEO configuration is incomplete",
            "validation_errors": errors,
            "success": False
        }

    # Get image info to extract page context
    image_info = await store.get_image_by_url(body.job_id, body.image_url)
    if not image_info:
        return {"error": "Image not found in crawl data", "success": False}

    # Get page data to extract H1
    page_data, _ = await store.get_page_issues_by_url(body.job_id, image_info.page_url)
    h1 = page_data.h1_tags[0] if page_data and page_data.h1_tags else ""

    # Build GEO config dict
    geo_dict = {
        "org_name": geo_config.org_name,
        "topic_entities": geo_config.topic_entities,
        "primary_location": geo_config.primary_location,
        "location_pool": geo_config.location_pool,
    }

    # Analyze image with GEO
    result = await analyze_image_with_geo(
        image_url=body.image_url,
        page_h1=h1,
        surrounding_text=image_info.surrounding_text,
        geo_config=geo_dict,
    )

    return result


class ApplyGeoMetadataRequest(BaseModel):
    job_id: str
    image_url: str
    alt_text: str
    description: str = ""


@router.post("/image/apply-geo-metadata")
async def apply_geo_metadata(body: ApplyGeoMetadataRequest, store=Depends(get_store)):
    """
    Apply GEO-generated metadata to an image.

    Updates BOTH WordPress AND local database with:
    - alt_text (GEO-optimized, 80-125 chars)
    - description (GEO-optimized, 150-300 words)

    This ensures changes persist even after fetch.
    """
    import json
    from pathlib import Path
    from urllib.parse import urlparse
    from api.services.wp_fixer import update_image_metadata
    from api.services.wp_client import WPClient, WPAuthError

    # Get image info
    image_info = await store.get_image_by_url(body.job_id, body.image_url)
    if not image_info:
        return {"error": "Image not found", "success": False}

    # Try to update WordPress first (if credentials available)
    _CREDS_PATH = Path("wp-credentials.json")
    wp_updated = False
    wp_error = None

    if _CREDS_PATH.exists():
        try:
            with open(_CREDS_PATH) as f:
                creds = json.load(f)

            # Validate domain matches crawl job
            job = await store.get_job(body.job_id)
            if job:
                job_domain = urlparse(job.target_url).netloc
                creds_domain = urlparse(creds.get("site_url", "")).netloc
                if job_domain != creds_domain:
                    wp_error = (
                        f"WordPress credentials are for {creds_domain}, "
                        f"but crawl job targets {job_domain}."
                    )
                    # Skip WP update but still update local DB below

            if not wp_error:
                wp = WPClient(
                    site_url=creds["site_url"],
                    login_url=creds["login_url"],
                    username=creds["username"],
                    password=creds["password"],
                )

                async with wp:
                    # Update WordPress with GEO-optimized metadata
                    await update_image_metadata(
                        wp,
                        body.image_url,
                        alt_text=body.alt_text,
                        description=body.description,
                    )
                    wp_updated = True

        except WPAuthError as e:
            wp_error = f"WordPress authentication failed: {str(e)}"
        except Exception as e:
            wp_error = f"WordPress update failed: {str(e)}"

    # Update local database (always, even if WP update failed)
    image_info.alt = body.alt_text
    image_info.description = body.description
    image_info.data_source = "geo_analyzed"

    # Re-analyze with updated alt text
    from api.crawler.image_analyzer import analyze_image
    issues, scores = analyze_image(image_info, job_id=body.job_id)

    # Update scores
    image_info.performance_score = scores["performance_score"]
    image_info.accessibility_score = scores["accessibility_score"]
    image_info.semantic_score = scores["semantic_score"]
    image_info.technical_score = scores["technical_score"]
    image_info.overall_score = scores["overall_score"]
    image_info.issues = [i.code for i in issues]

    # Save updated image
    await store.save_images([image_info])

    return {
        "success": True,
        "message": "GEO metadata applied successfully",
        "new_alt": image_info.alt,
        "new_scores": {
            "accessibility_score": image_info.accessibility_score,
            "overall_score": image_info.overall_score,
        },
        "wordpress_updated": wp_updated,
        "wordpress_error": wp_error,
    }


# ── GA3: GEO FAQ Schema Generator ────────────────────────────────────────


class GeoFaqRequest(BaseModel):
    """Request model for FAQ schema generation."""

    domain: str = Field(..., description="Domain to load GeoConfig for")
    mode: Literal["template", "ai"] = Field(
        default="template",
        description="Generation mode: 'template' (free, deterministic) or 'ai' (LLM-enriched)",
    )
    limit: int = Field(default=8, ge=1, le=20, description="Max questions to generate")


@router.post("/geo-faq")
async def generate_geo_faq(body: GeoFaqRequest, store=Depends(get_store)):
    """Generate Schema.org FAQPage JSON-LD from a domain's GeoConfig.

    Returns ready-to-paste structured data. Generate-and-suggest only — no
    WordPress write, no domain mutation.
    """
    from api.services.geo_faq import generate_faq_block

    # Load GeoConfig for the domain
    geo_config = await store.get_geo_config(body.domain)
    if geo_config is None:
        raise HTTPException(
            status_code=422,
            detail=f"No GEO configuration found for domain: {body.domain}. Configure GEO settings first.",
        )

    if not geo_config.topic_entities:
        raise HTTPException(
            status_code=422,
            detail="GEO configuration has no topic_entities. Add at least one topic entity in GEO settings.",
        )

    result = await generate_faq_block(geo_config, mode=body.mode, limit=body.limit)
    return result


class GeoLlmChecksRequest(BaseModel):
    """R8: opt-in LLM-driven GEO checks for a single page (one LLM call)."""
    page_url: str
    job_id: str | None = None  # optional — for logging/traceability


@router.post("/geo-llm-checks")
@limiter.limit(AI_ANALYSIS_LIMIT)
async def geo_llm_checks(request: Request, body: GeoLlmChecksRequest):
    """Run the three LLM-driven GEO checks (CENTRAL_CLAIM_BURIED,
    CHUNKS_NOT_SELF_CONTAINED, PROMOTIONAL_CONTENT_INTERRUPTS) on a page.

    Opt-in (costs one LLM call). Re-fetches + parses the page for its body text
    (the store does not persist it), then classifies. A failed/refused LLM
    response yields an empty verdict — never a spurious finding (P14).
    """
    from api.crawler.fetcher import fetch_page, make_client
    from api.crawler.parser import parse_page
    from api.services.geo_llm import classify_geo_llm, geo_llm_issues

    async with make_client() as client:
        result = await fetch_page(body.page_url, client)  # SSRF-guarded
    if result.status_code != 200 or not result.html:
        return {"error": f"Could not fetch page (status {result.status_code})"}

    page = parse_page(result, body.page_url)
    text = getattr(page, "first_1500_words", None) or ""
    if (getattr(page, "word_count", 0) or 0) < 200 or not text:
        return {"verdict": {}, "issues": [], "note": "insufficient content for GEO LLM analysis"}

    verdict = await classify_geo_llm(text)
    issues = geo_llm_issues(body.page_url, verdict)
    return {
        "verdict": verdict,
        "issues": [
            {"code": i.code, "severity": i.severity, "priority_rank": i.priority_rank}
            for i in issues
        ],
    }
