"""
API endpoints for Advisor (Tool A) and Rewriter (Tool B).

Endpoints:
  POST /api/ai/advisor — Evaluate page and return markdown report
  POST /api/ai/advisor/prompt — Generate rewrite prompt from report
  POST /api/ai/rewriter — Apply rewrite prompt to content (optional)

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.models.advisor import AdvisorRequest
from api.services.advisor import evaluate_page
from api.services.rewriter import rewrite_page, RewriterRequest
from api.services.job_store import get_job_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["advisor"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class AdvisorRequestPayload(BaseModel):
    """Request to evaluate a page."""
    url: Optional[str] = None
    content: Optional[str] = None
    original_content: Optional[str] = None


class AdvisorResponsePayload(BaseModel):
    """Response with markdown report and decision."""
    report_markdown: str
    should_generate_prompt: bool


class RewritePromptRequestPayload(BaseModel):
    """Request to generate rewrite prompt."""
    report_markdown: str
    # In practice, we'd extract findings from the report, but for now
    # the client can provide the prompt directly or we generate from report.


class RewritePromptResponsePayload(BaseModel):
    """Response with rewrite prompt."""
    prompt: str


class RewriterRequestPayload(BaseModel):
    """Request to rewrite content."""
    content: str
    prompt: str


class RewriterResponsePayload(BaseModel):
    """Response with rewritten content."""
    rewrite: str
    stopped_by_limit: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/advisor", response_model=AdvisorResponsePayload)
async def evaluate_content(payload: AdvisorRequestPayload) -> AdvisorResponsePayload:
    """
    Evaluate a page for AI retrieval quality.

    Accepts either URL or content (markdown/HTML).
    Optional: original_content for comparison (source fidelity check).

    Returns markdown report and flag for whether to generate rewrite prompt.
    """
    try:
        request = AdvisorRequest(
            url=payload.url,
            content=payload.content,
            original_content=payload.original_content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        report_markdown, should_generate_prompt = await evaluate_page(request)
        return AdvisorResponsePayload(
            report_markdown=report_markdown,
            should_generate_prompt=should_generate_prompt,
        )
    except Exception as e:
        logger.exception("Advisor evaluation failed")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")


@router.post("/advisor/prompt", response_model=RewritePromptResponsePayload)
async def generate_rewrite_prompt(payload: RewritePromptRequestPayload) -> RewritePromptResponsePayload:
    """
    Generate a rewrite prompt from an advisor report.

    For now, this endpoint demonstrates the flow.
    In practice, a more sophisticated prompt generator would extract
    findings from the markdown report and create a page-specific prompt.

    Args:
        payload.report_markdown: The markdown report from advisor evaluation

    Returns:
        A rewrite prompt suitable for Tool B (the rewriter)
    """
    # Basic prompt generator — in production, this would parse the report
    # and generate a more sophisticated page-specific prompt
    prompt = f"""You are an expert content rewriter optimizing for Generative Engine Optimization (GEO).

Review the following page evaluation and rewrite the content to address all findings.

REPORT FINDINGS:
{payload.report_markdown}

INSTRUCTIONS:
1. Preserve all original facts and citations
2. Do not fabricate claims or data
3. Make content self-contained (each section should answer a user question independently)
4. Strengthen authority signals (add citations, attribution)
5. Improve structural fitness (use lists, tables, code blocks appropriately)
6. Maintain the original heading structure and links
7. Focus on clarity and answer-density for AI retrieval

Return the rewritten content in markdown format."""

    return RewritePromptResponsePayload(prompt=prompt)


@router.post("/rewriter", response_model=RewriterResponsePayload)
async def rewrite_content(payload: RewriterRequestPayload) -> RewriterResponsePayload:
    """
    Apply a rewrite prompt to content.

    Calls the LLM once with low temperature (0.2) for faithful rewriting.
    No iteration, no variants.

    Args:
        payload.content: Page content (markdown)
        payload.prompt: Rewrite instructions

    Returns:
        Rewritten content and flag indicating if token limit was hit
    """
    try:
        request = RewriterRequest(
            content=payload.content,
            prompt=payload.prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = await rewrite_page(request)
        return RewriterResponsePayload(
            rewrite=result.rewrite,
            stopped_by_limit=result.stopped_by_limit,
        )
    except Exception as e:
        logger.exception("Rewriter failed")
        raise HTTPException(status_code=500, detail=f"Rewriting failed: {e}")


# ---------------------------------------------------------------------------
# Compatibility endpoint for legacy GEO Analyzer button
# ---------------------------------------------------------------------------


class LegacyGeoReportRequest(BaseModel):
    """Legacy request format from frontend."""
    job_id: str
    model: Optional[str] = None
    force_refresh: bool = False


class LegacyGeoReportResponse(BaseModel):
    """Legacy response format — minimal structure for compatibility."""
    report_markdown: str
    should_generate_prompt: bool


@router.post("/geo-report", response_model=LegacyGeoReportResponse)
async def generate_geo_report_legacy(payload: LegacyGeoReportRequest) -> LegacyGeoReportResponse:
    """
    Legacy endpoint: /api/ai/geo-report

    Accepts job_id and calls the new Advisor service on that job's target URL.
    This maintains backward compatibility with the existing frontend.

    Args:
        payload.job_id: The crawl job ID
        payload.model: Ignored (legacy parameter)
        payload.force_refresh: Ignored (legacy parameter)

    Returns:
        Markdown report and should_generate_prompt flag
    """
    try:
        store = get_job_store()
        job = await store.get_job(payload.job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found")

        if not job.target_url:
            raise HTTPException(status_code=400, detail="Job has no target_url")

        # Evaluate the target URL using the new Advisor service
        request = AdvisorRequest(url=job.target_url)
        report_markdown, should_generate_prompt = await evaluate_page(request)

        return LegacyGeoReportResponse(
            report_markdown=report_markdown,
            should_generate_prompt=should_generate_prompt,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Geo report generation failed for job {payload.job_id}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
