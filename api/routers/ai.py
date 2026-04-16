"""
Router for AI-assisted analysis and remediation (spec §4).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.routers.crawl import get_store
from api.services.ai_analyzer import analyze_with_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai")


class AIAnalysisRequest(BaseModel):
    job_id: str
    page_url: str
    analysis_type: str  # e.g. "title_meta_optimize", "semantic_alignment"


@router.post("/analyze")
async def analyze_page(request: AIAnalysisRequest, store=Depends(get_store)):
    """Analyze a page using AI and provide fix suggestions."""
    # Load page data
    page_data, _ = await store.get_page_issues_by_url(request.job_id, request.page_url)
    if not page_data:
        return {"error": f"Page not found: {request.page_url}"}

    context = {}
    if request.analysis_type == "title_meta_optimize":
        context = {
            "title": page_data.title or "",
            "meta_description": page_data.meta_description or "",
            "content_summary": (page_data.h1_tags[0] if page_data.h1_tags else "") + " " + (page_data.og_description or "")
        }
    elif request.analysis_type == "semantic_alignment":
        context = {
            "h1": page_data.h1_tags[0] if page_data.h1_tags else "None",
            "body_snippet": page_data.meta_description or "None"
        }
    else:
        return {"error": f"Invalid analysis type: {request.analysis_type}"}

    suggestion = await analyze_with_ai(request.analysis_type, context)
    return {
        "page_url": request.page_url,
        "analysis_type": request.analysis_type,
        "suggestion": suggestion
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
async def get_page_advisor(request: PageAdvisorRequest, store=Depends(get_store)):
    """
    Get AI-generated SEO recommendations for a specific page.

    Returns specific content suggestions for title, meta description, headings, and alt text.
    """
    # Load page data
    page_data, issues_by_category = await store.get_page_issues_by_url(request.job_id, request.page_url)
    if not page_data:
        return {"error": f"Page not found: {request.page_url}"}

    # Format issues for AI context - issues_by_category is a dict[str, list[Issue]]
    issue_summary = []
    for category in ["metadata", "heading", "image"]:
        if category in issues_by_category:
            for issue in issues_by_category[category]:
                issue_summary.append(f"{issue.issue_code}: {issue.description}")

    # Extract H2 tags from headings_outline
    h2_tags = [h["text"] for h in (page_data.headings_outline or []) if h.get("level") == 2]

    context = {
        "url": request.page_url,
        "title": page_data.title or "(none)",
        "meta_description": page_data.meta_description or "(none)",
        "h1_tags": ", ".join(page_data.h1_tags) if page_data.h1_tags else "(none)",
        "h2_tags": ", ".join(h2_tags[:5]) if h2_tags else "(none)",  # First 5 H2s
        "issues": "; ".join(issue_summary[:10]) if issue_summary else "No major issues"
    }

    # Get AI recommendations
    import json
    suggestion = await analyze_with_ai("page_advisor", context)

    # Try to parse JSON response
    try:
        recommendations = json.loads(suggestion)
    except json.JSONDecodeError:
        # Fallback if AI doesn't return valid JSON
        recommendations = {"raw_response": suggestion}

    return {
        "page_url": request.page_url,
        "recommendations": recommendations
    }


@router.post("/site-advisor")
async def get_site_advisor(request: SiteAdvisorRequest, store=Depends(get_store)):
    """
    Get AI-generated site-wide SEO recommendations.

    Analyzes patterns across the entire site and provides high-level strategic advice.
    """
    # Get job summary
    summary = await store.get_summary(request.job_id)
    if not summary:
        return {"error": f"Job not found: {request.job_id}"}

    # Get all issues to find common patterns
    all_issues = []
    async for issue in store.get_all_issues(request.job_id):
        all_issues.append(issue)

    # Count issue types
    from collections import Counter
    issue_counts = Counter([issue.issue_code for issue in all_issues])
    common_issues = [f"{code} ({count} occurrences)" for code, count in issue_counts.most_common(10)]

    # Get sample pages
    pages = []
    async for page in store.get_all_pages(request.job_id):
        pages.append(page)
        if len(pages) >= 5:
            break

    sample_pages = [
        f"{page.url} (Title: {page.title or 'none'}, Issues: {len([i for i in all_issues if i.page_url == page.url])})"
        for page in pages
    ]

    context = {
        "total_pages": summary.get("total_pages", 0),
        "common_issues": ", ".join(common_issues),
        "sample_pages": "; ".join(sample_pages)
    }

    # Get AI recommendations
    import json
    suggestion = await analyze_with_ai("site_advisor", context)

    # Try to parse JSON response
    try:
        recommendations = json.loads(suggestion)
    except json.JSONDecodeError:
        # Fallback if AI doesn't return valid JSON
        recommendations = [{"recommendation": suggestion, "priority": "high", "category": "general", "impact": "Unknown"}]

    return {
        "job_id": request.job_id,
        "total_pages": summary.get("total_pages", 0),
        "total_issues": len(all_issues),
        "recommendations": recommendations
    }
