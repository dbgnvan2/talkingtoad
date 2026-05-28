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
from api.routers.crawl import get_store  # v2.3 (M0.5): shared helper; was a duplicate definition
from api.services.advisor import evaluate_page
from api.services.auth import require_auth
from api.services.rewriter import rewrite_page, RewriterRequest

logger = logging.getLogger(__name__)

# v2.3 (M0.5): require_auth applied to every endpoint in this router.
# Previously the router was registered without `dependencies=[Depends(require_auth)]`,
# which meant /api/ai/advisor, /api/ai/advisor/prompt, /api/ai/rewriter,
# /api/ai/rewrite-url, /api/ai/geo-report, /api/ai/geo-report/pages were
# all reachable unauthenticated — burning AI credits and exposing /rewrite-url
# as an unauthenticated SSRF surface.
router = APIRouter(prefix="/api/ai", tags=["advisor"], dependencies=[Depends(require_auth)])


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


class RewriteUrlRequestPayload(BaseModel):
    """Request to rewrite a page from its URL."""
    url: str
    prompt: str


@router.post("/rewrite-url", response_model=RewriterResponsePayload)
async def rewrite_url(payload: RewriteUrlRequestPayload) -> RewriterResponsePayload:
    """
    Fetch a page from URL and rewrite it.

    Args:
        payload.url: URL to fetch and rewrite
        payload.prompt: Rewrite instructions

    Returns:
        Rewritten content and flag indicating if token limit was hit
    """
    try:
        # Fetch the page
        from api.services.advisor import _fetch_page, _html_to_markdown
        html = _fetch_page(payload.url)
        content = _html_to_markdown(html)

        # Rewrite it
        request = RewriterRequest(
            content=content,
            prompt=payload.prompt,
        )
        result = await rewrite_page(request)
        return RewriterResponsePayload(
            rewrite=result.rewrite,
            stopped_by_limit=result.stopped_by_limit,
        )
    except Exception as e:
        logger.exception(f"Rewrite URL failed for {payload.url}")
        raise HTTPException(status_code=500, detail=f"Rewriting failed: {e}")


# ---------------------------------------------------------------------------
# Compatibility endpoint for legacy GEO Analyzer button
# ---------------------------------------------------------------------------


class LegacyGeoReportRequest(BaseModel):
    """Legacy request format from frontend."""
    job_id: str
    model: Optional[str] = None
    force_refresh: bool = False
    page_urls: Optional[list[str]] = None  # Selected pages for multi-page analysis; None = target_url only


class LegacyGeoReportResponse(BaseModel):
    """Legacy response format — minimal structure for compatibility."""
    report_markdown: str
    should_generate_prompt: bool


@router.get("/geo-report/pages")
async def list_geo_report_pages(
    job_id: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
):
    """
    List crawled pages for a job so the user can select which ones to analyze.

    Args:
        job_id: The crawl job ID
        store: Job store (injected)

    Returns:
        {"pages": [{"url": ..., "title": ..., "issue_count": int}, ...]}
        Sorted by issue_count descending so most-problematic pages appear first.
    """
    job = await store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    pages, _total = await store.get_pages_with_issue_counts(job_id)

    out = []
    for page in pages:
        issue_counts = page.get("issue_counts") or {}
        out.append(
            {
                "url": page.get("url"),
                "title": page.get("title") or "",
                "issue_count": issue_counts.get("total", 0),
            }
        )

    # Most-problematic first
    out.sort(key=lambda p: p["issue_count"], reverse=True)

    return {"pages": out}


def _wrap_page_section(url: str, markdown: str) -> str:
    """Render one per-page block of the combined report."""
    return f"# {url}\n\n{markdown}".rstrip() + "\n"


@router.post("/geo-report")
async def generate_geo_report_legacy(
    payload: LegacyGeoReportRequest,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
):
    """
    Run the Advisor against either the job's target URL (legacy) or a list of
    user-selected page URLs (multi-page mode).

    Per-page errors (e.g. 403 fetch failure) appear inline in the combined
    report as "could not be analyzed" sections; they do NOT abort the run.

    Args:
        payload.job_id: The crawl job ID
        payload.page_urls: Optional list of page URLs to analyze. Must be a subset
            of pages from this job (validated against the job's crawled pages).
            If omitted/None, falls back to analyzing target_url only.
        payload.model: Ignored (legacy parameter)
        payload.force_refresh: Ignored (legacy parameter)
        store: Job store (injected)

    Returns:
        {"success": bool, "cached": bool, "report": {...}}
    """
    try:
        job = await store.get_job(payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found")

        if payload.page_urls is None:
            # Legacy single-page behavior
            if not job.target_url:
                raise HTTPException(status_code=400, detail="Job has no target_url")
            request = AdvisorRequest(url=job.target_url)
            report_markdown, should_generate_prompt = await evaluate_page(request)
        else:
            # Multi-page: validate URLs belong to this job, then analyze each
            if len(payload.page_urls) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="page_urls is empty. Select at least one page to analyze.",
                )

            pages, _total = await store.get_pages_with_issue_counts(payload.job_id)
            valid_urls = {p.get("url") for p in pages}
            invalid = [u for u in payload.page_urls if u not in valid_urls]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"page_urls contains URLs not in this job: {invalid}",
                )

            sections: list[str] = []
            any_should_generate = False
            for url in payload.page_urls:
                per_page_markdown, per_page_should_generate = await evaluate_page(
                    AdvisorRequest(url=url)
                )
                sections.append(_wrap_page_section(url, per_page_markdown))
                any_should_generate = any_should_generate or per_page_should_generate

            report_markdown = "\n".join(sections)
            should_generate_prompt = any_should_generate

        return {
            "success": True,
            "cached": False,
            "report": {
                "overall_score": 0.75,  # Placeholder - new system doesn't score
                "aggarwal_score": 0.75,  # Placeholder
                "tier1_scores": {},
                "findings": [],  # New system uses markdown instead
                "query_match_table": [],
                "chunk_containedness": [],
                "js_rendering": None,
                "model_used": "advisor-v1",
                "report_markdown": report_markdown,
                "should_generate_prompt": should_generate_prompt,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Geo report generation failed for job {payload.job_id}: {e}")
        logger.error(f"Traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
