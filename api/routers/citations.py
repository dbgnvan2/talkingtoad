"""
Router for AI citation ingestion (M5 — PLAN-V3.0 §M5).

Accepts per-URL AI-citation data from the sibling phrase tool and stores it
on crawled pages. Also emits AI_CITED_PAGE / AI_HIGH_VALUE_UNCITED issue codes
based on the ingested data and the page's health score.

SSRF note: Citation URLs are matched as strings, NEVER fetched. If a future
version needs to fetch them, it MUST go through is_ssrf_safe() first.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.crawler.checkers.registry import Issue as RegistryIssue, make_issue as registry_make_issue
from api.crawler.normaliser import normalise_url
from api.models.issue import Issue
from api.routers.crawl import get_store
from api.services.auth import require_auth
from api.services.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/jobs/{job_id}/ai-citations",
    tags=["citations"],
    dependencies=[Depends(require_auth)],
)


# ── Pydantic models ──────────────────────────────────────────────────────────

class EngineCitation(BaseModel):
    engine: str
    count_30d: int
    last_seen: Optional[str] = None


class CitationEntry(BaseModel):
    url: str
    engines: list[EngineCitation]


class CitationIngestionRequest(BaseModel):
    citations: list[CitationEntry]


class CitationIngestionResponse(BaseModel):
    matched_count: int
    unmatched_count: int
    unmatched_urls: list[str]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("", response_model=CitationIngestionResponse)
@limiter.limit("10/minute")
async def ingest_ai_citations(
    request: Request,
    job_id: str,
    body: CitationIngestionRequest,
    store=Depends(get_store),
):
    """Ingest AI citation data for a crawl job's pages.

    Matches each citation entry URL (normalised) against the job's crawled pages.
    Matched pages get their ai_citation_* fields updated. Returns counts of
    matched/unmatched URLs.
    """
    # Validate job_id UUID format
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid job_id format")

    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    pages = await store.get_pages(job_id)

    # Build normalised URL map
    page_map: dict[str, int] = {}  # norm_url -> index in pages list
    for idx, page in enumerate(pages):
        norm = normalise_url(page.url)
        page_map[norm] = idx

    matched_count = 0
    unmatched_urls: list[str] = []

    now_iso = datetime.now(timezone.utc).isoformat()

    for entry in body.citations:
        norm_entry = normalise_url(entry.url)
        if norm_entry in page_map:
            page = pages[page_map[norm_entry]]
            total_count = sum(ec.count_30d for ec in entry.engines)
            engine_names = [ec.engine for ec in entry.engines]
            page.ai_citation_count_30d = total_count
            page.ai_citation_engines = engine_names
            page.ai_citation_last_updated = now_iso
            matched_count += 1
        else:
            unmatched_urls.append(entry.url)

    await store.save_pages(pages)

    # ── Emit AI_CITED_PAGE / AI_HIGH_VALUE_UNCITED issues ─────────────────
    # Compute per-page health from existing issues to determine eligibility
    all_issues = await store.get_all_issues(job_id)
    impact_by_url: dict[str, int] = {}
    for issue in all_issues:
        if issue.page_url:
            norm_url = issue.page_url.rstrip("/")
            impact_by_url[norm_url] = impact_by_url.get(norm_url, 0) + issue.impact

    today = datetime.now(timezone.utc).date()
    new_issues: list[Issue] = []

    for page in pages:
        if page.ai_citation_count_30d is None:
            continue  # No citation data ingested — emit neither code

        if page.ai_citation_count_30d > 0:
            # AI_CITED_PAGE: positive signal
            ri = registry_make_issue("AI_CITED_PAGE", page_url=page.url, job_id=job_id)
            new_issues.append(_registry_to_model_issue(ri, job_id, page.page_id, page.url))
        elif page.ai_citation_count_30d == 0:
            # AI_HIGH_VALUE_UNCITED: only if page is healthy + content-rich + recent ingest
            norm_url = page.url.rstrip("/")
            total_impact = impact_by_url.get(norm_url, 0)
            page_score = max(0, 100 - total_impact)
            word_count = page.word_count or 0

            if page_score >= 80 and word_count > 300 and page.ai_citation_last_updated:
                try:
                    last_updated = datetime.fromisoformat(page.ai_citation_last_updated).date()
                    if (today - last_updated).days <= 60:
                        ri = registry_make_issue("AI_HIGH_VALUE_UNCITED", page_url=page.url, job_id=job_id)
                        new_issues.append(_registry_to_model_issue(ri, job_id, page.page_id, page.url))
                except (ValueError, TypeError):
                    pass

    # Remove any existing citation issues before saving new ones
    for page in pages:
        if page.ai_citation_count_30d is not None:
            await store.delete_issues_by_code_and_url(job_id, "AI_CITED_PAGE", page.url)
            await store.delete_issues_by_code_and_url(job_id, "AI_HIGH_VALUE_UNCITED", page.url)

    if new_issues:
        await store.save_issues(new_issues)

    return CitationIngestionResponse(
        matched_count=matched_count,
        unmatched_count=len(unmatched_urls),
        unmatched_urls=unmatched_urls,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _registry_to_model_issue(
    ri: RegistryIssue,
    job_id: str,
    page_id: str,
    page_url: str,
) -> Issue:
    """Convert a registry Issue (dataclass) to a Pydantic Issue model for storage."""
    return Issue(
        job_id=job_id,
        page_id=page_id,
        page_url=page_url,
        category=ri.category,
        severity=ri.severity,
        issue_code=ri.code,
        description=ri.description,
        recommendation=ri.recommendation,
        impact=ri.impact,
        effort=ri.effort,
        priority_rank=ri.priority_rank,
        human_description=ri.human_description,
        what_it_is=ri.what_it_is,
        impact_desc=ri.impact_desc,
        how_to_fix=ri.how_to_fix,
        fixability=ri.fixability,
        confidence_label=ri.confidence_label,
    )
