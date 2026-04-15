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
